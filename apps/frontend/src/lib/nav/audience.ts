import type { ProjectRole, Role } from '../types'
import type { ProjectNavItem } from './types'

/**
 * Visibility is an explicit audience per item, not a rank comparison: `rbac.py` grants GOVERN
 * surfaces to specific roles (a billing user gets Usage & Billing, an admin does not), which a
 * "role >= member" test cannot express.
 */

/** The roles that can hold a workspace: `rbac.WORKSPACE_PERMISSIONS` uses these names. */
export const STAFF: Role[] = ['owner', 'admin', 'member', 'reviewer', 'annotator']
export const OWNER_ADMIN: Role[] = ['owner', 'admin']
// Owners and admins see GOVERN complete; billing sees its one surface and nothing else.
export const BILLING_AUDIENCE: Role[] = ['owner', 'admin', 'billing']

/** Legacy workspace roles that do project work only; the IA gives them no workspace ML surfaces. */
export const NO_BUILD: Role[] = ['reviewer', 'annotator']

/** True when an item's optional audience admits the caller; no audience means everyone. */
export function inAudience<T extends string>(roles: readonly T[] | undefined, role: T | null | undefined): boolean {
  return !roles || !role || roles.includes(role)
}

export function canSeeProjectItem(
  item: Pick<ProjectNavItem, 'perm' | 'roles' | 'flag'>, can: (perm: string) => boolean,
  role?: ProjectRole | null, flags?: ReadonlySet<string>,
): boolean {
  if (item.flag && flags && !flags.has(item.flag)) return false
  return can(item.perm) && inAudience(item.roles, role)
}
