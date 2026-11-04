import { STAFF } from '../audience.ts'
import type { NavGroup, WorkspaceNavItem } from '../types'

export const buildNav: NavGroup<WorkspaceNavItem> = {
  id: 'build', label: 'BUILD', items: [
    { to: 'models', label: 'Models', icon: 'models', roles: STAFF },
    { to: 'playground', label: 'Playground', icon: 'playground', roles: STAFF },
    { to: 'deployments', label: 'Deployments', icon: 'deployments', roles: STAFF },
  ],
}
