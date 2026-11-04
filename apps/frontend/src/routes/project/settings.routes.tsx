import { Route } from 'react-router-dom'
import ProjectSettings from '@/features/project/ProjectSettings'

/** SETTINGS: the project settings tabs (Access lives here since the v2 tree). */
export const projectSettingsRoutes = (
  <>
    <Route path="settings" element={<ProjectSettings />} />
  </>
)
