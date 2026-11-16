import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, AlertTriangle, BrainCircuit, CheckCircle2, Plus, ScanSearch } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import { useFlag } from '@/lib/flags'
import { useProjectPermissions } from '@/lib/perms'
import type { AnomalyResult, AnomalyStation } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Spinner, Switch, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'
import { heatColor, hotCells } from './anomalyView'

const MIN_NORMAL_IMAGES = 5
const THUMBS = 24

const STATUS_TONE: Record<AnomalyStation['status'], string> = {
  untrained: 'bg-secondary text-secondary-foreground',
  queued: 'bg-info/15 text-info',
  training: 'bg-info/15 text-info',
  ready: 'bg-success/15 text-success',
  failed: 'bg-destructive/15 text-destructive',
}

const STATUS_LABEL: Record<AnomalyStation['status'], string> = {
  untrained: 'Not trained',
  queued: 'Queued',
  training: 'Training',
  ready: 'Ready',
  failed: 'Failed',
}

/** Threshold slider range. Scores are distances in units of the calibration p99, so 1 is the
 *  noisiest normal image and a glaring defect can sit two orders of magnitude higher. */
const MAX_THRESHOLD = 1000

function Heatmap({ result }: { result: AnomalyResult }) {
  const { grid, values } = result.heatmap
  const cells = useMemo(() => hotCells(values, result.threshold), [values, result.threshold])
  return (
    <div className="relative overflow-hidden rounded-lg border bg-scrim">
      <img src={fileUrl(result.image.url)} alt={result.image.name} className="block w-full" />
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        {cells.map((c) => (
          <span key={`${c.row}-${c.col}`} className="absolute"
            style={{
              left: `${(c.col / grid) * 100}%`, top: `${(c.row / grid) * 100}%`,
              width: `${100 / grid}%`, height: `${100 / grid}%`,
              backgroundColor: heatColor(c.value, result.threshold), opacity: c.opacity,
            }} />
        ))}
        {result.regions.map((r, i) => (
          <span key={i} className="absolute rounded-sm border-2 border-warning"
            style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%` }} />
        ))}
      </div>
    </div>
  )
}

function ResultPanel({ result }: { result: AnomalyResult }) {
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={result.is_anomaly ? 'bg-destructive/15 text-destructive' : 'bg-success/15 text-success'}>
          {result.is_anomaly
            ? <><AlertTriangle className="h-3 w-3" /> Anomaly</>
            : <><CheckCircle2 className="h-3 w-3" /> Normal</>}
        </Badge>
        <span className="text-sm text-muted-foreground">
          score <span className="font-mono text-foreground">{result.score.toFixed(2)}</span>
          {' '}/ threshold <span className="font-mono text-foreground">{result.threshold}</span>
        </span>
        <span className="text-sm text-muted-foreground">
          {result.regions.length} suspicious {result.regions.length === 1 ? 'region' : 'regions'}
        </span>
        <span className="ml-auto text-xs text-muted-foreground">backend: {result.backend}</span>
      </div>
      {result.vlm && (
        <p className="text-sm text-muted-foreground">
          {result.vlm.available
            ? `VLM zero-shot: ${result.vlm.anomaly ? 'anomaly' : 'normal'} — ${result.vlm.agrees ? 'agrees' : 'disagrees'}`
            : `VLM comparison unavailable: ${result.vlm.reason ?? 'not configured'}`}
        </p>
      )}
      <Heatmap result={result} />
    </div>
  )
}

export default function Anomaly() {
  const { project, ws } = useProject()
  const enabled = useFlag('task_29')
  const { can } = useProjectPermissions(ws, project.slug)
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string>('')
  const [name, setName] = useState('')
  const [newThreshold, setNewThreshold] = useState('1')
  // The station editor's value is a draft: until the user types, it follows the selected station,
  // so opening the page can never silently re-save one station's threshold onto another.
  const [thresholdDraft, setThresholdDraft] = useState<string | null>(null)
  const [imageId, setImageId] = useState('')
  const [compareVlm, setCompareVlm] = useState(false)
  const [result, setResult] = useState<AnomalyResult | null>(null)
  const [busy, setBusy] = useState(false)

  const stations = useQuery({
    queryKey: ['anomaly-stations', ws, project.slug],
    queryFn: () => api.anomalyStations(ws, project.slug),
    enabled,
    refetchInterval: (q) => (q.state.data ?? []).some((s) => s.status === 'queued' || s.status === 'training')
      ? 2000 : false,
  })
  const images = useQuery({
    queryKey: ['anomaly-images', ws, project.slug],
    queryFn: () => api.images(ws, project.slug, { limit: THUMBS, sort: 'newest' }),
    enabled,
  })
  const normal = useQuery({
    queryKey: ['anomaly-normal-count', ws, project.slug],
    queryFn: () => api.images(ws, project.slug, { annotated: 'no', limit: 1 }),
    enabled,
  })

  const rows = stations.data ?? []
  const station = rows.find((s) => s.id === selected) ?? rows[0]
  const list = images.data?.items ?? []
  const normalCount = normal.data?.total ?? 0
  const trainable = can('project.train')
  const threshold = thresholdDraft ?? String(station?.threshold ?? 1)
  const newThresholdValue = Number(newThreshold)
  const validNewThreshold = Number.isFinite(newThresholdValue) && newThresholdValue >= 0
    && newThresholdValue <= MAX_THRESHOLD
  const thresholdValue = Number(threshold)
  const validThreshold = Number.isFinite(thresholdValue) && thresholdValue >= 0 && thresholdValue <= MAX_THRESHOLD

  const refresh = () => qc.invalidateQueries({ queryKey: ['anomaly-stations', ws, project.slug] })
  const act = async (fn: () => Promise<unknown>, onDone?: () => void) => {
    setBusy(true)
    try { await fn(); onDone?.(); refresh() } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  if (!enabled) {
    return <EmptyState title="Anomaly detection is not enabled" hint="An administrator can turn it on for this workspace." />
  }
  if (stations.isLoading) return <div className="flex justify-center py-16"><Spinner /></div>
  if (stations.isError) {
    return (
      <EmptyState title="Could not load the stations" hint={(stations.error as Error)?.message}
        action={<Button size="sm" onClick={() => stations.refetch()}>Try again</Button>} />
    )
  }

  const pickStation = (s: AnomalyStation) => { setSelected(s.id); setThresholdDraft(null); setResult(null) }
  const create = () => act(
    () => api.createAnomalyStation(ws, project.slug, { name: name.trim(), threshold: newThresholdValue }),
    () => setName(''),
  )
  const saveThreshold = () => {
    if (!station || !validThreshold) return
    return act(
      () => api.updateAnomalyStation(ws, project.slug, station.id, { threshold: thresholdValue }),
      () => setThresholdDraft(null),
    )
  }
  const train = () => {
    if (!station) return
    return act(async () => {
      const out = await api.trainAnomalyStation(ws, project.slug, station.id)
      setSelected(out.station.id)
      setThresholdDraft(null)
      toast.ok('Training queued — the station updates when it finishes')
    })
  }
  const predict = () => {
    if (!station || !imageId) return
    return act(async () => setResult(await api.predictAnomaly(ws, project.slug, station.id,
      { image_id: imageId, compare_vlm: compareVlm })))
  }

  return (
    <div className="anim-page max-w-5xl">
      <PageHeader title="Anomaly Detection"
        desc="Train a station on good images only. Every image is scored against that station's normal patch bank; the heatmap shows where it deviates." />
      <div className="grid gap-4 px-8 pb-10 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Stations</h2>
            {rows.length ? (
              <ul className="space-y-1.5">
                {rows.map((s) => (
                  <li key={s.id}>
                    <button type="button" onClick={() => pickStation(s)}
                      className={cn('w-full cursor-pointer rounded-md border px-2.5 py-2 text-left transition-colors',
                        station?.id === s.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
                      <span className="flex items-center justify-between gap-2 text-sm font-medium">
                        <span className="truncate">{s.name}</span>
                        <Badge className={STATUS_TONE[s.status]}>{STATUS_LABEL[s.status]}</Badge>
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">threshold {s.threshold}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">No stations yet — create one per camera or line.</p>}
          </Card>

          {trainable && (
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold">New station</h2>
              <div className="space-y-3">
                <Field label="Name"><Input placeholder="Line A — solder" value={name} onChange={(e) => setName(e.target.value)} /></Field>
                <Field label="Threshold" hint="1.0 flags anything noisier than the normal images.">
                  <Input type="number" min={0} max={MAX_THRESHOLD} step="0.1" value={newThreshold}
                    onChange={(e) => setNewThreshold(e.target.value)} />
                </Field>
                <Button size="sm" disabled={!name.trim() || !validNewThreshold || busy} onClick={create}>
                  <Plus className="h-4 w-4" /> Create station
                </Button>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          {!station ? (
            <Card className="p-6">
              <EmptyState icon={<Activity className="h-8 w-8 text-muted-foreground" />}
                title="Create a station to start" hint="Each station keeps its own normal patch bank and threshold." />
            </Card>
          ) : (
            <>
              <Card className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">{station.name}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {station.status === 'ready'
                        ? `${station.metrics.normal_images ?? 0} good images · ${station.metrics.patches ?? 0} patches · calibration p99 ${station.metrics.train_p99 ?? '—'} · ${station.metrics.backend ?? 'colour/layout'}`
                        : station.status === 'failed' ? station.error || 'Training failed'
                        : station.status === 'untrained' ? 'Train on normal images to build this station.'
                        : 'Training — this page refreshes automatically.'}
                    </p>
                  </div>
                  <Badge className={STATUS_TONE[station.status]}>{STATUS_LABEL[station.status]}</Badge>
                </div>

                <div className="mt-4 flex flex-wrap items-end gap-3">
                  <Field label="Threshold" hint={`Normal images available: ${normalCount}`}>
                    <Input type="number" min={0} max={MAX_THRESHOLD} step="0.1" className="w-28" value={threshold}
                      onChange={(e) => setThresholdDraft(e.target.value)} />
                  </Field>
                  <Button size="sm" variant="outline" disabled={!trainable || !validThreshold || busy} onClick={saveThreshold}>
                    Save threshold
                  </Button>
                  {trainable && (
                    <Button size="sm" disabled={busy || station.status === 'queued' || station.status === 'training'
                      || normalCount < MIN_NORMAL_IMAGES} onClick={train}>
                      <BrainCircuit className="h-4 w-4" />
                      {station.status === 'ready' ? 'Retrain on good images' : 'Train on good images'}
                    </Button>
                  )}
                  {trainable && normalCount < MIN_NORMAL_IMAGES && (
                    <p className="text-xs text-muted-foreground">At least {MIN_NORMAL_IMAGES} unannotated images are needed.</p>
                  )}
                </div>
              </Card>

              <Card className="p-4">
                <h2 className="mb-1 text-sm font-semibold">Check an image</h2>
                <p className="mb-3 text-sm text-muted-foreground">Score a project image against this station and see where it deviates.</p>
                {images.isError ? (
                  <p className="text-sm text-destructive">Could not load the project images.</p>
                ) : list.length ? (
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {list.map((im) => (
                      <button key={im.id} type="button" onClick={() => { setImageId(im.id); setResult(null) }}
                        aria-pressed={imageId === im.id} title={im.name}
                        className={cn('shrink-0 cursor-pointer overflow-hidden rounded-md border-2 transition-colors',
                          imageId === im.id ? 'border-primary' : 'border-transparent hover:border-input')}>
                        <img src={fileUrl(im.thumbnail)} alt={im.name} className="h-16 w-16 object-cover" />
                      </button>
                    ))}
                  </div>
                ) : <p className="text-sm text-muted-foreground">Upload images to this project first.</p>}

                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <Button size="sm" disabled={!imageId || busy || station.status !== 'ready'} onClick={predict}>
                    <ScanSearch className="h-4 w-4" /> Run check
                  </Button>
                  <span className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Switch checked={compareVlm} onChange={setCompareVlm} label="Compare with VLM" />
                    Compare with VLM
                  </span>
                  {station.status !== 'ready' && <span className="text-xs text-muted-foreground">Train the station first.</span>}
                </div>
                {result && <ResultPanel result={result} />}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
