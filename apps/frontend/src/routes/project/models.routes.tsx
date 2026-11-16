import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'
import Train from '@/features/project/Train'

const Models = lazy(() => import('@/features/project/Models'))
const Anomaly = lazy(() => import('@/features/project/Anomaly'))
const Workflows = lazy(() => import('@/features/project/Workflows'))

/** MODELS: training runs, the project model registry, the good-only anomaly station and workflows. */
export const projectModelRoutes = (
  <>
    <Route path="train" element={<PermGate perm="project.train"><Train /></PermGate>} />
    <Route path="anomaly" element={<FlagGate flag="task_29"><PermGate perm="project.read"><Anomaly /></PermGate></FlagGate>} />
    <Route path="models" element={<PermGate perm="project.models"><Models /></PermGate>} />
    <Route path="workflows" element={<FlagGate flag="task_31"><PermGate perm="project.models"><Workflows /></PermGate></FlagGate>} />
  </>
)
