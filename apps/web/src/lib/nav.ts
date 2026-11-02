import type { ProjectRole, Role } from './types'

/**
 * Nav v2 information architecture, kept free of React so the role matrix stays unit-testable.
 * Structure follows the IA report tree: workspace = core + BUILD + GOVERN + footer, and the
 * project panel = DATA / LABEL / MODELS / DEPLOY / SETTINGS. Routes that were renamed keep a
 * redirect in App.tsx via LEGACY_PROJECT_PATHS.
 *
 * Visibility is an explicit audience per item, not a rank comparison: `rbac.py` grants GOVERN
 * surfaces to specific roles (a billing user gets Usage & Billing, an admin does not), which a
 * "role >= member" test cannot express.
 */
export type NavIcon =
  | 'projects' | 'models' | 'playground' | 'deployments' | 'members' | 'audit' | 'usage'
  | 'integrations' | 'activity' | 'settings' | 'admin'
  | 'upload' | 'annotate' | 'dataset' | 'video' | 'versions' | 'classes' | 'insights' | 'train'
  | 'modelInsights' | 'deploy' | 'qa' | 'streams' | 'access' | 'projectSettings'
  | 'lineage' | 'dashboards' | 'streamAnalytics'

/** The roles that can hold a workspace: `rbac.WORKSPACE_PERMISSIONS` uses these names. */
const STAFF: Role[] = ['owner', 'admin', 'member', 'reviewer', 'annotator']
const OWNER_ADMIN: Role[] = ['owner', 'admin']
// Owners and admins see GOVERN complete; billing sees its one surface and nothing else.
const BILLING_AUDIENCE: Role[] = ['owner', 'admin', 'billing']

export interface WorkspaceNavItem {
  to: string
  label: string
  icon: NavIcon
  /** Exact match only (the core entry must not stay active on every workspace page). */
  end?: boolean
  /** Roles that may see the route; omitted = every member. */
  roles?: Role[]
  /** Platform operator entry, not a workspace role. */
  superadmin?: boolean
}

export interface ProjectNavItem {
  to: string
  label: string
  icon: NavIcon
  /** Project permission required by the API gateway for the route. */
  perm: string
  /** Narrower audience than the permission, for pages the IA hides from labelers. */
  roles?: ProjectRole[]
  /** Show the project's image count beside the label. */
  count?: boolean
}

export interface NavGroup<T> {
  id: string
  label?: string
  items: T[]
}

export const workspaceNav: NavGroup<WorkspaceNavItem>[] = [
  { id: 'core', items: [
    { to: '', label: 'Projects', icon: 'projects', end: true, roles: STAFF },
  ]},
  { id: 'build', label: 'BUILD', items: [
    { to: 'models', label: 'Models', icon: 'models', roles: STAFF },
    { to: 'playground', label: 'Playground', icon: 'playground', roles: STAFF },
    { to: 'deployments', label: 'Deployments', icon: 'deployments', roles: STAFF },
  ]},
  { id: 'govern', label: 'GOVERN', items: [
    // Labels follow the Settings tab they open, so the sidebar and the page never name one screen twice.
    { to: 'settings/members', label: 'Members', icon: 'members', roles: OWNER_ADMIN },
    { to: 'audit', label: 'Audit log', icon: 'audit', roles: OWNER_ADMIN },
    { to: 'settings/usage', label: 'Plan & Usage', icon: 'usage', roles: BILLING_AUDIENCE },
    { to: 'settings/api', label: 'API Keys', icon: 'integrations', roles: OWNER_ADMIN },
  ]},
  { id: 'footer', items: [
    { to: 'activity', label: 'Activity', icon: 'activity', roles: STAFF },
    // Settings holds the caller's own profile, security and preferences, so every role keeps it.
    { to: 'settings', label: 'Settings', icon: 'settings' },
    { to: 'admin', label: 'Admin', icon: 'admin', superadmin: true },
  ]},
]

