import { lazy } from 'react'
import { Route } from 'react-router-dom'
import { FlagGate, PermGate } from '@/routes/guards'

const Lineage = lazy(() => import('@/features/lineage/Lineage'))
const Dashboards = lazy(() => import('@/features/dashboards/Dashboards'))
const DashboardEditor = lazy(() => import('@/features/dashboards/DashboardEditor'))
const StreamAnalytics = lazy(() => import('@/features/streams/StreamAnalytics'))

/** STUDIO (Task 20c): lineage, the dashboard builder and stream analytics, all flag-gated. */
export const projectStudioRoutes = (
  <>
    <Route path="lineage" element={<FlagGate flag="task_20c"><PermGate perm="project.review"><Lineage /></PermGate></FlagGate>} />
    <Route path="dashboards" element={<FlagGate flag="task_20c"><PermGate perm="project.review"><Dashboards /></PermGate></FlagGate>} />
    {/* A shared dashboard is a read-only link for every project member, matching the API. */}
    <Route path="dashboards/shared/:token" element={<FlagGate flag="task_20c"><PermGate perm="project.read"><DashboardEditor /></PermGate></FlagGate>} />
    <Route path="dashboards/:id" element={<FlagGate flag="task_20c"><PermGate perm="project.review"><DashboardEditor /></PermGate></FlagGate>} />
    <Route path="stream-analytics" element={<FlagGate flag="task_20c"><PermGate perm="project.review"><StreamAnalytics /></PermGate></FlagGate>} />
  </>
)
