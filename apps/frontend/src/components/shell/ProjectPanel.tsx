import { ArrowLeft, MoreVertical } from 'lucide-react'
import { Link, NavLink, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, fileUrl } from '@/lib/api'
import { projectPath } from '@/lib/routes'
import { useFlag, useWorkspaceFlags } from '@/lib/flags'
import { useApp } from '@/lib/store'
import { typeLabel } from '@/features/project/projectTypes'
import {
  canSeeProjectItem, groupSummary, SECONDARY, stageFacts, visibleProjectNav, visibleStageGroups,
} from '@/lib/nav'
import { panelSections } from '@/lib/nav/project/panelLayout.ts'
import { useProjectPermissions } from '@/lib/perms'
import type { Project, ProjectRole } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { Button, Dropdown } from '../ui'
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

/** The shipped panel (flag off): back link, project card, then DATA / MODELS / DEPLOY collapsible groups. */
function ClassicPanel({ project, legacy }: { project: Project; legacy: ReturnType<typeof projectNavGroups> }) {
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const { pathname } = useLocation()
  const me = useApp((s) => s.me)
  const wsName = me?.workspaces.find((w) => w.slug === ws)?.name ?? ws
  const deployments = { to: `/${ws}/deployments`, label: 'Deployments', icon: ICONS.deployments, perm: 'project.read' }
  const sections = panelSections(legacy, deployments)
  const hrefOf = (to: string) => (to.startsWith('/') ? to : projectPath(ws, project.slug, to))
  const isActive = (to: string) => pathname === hrefOf(to) || pathname.startsWith(`${hrefOf(to)}/`)
  const settings = sections.flatMap((s) => s.entries).find((e) => e !== 'divider' && e.to === 'settings')
  return (
    <Glass as="div" className="glass-sidebar m-2 mr-0 mt-16 hidden h-[calc(100%-4.5rem)] w-56 shrink-0 flex-col overflow-y-auto rounded-2xl md:flex">
      <Link to={`/${ws}`} className="flex items-center gap-1.5 px-3 pt-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
        <span className="truncate">{wsName}</span>
      </Link>
      <div className="p-3">
        <div className="overflow-hidden rounded-lg border">
          <div className="relative h-20 bg-muted">
            {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
            <span className="absolute left-2 top-2 rounded bg-scrim/70 px-1.5 py-0.5 text-xs text-white">{typeLabel(project.type)}</span>
          </div>
          <div className="flex items-center gap-1 px-2.5 py-1.5">
            <Link to={projectPath(ws, project.slug)} className="min-w-0 flex-1 truncate text-sm font-semibold hover:underline">{project.name}</Link>
            {settings && (
              <Dropdown align="right"
                trigger={<button type="button" aria-label="Project menu" className="grid h-7 w-7 cursor-pointer place-items-center rounded-md text-muted-foreground hover:bg-sidebar-accent"><MoreVertical className="h-4 w-4" /></button>}
                items={[{ label: 'Project settings', onClick: () => nav(projectPath(ws, project.slug, 'settings')) }]} />
            )}
          </div>
        </div>
      </div>
      <nav aria-label="Project sections" className="flex-1 px-2 pb-4">
        {sections.map((sec) => (
          <RailGroup key={sec.id} id={sec.id} label={sec.label} summary={null}
            holdsActive={sec.entries.some((e) => e !== 'divider' && isActive(e.to))}>
            {sec.entries.map((e, i) => e === 'divider' ? <li key={i} role="separator" className="my-1.5 border-t" /> : (
              <li key={e.to}>
                <NavLink to={hrefOf(e.to)} end={false}
                  className={cn('flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm',
                    isActive(e.to) ? 'border-primary font-medium text-foreground' : 'border-transparent text-foreground hover:bg-sidebar-accent/60')}>
                  <e.icon className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1">{e.label}</span>
                  {"count" in e && e.count === true && <span className="rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{project.images}</span>}
                </NavLink>
              </li>
            ))}
          </RailGroup>
        ))}
      </nav>
    </Glass>
  )
}

export function ProjectPanel({ project }: { project: Project }) {
  const { ws, facts, groups, secondary, activeId, legacy, loading, failed, retry } = useProjectRail(project)
  // `task_470` (`ui_v3`): off keeps the shipped grouped panel exactly as it renders today.
  const uiV3 = useFlag('task_470')

  if (!uiV3) return <ClassicPanel project={project} legacy={legacy} />

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
