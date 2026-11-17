/**
 * One place that builds a project URL, so the `/p/` prefix is a single edit.
 * Pure — no React — so `tests/project-routes.test.mjs` executes it with Node's type stripping.
 */
import { LEGACY_PROJECT_PATHS, projectNav } from './nav.ts'

/** The project shell match; every consumer reads this, so the prefix moves once. */
export const PROJECT_ROUTE_MATCH = '/:ws/p/:project/*'

/** `/w/p/ppe` and `/w/p/ppe/<to>`; `to` is a stage id or a stage/id pair. */
export function projectPath(ws: string, project: string, to = '') {
  return `/${ws}/p/${project}${to ? `/${to}` : ''}`
}

/** A stage tab lives in the query, so a refresh or a pasted link lands on the same tab. */
export function stageTab(ws: string, project: string, stage: string, tab: string) {
  return `${projectPath(ws, project, stage)}?tab=${tab}`
}

/** The editor keeps the image in the path and the slice (status / batch / review) in the query. */
export function editorPath(ws: string, project: string, imageId: string, query = '') {
  return `${projectPath(ws, project, `annotate/${imageId}`)}${query}`
}

/** Where the editor's back arrow goes: the board while reviewing, the dataset otherwise. */
export function backPath(ws: string, project: string, { review }: { review: boolean }) {
  return projectPath(ws, project, review ? 'annotate' : 'dataset')
}

/** Screens that moved: old first segment → the new relative path, `''` for the project root. */
const MOVED_SEGMENTS = new Map<string, string>([
  ['index', ''], ['browse', 'dataset'], ['versions', 'dataset?tab=versions'],
  ['model-insights', 'train?tab=models'], ['streams', 'deploy?tab=streams'],
])

/** Screens that only gained the `/p/` prefix; their old segment is still their relative path. */
const PROJECT_SCREENS = new Set(projectNav.flatMap((g) => g.items.map((i) => i.to)))

/**
 * Old `/:ws/:project/<segment>` → its new relative path, or null when the segment is not a screen
 * we know (the shell shows not-found rather than guessing).
 */
export function legacyProjectPath(segment: string): string | null {
  if (segment === '') return ''
  const moved = MOVED_SEGMENTS.get(segment)
  if (moved !== undefined) return moved
  if (Object.hasOwn(LEGACY_PROJECT_PATHS, segment)) return (LEGACY_PROJECT_PATHS as Record<string, string>)[segment]
  // Screens that only gained the prefix keep their own path; the shipped nav still links them.
  return PROJECT_SCREENS.has(segment) ? segment : null
}
