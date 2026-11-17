import { lazy } from 'react'
import { Navigate, Route } from 'react-router-dom'
import { LEGACY_PROJECT_PATHS } from '@/lib/nav'
import ProjectLayout from '@/features/project/ProjectLayout'
import DatasetStage from '@/features/project/DatasetStage'
import { projectDataRoutes } from './data.routes'
import { projectLabelRoutes } from './label.routes'
import { projectModelRoutes } from './models.routes'
import { projectStudioRoutes } from './studio.routes'
import { projectDeployRoutes } from './deploy.routes'
import { projectSearchRoutes } from './search.routes'
import { projectSettingsRoutes } from './settings.routes'
import { LegacyProject } from './LegacyProject'

const Editor = lazy(() => import('@/features/editor/Editor'))

/** The annotation editor sits directly under /:ws, outside the app layout. */
export const projectEditorRoute = <Route path="p/:project/annotate/:imageId" element={<Editor />} />

/** Old editor URL: the image id moves into the path, the query is kept by `LegacyProject`. */
export const legacyEditorRoute = <Route path=":project/images/:imageId" element={<LegacyProject />} />

/**
 * One child list, mounted under the `/p/` prefix only: a second copy under the old shape would
 * drift the first time a page is added.
 */
const PROJECT_CHILDREN = (
  <>
    <Route index element={<Navigate to="browse" replace />} />
    {projectDataRoutes}
    {projectSearchRoutes}
    {projectLabelRoutes}
    {projectModelRoutes}
    {projectStudioRoutes}
    {projectDeployRoutes}
    {projectSettingsRoutes}
    {/* `/dataset` is the v3 name for the grid; T-479 mounts the tabbed stage on this path. */}
    <Route path="dataset" element={<DatasetStage />} />
    {/* Nav v2 folds Access into Project settings; old deep links keep their tab. */}
    {Object.entries(LEGACY_PROJECT_PATHS).map(([from, to]) => (
      <Route key={from} path={from} element={<Navigate to={`../${to}`} replace />} />
    ))}
  </>
)

/** Project shell under `/p/`; the old `/:ws/:project/...` shape redirects into it. */
export const projectRoutes = (
  <>
    <Route path="p/:project" element={<ProjectLayout />}>{PROJECT_CHILDREN}</Route>
    <Route path=":project/*" element={<LegacyProject />} />
  </>
)
