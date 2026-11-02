import { useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Outlet, useLocation, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, Eye } from 'lucide-react'
import { api } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import type { Project } from '@/lib/types'
import { ProjectPanel, projNav } from '@/components/shell'
import { Button, EmptyState, Select, Spinner } from '@/components/ui'

export function useProject() {
  return useOutletContext<{ project: Project; ws: string }>()
}

export default function ProjectLayout() {
  const { ws = '', project: slug = '' } = useParams()
  const nav = useNavigate()
  const location = useLocation()
  const { can: canProject } = useProjectPermissions(ws, slug)
  const q = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug) })
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useLayoutEffect(() => { setSlot(document.getElementById('topbar-actions')) }, [])
  if (q.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  if (!q.data) return <EmptyState title="Project not found" hint={(q.error as Error)?.message} />
  const project = q.data
  const review = project.statusCounts?.review ?? 0
  // Below md the project sidebar is hidden; one compact select keeps every section reachable.
  const items = projNav.flatMap((g) => g.items).filter((i) => canProject(i.perm))
  const section = location.pathname.split('/').pop() ?? 'browse'
  return (
    <div className="flex h-full">
      <ProjectPanel project={project} />
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
          <div className="px-4 pb-1 md:hidden">
            <Select aria-label="Project section" value={items.some((i) => i.to === section) ? section : 'browse'}
              onChange={(e) => nav(`/${ws}/${slug}/${e.target.value}`)}>
              {items.map((i) => <option key={i.to} value={i.to}>{i.label}</option>)}
            </Select>
          </div>
          <Outlet context={{ project, ws }} />
        </div>
      </div>
    </div>
  )
}
