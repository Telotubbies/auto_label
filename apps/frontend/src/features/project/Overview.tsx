import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button, Card, PageHeader } from '@/components/ui'
import { typeLabel } from '@/components/shell'
import { projectPath } from '@/lib/routes'
import { useProjectPermissions } from '@/lib/perms'
import { useProject } from './ProjectLayout'
import { board, overviewFacts, STAGE_ORDER } from './overviewModel'
import { StageCard } from './StageCard'

/**
 * The project's cockpit: which of the five steps is done, blocked or next, in one screen.
 * Every count comes from a call the shell already makes; the header owns the one primary button.
 */
export default function Overview() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const versions = useQuery({ queryKey: ['versions', ws, project.slug], queryFn: () => api.versions(ws, project.slug) })
  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug) })
  const jobs = useQuery({ queryKey: ['jobs', ws, project.slug], queryFn: () => api.jobs(ws, project.slug) })
  const perms = useProjectPermissions(ws, project.slug)
  const approved = project.statusCounts?.done ?? 0
  const loading = versions.isPending || models.isPending || jobs.isPending
  const facts = overviewFacts({
    images: project.images,
    statusCounts: project.statusCounts,
    versions: versions.isError ? null : (versions.data ?? []),
    models: models.isError ? null : (models.data ?? []),
    jobs: jobs.isError ? null : (jobs.data ?? []),
    // Until /permissions lands, assume access: PermGate still owns the destination's enforcement.
    canTrain: !perms.ready || perms.can('project.train'),
    canDeploy: !perms.ready || perms.can('project.models'),
  })
  const retry = () => { void versions.refetch(); void models.refetch(); void jobs.refetch() }
  return (
    <div className="anim-page">
      <PageHeader
        title={project.name}
        desc={`${typeLabel(project.type)} · ${approved} approved`}
        actions={
          <Button variant="primary" onClick={() => nav(projectPath(ws, project.slug, facts.primary.to))}>
            {facts.primary.label}
          </Button>
        }
      />
      <div className="px-8 pb-10">
        <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start xl:gap-6">
          {loading ? (
            <ol aria-label="Project pipeline" aria-busy="true" className="grid gap-3 md:grid-cols-5">
              {STAGE_ORDER.map((id) => <li key={id}><Card className="h-[168px] animate-pulse" /></li>)}
            </ol>
          ) : (
            <ol aria-label="Project pipeline" className="grid gap-3 md:grid-cols-5">
              {board(facts.stages).map((stage) => (
                <StageCard key={stage.id} stage={stage} ws={ws} project={project.slug} onRetry={retry} />
              ))}
            </ol>
          )}
          {/* T-484 owns the 360 px column (health ring, latest run, blocked-by, activity). */}
          <aside className="hidden xl:block xl:w-[360px]" aria-hidden />
        </div>
      </div>
    </div>
  )
}
