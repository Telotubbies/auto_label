import type {
  AdminJobsHealth, AdminOverview, AdminStatus, AdminWorkspace, AuditFilters, AuditRow, CustomRole, DpaDoc,
  Permissions, ProjectAccess, ProjectPrivacy, ProjectPrivacyInput, ProjectRole, RoleLevel, WorkspacePrivacy,
  WorkerRow,
} from '../types'
import { del, get, P, patch, post, qs } from './client'

/** RBAC, audit, privacy/PDPA and the platform admin console. */
export const governanceApi = {
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
}
