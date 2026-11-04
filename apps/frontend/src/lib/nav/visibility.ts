import type { ProjectRole, Role } from '../types'
import { canSeeProjectItem, inAudience, NO_BUILD } from './audience.ts'
import { projectNav, workspaceNav } from './registry.ts'
import type { NavGroup, ProjectNavItem, WorkspaceNavItem } from './types'

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

export function visibleProjectNav(
  can: (perm: string) => boolean, role?: ProjectRole | null, flags?: ReadonlySet<string>,
): NavGroup<ProjectNavItem>[] {
  return projectNav
    .map((g) => ({ ...g, items: g.items.filter((i) => canSeeProjectItem(i, can, role, flags)) }))
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
