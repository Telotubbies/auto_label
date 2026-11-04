import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'

const Deploy = lazy(() => import('@/features/project/Deploy'))
const Streams = lazy(() => import('@/features/streams/Streams'))
const StreamDetail = lazy(() => import('@/features/streams/StreamDetail'))

/** DEPLOY: model deployment and the CCTV stream surfaces (Task 10b). */
export const projectDeployRoutes = (
  <>
    <Route path="deploy" element={<PermGate perm="project.models"><Deploy /></PermGate>} />
    <Route path="streams" element={<FlagGate flag="task_10b"><PermGate perm="project.streams"><Streams /></PermGate></FlagGate>} />
    <Route path="streams/:sid" element={<FlagGate flag="task_10b"><PermGate perm="project.streams"><StreamDetail /></PermGate></FlagGate>} />
  </>
)
