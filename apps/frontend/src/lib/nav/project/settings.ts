import type { NavGroup, ProjectNavItem } from '../types'

// Access is a tab of Project settings since the v2 tree; the separate /access route redirects.
export const settingsNav: NavGroup<ProjectNavItem> = {
  id: 'settings', label: 'SETTINGS', items: [
    { to: 'settings', label: 'Project Settings', icon: 'projectSettings', perm: 'project.settings' },
  ],
}
