import { lazy } from 'react'
import { Navigate, Route } from 'react-router-dom'
import { LEGACY_PROJECT_PATHS } from '@/lib/nav'
import ProjectLayout from '@/features/project/ProjectLayout'
import { projectDataRoutes } from './data.routes'
import { projectLabelRoutes } from './label.routes'
import { projectModelRoutes } from './models.routes'
import { projectStudioRoutes } from './studio.routes'
import { projectDeployRoutes } from './deploy.routes'
import { projectSettingsRoutes } from './settings.routes'

const Editor = lazy(() => import('@/features/editor/Editor'))

/** The annotation editor sits directly under /:ws, outside the app layout. */
export const projectEditorRoute = <Route path=":project/images/:imageId" element={<Editor />} />

/** Project shell: every feature registers its own routes; this file only fixes the order. */
export const projectRoutes = (
  <Route path=":project" element={<ProjectLayout />}>
    <Route index element={<Navigate to="browse" replace />} />
    {projectDataRoutes}
    {projectLabelRoutes}
    {projectModelRoutes}
    {projectStudioRoutes}
    {projectDeployRoutes}
    {projectSettingsRoutes}
    {/* Nav v2 folds Access into Project settings; old deep links keep their tab. */}
    {Object.entries(LEGACY_PROJECT_PATHS).map(([from, to]) => (
      <Route key={from} path={from} element={<Navigate to={`../${to}`} replace />} />
    ))}
  </Route>
)
