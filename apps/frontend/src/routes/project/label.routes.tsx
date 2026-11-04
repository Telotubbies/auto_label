import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'
import AnnotateBoard from '@/features/project/AnnotateBoard'

const QA = lazy(() => import('@/features/project/QA'))

/** LABEL: the annotation board and the review/quality hub. */
export const projectLabelRoutes = (
  <>
    <Route path="annotate" element={<PermGate perm="project.annotate"><AnnotateBoard /></PermGate>} />
    <Route path="qa" element={<FlagGate flag="task_23"><PermGate perm="project.review"><QA /></PermGate></FlagGate>} />
  </>
)
