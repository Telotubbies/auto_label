import type { NavGroup, ProjectNavItem, WorkspaceNavItem } from './types'
import { coreNav } from './workspace/core.ts'
import { buildNav } from './workspace/build.ts'
import { governNav } from './workspace/govern.ts'
import { footerNav } from './workspace/footer.ts'
import { dataNav } from './project/data.ts'
import { labelNav } from './project/label.ts'
import { modelsNav } from './project/models.ts'
import { studioNav } from './project/studio.ts'
import { deployNav } from './project/deploy.ts'
import { settingsNav } from './project/settings.ts'

/**
 * Nav v2 information architecture, kept free of React so the role matrix stays unit-testable.
 * Structure follows the IA report tree: workspace = core + BUILD + GOVERN + footer, and the
 * project panel = DATA / LABEL / MODELS / DEPLOY / SETTINGS.
 *
 * Each group lives in its own feature module; this file only fixes the render order, so adding a
 * nav entry touches one feature file instead of a shared hot file.
 */
export const workspaceNav: NavGroup<WorkspaceNavItem>[] = [coreNav, buildNav, governNav, footerNav]

export const projectNav: NavGroup<ProjectNavItem>[] = [
  dataNav, labelNav, modelsNav, studioNav, deployNav, settingsNav,
]

/** Old project URLs kept alive after the nav rename. */
export const LEGACY_PROJECT_PATHS = {
  access: 'settings?tab=access',
  analytics: 'insights?tab=health',
} as const

/**
 * Workspace-level route segments that must never be read as a project slug. The shell gives
 * anything outside this set project chrome (no top padding, no page scroll), so every workspace
 * destination has to be listed here — see `tests/nav.test.mjs`.
 */
export const RESERVED_WORKSPACE_SEGMENTS = new Set([
  'models', 'playground', 'deployments', 'activity', 'settings', 'audit', 'admin', 'legal',
])

/** Breadcrumb names for workspace routes; project pages use their project nav label instead. */
export const WORKSPACE_PAGE_LABELS: Record<string, string> = {
  models: 'Models', playground: 'Playground', deployments: 'Deployments', activity: 'Activity',
  audit: 'Audit log', admin: 'Admin console', settings: 'Settings', legal: 'Legal',
  'settings/members': 'Members & Roles', 'settings/usage': 'Usage & Billing', 'settings/api': 'Integrations',
  'settings/roles': 'Roles', 'settings/trash': 'Trash',
}
