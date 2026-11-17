import type { Job } from './types'

/** One line per job kind the tray can list; the project name is appended by `resultLine`. */
export const JOB_KIND_LABEL: Record<Job['kind'], string> = {
  version: 'Version', export: 'Export', export_engine: 'TensorRT export', export_preset: 'Edge export',
  train: 'Training', autolabel: 'Auto-label', health: 'Health check',
  insights_images: 'Image stats', insights_leakage: 'Leakage scan', insights_embedding: 'Embedding map',
}

/** The page a job's Retry link and its row lead to, by kind. */
const JOB_KIND_PAGE: Record<Job['kind'], string> = {
  version: 'versions', export: 'versions', export_engine: 'models', export_preset: 'models',
  train: 'models', autolabel: 'annotate', health: 'analytics',
  insights_images: 'insights', insights_leakage: 'insights', insights_embedding: 'insights',
}

const ACTIVE = new Set<Job['status']>(['queued', 'running', 'cancelling'])

export const isActive = (job: Pick<Job, 'status'>) => ACTIVE.has(job.status)

/** Jobs a reviewer still has to wait for; finished, failed and cancelled do not count. */
export const activeCount = (jobs: Job[]) => jobs.filter(isActive).length

/**
 * `~2 min left` from progress and elapsed time. Queued jobs and runs under 5 % have no signal yet,
 * so they read `estimating`. `now` is epoch seconds, the unit of `Job.started`.
 */
export function etaLabel(job: Job, now: number): string {
  const elapsed = now - (job.started ?? job.created)
  if (job.status === 'queued' || job.progress < 5 || elapsed <= 0) return 'estimating'
  const minutes = Math.max(1, Math.round((elapsed / job.progress) * (100 - job.progress) / 60))
  return minutes < 60 ? `~${minutes} min left` : `~${Math.floor(minutes / 60)} h ${minutes % 60} min left`
}

/** `Training · Helmets` — the row's one line, U+00B7 between kind and project. */
export function resultLine(job: Pick<Job, 'kind' | 'project_name'>): string {
  return [JOB_KIND_LABEL[job.kind] ?? job.kind, job.project_name].filter(Boolean).join(' \u00B7 ')
}

/** The job's own project, so the workspace panel can cancel a row whatever route opened it. */
export function cancelPath(ws: string, job: Pick<Job, 'id' | 'project'>): string {
  return `/ws/${ws}/projects/${job.project ?? ''}/jobs/${job.id}/cancel`
}

/** The page where the job's outcome lives; Retry opens it. */
export function jobPath(ws: string, job: Pick<Job, 'kind' | 'project'>): string {
  return `/${ws}/${job.project ?? ''}/${JOB_KIND_PAGE[job.kind] ?? 'versions'}`
}
