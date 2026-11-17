import type { Job, Me, Member, Project, RegistryItem, WorkspaceFlags, WorkspaceHome, WorkspaceInfo } from '../types'
import { get, P, post, put } from './client'

/** Session, workspace and project lookup — the calls every shell surface makes. */
export const coreApi = {
  config: () => get<{
    signup_enabled: boolean
    max_upload_mb: number
    sam: { enabled: boolean; loaded: boolean; error: string | null }
    vlm: { configured: boolean }
    addons: { available: boolean }
  }>('/config'),
  me: () => get<Me>('/me'),
  workspaceSlug: (name: string) =>
    get<{ slug: string; available: boolean; suggestion?: string }>(`/workspaces/slug?name=${encodeURIComponent(name)}`),
  createWorkspace: (name: string, slug?: string) => post<{ slug: string; name: string }>('/workspaces', { name, slug }),
  workspace: (ws: string) => get<WorkspaceInfo>(`/ws/${ws}`),
  home: (ws: string) => get<WorkspaceHome>(`/ws/${ws}/home`),
  flags: (ws: string) => get<WorkspaceFlags>(`/ws/${ws}/flags`),
  setFlag: (ws: string, key: string, enabled: boolean) =>
    put<{ key: string; enabled: boolean }>(`/ws/${ws}/flags/${encodeURIComponent(key)}`, { enabled }),
  projects: (ws: string) => get<Project[]>(`/ws/${ws}/projects`),
  /** "I need a type you do not offer yet" — one audit row on the server (T-017). */
  requestType: (ws: string, body: { wanted: string; example?: string }) =>
    post<{ ok: boolean }>(`/ws/${ws}/type-requests`, body),
  project: (ws: string, p: string) => get<Project>(P(ws, p)),
  members: (ws: string) => get<{ members: Member[]; invites: { token: string; email: string; role: string; link: string }[] }>(`/ws/${ws}/members`),
  registry: (ws: string) => get<RegistryItem[]>(`/ws/${ws}/registry`),
  jobsList: (ws: string) => get<Job[]>(`/ws/${ws}/jobs`),
}
