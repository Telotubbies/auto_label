import type { NavGroup, ProjectNavItem } from '../types'

export const modelsNav: NavGroup<ProjectNavItem> = {
  id: 'models', label: 'MODELS', items: [
    { to: 'train', label: 'Train', icon: 'train', perm: 'project.train' },
    { to: 'model-insights', label: 'Model insights', icon: 'modelInsights', perm: 'project.review' },
    { to: 'models', label: 'Models', icon: 'models', perm: 'project.models' },
  ],
}