export const projectNav: NavGroup<ProjectNavItem>[] = [
  { id: 'data', label: 'DATA', items: [
    { to: 'upload', label: 'Upload', icon: 'upload', perm: 'project.upload' },
    { to: 'browse', label: 'Dataset', icon: 'dataset', perm: 'project.read', count: true },
    // Video authoring (Task 22) sits with the images it annotates.
    { to: 'videos', label: 'Video', icon: 'video', perm: 'project.annotate' },
    { to: 'versions', label: 'Versions', icon: 'versions', perm: 'project.export' },
    // Labelers may edit the ontology through the API, but the IA keeps the page for reviewers+.
    { to: 'classes', label: 'Classes & Tags', icon: 'classes', perm: 'project.classes', roles: ['manager', 'reviewer'] },
    // The dataset health check (Task 9) is a tab of the Insights studio, per the v2 tree;
    // /analytics stays alive as a legacy redirect into that tab.
    { to: 'insights', label: 'Insights', icon: 'insights', perm: 'project.review' },
  ]},
  { id: 'label', label: 'LABEL', items: [
    { to: 'annotate', label: 'Annotate', icon: 'annotate', perm: 'project.annotate' },
    // Task 23's QA hub opens on project.review; labelers reach their queue through Annotate.
    { to: 'qa', label: 'Review & Quality', icon: 'qa', perm: 'project.review', roles: ['manager', 'reviewer'] },
  ]},
  { id: 'models', label: 'MODELS', items: [
    { to: 'train', label: 'Train', icon: 'train', perm: 'project.train' },
    { to: 'model-insights', label: 'Model insights', icon: 'modelInsights', perm: 'project.review' },
    { to: 'models', label: 'Models', icon: 'models', perm: 'project.models' },
  ]},
  // Task 20c's analysis studio: lineage, dashboard builder and stream analytics.
  { id: 'studio', label: 'STUDIO', items: [
    { to: 'lineage', label: 'Lineage', icon: 'lineage', perm: 'project.review' },
    { to: 'dashboards', label: 'Dashboards', icon: 'dashboards', perm: 'project.review' },
    { to: 'stream-analytics', label: 'Stream analytics', icon: 'streamAnalytics', perm: 'project.review' },
  ]},
  { id: 'deploy', label: 'DEPLOY', items: [
    { to: 'deploy', label: 'Deploy & Test', icon: 'deploy', perm: 'project.models' },
    // Streams are cameras + footage: watching follows project.streams (manager/reviewer).
    { to: 'streams', label: 'Streams', icon: 'streams', perm: 'project.streams' },
  ]},
  // Access is a tab of Project settings since the v2 tree; the separate /access route redirects.
  { id: 'settings', label: 'SETTINGS', items: [
    { to: 'settings', label: 'Project Settings', icon: 'projectSettings', perm: 'project.settings' },
  ]},
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

/** True when an item's optional audience admits the caller; no audience means everyone. */
function inAudience<T extends string>(roles: readonly T[] | undefined, role: T | null | undefined): boolean {
  return !roles || !role || roles.includes(role)
}

/** Legacy workspace roles that do project work only; the IA gives them no workspace ML surfaces. */
const NO_BUILD: Role[] = ['reviewer', 'annotator']

/**
 * A workspace role arrives after /me resolves. Until then the sidebar shows the member view:
 * never a privileged item, and no flash of an almost-empty rail.
 *
 * Inside a project, the effective project role also applies: a project labeler sees the IA
 * labeler view even when their workspace row says member (owner/admin keep the build surfaces).
 */
export function visibleWorkspaceNav(
  role: Role | null, superadmin = false, projectRole?: ProjectRole | null,
): NavGroup<WorkspaceNavItem>[] {
  const audience = role ?? 'member'
  const staffRole = audience === 'owner' || audience === 'admin'
  const hideBuild = NO_BUILD.includes(audience) || (projectRole === 'labeler' && !staffRole)
  return workspaceNav
    .filter((g) => !(hideBuild && g.id === 'build'))
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => inAudience(i.roles, audience) && (!i.superadmin || superadmin)),
    }))
    .filter((g) => g.items.length > 0)
}

/**
 * The workspace index is the Projects grid. A role whose visible nav has no Projects entry
 * (billing) would otherwise land on a page with no active item and no way back in.
 */
export function workspaceIndexPath(role: Role | null): string {
  const hasProjects = visibleWorkspaceNav(role).some((g) => g.items.some((i) => i.to === ''))
  return hasProjects ? '' : 'settings/usage'
}

export function canSeeProjectItem(
  item: Pick<ProjectNavItem, 'perm' | 'roles'>, can: (perm: string) => boolean, role?: ProjectRole | null,
): boolean {
  return can(item.perm) && inAudience(item.roles, role)
}

export function visibleProjectNav(
  can: (perm: string) => boolean, role?: ProjectRole | null,
): NavGroup<ProjectNavItem>[] {
  return projectNav
    .map((g) => ({ ...g, items: g.items.filter((i) => canSeeProjectItem(i, can, role)) }))
    .filter((g) => g.items.length > 0)
}

/**
 * NavLink's own active test highlights a prefix item too, so Settings would stay lit on
 * /settings/members. A shorter match loses to a longer one in the same nav.
 *
 * `items` is the list the caller actually renders: an item this role cannot see must not
 * suppress a visible shorter one, or a member on Settings → Members has no current item.
 * Omit it to test against the full nav (the role matrix's default view).
 */
export function isWorkspaceNavActive(
  item: WorkspaceNavItem, pathname: string, base: string, items?: WorkspaceNavItem[],
): boolean {
  // React Router keeps the trailing slash the sidebar link renders (`/acme/`), so normalise the
  // pathname once: without it the core Projects entry is never the current item after a click.
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  const target = `${base}/${item.to}`.replace(/\/+$/, '')
  const matches = item.end ? path === target : path === target || path.startsWith(`${target}/`)
  if (!matches) return false
  const candidates = items ?? workspaceNav.flatMap((g) => g.items)
  return !candidates.some((other) => {
    if (other.to.length <= item.to.length) return false
    const t = `${base}/${other.to}`.replace(/\/+$/, '')
    return path === t || path.startsWith(`${t}/`)
  })
}
