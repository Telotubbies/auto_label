import { useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, Eye } from 'lucide-react'
import { api } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import type { Project } from '@/lib/types'
import { ProjectPanel, projectNavGroups } from '@/components/shell'
import { cn } from '@/lib/utils'
import { Button, EmptyState, Spinner } from '@/components/ui'

export function useProject() {
  return useOutletContext<{ project: Project; ws: string }>()
}

export default function ProjectLayout() {
  const { ws = '', project: slug = '' } = useParams()
  const nav = useNavigate()
  const location = useLocation()
  const { can: canProject, role: projectRole } = useProjectPermissions(ws, slug)
  const q = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug) })
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useLayoutEffect(() => { setSlot(document.getElementById('topbar-actions')) }, [])
  if (q.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  if (!q.data) return <EmptyState title="Project not found" hint={(q.error as Error)?.message} />
  const project = q.data
  const review = project.statusCounts?.review ?? 0
  // Below lg the project panel is hidden; one compact strip keeps every section reachable.
  // Same builder and project role as ProjectPanel, so a role never sees a different IA by width.
  const items = projectNavGroups(canProject, projectRole).flatMap((g) => g.items)
  const section = location.pathname.split('/').pop() ?? 'browse'
  return (
    <div className="flex h-full">
      <div className="hidden shrink-0 lg:flex"><ProjectPanel project={project} /></div>
      <div className="flex min-w-0 flex-1 flex-col">
        {slot && createPortal(
          <>
            {canProject('project.review') && review > 0 && (
              <Button variant="outline" size="sm" onClick={() => nav(`/${ws}/${slug}/annotate`)}><Eye className="h-4 w-4" /> {review} awaiting review</Button>
            )}
            {canProject('project.train') && !location.pathname.endsWith('/train') && (
              <Button size="sm" onClick={() => nav(`/${ws}/${slug}/train`)}>
                <BrainCircuit className="h-4 w-4" /> Train Model
              </Button>
            )}
          </>, slot)}
        <div data-scroll className="min-h-0 flex-1 overflow-y-auto pt-14">
          {/* Below lg the project panel is hidden, so navigation lives in a scrollable strip. */}
          <nav aria-label="Project sections" className="sticky top-0 z-10 flex gap-1 overflow-x-auto border-b bg-card/95 px-2 py-1.5 backdrop-blur lg:hidden">
            {items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={`/${ws}/${slug}/${to}`}
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
