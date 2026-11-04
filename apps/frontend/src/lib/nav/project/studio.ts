import type { NavGroup, ProjectNavItem } from '../types'

// Task 20c's analysis studio: lineage, dashboard builder and stream analytics.
export const studioNav: NavGroup<ProjectNavItem> = {
  id: 'studio', label: 'STUDIO', items: [
    { to: 'lineage', label: 'Lineage', icon: 'lineage', perm: 'project.review', flag: 'task_20c' },
    { to: 'dashboards', label: 'Dashboards', icon: 'dashboards', perm: 'project.review', flag: 'task_20c' },
    { to: 'stream-analytics', label: 'Stream analytics', icon: 'streamAnalytics', perm: 'project.review', flag: 'task_20c' },
  ],
}
