/**
 * The Segmentation tab (T-1015): one project picked above a grid of the segmentation models auto-label
 * can run, each with its memory at 512 px and 1024 px, its licence and this host's verdict. A Ready
 * row hands off to the dataset's existing Auto label dialog (T-1016) with the ref in the link; a row
 * that is not ready names the env var and path to fix instead of offering a button that would fail.
 * The host picker lives in the hub header; this panel only consumes the chosen host.
 */
import { useEffect, useState, useTransition } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, ServerOff } from 'lucide-react'
import { Glass } from '@/components/glass'
import { Button, Card, EmptyState, Select, Spinner } from '@/components/ui'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { inferenceSegmentation } from '@/lib/api/inference'
import type { InferenceHost, Project, SegmentationModel } from '@/lib/types'
import {
  NO_MODEL, NO_PROJECT, SETUP_DOC, action, lastProject, licenceTone, pickProject, ready,
  rememberProject, stateCopy, vramCopy,
} from './segRows'

const SKELETON = [0, 1, 2, 3, 4, 5]

/** Six cards while the host or its catalogue are still on the wire. */
const SkeletonCards = () => (
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading models">
    {SKELETON.map((i) => (
      <Card key={i} className="space-y-3 p-4">
        <div className="h-4 w-32 animate-pulse rounded bg-muted" />
        <div className="h-3 w-24 animate-pulse rounded bg-muted" />
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-8 w-full animate-pulse rounded bg-muted" />
      </Card>
    ))}
  </div>
)

function ModelCard({ row, ws, project }: { row: SegmentationModel; ws: string; project: string | null }) {
  const navigate = useNavigate()
  const [going, startTransition] = useTransition()
  const [goingId, setGoingId] = useState('')
  const state = stateCopy(row)
  const licence = licenceTone(row)
  const act = action(row, ws, project)

  const openLabel = (id: string, href: string) => {
    setGoingId(id)
    startTransition(() => navigate(href))
  }

  return (
    <Card role="listitem" className="flex flex-col gap-3 p-4" aria-labelledby={`seg-${row.id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div>
          <h3 id={`seg-${row.id}`} className="text-sm font-medium">{row.name}</h3>
          <p className="text-xs text-muted-foreground">{row.family} · {row.params_m} M params</p>
        </div>
        <a href={row.licence.url} target="_blank" rel="noreferrer noopener"
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${licence.className}`}>
          {licence.label}
          <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>

      {licence.note && (
        <p className="inline-flex w-fit rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
          {licence.note}
        </p>
      )}

      <p className="text-xs tabular-nums text-muted-foreground" title={row.note}>
        {vramCopy(row).split(' · ').map((line) => <span key={line} className="block">{line}</span>)}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {/* StatusPill title-cases every word, which would rewrite "Missing checkpoint"; same tone, same words. */}
        <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
          ready(row) ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning')}>
          {state.label}
        </span>
        <a href={row.source_url} target="_blank" rel="noreferrer noopener"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline">
          Source <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>
      {state.detail && <p className="text-xs text-muted-foreground">{state.detail}</p>}

      <div className="mt-auto flex flex-col gap-2 border-t pt-3 sm:flex-row sm:items-center">
        <Button className="w-full sm:w-auto" disabled={act.disabled || going}
          title={act.reason || undefined} aria-label={`Use ${row.name} for auto-label`}
          onClick={() => act.href && openLabel(row.id, act.href)}>
          {going && goingId === row.id ? <><Spinner className="h-3.5 w-3.5" /> Opening…</> : 'Use for auto-label'}
        </Button>
        <a href={row.source_url} target="_blank" rel="noreferrer noopener"
          aria-label={`Open documentation for ${row.name}`}
          className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-input bg-card px-3 text-sm font-medium hover:bg-accent sm:w-auto">
          Open documentation <ExternalLink className="h-3.5 w-3.5" aria-hidden />
        </a>
      </div>
      {act.reason === NO_PROJECT && <p className="text-xs text-muted-foreground">{act.reason}</p>}
    </Card>
  )
}

