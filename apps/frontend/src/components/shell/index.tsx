/**
 * App shell, split by surface so a change to one piece does not touch the others:
 * sidebar (nav rail + workspace switcher), project panel, top bar, job tray, and the layout
 * that wires them. The nav itself is registered in `@/lib/nav`, not here.
 */
export { AppLayout } from './AppLayout'
export { AppSidebar } from './AppSidebar'
export { GpuBadge, TopBar } from './TopBar'
export { JobTray } from './JobTray'
export { ProjectPanel, projNav, projectNavGroups, typeLabel } from './ProjectPanel'
