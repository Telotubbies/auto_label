/**
 * The API's project-address rule (`apps/backend/app/routers/projects.py:slugify`), so the
 * new-project dialog can show the address before submit. Both sides assert the same table:
 * `tests/slug.test.mjs` here and `apps/backend/tests/test_project_address.py` there.
 */
const PROJECT_RESERVED = new Set(['models', 'deployments', 'activity', 'settings', 'audit', 'admin', 'legal', 'qa'])
const WORKSPACE_RESERVED = new Set(['models', 'playground', 'deployments', 'activity', 'settings', 'audit', 'admin',
  'legal', 'inference', 'p'])   // the shell's RESERVED_WORKSPACE_SEGMENTS

export function projectSlug(name: string): string {
  const s = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'project'
  return PROJECT_RESERVED.has(s) ? `${s}-project` : s
}

/** The API's workspace-address rule (`apps/backend/app/routers/auth.py:slugify_workspace`). */
export function workspaceSlug(name: string): string {
  const s = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, '') || 'workspace'
  return WORKSPACE_RESERVED.has(s) ? `${s}-ws` : s
}

export const isWorkspaceSlug = (slug: string): boolean => /^[a-z0-9][a-z0-9-]{2,39}$/.test(slug)

export type WorkspaceLinkState = 'empty' | 'loading' | 'free' | 'taken' | 'invalid'

/** One line under the name field; the screen and its test read the same strings. */
export function workspaceLinkCopy(state: WorkspaceLinkState, slug = '', suggestion = ''): string {
  if (state === 'loading') return 'Checking…'
  if (state === 'taken') return `Taken — try ${suggestion}`
  if (state === 'invalid') return 'Use letters, numbers and dashes'
  return state === 'free' ? `Your workspace link: /${slug} — Available` : `Your workspace link: /${slug}`
}
