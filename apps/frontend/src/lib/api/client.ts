// Transport for the typed API client: origin, auth tokens, retry/refresh, JSON helpers.
// VITE_API_URL points at the API origin when web and api are on different hosts
// (e.g. Vercel + a VM); empty = same origin (dev proxy / single container).

export const API_ORIGIN = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

/** Signed file paths come back as "/api/files/…"; prefix the API origin for <img src>. */
export const fileUrl = (u?: string | null) => (u ? (u.startsWith('http') ? u : API_ORIGIN + u) : '')

export const tokens = {
  get access() { return localStorage.getItem('ld_token') },
  get refresh() { return localStorage.getItem('ld_refresh') },
  /** sha256 of this browser's refresh token — matches an id from /api/me/sessions. */
  get session() { return localStorage.getItem('ld_session') },
  set(a: string, r?: string, session?: string) {
    localStorage.setItem('ld_token', a)
    if (r) localStorage.setItem('ld_refresh', r)
    if (session) localStorage.setItem('ld_session', session)
  },
  clear() {
    localStorage.removeItem('ld_token'); localStorage.removeItem('ld_refresh'); localStorage.removeItem('ld_session')
  },
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

let refreshing: Promise<boolean> | null = null
async function tryRefresh(): Promise<boolean> {
  refreshing ??= (async () => {
    const rt = tokens.refresh
    if (!rt) return false
    try {
      const r = await fetch(`${API_ORIGIN}/api/auth/refresh`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: rt }),
      })
      if (!r.ok) return false
      const d = await r.json()
      tokens.set(d.token, d.refresh_token, d.session)
      return true
    } catch { return false }
  })().finally(() => { refreshing = null })
  return refreshing
}

export async function req<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const isForm = init.body instanceof FormData
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  if (!isForm && init.body) headers['Content-Type'] = 'application/json'
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`
  // Lets auth endpoints revoke every other device while keeping this one signed in.
  if (tokens.session) headers['X-Session'] = tokens.session
  const r = await fetch(`${API_ORIGIN}/api${path}`, { ...init, headers })
  if (r.status === 401 && retry && tokens.refresh) {
    if (await tryRefresh()) return req<T>(path, init, false)
    tokens.clear(); window.dispatchEvent(new Event('ld:logout'))
  }
  if (!r.ok) {
    const d = await r.json().catch(() => ({}))
    const msg = typeof d.detail === 'string' ? d.detail : Array.isArray(d.detail) ? d.detail.map((x: any) => x.msg).join(', ') : r.statusText
    throw new ApiError(r.status, msg)
  }
  return r.json()
}

const json = (method: string) => <T>(path: string, body?: unknown) =>
  req<T>(path, { method, body: body instanceof FormData ? body : JSON.stringify(body ?? {}) })
export const get = <T>(path: string) => req<T>(path)
export const post = json('POST')
export const put = json('PUT')
export const patch = json('PATCH')
export const del = <T>(path: string) => req<T>(path, { method: 'DELETE' })

/** Upload with progress (fetch has no upload progress events). */
export function upload<T>(path: string, form: FormData, onProgress: (f: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest()
    x.open('POST', `${API_ORIGIN}/api${path}`)
    if (tokens.access) x.setRequestHeader('Authorization', `Bearer ${tokens.access}`)
    if (tokens.session) x.setRequestHeader('X-Session', tokens.session)
    x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    x.onload = () => {
      let d: any = {}
      try { d = JSON.parse(x.responseText) } catch { /* empty */ }
      x.status < 300 ? resolve(d) : reject(new ApiError(x.status, d.detail || x.statusText))
    }
    x.onerror = () => reject(new ApiError(0, 'network error'))
    x.send(form)
  })
}

/** Project-scoped path prefix every feature client builds on. */
export const P = (ws: string, p: string) => `/ws/${ws}/projects/${p}`

/** Query string from defined, non-empty values only. */
export const qs = (q: Record<string, string | number | boolean | null | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

/**
 * Download a token-protected file. The bearer token stays in an Authorization header (never in the URL),
 * so audit exports and future CSV links never leak it through history, logs or Referer.
 */
export async function download(path: string, fallbackName: string, retry = true): Promise<void> {
  const headers: Record<string, string> = {}
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`
  if (tokens.session) headers['X-Session'] = tokens.session
  const r = await fetch(`${API_ORIGIN}/api${path}`, { headers })
  if (r.status === 401 && retry && tokens.refresh && (await tryRefresh())) return download(path, fallbackName, false)
  if (!r.ok) {
    const d: { detail?: unknown } = await r.json().catch(() => ({}))
    throw new ApiError(r.status, typeof d.detail === 'string' ? d.detail : r.statusText)
  }
  const disposition = r.headers.get('Content-Disposition') ?? ''
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(disposition)
  const name = match?.[1] ? decodeURIComponent(match[1].replace(/"/g, '')) : fallbackName
  const url = URL.createObjectURL(await r.blob())
  const a = document.createElement('a')
  a.href = url; a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
