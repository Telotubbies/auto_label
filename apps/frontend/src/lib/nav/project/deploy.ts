import type { NavGroup, ProjectNavItem } from '../types'

export const deployNav: NavGroup<ProjectNavItem> = {
  id: 'deploy', label: 'DEPLOY', items: [
    { to: 'deploy', label: 'Deploy & Test', icon: 'deploy', perm: 'project.models' },
    // Task 10b's CCTV streams are a deploy surface: watching follows project.streams (manager/reviewer).
    { to: 'streams', label: 'Streams', icon: 'streams', perm: 'project.streams', flag: 'task_10b' },
  ],
}
