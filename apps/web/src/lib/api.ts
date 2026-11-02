// Typed API client. VITE_API_URL points at the API origin when web and api are on
// different hosts (e.g. Vercel + a VM); empty = same origin (dev proxy / single container).
import type {
  AdminJobsHealth, AdminOverview, AdminStatus, AdminWorkspace, Analytics, Annotation, AuditFilters,
  AuditRow, AutoLabelInput, AutoLabelPreview, Batch, Board, CompareInsights, ConsensusJob,
  ConsensusJobDetail, ConsensusSubmitResult, CustomRole, DashboardSummary, DeploymentAlias, DeploymentOverview,
  DpaDoc, HoneypotItem, HoneypotList, ImageItem, InsightDistribution, InsightEmbedding, InsightGeometry,
  InsightImageStats, InsightLabeling, InsightLeakage, InsightSelection, InsightSelectionRef, InsightSummary,
  InsightVersionDiff, Job, LabelClass, LabelingDashboard, LeaderboardRow, Lineage, Me, Member, ModelDetections,
  ModelInsights, ModelItem, MyTask, Permissions, PlaygroundResult, Project, ProjectAccess, ProjectPrivacy,
  ProjectPrivacyInput, ProjectRole, RegistryItem, ReviewQueueItem, RoleLevel, StreamAnalytics, StreamCreateBody,
  StreamEventItem, StreamEventPage, StreamItem, StreamPatchBody, StreamVideoUpload, TrainingInsights, Version,
  VideoFrame, VideoItem, WidgetData, WorkerRow, WorkspaceFlags, WorkspaceHome, WorkspaceInfo, WorkspacePrivacy,
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

/** Query string from defined, non-empty values only. */
const qs = (q: Record<string, string | number | boolean | null | undefined>) => {
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

export const api = {
  config: () => get<{ signup_enabled: boolean; sam: { loaded: boolean; error: string | null } }>('/config'),
  me: () => get<Me>('/me'),
  workspace: (ws: string) => get<WorkspaceInfo>(`/ws/${ws}`),
  home: (ws: string) => get<WorkspaceHome>(`/ws/${ws}/home`),
  flags: (ws: string) => get<WorkspaceFlags>(`/ws/${ws}/flags`),
  setFlag: (ws: string, key: string, enabled: boolean) =>
    put<{ key: string; enabled: boolean }>(`/ws/${ws}/flags/${encodeURIComponent(key)}`, { enabled }),
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
  insightsTraining: (ws: string, p: string, runs?: string[]) =>
    get<TrainingInsights>(`${P(ws, p)}/insights/training${runs?.length ? `?runs=${encodeURIComponent(runs.join(','))}` : ''}`),
  insightsModel: (ws: string, p: string, id: string) => get<ModelInsights>(`${P(ws, p)}/insights/models/${id}`),
  insightsDetections: (ws: string, p: string, id: string, files: string[]) =>
    get<ModelDetections>(`${P(ws, p)}/insights/models/${id}/detections?files=${encodeURIComponent(files.join(','))}`),
  insightsCompare: (ws: string, p: string, models: string[]) =>
    get<CompareInsights>(`${P(ws, p)}/insights/compare?models=${encodeURIComponent(models.join(','))}`),
  videos: (ws: string, p: string) => get<VideoItem[]>(`${P(ws, p)}/videos`),
  video: (ws: string, p: string, id: string) => get<VideoItem>(`${P(ws, p)}/videos/${id}`),
  videoTimeline: (ws: string, p: string, id: string, from = 0, limit = 120) =>
    get<{ video: VideoItem; total: number; frames: VideoFrame[] }>(`${P(ws, p)}/videos/${id}/timeline?from=${from}&limit=${limit}`),
  interpolate: (ws: string, p: string, id: string, fromImageId: string, toImageId: string) =>
    post<{ frames: number; annotations: number }>(`${P(ws, p)}/videos/${id}/interpolate`,
      { from_image_id: fromImageId, to_image_id: toImageId }),
  trackForward: (imageId: string, body: { annotation_id: string; frames: number }) =>
    post<Job>(`/images/${imageId}/track-forward`, body),
  deployments: (ws: string) => get<DeploymentOverview>(`/ws/${ws}/deployments`),
  setDeployment: (ws: string, p: string, alias: string, model_id: string) =>
    put<DeploymentAlias>(`${P(ws, p)}/deployments/${encodeURIComponent(alias)}`, { model_id }),
  rollbackDeployment: (ws: string, p: string, alias: string) =>
    post<DeploymentAlias>(`${P(ws, p)}/deployments/${encodeURIComponent(alias)}/rollback`, {}),
  sendDriftToLabeling: (ws: string, p: string, runId: string) =>
    post<{ sent: number }>(`${P(ws, p)}/drift/${encodeURIComponent(runId)}/send-to-labeling`, {}),
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

  // --- Insights Studio (Task 20c): lineage, stream analytics, dashboard builder ---
  lineage: (ws: string, p: string) => get<Lineage>(`${P(ws, p)}/insights/lineage`),
  streamAnalytics: (ws: string, p: string, days = 30, tzOffset = 0) =>
    get<StreamAnalytics>(`${P(ws, p)}/insights/streams?days=${days}&tz_offset=${tzOffset}`),
  widgetQuery: (ws: string, p: string,
    body: { source: string; measure: string; dimension: string; dimension2?: string | null; filters?: Record<string, string | number | undefined> }) =>
    post<WidgetData>(`${P(ws, p)}/insights/query`, body),
  dashboards: (ws: string, p: string) => get<DashboardSummary[]>(`${P(ws, p)}/dashboards`),
  dashboard: (ws: string, p: string, id: string) => get<DashboardSummary>(`${P(ws, p)}/dashboards/${id}`),
  createDashboard: (ws: string, p: string, body: { name: string; widgets: unknown[] }) =>
    post<DashboardSummary>(`${P(ws, p)}/dashboards`, body),
  updateDashboard: (ws: string, p: string, id: string, body: { name?: string; widgets?: unknown[] }) =>
    patch<DashboardSummary>(`${P(ws, p)}/dashboards/${id}`, body),
  deleteDashboard: (ws: string, p: string, id: string) => del<{ ok: boolean }>(`${P(ws, p)}/dashboards/${id}`),
  shareDashboard: (ws: string, p: string, id: string) =>
    post<{ token: string; path: string }>(`${P(ws, p)}/dashboards/${id}/share`, {}),
  sharedDashboard: (ws: string, p: string, token: string) =>
    get<DashboardSummary>(`${P(ws, p)}/dashboards/shared/${encodeURIComponent(token)}`),

  // --- RBAC ---
  permissions: (ws: string, project?: string) => get<Permissions>(`/ws/${ws}/permissions${qs({ project })}`),
  customRoles: (ws: string) => get<CustomRole[]>(`/ws/${ws}/roles`),
  createCustomRole: (ws: string, body: { name: string; level: RoleLevel; permissions: string[] }) =>
    post<CustomRole>(`/ws/${ws}/roles`, body),
  updateCustomRole: (ws: string, id: string, body: { name?: string; level?: RoleLevel; permissions?: string[] }) =>
    patch<CustomRole>(`/ws/${ws}/roles/${id}`, body),
  deleteCustomRole: (ws: string, id: string) => del<{ ok: boolean }>(`/ws/${ws}/roles/${id}`),
  setWorkspaceCustomRole: (ws: string, uid: string, custom_role_id: string | null) =>
    patch<{ id: string; custom_role_id: string | null }>(`/ws/${ws}/members/${uid}/custom-role`, { custom_role_id }),
  projectAccess: (ws: string, project: string) => get<ProjectAccess>(`${P(ws, project)}/roles`),
  setProjectMember: (ws: string, project: string, uid: string, body: { role: ProjectRole; custom_role_id?: string | null }) =>
    patch<{ id: string; role: ProjectRole; custom_role_id: string | null }>(`${P(ws, project)}/members/${uid}`, body),
  removeProjectMember: (ws: string, project: string, uid: string) => del<{ ok: boolean }>(`${P(ws, project)}/members/${uid}`),

  // --- audit ---
  audit: (ws: string, f: AuditFilters = {}) => get<AuditRow[]>(`/ws/${ws}/audit${qs({ ...f })}`),
  auditExportPath: (ws: string, f: AuditFilters = {}) => `/ws/${ws}/audit/export${qs({ format: 'csv', ...f })}`,

  // --- privacy / PDPA ---
  privacy: (ws: string) => get<WorkspacePrivacy>(`/ws/${ws}/privacy`),
  setWorkspacePrivacy: (ws: string, body: { data_region: string }) =>
    patch<{ data_region: string; region_label: string }>(`/ws/${ws}/privacy`, body),
  projectPrivacy: (ws: string, project: string) => get<ProjectPrivacy>(`${P(ws, project)}/privacy`),
  setProjectPrivacy: (ws: string, project: string, body: ProjectPrivacyInput) =>
    patch<ProjectPrivacy>(`${P(ws, project)}/privacy`, body),
  runRetention: (ws: string, project: string) => post<{ job_id: string }>(`${P(ws, project)}/privacy/retention/run`),
  dpa: (ws: string, project?: string) => get<DpaDoc>(`/ws/${ws}/dpa${qs({ project })}`),

  // --- super-admin ---
  adminOverview: () => get<AdminOverview>('/admin/overview'),
  adminWorkspaces: (q = '') => get<AdminWorkspace[]>(`/admin/workspaces${qs({ q })}`),
  adminSetPlan: (id: string, plan: string) => patch<AdminWorkspace>(`/admin/workspaces/${id}`, { plan }),
  adminJobs: (f: { status?: string; kind?: string; limit?: number } = {}) => get<AdminJobsHealth>(`/admin/jobs${qs(f)}`),
  adminWorkers: () => get<{ stale_after: number; workers: WorkerRow[] }>('/admin/workers'),
  adminStatus: () => get<AdminStatus>('/admin/status'),
  // --- labeling QA & workforce (Task 23) --------------------------------------
  labelingDashboard: (ws: string, p: string, days = 30) => get<LabelingDashboard>(`${P(ws, p)}/labeling/dashboard?days=${days}`),
  labelingTasks: (ws: string, p: string) => get<{ tasks: MyTask[] }>(`${P(ws, p)}/labeling/my-tasks`),
  labelingReviewQueue: (ws: string, p: string, limit = 50) =>
    get<{ items: ReviewQueueItem[] }>(`${P(ws, p)}/labeling/review-queue?limit=${limit}`),
  labelingJobs: (ws: string, p: string) => get<{ jobs: ConsensusJob[] }>(`${P(ws, p)}/labeling/consensus`),
  labelingJob: (ws: string, p: string, id: string) => get<ConsensusJobDetail>(`${P(ws, p)}/labeling/consensus/${id}`),
  createConsensus: (ws: string, p: string, body: { image_ids?: string[]; count?: number; k?: number; iou_threshold?: number }) =>
    post<ConsensusJob>(`${P(ws, p)}/labeling/consensus`, body),
  mergeConsensus: (ws: string, p: string, id: string) =>
    post<{ merged: number; skipped: number; status: 'merged' }>(`${P(ws, p)}/labeling/consensus/${id}/merge`, {}),
  // Autosave only writes the caller's private draft; this is the only call that submits it.
  submitConsensus: (ws: string, p: string, jobId: string, imageId: string, annotations?: Annotation[]) =>
    post<ConsensusSubmitResult>(`${P(ws, p)}/labeling/consensus/${jobId}/images/${imageId}/submit`, { annotations }),
  honeypots: (ws: string, p: string) => get<HoneypotList>(`${P(ws, p)}/labeling/honeypots`),
  createHoneypot: (ws: string, p: string, body: { image_id: string; annotations?: Annotation[] }) =>
    post<HoneypotItem>(`${P(ws, p)}/labeling/honeypots`, body),
  deleteHoneypot: (ws: string, p: string, id: string) => del<{ ok: true }>(`${P(ws, p)}/labeling/honeypots/${id}`),

  // ---- streams (CCTV) -------------------------------------------------------
  streams: (ws: string, p: string) => get<StreamItem[]>(`${P(ws, p)}/streams`),
  stream: (ws: string, p: string, id: string) => get<StreamItem>(`${P(ws, p)}/streams/${id}`),
  createStream: (ws: string, p: string, body: StreamCreateBody) => post<StreamItem>(`${P(ws, p)}/streams`, body),
  updateStream: (ws: string, p: string, id: string, body: StreamPatchBody) => patch<StreamItem>(`${P(ws, p)}/streams/${id}`, body),
  deleteStream: (ws: string, p: string, id: string) => del<{ ok: boolean }>(`${P(ws, p)}/streams/${id}`),
  startStream: (ws: string, p: string, id: string) => post<StreamItem>(`${P(ws, p)}/streams/${id}/start`, {}),
  stopStream: (ws: string, p: string, id: string) => post<StreamItem>(`${P(ws, p)}/streams/${id}/stop`, {}),
  /** Multipart upload: req() leaves Content-Type to the browser, like Playground's predict. */
  uploadStreamVideo: (ws: string, p: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return req<StreamVideoUpload>(`${P(ws, p)}/streams/upload-video`, { method: 'POST', body: form })
  },
  /** Server-side filters: `rule` is the rule index, `class` a class name, `reviewed` yes|no. */
  streamEvents: (ws: string, p: string, id: string, q: { rule?: number; class?: string; reviewed?: 'yes' | 'no'; kind?: string; offset?: number; limit?: number } = {}) => {
    const search = new URLSearchParams()
    for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') search.set(k, String(v))
    const qs = search.toString()
    return get<StreamEventPage>(`${P(ws, p)}/streams/${id}/events${qs ? `?${qs}` : ''}`)
  },
  patchStreamEvent: (ws: string, p: string, id: string, eid: string, reviewed: boolean) =>
    patch<StreamEventItem>(`${P(ws, p)}/streams/${id}/events/${eid}`, { reviewed }),
  eventToDataset: (ws: string, p: string, id: string, eid: string) =>
    post<{ uploaded: number; duplicates: number }>(`${P(ws, p)}/streams/${id}/events/${eid}/to-dataset`, {}),
  P,
}
