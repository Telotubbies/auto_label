import { useEffect } from 'react'
import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useWorkspaceFlags } from '@/lib/flags'
import { useProjectPermissions } from '@/lib/perms'
import { useApp } from '@/lib/store'
import type { Role } from '@/lib/types'
import { workspaceIndexPath } from '@/lib/nav'
import { flagDecision, flagSurfaceLabel } from '@/lib/flagGate'
import { Button, Spinner } from '@/components/ui'
import { NotEnabled } from '@/components/NotEnabled'
import { MfaGate } from '@/features/auth/Auth'
import Home from '@/features/workspace/Home'
import { Settings } from './lazy'
import { meNeedsLogin } from './mePolicy'

export function Loading() {
  return <div className="flex h-screen items-center justify-center text-muted-foreground"><Spinner /></div>
}

/** A failed refetch of /me is retryable while the token may still be valid; never a silent bounce to login.
 *  A cached /me always wins: one failed refetch must not unmount a working screen. */
function MeFailure({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex h-screen flex-col items-center justify-center gap-2 px-6 text-center">
      <p className="text-sm font-medium">Could not load your account</p>
      <p className="text-xs text-muted-foreground">Check your connection, then try again.</p>
      <Button size="sm" variant="outline" onClick={onRetry}>Retry</Button>
    </div>
  )
}

/** The cached session still renders; report the failed refresh without taking the screen away. */
function MeStale({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 border-b bg-warning/10 px-4 py-1.5 text-xs">
      Could not refresh your account. <Button size="sm" variant="ghost" onClick={onRetry}>Retry</Button>
    </div>
  )
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
  if (me.isError && !me.data) {
    return meNeedsLogin(me.error) ? <Navigate to="/login" replace /> : <MeFailure onRetry={() => me.refetch()} />
  }
  if (!me.data) return <Navigate to="/login" replace />
  if (!current) return <Navigate to={me.data.workspaces[0] ? `/${me.data.workspaces[0].slug}` : '/'} replace />
  if (current.mfa_required && !me.data.mfa_enabled) {
    const next = `${location.pathname}${location.search}${location.hash}`
    return <MfaGate ws={current.slug} workspaceName={current.name} next={next} />
  }
  return (
    <>
      {me.isError && <MeStale onRetry={() => me.refetch()} />}
      <Outlet />
    </>
  )
}

export function Home0() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  if (me.isError && !me.data) {
    return meNeedsLogin(me.error) ? <Navigate to="/login" replace /> : <MeFailure onRetry={() => me.refetch()} />
  }
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
  const { pathname } = useLocation()
  const decision = flagDecision({ loading: q.isLoading, enabled: q.data?.enabled ?? [], flag })
  if (decision === 'loading') return <Loading />
  return decision === 'render' ? <>{children}</> : <NotEnabled label={flagSurfaceLabel(pathname)} />
}

/** Platform operators only; the API enforces the same flag on /api/admin. */
export function SuperAdminGate({ children }: { children: React.ReactNode }) {
  // Read the cached /me result directly: the store's superadmin flag is published in an effect,
  // so a hard refresh on /:ws/admin would otherwise redirect before the flag arrives.
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  if (me.isError && !me.data) {
    return meNeedsLogin(me.error) ? <Navigate to="/login" replace /> : <MeFailure onRetry={() => me.refetch()} />
  }
  return me.data?.superadmin ? (
    <>
      {me.isError && <MeStale onRetry={() => me.refetch()} />}
      {children}
    </>
  ) : <Navigate to=".." replace />
}
