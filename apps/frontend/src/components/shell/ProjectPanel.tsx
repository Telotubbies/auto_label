import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, fileUrl } from '@/lib/api'
import { projectPath } from '@/lib/routes'
import { useFlag, useWorkspaceFlags } from '@/lib/flags'
import { useApp } from '@/lib/store'
import { typeLabel } from '@/features/project/projectTypes'
import {
  canSeeProjectItem, groupSummary, SECONDARY, stageFacts, visibleProjectNav, visibleStageGroups,
} from '@/lib/nav'
import { useProjectPermissions } from '@/lib/perms'
import type { Project, ProjectRole } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { Button } from '../ui'
import { ICONS } from './icons'
import { RailGroup, SEP } from './RailGroup'
import { StageItem } from './StageItem'

/**
 * Icon-carrying project nav for every renderer. The desktop panel and the compact strip both call
 * this with the same permission check and project role, so a role never sees a different IA by width.
 * Flag off (below) renders this; the v3 rail renders `useProjectRail` instead.
 */
export function projectNavGroups(
  can: (perm: string) => boolean, role?: ProjectRole | null, flags?: ReadonlySet<string>,
  projectType?: string,
) {
  return visibleProjectNav(can, role, flags, projectType).map((g) => ({
    group: g.label ?? '',
    items: g.items.map((i) => ({ ...i, icon: ICONS[i.icon] })),
  }))
}

/** Unfiltered shape used for breadcrumb label lookup. */
export const projNav = projectNavGroups(() => true)

// One catalogue for the grid, the Home filter and this rail (T-017).
export { typeLabel }

/**
 * One rail model for both widths: the three purpose groups with the numbers, counts, states and
 * locks they render. Every count comes from a call the project shell already makes — the project
 * payload, `GET /versions` and `GET /jobs` — so the rail shares its cache with the overview and the
 * train screen and never invents a zero. An unloaded or failed call derives `null`, which the rail
 * paints as a skeleton or a dash.
 */
export function useProjectRail(project: Project) {
  const { ws = '' } = useParams()
  const location = useLocation()
  const can = useApp((s) => s.can)
  // Project routes follow the resolved project role (manager/reviewer may sit on a member workspace
  // account). Until the fetch lands, workspace admins keep seeing the full nav.
  const { can: canProject, ready, role: projectRole } = useProjectPermissions(ws, project.slug)
  const flagsQuery = useWorkspaceFlags()
  const flags = flagsQuery.data ? new Set(flagsQuery.data.enabled) : undefined
  // The rail is the v3 chrome; flag off renders the v2 panel and never pays for these two calls.
  const uiV3 = useFlag('task_470')
  const versions = useQuery({ queryKey: ['versions', ws, project.slug], queryFn: () => api.versions(ws, project.slug), enabled: uiV3 })
  const jobs = useQuery({ queryKey: ['jobs', ws, project.slug], queryFn: () => api.jobs(ws, project.slug), enabled: uiV3 })
  const visible = (perm: string) => (ready ? canProject(perm) : can('admin'))
  const groups = visibleStageGroups(visible, projectRole, flags, project.type)
  const secondary = SECONDARY
    .filter((i) => canSeeProjectItem(i, visible, projectRole, flags, project.type))
    .map((i) => ({ ...i, id: i.to }))
  const facts = stageFacts({
    project,
    versions: versions.isError ? null : versions.data,
    jobs: jobs.isError ? null : jobs.data,
  })
  // `Model search` opens `models?tab=search`: a query-qualified row wins over the plain row on the
  // same path, so exactly one row is ever tinted. A child route (the editor under `annotate`) keeps
  // its stage current.
  const path = location.pathname.replace(/\/+$/, '')
  const hit = (to: string) => {
    const [segment, query = ''] = to.split('?')
    const href = projectPath(ws, project.slug, segment)
    if (path !== href && !path.startsWith(`${href}/`)) return false
    if (!query) return true
    const have = new URLSearchParams(location.search)
    return [...new URLSearchParams(query)].every(([key, value]) => have.get(key) === value)
  }
  const rows: { id: string; to: string }[] = [...groups.flatMap((g) => g.items), ...secondary]
  const activeId = rows.find((r) => r.to.includes('?') && hit(r.to))?.id ?? rows.find((r) => hit(r.to))?.id
  return {
    ws, facts, groups, secondary, activeId,
    legacy: projectNavGroups(visible, projectRole, flags, project.type),
    loading: versions.isPending || jobs.isPending,
    failed: versions.isError || jobs.isError,
    retry: () => { void versions.refetch(); void jobs.refetch() },
  }
}

