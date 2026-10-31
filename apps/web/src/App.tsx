import { Suspense, lazy, useEffect } from 'react'
// Light, frequently used pages load eagerly: React 19 holds each Suspense fallback for ~300 ms,
// so nested lazy routes cost a visible delay. Heavy pages (konva editor, recharts) stay lazy.
import { Navigate, Outlet, Route, Routes, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useLightOnly } from '@/lib/theme'
import { useApp } from '@/lib/store'
import type { Role } from '@/lib/types'
import { AppLayout } from '@/components/shell'
import { Spinner } from '@/components/ui'
import { Login, Signup, AcceptInvite } from '@/features/auth/Auth'
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
import Classes from '@/features/project/Classes'
import Train from '@/features/project/Train'
const Models = lazy(() => import('@/features/project/Models'))
const Deploy = lazy(() => import('@/features/project/Deploy'))
import ProjectSettings from '@/features/project/ProjectSettings'
const Editor = lazy(() => import('@/features/editor/Editor'))

function LightOnly({ children }: { children: React.ReactNode }) {
  useLightOnly()
  return <>{children}</>
}

function Loading() {
  return <div className="flex h-screen items-center justify-center text-muted-foreground"><Spinner /></div>
}

/** Loads /me, picks the workspace from the URL and publishes the caller's role in it. */
function WorkspaceGate() {
  const { ws } = useParams()
  const { setMe, setRole } = useApp()
  const me = useQuery({ queryKey: ['me'], queryFn: api.me })
  const current = me.data?.workspaces.find((w) => w.slug === ws)
  useEffect(() => { if (me.data) setMe(me.data) }, [me.data, setMe])
  useEffect(() => { setRole(current?.role ?? null) }, [current, setRole])
  if (me.isLoading) return <Loading />
  if (!me.data) return <Navigate to="/login" replace />
  if (!current) return <Navigate to={me.data.workspaces[0] ? `/${me.data.workspaces[0].slug}` : '/'} replace />
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

export default function App() {
  const authed = useApp((s) => s.authed)
  if (!authed) {
    return (
      <Routes>
        <Route path="/signup" element={<Signup />} />
        <Route path="/invite/:token" element={<AcceptInvite />} />
        <Route path="*" element={<Login />} />
      </Routes>
    )
  }
  return (
    <Suspense fallback={<Loading />}>
    <Routes>
      <Route path="/" element={<Home0 />} />
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="/signup" element={<Navigate to="/" replace />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/:ws" element={<WorkspaceGate />}>
        <Route path=":project/images/:imageId" element={<LightOnly><Editor /></LightOnly>} />
        <Route element={<AppLayout />}>
          <Route index element={<Home />} />
          <Route path="models" element={<WorkspaceModels />} />
          <Route path="deployments" element={<Deployments />} />
          <Route path="activity" element={<Activity />} />
          <Route path="settings/*" element={<Settings />} />
          <Route path=":project" element={<ProjectLayout />}>
            <Route index element={<Navigate to="browse" replace />} />
            <Route path="upload" element={<Gate min="reviewer"><Upload /></Gate>} />
            <Route path="annotate" element={<AnnotateBoard />} />
            <Route path="browse" element={<Dataset />} />
            <Route path="versions" element={<Gate min="reviewer"><Versions /></Gate>} />
            <Route path="analytics" element={<Gate min="reviewer"><Analytics /></Gate>} />
            <Route path="classes" element={<Gate min="reviewer"><Classes /></Gate>} />
            <Route path="train" element={<Gate min="admin"><Train /></Gate>} />
            <Route path="models" element={<Gate min="reviewer"><Models /></Gate>} />
            <Route path="deploy" element={<Gate min="reviewer"><Deploy /></Gate>} />
            <Route path="settings" element={<Gate min="admin"><ProjectSettings /></Gate>} />
          </Route>
        </Route>
      </Route>
    </Routes>
    </Suspense>
  )
}
