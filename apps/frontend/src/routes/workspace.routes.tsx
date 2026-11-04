import { lazy } from 'react'
import { Navigate, Route } from 'react-router-dom'
import { Gate, SuperAdminGate, WorkspaceHome } from './guards'
import { Settings } from './lazy'

const WorkspaceModels = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.WorkspaceModels })))
const Deployments = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.Deployments })))
const Activity = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.Activity })))
const Playground = lazy(() => import('@/features/playground/Playground'))
const AuditLog = lazy(() => import('@/features/governance/AuditLog'))
const Dpa = lazy(() => import('@/features/governance/Dpa'))
const AdminConsole = lazy(() => import('@/features/admin/AdminConsole'))

/** Workspace-level destinations rendered inside the app shell (no project chrome). */
export const workspaceRoutes = (
  <>
    <Route index element={<WorkspaceHome />} />
    <Route path="models" element={<WorkspaceModels />} />
    <Route path="deployments" element={<Deployments />} />
    <Route path="activity" element={<Activity />} />
    <Route path="audit" element={<Gate min="admin"><AuditLog /></Gate>} />
    <Route path="admin" element={<SuperAdminGate><AdminConsole /></SuperAdminGate>} />
    <Route path="legal" element={<Navigate to="dpa" replace />} />
    <Route path="legal/dpa" element={<Dpa />} />
    <Route path="playground" element={<Playground />} />
    <Route path="settings/*" element={<Settings />} />
  </>
)
