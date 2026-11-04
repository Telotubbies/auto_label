import type { ProjectRole, Role } from '../types'

export type NavIcon =
  | 'projects' | 'models' | 'playground' | 'deployments' | 'members' | 'audit' | 'usage'
  | 'integrations' | 'activity' | 'settings' | 'admin'
  | 'upload' | 'annotate' | 'dataset' | 'video' | 'versions' | 'classes' | 'insights' | 'train'
  | 'modelInsights' | 'deploy' | 'qa' | 'streams' | 'access' | 'projectSettings'
  | 'lineage' | 'dashboards' | 'streamAnalytics'

export interface WorkspaceNavItem {
  to: string
  label: string
  icon: NavIcon
  /** Exact match only (the core entry must not stay active on every workspace page). */
  end?: boolean
  /** Roles that may see the route; omitted = every member. */
  roles?: Role[]
  /** Platform operator entry, not a workspace role. */
  superadmin?: boolean
}

export interface ProjectNavItem {
  to: string
  label: string
  icon: NavIcon
  /** Project permission required by the API gateway for the route. */
  perm: string
  /** Narrower audience than the permission, for pages the IA hides from labelers. */
  roles?: ProjectRole[]
  /** Feature flag that gates both this nav entry and its API surface. */
  flag?: string
  /** Show the project's image count beside the label. */
  count?: boolean
}

export interface NavGroup<T> {
  id: string
  label?: string
  items: T[]
}
