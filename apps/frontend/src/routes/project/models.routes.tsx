import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { PermGate } from '@/routes/guards'
import Train from '@/features/project/Train'

const Models = lazy(() => import('@/features/project/Models'))

/** MODELS: training runs and the project model registry. */
export const projectModelRoutes = (
  <>
    <Route path="train" element={<PermGate perm="project.train"><Train /></PermGate>} />
    <Route path="models" element={<PermGate perm="project.models"><Models /></PermGate>} />
  </>
)
