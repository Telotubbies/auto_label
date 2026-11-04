import { Link, NavLink, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, fileUrl } from '@/lib/api'
import { useWorkspaceFlags } from '@/lib/flags'
import { useApp } from '@/lib/store'
import { visibleProjectNav } from '@/lib/nav'
import { useProjectPermissions } from '@/lib/perms'
import type { Project, ProjectRole } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { ICONS } from './icons'

/**
 * Icon-carrying project nav for every renderer. The desktop panel and the compact strip both call
 * this with the same permission check and project role, so a role never sees a different IA by width.
 */
export function projectNavGroups(
  can: (perm: string) => boolean, role?: ProjectRole | null, flags?: ReadonlySet<string>,
) {
  return visibleProjectNav(can, role, flags).map((g) => ({
    group: g.label ?? '',
    items: g.items.map((i) => ({ ...i, icon: ICONS[i.icon] })),
  }))
}

/** Unfiltered shape used for breadcrumb label lookup. */
export const projNav = projectNavGroups(() => true)

export const typeLabel = (t: string) =>
  ({ 'object-detection': 'Object Detection', 'instance-segmentation': 'Instance Segmentation', classification: 'Classification', 'keypoint-detection': 'Keypoint Detection' } as Record<string, string>)[t] ?? t

export function ProjectPanel({ project }: { project: Project }) {
  const { ws = '' } = useParams()
  const can = useApp((s) => s.can)
  // Project routes follow the resolved project role (manager/reviewer may sit on a member workspace
  // account). Until the fetch lands, workspace admins keep seeing the full nav.
  const { can: canProject, ready, role: projectRole } = useProjectPermissions(ws, project.slug)
  const flagsQuery = useWorkspaceFlags()
  const flags = flagsQuery.data ? new Set(flagsQuery.data.enabled) : undefined
  const visible = (perm: string) => (ready ? canProject(perm) : can('admin'))
  const groups = projectNavGroups(visible, projectRole, flags)
  return (
    <Glass as="div" className="glass-sidebar m-2 mr-0 mt-16 hidden h-[calc(100%-4.5rem)] w-56 shrink-0 flex-col overflow-y-auto rounded-2xl md:flex">
      <div className="p-3">
        <div className="overflow-hidden rounded-lg border">
          <div className="relative h-20 bg-muted">
            {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
            <span className="absolute left-2 top-2 rounded bg-scrim/70 px-1.5 py-0.5 text-[10px] text-white">{typeLabel(project.type)}</span>
          </div>
          <div className="px-2.5 py-2 text-sm font-semibold">{project.name}</div>
        </div>
      </div>
      <nav aria-label="Project sections" className="flex-1 px-2 pb-4">
        {groups.map((g) => (
          <div key={g.group} role="group" aria-labelledby={`proj-nav-${g.group}`} className="mb-3">
            <div id={`proj-nav-${g.group}`} className="px-2 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground">{g.group}</div>
            {g.items.map(({ to, label, icon: Icon, count }) => (
              <NavLink key={to} to={`/${ws}/${project.slug}/${to}`}
                className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
                  isActive ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground' : 'text-foreground hover:bg-sidebar-accent/60')}>
                <Icon className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1">{label}</span>
                {count && <span className="text-[11px] text-muted-foreground">{project.images}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </Glass>
  )
}