function Switcher({ project, approved }: { project: Project; approved: number | null }) {
  const { ws = '' } = useParams()
  return (
    <div className="flex items-center gap-2.5 border-b px-3 py-3">
      <span className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-muted">
        {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
      </span>
      <div className="min-w-0">
        <Link to={projectPath(ws, project.slug)} className="block truncate text-sm font-semibold hover:underline">{project.name}</Link>
        <p className="truncate text-sm text-muted-foreground">
          {`${typeLabel(project.type).toLowerCase()} ${SEP} ${approved ?? '—'} approved`}
        </p>
      </div>
    </div>
  )
}

export function ProjectPanel({ project }: { project: Project }) {
  const { ws, facts, groups, secondary, activeId, legacy, loading, failed, retry } = useProjectRail(project)
  // `task_470` (`ui_v3`): off keeps the shipped grouped panel exactly as it renders today.
  const uiV3 = useFlag('task_470')

  if (!uiV3) {
    return (
      <Glass as="div" className="glass-sidebar m-2 mr-0 mt-16 hidden h-[calc(100%-4.5rem)] w-56 shrink-0 flex-col overflow-y-auto rounded-2xl md:flex">
        <div className="p-3">
          <div className="overflow-hidden rounded-lg border">
            <div className="relative h-20 bg-muted">
              {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
              <span className="absolute left-2 top-2 rounded bg-scrim/70 px-1.5 py-0.5 text-xs text-white">{typeLabel(project.type)}</span>
            </div>
            <Link to={projectPath(ws, project.slug)} className="block px-2.5 py-2 text-sm font-semibold hover:underline">{project.name}</Link>
          </div>
        </div>
        <nav aria-label="Project sections" className="flex-1 px-2 pb-4">
          {legacy.map((g) => (
            <div key={g.group} role="group" aria-labelledby={`proj-nav-${g.group}`} className="mb-3">
              <div id={`proj-nav-${g.group}`} className="px-2 pb-1 text-sm font-semibold tracking-wider text-muted-foreground">{g.group}</div>
              {g.items.map(({ to, label, icon: Icon, count }) => (
                <NavLink key={to} to={projectPath(ws, project.slug, to)}
                  className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                    isActive ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground' : 'text-foreground hover:bg-sidebar-accent/60')}>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1">{label}</span>
                  {count && <span className="text-sm text-muted-foreground">{project.images}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </Glass>
    )
  }

  return (
    <Glass as="div" className="glass-sidebar m-2 mr-0 mt-16 hidden h-[calc(100%-4.5rem)] w-60 shrink-0 flex-col overflow-y-auto rounded-2xl md:flex">
      <Switcher project={project} approved={facts.approved} />
      <nav aria-label="Project sections" className="flex-1 px-2 pb-4">
        {groups.map((g) => (
          <RailGroup key={g.id} id={g.id} label={g.label ?? ''} summary={groupSummary(facts, g.id)}
            holdsActive={g.items.some((i) => i.id === activeId)}>
            {g.items.map((row) => (
              <StageItem key={row.id} row={row} facts={facts} ws={ws} slug={project.slug}
                active={row.id === activeId} loading={loading} />
            ))}
          </RailGroup>
        ))}
        {failed && (
          <div className="mt-3 flex items-center justify-between gap-2 rounded px-2 text-sm text-muted-foreground">
            <span>Project facts did not load</span>
            <Button variant="ghost" size="sm" onClick={retry}>Retry</Button>
          </div>
        )}
        {secondary.length > 0 && (
          <div className="mt-3 border-t px-2 pt-2">
            {secondary.map((i) => (
              <Link key={i.id} to={projectPath(ws, project.slug, i.to)}
                aria-current={i.id === activeId ? 'page' : undefined}
                className={cn('flex min-h-9 items-center gap-2 rounded-lg px-2 text-sm',
                  i.id === activeId
                    ? 'bg-accent font-semibold text-accent-foreground ring-1 ring-primary/40'
                    : 'text-foreground hover:bg-sidebar-accent/60')}>
                {i.label}
              </Link>
            ))}
          </div>
        )}
      </nav>
    </Glass>
  )
}
