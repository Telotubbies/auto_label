import { Route } from 'react-router-dom'
import { AppLayout } from '@/components/shell'
import { Home0, WorkspaceGate } from './guards'
import { accountRoutes } from './account.routes'
import { publicRoutes } from './public.routes'
import { workspaceRoutes } from './workspace.routes'
import { projectEditorRoute, projectRoutes } from './project'

/**
 * Route registry. Each feature owns a `*.routes.tsx` file; this module composes them in the
 * order the IA renders and keeps the guard placement identical to the pre-split tree.
 */
export { publicRoutes }

export const appRoutes = (
  <>
    <Route path="/" element={<Home0 />} />
    {accountRoutes}
    <Route path="/:ws" element={<WorkspaceGate />}>
      {projectEditorRoute}
      <Route element={<AppLayout />}>
        {workspaceRoutes}
        {projectRoutes}
      </Route>
    </Route>
  </>
)
