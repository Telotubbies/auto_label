import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'
import { LegacyTabRedirect } from '@/components/shell/StageTabs'
import DeployStage from '@/features/project/DeployStage'

const Streams = lazy(() => import('@/features/streams/Streams'))
const StreamDetail = lazy(() => import('@/features/streams/StreamDetail'))

/** DEPLOY: model deployment and the CCTV stream surfaces (Task 10b). */
export const projectDeployRoutes = (
  <>
    <Route path="deploy" element={<DeployStage />} />
    <Route path="streams" element={<LegacyTabRedirect to="../deploy?tab=streams"><FlagGate flag="task_10b"><PermGate perm="project.streams"><Streams /></PermGate></FlagGate></LegacyTabRedirect>} />
    <Route path="streams/:sid" element={<FlagGate flag="task_10b"><PermGate perm="project.streams"><StreamDetail /></PermGate></FlagGate>} />
  </>
)
