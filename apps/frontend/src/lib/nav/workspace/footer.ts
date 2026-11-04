import { STAFF } from '../audience.ts'
import type { NavGroup, WorkspaceNavItem } from '../types'

export const footerNav: NavGroup<WorkspaceNavItem> = {
  id: 'footer', items: [
    { to: 'activity', label: 'Activity', icon: 'activity', roles: STAFF },
    // Settings holds the caller's own profile, security and preferences, so every role keeps it.
    { to: 'settings', label: 'Settings', icon: 'settings' },
    { to: 'admin', label: 'Admin', icon: 'admin', superadmin: true },
  ],
}
