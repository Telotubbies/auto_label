import type { NavGroup, ProjectNavItem } from '../types'

export const modelsNav: NavGroup<ProjectNavItem> = {
  id: 'models', label: 'MODELS', items: [
    { to: 'train', label: 'Train', icon: 'train', perm: 'project.train' },
    // Task 29's good-only station trains a detector on normal images; anomaly projects only.
    { to: 'anomaly', label: 'Anomaly', icon: 'anomaly', perm: 'project.read', roles: ['manager', 'reviewer'], flag: 'task_29', type: 'anomaly-detection' },
    { to: 'model-insights', label: 'Model insights', icon: 'modelInsights', perm: 'project.review' },
    { to: 'models', label: 'Models', icon: 'models', perm: 'project.models' },
  ],
}
