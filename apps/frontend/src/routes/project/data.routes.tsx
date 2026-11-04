import { Route } from 'react-router-dom'
import { PermGate, FlagGate } from '@/routes/guards'
import Upload from '@/features/project/Upload'
import Dataset from '@/features/project/Dataset'
import VideoTimeline from '@/features/project/VideoTimeline'
import Classes from '@/features/project/Classes'
import { lazy } from 'react'

const Versions = lazy(() => import('@/features/project/Versions'))
const Insights = lazy(() => import('@/features/project/Insights'))
const ModelInsights = lazy(() => import('@/features/insights/Insights'))

/** DATA: dataset intake, the grid, versions and the insights studio tabs. */
export const projectDataRoutes = (
  <>
    <Route path="upload" element={<PermGate perm="project.upload"><Upload /></PermGate>} />
    <Route path="browse" element={<Dataset />} />
    <Route path="videos" element={<FlagGate flag="task_22"><PermGate perm="project.annotate"><VideoTimeline /></PermGate></FlagGate>} />
    <Route path="versions" element={<PermGate perm="project.export"><Versions /></PermGate>} />
    <Route path="insights" element={<PermGate perm="project.review"><Insights /></PermGate>} />
    <Route path="model-insights" element={<PermGate perm="project.review"><ModelInsights /></PermGate>} />
    <Route path="classes" element={<PermGate perm="project.classes"><Classes /></PermGate>} />
  </>
)
