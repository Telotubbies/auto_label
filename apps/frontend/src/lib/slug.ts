/**
 * The API's project-address rule (`apps/backend/app/routers/projects.py:slugify`), so the
 * new-project dialog can show the address before submit. Both sides assert the same table:
 * `tests/slug.test.mjs` here and `apps/backend/tests/test_project_address.py` there.
 */
const RESERVED = new Set(['models', 'deployments', 'activity', 'settings', 'audit', 'admin', 'legal', 'qa'])

export function projectSlug(name: string): string {
  const s = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'project'
  return RESERVED.has(s) ? `${s}-project` : s
}
