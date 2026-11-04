import { useEffect } from 'react'
import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceFlags } from '@/lib/flags'
import { useProjectPermissions } from '@/lib/perms'
import { useApp } from '@/lib/store'
import type { Role } from '@/lib/types'
import { workspaceIndexPath } from '@/lib/nav'
import { Spinner } from '@/components/ui'
import { MfaGate } from '@/features/auth/Auth'
import Home from '@/features/workspace/Home'
import { Settings } from './lazy'

export function Loading() {
  return <div className="flex h-screen items-center justify-center text-muted-foreground"><Spinner /></div>
}

/** Anonymous deep link: remember the path so login can return to it. */
export function LoginRedirect() {
  const { pathname, search, hash } = useLocation()
  const next = `${pathname}${search}${hash}`
  return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
}

/** Loads /me, picks the workspace from the URL and publishes the caller's role in it. */
export function WorkspaceGate() {
  const { ws } = useParams()
  const location = useLocation()
  const { setMe, setRole } = useApp()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const current = me.data?.workspaces.find((w) => w.slug === ws)
  useEffect(() => { if (me.data) setMe(me.data) }, [me.data, setMe])
  useEffect(() => { setRole(current?.role ?? null) }, [current, setRole])
  if (me.isLoading) return <Loading />
  if (!me.data) return <Navigate to="/login" replace />
  if (!current) return <Navigate to={me.data.workspaces[0] ? `/${me.data.workspaces[0].slug}` : '/'} replace />
  if (current.mfa_required && !me.data.mfa_enabled) {
    const next = `${location.pathname}${location.search}${location.hash}`
    return <MfaGate ws={current.slug} workspaceName={current.name} next={next} />
  }
  return <Outlet />
}

export function Home0() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  const first = me.data?.workspaces[0]
  return first ? <Navigate to={`/${first.slug}`} replace /> : <Settings firstRun />
}

/** Billing has no Projects entry in the IA; its workspace index is the usage page, not the grid. */
export function WorkspaceHome() {
  const role = useApp((s) => s.role)
  const { ws = '' } = useParams()
  const target = workspaceIndexPath(role)
  return target ? <Navigate to={`/${ws}/${target}`} replace /> : <Home />
}

export function Gate({ min, children }: { min: Role; children: React.ReactNode }) {
  const can = useApp((s) => s.can)
  const role = useApp((s) => s.role)
  if (!role) return null
  return can(min) ? <>{children}</> : <Navigate to=".." replace />
}

/** Project routes gate on the effective project permission, not the workspace rank (I7). */
export function PermGate({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { ws = '', project = '' } = useParams()
  const { can, ready } = useProjectPermissions(ws, project)
  if (!project) return null
  if (!ready) return <Loading />
  return can(perm) ? <>{children}</> : <Navigate to=".." replace />
}

/** Launch gate: a shipped surface stays unreachable until its workspace flag is on (I13). */
export function FlagGate({ flag, children }: { flag: string; children: React.ReactNode }) {
  const q = useWorkspaceFlags()
  if (q.isLoading) return <Loading />
  return q.data?.enabled.includes(flag) ? <>{children}</> : <Navigate to=".." replace />
}

/** Platform operators only; the API enforces the same flag on /api/admin. */
export function SuperAdminGate({ children }: { children: React.ReactNode }) {
  // Read the cached /me result directly: the store's superadmin flag is published in an effect,
  // so a hard refresh on /:ws/admin would otherwise redirect before the flag arrives.
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  return me.data?.superadmin ? <>{children}</> : <Navigate to=".." replace />
}
