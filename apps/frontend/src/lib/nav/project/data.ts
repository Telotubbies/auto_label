import type { NavGroup, ProjectNavItem } from '../types'

export const dataNav: NavGroup<ProjectNavItem> = {
  id: 'data', label: 'DATA', items: [
    { to: 'upload', label: 'Upload', icon: 'upload', perm: 'project.upload' },
    { to: 'browse', label: 'Dataset', icon: 'dataset', perm: 'project.read', count: true },
    // Video authoring (Task 22) sits with the images it annotates.
    { to: 'videos', label: 'Video', icon: 'video', perm: 'project.annotate', flag: 'task_22' },
    { to: 'versions', label: 'Versions', icon: 'versions', perm: 'project.export' },
    // Labelers may edit the ontology through the API, but the IA keeps the page for reviewers+.
    { to: 'classes', label: 'Classes & Tags', icon: 'classes', perm: 'project.classes', roles: ['manager', 'reviewer'] },
    // The dataset health check (Task 9) is a tab of the Insights studio, per the v2 tree;
    // /analytics stays alive as a legacy redirect into that tab.
    { to: 'insights', label: 'Insights', icon: 'insights', perm: 'project.review' },
  ],
}
