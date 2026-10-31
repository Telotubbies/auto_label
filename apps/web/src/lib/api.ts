// Typed API client. VITE_API_URL points at the API origin when web and api are on
// different hosts (e.g. Vercel + a VM); empty = same origin (dev proxy / single container).
import type {
  Annotation, Analytics, Batch, Board, ImageItem, Job, LabelClass, Me, Member, ModelItem, Project, Version,
  WorkspaceInfo,
} from './types'

export const API_ORIGIN = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

/** Signed file paths come back as "/api/files/…"; prefix the API origin for <img src>. */
export const fileUrl = (u?: string | null) => (u ? (u.startsWith('http') ? u : API_ORIGIN + u) : '')

const tokens = {
  get access() { return localStorage.getItem('ld_token') },
  get refresh() { return localStorage.getItem('ld_refresh') },
  set(a: string, r?: string) { localStorage.setItem('ld_token', a); if (r) localStorage.setItem('ld_refresh', r) },
  clear() { localStorage.removeItem('ld_token'); localStorage.removeItem('ld_refresh') },
}
export { tokens }

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
      tokens.set(d.token, d.refresh_token)
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

const P = (ws: string, p: string) => `/ws/${ws}/projects/${p}`

export const api = {
  config: () => get<{ signup_enabled: boolean; sam: { loaded: boolean; error: string | null } }>('/config'),
  me: () => get<Me>('/me'),
  workspace: (ws: string) => get<WorkspaceInfo>(`/ws/${ws}`),
  projects: (ws: string) => get<Project[]>(`/ws/${ws}/projects`),
  project: (ws: string, p: string) => get<Project>(P(ws, p)),
  classes: (ws: string, p: string) => get<LabelClass[]>(`${P(ws, p)}/classes`),
  tags: (ws: string, p: string) => get<{ name: string; count: number }[]>(`${P(ws, p)}/tags`),
  batches: (ws: string, p: string) => get<Batch[]>(`${P(ws, p)}/batches`),
  images: (ws: string, p: string, q: Record<string, string | number> = {}) =>
    get<{ total: number; items: ImageItem[] }>(`${P(ws, p)}/images?${new URLSearchParams(q as Record<string, string>)}`),
  image: (id: string) => get<ImageItem & { annotations: Annotation[] }>(`/images/${id}`),
  board: (ws: string, p: string) => get<Board>(`${P(ws, p)}/board`),
  versions: (ws: string, p: string) => get<Version[]>(`${P(ws, p)}/versions`),
  formats: (ws: string, p: string) => get<{ id: string; label: string }[]>(`${P(ws, p)}/versions/formats`),
  models: (ws: string, p: string) => get<ModelItem[]>(`${P(ws, p)}/models`),
  jobs: (ws: string, p: string, kind = '') => get<Job[]>(`${P(ws, p)}/jobs${kind ? `?kind=${kind}` : ''}`),
  analytics: (ws: string, p: string) => get<Analytics>(`${P(ws, p)}/analytics`),
  members: (ws: string) => get<{ members: Member[]; invites: { token: string; email: string; role: string; link: string }[] }>(`/ws/${ws}/members`),
  P,
}
