import type { NavGroup, WorkspaceNavItem } from '../types'

export const footerNav: NavGroup<WorkspaceNavItem> = {
  id: 'footer', items: [
    // Settings holds the caller's own profile, security and preferences, so every role keeps it —
    // and it is the one entry a billing role lands on, via Plan & Usage.
    { to: 'settings', label: 'Settings', icon: 'settings' },
    { to: 'admin', label: 'Admin', icon: 'admin', superadmin: true },
  ],
}
