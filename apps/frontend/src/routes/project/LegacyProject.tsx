import { Navigate, useLocation, useParams } from 'react-router-dom'
import { editorPath, legacyProjectPath, projectPath } from '@/lib/routes'

/**
 * Old project URLs (`/:ws/:project/...`) keep working: map the first segment to its new screen and
 * replace the history entry, so Back does not bounce through the redirect. An unknown segment
 * renders nothing, which leaves the shell on its not-found state instead of guessing a screen.
 */
export function LegacyProject() {
  const { ws = '', project = '', imageId, '*': rest = '' } = useParams()
  const search = useLocation().search
  // The old editor URL carried the image in the path; the slice stays in the query.
  if (imageId) return <Navigate to={editorPath(ws, project, imageId, search)} replace />
  const to = legacyProjectPath(rest.split('/')[0])
  return to === null ? null : <Navigate to={projectPath(ws, project, to)} replace />
}
