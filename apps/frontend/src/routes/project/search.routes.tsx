import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'

const SearchPage = lazy(() => import('@/features/search/SearchPage'))
const EventSearch = lazy(() => import('@/features/project/EventSearch'))

/** Semantic search (Task 27) and event search (Task 38), each behind its own flag. */
export const projectSearchRoutes = (
  <>
    <Route path="search" element={<FlagGate flag="task_27"><PermGate perm="project.read"><SearchPage /></PermGate></FlagGate>} />
    <Route path="events" element={<FlagGate flag="task_38"><PermGate perm="project.read"><EventSearch /></PermGate></FlagGate>} />
  </>
)
