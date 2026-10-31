import { Outlet, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, Eye } from 'lucide-react'
import { api } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Project } from '@/lib/types'
import { ProjectPanel } from '@/components/shell'
import { Button, EmptyState, Spinner } from '@/components/ui'

export function useProject() {
  return useOutletContext<{ project: Project; ws: string }>()
}

export default function ProjectLayout() {
  const { ws = '', project: slug = '' } = useParams()
  const nav = useNavigate()
  const can = useApp((s) => s.can)
  const q = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug) })
  if (q.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  if (!q.data) return <EmptyState title="Project not found" hint={(q.error as Error)?.message} />
  const project = q.data
  const review = project.statusCounts?.review ?? 0
  return (
    <div className="flex h-full">
      <ProjectPanel project={project} />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b px-6 py-2.5">
          <span className="text-sm font-medium text-muted-foreground">{project.name}</span>
          <div className="ml-auto flex items-center gap-2">
            {can('reviewer') && review > 0 && (
              <Button variant="outline" size="sm" onClick={() => nav(`/${ws}/${slug}/annotate`)}><Eye className="h-4 w-4" /> {review} awaiting review</Button>
            )}
            {can('admin') && (
              <Button size="sm" className="bg-gradient-to-r from-violet-600 to-indigo-600" onClick={() => nav(`/${ws}/${slug}/train`)}>
                <BrainCircuit className="h-4 w-4" /> Train Model
              </Button>
            )}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto"><Outlet context={{ project, ws }} /></div>
      </div>
    </div>
  )
}