export default function SegmentationTab({ ws, host, hostsLoading, hostsError, onRetryHosts }: {
  ws: string
  host: InferenceHost | null
  hostsLoading: boolean
  hostsError: boolean
  onRetryHosts: () => void
}) {
  const hostId = host?.id ?? ''
  const projects = useQuery({ queryKey: ['projects', ws], queryFn: () => api.projects(ws), enabled: !!ws })
  const [project, setProject] = useState('')
  const list = projects.data ?? []

  // The card asks for the last opened project; until a pick is made, the remembered one (or the most
  // recently updated) is the default. A remembered slug that no longer exists falls back, not 404s.
  useEffect(() => {
    if (project || !list.length) return
    const next = pickProject(list as Project[], lastProject(ws))
    if (next) setProject(next)
  }, [list, project, ws])

  const models = useQuery({
    queryKey: ['inference-segmentation', ws, hostId, project],
    enabled: !!hostId,
    retry: false,
    queryFn: () => inferenceSegmentation(ws, hostId, project),
  })
  const rows = models.data?.models ?? []
  const anyReady = rows.some((row) => row.provisioned.ok && row.auto_label.ref)

  if (hostsLoading) return <SkeletonCards />

  if (hostsError) {
    return (
      <Card className="p-6">
        <p className="text-sm text-destructive">Segmentation did not load for this host.</p>
        <Button variant="outline" size="sm" className="mt-2" onClick={onRetryHosts}>Retry</Button>
      </Card>
    )
  }

  if (!host) {
    return (
      <Card className="p-6">
        <EmptyState icon={<ServerOff className="h-6 w-6 text-muted-foreground" aria-hidden />}
          title="Pick a host to see what fits."
          hint="A worker reports its GPU and its checkpoints when it claims a job." />
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <Glass className="rounded-xl p-3">
        {projects.isError ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-destructive">Projects did not load.</span>
            <Button variant="outline" size="sm" onClick={() => void projects.refetch()}>Retry</Button>
          </div>
        ) : projects.isLoading ? (
          <div className="h-9 w-full animate-pulse rounded bg-muted sm:w-72" aria-label="Loading projects" />
        ) : !list.length ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span>No projects yet.</span>
            <Link to={`/${ws}`} className="text-xs font-medium underline underline-offset-2">Create a project</Link>
          </div>
        ) : (
          <label className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
            <span className="text-xs font-medium text-muted-foreground">Project</span>
            <Select aria-label="Project" className="w-full sm:w-72" value={project}
              onChange={(e) => {
                setProject(e.target.value)
                rememberProject(ws, e.target.value)
              }}>
              <option value="">Choose a project</option>
              {list.map((item) => <option key={item.id} value={item.slug}>{item.name}</option>)}
            </Select>
            <span className="text-xs text-muted-foreground">Auto label opens on the dataset of this project.</span>
          </label>
        )}
      </Glass>

      {!anyReady && !models.isLoading && (
        <Card className="flex flex-wrap items-center justify-between gap-2 p-4">
          <p className="text-sm text-muted-foreground">{NO_MODEL}</p>
          <a href={SETUP_DOC} target="_blank" rel="noreferrer noopener"
            className="text-xs font-medium underline underline-offset-2">Read the setup notes</a>
        </Card>
      )}

      {models.isLoading ? <SkeletonCards /> : models.isError ? (
        <Card className="p-6">
          <p className="text-sm text-destructive">Segmentation did not load for this host.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => void models.refetch()}>Retry</Button>
        </Card>
      ) : !rows.length ? (
        <Card className="p-6">
          <EmptyState title="No segmentation model is listed for this deployment."
            hint="The catalogue is served with the API; a deployment without it has nothing to offer here." />
        </Card>
      ) : (
        <div role="list" aria-label="Segmentation models" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((row) => (
            <ModelCard key={row.id} row={row} ws={ws} project={project || null} />
          ))}
        </div>
      )}
    </div>
  )
}
