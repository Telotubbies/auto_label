import type { Me, Member, Project, RegistryItem, WorkspaceFlags, WorkspaceHome, WorkspaceInfo } from '../types'
import { get, P, put } from './client'

/** Session, workspace and project lookup — the calls every shell surface makes. */
export const coreApi = {
  config: () => get<{
    signup_enabled: boolean
    sam: { enabled: boolean; loaded: boolean; error: string | null }
    vlm: { configured: boolean }
    addons: { available: boolean }
  }>('/config'),
  me: () => get<Me>('/me'),
  workspace: (ws: string) => get<WorkspaceInfo>(`/ws/${ws}`),
  home: (ws: string) => get<WorkspaceHome>(`/ws/${ws}/home`),
  flags: (ws: string) => get<WorkspaceFlags>(`/ws/${ws}/flags`),
  setFlag: (ws: string, key: string, enabled: boolean) =>
    put<{ key: string; enabled: boolean }>(`/ws/${ws}/flags/${encodeURIComponent(key)}`, { enabled }),
  projects: (ws: string) => get<Project[]>(`/ws/${ws}/projects`),
  project: (ws: string, p: string) => get<Project>(P(ws, p)),
  members: (ws: string) => get<{ members: Member[]; invites: { token: string; email: string; role: string; link: string }[] }>(`/ws/${ws}/members`),
  registry: (ws: string) => get<RegistryItem[]>(`/ws/${ws}/registry`),
}
