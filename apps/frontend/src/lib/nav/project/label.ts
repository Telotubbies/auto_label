import type { NavGroup, ProjectNavItem } from '../types'

export const labelNav: NavGroup<ProjectNavItem> = {
  id: 'label', label: 'LABEL', items: [
    { to: 'annotate', label: 'Annotate', icon: 'annotate', perm: 'project.annotate' },
    // Task 23's QA hub opens on project.review; labelers reach their queue through Annotate.
    { to: 'qa', label: 'Review & Quality', icon: 'qa', perm: 'project.review', roles: ['manager', 'reviewer'], flag: 'task_23' },
  ],
}
