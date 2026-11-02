import { Suspense, lazy, useEffect } from 'react'
// Light, frequently used pages load eagerly: React 19 holds each Suspense fallback for ~300 ms,
// so nested lazy routes cost a visible delay. Heavy pages (konva editor, recharts) stay lazy.
import { Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import { useApp } from '@/lib/store'
import type { Role } from '@/lib/types'
import { AppLayout } from '@/components/shell'
import { Spinner } from '@/components/ui'
import { Login, Signup, AcceptInvite, Forgot, Reset, VerifyEmail, MfaGate } from '@/features/auth/Auth'
const Landing = lazy(() => import('@/features/landing/Landing'))
const LandingPreview = lazy(() => import('@/features/landing/Landing').then((m) => ({ default: m.LandingPreview })))
import Home from '@/features/workspace/Home'
const WorkspaceModels = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.WorkspaceModels })))
const Deployments = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.Deployments })))
const Activity = lazy(() => import('@/features/workspace/WorkspacePages').then((m) => ({ default: m.Activity })))
const Settings = lazy(() => import('@/features/settings/Settings'))
import ProjectLayout from '@/features/project/ProjectLayout'
import Upload from '@/features/project/Upload'
import AnnotateBoard from '@/features/project/AnnotateBoard'
import Dataset from '@/features/project/Dataset'
const Versions = lazy(() => import('@/features/project/Versions'))
const Analytics = lazy(() => import('@/features/project/Analytics'))
const Insights = lazy(() => import('@/features/project/Insights'))
const ModelInsights = lazy(() => import('@/features/insights/Insights'))
import Classes from '@/features/project/Classes'
import Train from '@/features/project/Train'
const Models = lazy(() => import('@/features/project/Models'))
const Deploy = lazy(() => import('@/features/project/Deploy'))
import ProjectSettings from '@/features/project/ProjectSettings'
import VideoTimeline from '@/features/project/VideoTimeline'
const Editor = lazy(() => import('@/features/editor/Editor'))
const Playground = lazy(() => import('@/features/playground/Playground'))
const AuditLog = lazy(() => import('@/features/governance/AuditLog'))
const Dpa = lazy(() => import('@/features/governance/Dpa'))
const AdminConsole = lazy(() => import('@/features/admin/AdminConsole'))

function Loading() {
  return <div className="flex h-screen items-center justify-center text-muted-foreground"><Spinner /></div>
}

/** Anonymous deep link: remember the path so login can return to it. */
function LoginRedirect() {
  const { pathname, search, hash } = useLocation()
  const next = `${pathname}${search}${hash}`
  return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
}

/** Loads /me, picks the workspace from the URL and publishes the caller's role in it. */
function WorkspaceGate() {
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

function Home0() {
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  const first = me.data?.workspaces[0]
  return first ? <Navigate to={`/${first.slug}`} replace /> : <Settings firstRun />
}

function Gate({ min, children }: { min: Role; children: React.ReactNode }) {
  const can = useApp((s) => s.can)
  const role = useApp((s) => s.role)
  if (!role) return null
  return can(min) ? <>{children}</> : <Navigate to=".." replace />
}

/** Project routes gate on the effective project permission, not the workspace rank (I7). */
function PermGate({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { ws = '', project = '' } = useParams()
  const { can, ready } = useProjectPermissions(ws, project)
  if (!project) return null
  if (!ready) return <Loading />
  return can(perm) ? <>{children}</> : <Navigate to=".." replace />
}

/** Platform operators only; the API enforces the same flag on /api/admin. */
function SuperAdminGate({ children }: { children: React.ReactNode }) {
  // Read the cached /me result directly: the store's superadmin flag is published in an effect,
  // so a hard refresh on /:ws/admin would otherwise redirect before the flag arrives.
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  if (me.isLoading) return <Loading />
  return me.data?.superadmin ? <>{children}</> : <Navigate to=".." replace />
}

export default function App() {
  const authed = useApp((s) => s.authed)
  if (!authed) {
    return (
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot" element={<Forgot />} />
          <Route path="/reset/:token" element={<Reset />} />
          <Route path="/verify/:token" element={<VerifyEmail />} />
          <Route path="/invite/:token" element={<AcceptInvite />} />
          {import.meta.env.DEV && <Route path="/__preview/:section" element={<LandingPreview />} />}
          <Route path="*" element={<LoginRedirect />} />
        </Routes>
      </Suspense>
    )
  }
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      <Route path="/" element={<Home0 />} />
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="/signup" element={<Navigate to="/" replace />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      {/* Account pages are reachable while signed in (email links, password changes) and sit outside the app layout. */}
      <Route path="/forgot" element={<Forgot />} />
      <Route path="/reset/:token" element={<Reset />} />
      <Route path="/verify/:token" element={<VerifyEmail />} />
      <Route path="/:ws" element={<WorkspaceGate />}>
        <Route path=":project/images/:imageId" element={<Editor />} />
        <Route element={<AppLayout />}>
          <Route index element={<Home />} />
          <Route path="models" element={<WorkspaceModels />} />
          <Route path="deployments" element={<Deployments />} />
          <Route path="activity" element={<Activity />} />
          <Route path="audit" element={<Gate min="admin"><AuditLog /></Gate>} />
          <Route path="admin" element={<SuperAdminGate><AdminConsole /></SuperAdminGate>} />
          <Route path="legal" element={<Navigate to="dpa" replace />} />
          <Route path="legal/dpa" element={<Dpa />} />
          <Route path="playground" element={<Playground />} />
          <Route path="settings/*" element={<Settings />} />
          <Route path=":project" element={<ProjectLayout />}>
            <Route index element={<Navigate to="browse" replace />} />
            <Route path="upload" element={<PermGate perm="project.upload"><Upload /></PermGate>} />
            <Route path="annotate" element={<PermGate perm="project.annotate"><AnnotateBoard /></PermGate>} />
            <Route path="browse" element={<Dataset />} />
            <Route path="videos" element={<PermGate perm="project.annotate"><VideoTimeline /></PermGate>} />
            <Route path="versions" element={<PermGate perm="project.export"><Versions /></PermGate>} />
            <Route path="analytics" element={<PermGate perm="project.review"><Analytics /></PermGate>} />
            <Route path="insights" element={<PermGate perm="project.review"><Insights /></PermGate>} />
            <Route path="model-insights" element={<PermGate perm="project.review"><ModelInsights /></PermGate>} />
            <Route path="classes" element={<PermGate perm="project.classes"><Classes /></PermGate>} />
            <Route path="train" element={<PermGate perm="project.train"><Train /></PermGate>} />
            <Route path="models" element={<PermGate perm="project.models"><Models /></PermGate>} />
            <Route path="deploy" element={<PermGate perm="project.models"><Deploy /></PermGate>} />
            <Route path="settings" element={<ProjectSettings />} />
            <Route path="access" element={<ProjectSettings initialTab="access" />} />
          </Route>
        </Route>
      </Route>
    </Routes>
    </Suspense>
  )
}
