import { useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, Eye } from 'lucide-react'
import { api } from '@/lib/api'
import { useFlag, useWorkspaceFlags } from '@/lib/flags'
import { useProjectPermissions } from '@/lib/perms'
import { projectPath } from '@/lib/routes'
import type { Project } from '@/lib/types'
import { ProjectPanel, projectNavGroups, useProjectRail } from '@/components/shell'
import { StageItem } from '@/components/shell/StageItem'
import { cn } from '@/lib/utils'
import { Button, EmptyState, Spinner } from '@/components/ui'

export function useProject() {
  return useOutletContext<{ project: Project; ws: string }>()
}

export default function ProjectLayout() {
  const { ws = '', project: slug = '' } = useParams()
  const q = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug) })
  if (q.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  // A slug this member cannot read is a 404, never a rail over another workspace's data.
  if (!q.data) return <EmptyState title="Project not found" hint={(q.error as Error)?.message} />
  return <ProjectShell project={q.data} slug={slug} />
}

function ProjectShell({ project, slug }: { project: Project; slug: string }) {
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const location = useLocation()
  const { can: canProject, role: projectRole } = useProjectPermissions(ws, slug)
  const flagsQuery = useWorkspaceFlags()
  const flags = flagsQuery.data ? new Set(flagsQuery.data.enabled) : undefined
  // `task_470` (`ui_v3`): off keeps the v2 strip and the two portal buttons exactly as they ship.
  const uiV3 = useFlag('task_470')
  const rail = useProjectRail(project)
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useLayoutEffect(() => { setSlot(document.getElementById('topbar-actions')) }, [])
  const review = project.statusCounts?.review ?? 0
  // Below lg the project panel is hidden; one compact strip keeps every section reachable.
  // Same builder and project role as ProjectPanel, so a role never sees a different IA by width.
  const items = projectNavGroups(canProject, projectRole, flags, project.type).flatMap((g) => g.items)
  return (
    <div className="flex h-full">
      <div className="hidden shrink-0 lg:flex"><ProjectPanel project={project} /></div>
      <div className="flex min-w-0 flex-1 flex-col">
        {!uiV3 && slot && createPortal(
          <>
            {canProject('project.review') && review > 0 && (
              <Button variant="outline" size="sm" onClick={() => nav(projectPath(ws, slug, 'annotate'))}><Eye className="h-4 w-4" /> {review} awaiting review</Button>
            )}
            {canProject('project.train') && !location.pathname.endsWith('/train') && (
              <Button size="sm" onClick={() => nav(projectPath(ws, slug, 'train'))}>
                <BrainCircuit className="h-4 w-4" /> Train Model
              </Button>
            )}
          </>, slot)}
        <div data-scroll className="min-h-0 flex-1 overflow-y-auto pt-14">
          {/* Below lg the project panel is hidden, so navigation lives in a scrollable strip. */}
          <nav aria-label="Project sections" className="sticky top-0 z-10 flex gap-3 overflow-x-auto border-b bg-card/95 px-2 py-1.5 backdrop-blur lg:hidden">
            {uiV3 ? (
              <>
                {rail.groups.map((g) => (
                  <div key={g.id} className="shrink-0">
                    <div className="pb-0.5 text-xs font-medium text-muted-foreground">{g.label}</div>
                    {/* StageItem renders its own <li>; the strip keeps each one from shrinking. */}
                    <ul className="flex gap-1 [&>li]:shrink-0">
                      {g.items.map((row) => (
                        <StageItem key={row.id} row={row} facts={rail.facts} ws={ws} slug={slug}
                          active={row.id === rail.activeId} loading={rail.loading} />
                      ))}
                    </ul>
                  </div>
                ))}
                {rail.secondary.map((i) => (
                  <div key={i.id} className="shrink-0 self-end">
                    <Link to={projectPath(ws, slug, i.to)}
                      aria-current={i.id === rail.activeId ? 'page' : undefined}
                      className={cn('flex h-8 items-center rounded-md border px-2 text-sm',
                        i.id === rail.activeId
                          ? 'border-primary bg-accent font-medium text-accent-foreground'
                          : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground')}>
                      {i.label}
                    </Link>
                  </div>
                ))}
              </>
            ) : items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={projectPath(ws, slug, to)}
                className={({ isActive }) => cn('flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs',
                  isActive ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
                <Icon className="h-3.5 w-3.5" aria-hidden />{label}
              </NavLink>
            ))}
          </nav>
          <Outlet context={{ project, ws }} />
        </div>
      </div>
    </div>
  )
}
