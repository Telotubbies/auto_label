// Typed API client. VITE_API_URL points at the API origin when web and api are on
// different hosts (e.g. Vercel + a VM); empty = same origin (dev proxy / single container).
import type {
  Annotation, Analytics, AutoLabelInput, AutoLabelPreview, Batch, Board, ImageItem, InsightDistribution, InsightEmbedding,
  InsightGeometry, InsightImageStats, InsightLabeling, InsightLeakage, InsightSelection, InsightSelectionRef, InsightSummary,
  InsightVersionDiff, Job, LabelClass, LeaderboardRow, Me, Member, ModelItem, PlaygroundResult, Project, RegistryItem, Version,
  WorkspaceInfo,
} from './types'

export const API_ORIGIN = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

/** Signed file paths come back as "/api/files/…"; prefix the API origin for <img src>. */
export const fileUrl = (u?: string | null) => (u ? (u.startsWith('http') ? u : API_ORIGIN + u) : '')

const tokens = {
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
    // `selection` is a saved lasso token; the ids themselves never go in the URL.
    get<{ total: number; items: ImageItem[] }>(`${P(ws, p)}/images?${new URLSearchParams(q as Record<string, string>)}`),
  image: (id: string) => get<ImageItem & { annotations: Annotation[] }>(`/images/${id}`),
  board: (ws: string, p: string) => get<Board>(`${P(ws, p)}/board`),
  versions: (ws: string, p: string) => get<Version[]>(`${P(ws, p)}/versions`),
  formats: (ws: string, p: string) => get<{ id: string; label: string }[]>(`${P(ws, p)}/versions/formats`),
  models: (ws: string, p: string) => get<ModelItem[]>(`${P(ws, p)}/models`),
  model: (ws: string, p: string, id: string) => get<ModelItem>(`${P(ws, p)}/models/${id}`),
  leaderboard: (ws: string, p: string) => get<LeaderboardRow[]>(`${P(ws, p)}/leaderboard`),
  jobs: (ws: string, p: string, kind = '') => get<Job[]>(`${P(ws, p)}/jobs${kind ? `?kind=${kind}` : ''}`),
  analytics: (ws: string, p: string) => get<Analytics>(`${P(ws, p)}/analytics`),
  healthCheck: (ws: string, p: string, imgsz?: number) => post<Job>(`${P(ws, p)}/health`, imgsz ? { imgsz } : {}),
  members: (ws: string) => get<{ members: Member[]; invites: { token: string; email: string; role: string; link: string }[] }>(`/ws/${ws}/members`),
  registry: (ws: string) => get<RegistryItem[]>(`/ws/${ws}/registry`),
  autolabelPreview: (ws: string, p: string, body: AutoLabelInput & { sample?: number }) =>
    post<AutoLabelPreview>(`${P(ws, p)}/autolabel/preview`, body),
  playgroundPredict: (ws: string, form: FormData) => post<{ results: PlaygroundResult[] }>(`/ws/${ws}/playground/predict`, form),
  insights: {
    summary: (ws: string, p: string, version?: string) =>
      get<InsightSummary>(`${P(ws, p)}/insights/summary${version ? `?version=${encodeURIComponent(version)}` : ''}`),
    distribution: (ws: string, p: string, version?: string) =>
      get<InsightDistribution>(`${P(ws, p)}/insights/distribution${version ? `?version=${encodeURIComponent(version)}` : ''}`),
    geometry: (ws: string, p: string, version?: string) =>
      get<InsightGeometry>(`${P(ws, p)}/insights/geometry${version ? `?version=${encodeURIComponent(version)}` : ''}`),
    imageStats: (ws: string, p: string) => get<InsightImageStats>(`${P(ws, p)}/insights/image-stats`),
    scanImageStats: (ws: string, p: string) => post<Job>(`${P(ws, p)}/insights/image-stats/scan`, {}),
    leakage: (ws: string, p: string, version?: string) =>
      get<InsightLeakage>(`${P(ws, p)}/insights/leakage${version ? `?version=${encodeURIComponent(version)}` : ''}`),
    scanLeakage: (ws: string, p: string, version?: string) =>
      post<Job>(`${P(ws, p)}/insights/leakage/scan${version ? `?version=${encodeURIComponent(version)}` : ''}`, {}),
    embedding: (ws: string, p: string) => get<InsightEmbedding>(`${P(ws, p)}/insights/embedding`),
    scanEmbedding: (ws: string, p: string) => post<Job>(`${P(ws, p)}/insights/embedding/scan`, {}),
    versionDiff: (ws: string, p: string, base: string, target: string) =>
      get<InsightVersionDiff>(`${P(ws, p)}/insights/version-diff?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`),
    labeling: (ws: string, p: string) => get<InsightLabeling>(`${P(ws, p)}/insights/labeling`),
    /** Persist the lasso's image ids server-side and hand back a short-lived token for the URL. */
    saveSelection: (ws: string, p: string, imageIds: string[]) =>
      post<InsightSelectionRef>(`${P(ws, p)}/insights/selections`, { image_ids: imageIds }),
    selection: (ws: string, p: string, token: string) =>
      get<InsightSelection>(`${P(ws, p)}/insights/selections/${encodeURIComponent(token)}`),
  },
  P,
}
