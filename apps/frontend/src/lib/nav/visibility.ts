import type { ProjectRole, Role } from '../types'
import { BILLING_AUDIENCE, canSeeProjectItem, inAudience, NO_BUILD, OWNER_ADMIN, STAFF } from './audience.ts'
import { GROUPS, railItem } from './project/stages.ts'
import type { RailId, StageRow } from './project/stages.ts'
import { projectNav, workspaceNav } from './registry.ts'
import type { NavGroup, ProjectNavItem, WorkspaceNavItem } from './types'

/**
 * The rail as it shipped before `task_470`, frozen apart from T-1000's flag-gated Inference row.
 * T-476 deleted the `build` and `govern` modules, so the old rail lives here until the flag
 * retires: off ⇒ every old destination is exactly where it was.
 */
export const v2WorkspaceNav: NavGroup<WorkspaceNavItem>[] = [
  { id: 'core', items: [
    { to: '', label: 'Projects', icon: 'projects', end: true, roles: STAFF },
  ] },
  { id: 'build', label: 'BUILD', items: [
    { to: 'models', label: 'Models', icon: 'models', roles: STAFF },
    { to: 'playground', label: 'Playground', icon: 'playground', roles: STAFF },
    { to: 'deployments', label: 'Deployments', icon: 'deployments', roles: STAFF },
    // T-1000: the Inference hub rides BUILD while this rail ships; `task_inference` owns it.
    { to: 'inference', label: 'Inference', icon: 'models', roles: OWNER_ADMIN, flag: 'task_inference' },
  ] },
  { id: 'govern', label: 'GOVERN', items: [
    // Labels follow the Settings tab they open, so the sidebar and the page never name one screen twice.
    { to: 'settings/members', label: 'Members', icon: 'members', roles: OWNER_ADMIN },
    { to: 'audit', label: 'Audit log', icon: 'audit', roles: OWNER_ADMIN },
    { to: 'settings/usage', label: 'Plan & Usage', icon: 'usage', roles: BILLING_AUDIENCE },
    { to: 'settings/api', label: 'API Keys', icon: 'integrations', roles: OWNER_ADMIN },
  ] },
  { id: 'footer', items: [
    { to: 'activity', label: 'Activity', icon: 'activity', roles: STAFF },
    // Settings holds the caller's own profile, security and preferences, so every role keeps it.
    { to: 'settings', label: 'Settings', icon: 'settings' },
    { to: 'admin', label: 'Admin', icon: 'admin', superadmin: true },
  ] },
]

/**
 * The workspace ML surfaces the v2 BUILD group held. A labeler works around them, not in them:
 * they keep Projects, Activity and Settings, in both rails.
 */
const BUILD_TO = new Set(['models', 'playground', 'deployments'])

/**
 * A workspace role arrives after /me resolves. Until then the sidebar shows the member view:
 * never a privileged item, and no flash of an almost-empty rail.
 *
 * Inside a project, the effective project role also applies: a project labeler sees the IA
 * labeler view even when their workspace row says member (owner/admin keep the build surfaces).
 *
 * `uiV3` is the `task_470` flag: off renders the frozen v2 rail, unchanged.
 * `flags` is the workspace's enabled set: a flag-gated item is hidden without it.
 */
export function visibleWorkspaceNav(
  role: Role | null, superadmin = false, projectRole?: ProjectRole | null, uiV3 = false,
  flags?: ReadonlySet<string>,
): NavGroup<WorkspaceNavItem>[] {
  const audience = role ?? 'member'
  const staffRole = audience === 'owner' || audience === 'admin'
  const hideBuild = NO_BUILD.includes(audience) || (projectRole === 'labeler' && !staffRole)
  return (uiV3 ? workspaceNav : v2WorkspaceNav)
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => inAudience(i.roles, audience) && (!i.superadmin || superadmin)
        && (!i.flag || flags?.has(i.flag))
        && !(hideBuild && BUILD_TO.has(i.to))),
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

export function visibleProjectNav(
  can: (perm: string) => boolean, role?: ProjectRole | null, flags?: ReadonlySet<string>,
  projectType?: string,
): NavGroup<ProjectNavItem>[] {
  return projectNav
    .map((g) => ({ ...g, items: g.items.filter((i) => canSeeProjectItem(i, can, role, flags, projectType)) }))
    .filter((g) => g.items.length > 0)
}

/**
 * The v3 project rail (T-477): three purpose groups holding the manifest. A numbered stage is never
 * filtered out — a role that cannot act on it gets the row dimmed with a lock. The unnumbered
 * destinations keep the v2 audience, flag and type filter.
 */
export function visibleStageGroups(
  can: (perm: string) => boolean, role?: ProjectRole | null, flags?: ReadonlySet<string>,
  projectType?: string,
): NavGroup<StageRow>[] {
  return GROUPS.map((g) => ({
    id: g.id,
    label: g.label,
    items: (g.items as readonly RailId[])
      .map(railItem)
      .filter((i) => i.number !== undefined || canSeeProjectItem(i, can, role, flags, projectType))
      .map((i) => ({ ...i, locked: i.number !== undefined && !can(i.perm) })),
  })).filter((g) => g.items.length > 0)
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
