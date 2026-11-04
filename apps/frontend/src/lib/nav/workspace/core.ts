import { STAFF } from '../audience.ts'
import type { NavGroup, WorkspaceNavItem } from '../types'

export const coreNav: NavGroup<WorkspaceNavItem> = {
  id: 'core', items: [
    { to: '', label: 'Projects', icon: 'projects', end: true, roles: STAFF },
  ],
}
