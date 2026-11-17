import { OWNER_ADMIN, STAFF } from '../audience.ts'
import type { NavGroup, WorkspaceNavItem } from '../types'

/**
 * The five destinations of the v3 workspace rail, in the order the redesign fixes. Members, plan
 * and usage, keys and audit are Settings tabs; Playground is reached from Deploy's Test tab and the
 * command palette. Nothing here is a second copy of a Settings tab.
 */
export const coreNav: NavGroup<WorkspaceNavItem> = {
  id: 'core', items: [
    { to: '', label: 'Projects', icon: 'projects', end: true, roles: STAFF },
    { to: 'models', label: 'Models', icon: 'models', roles: STAFF },
    { to: 'deployments', label: 'Deployments', icon: 'deployments', roles: STAFF },
    { to: 'activity', label: 'Activity', icon: 'activity', roles: STAFF },
    { to: 'inference', label: 'Inference', icon: 'models', roles: OWNER_ADMIN, flag: 'task_inference' },
  ],
}
