import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Cctv, Eye, MoreVertical, Play, Plus, Square, Trash2, TriangleAlert, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { RegistryItem, StreamItem, StreamStatus } from '@/lib/types'
import { Button, Card, Dropdown, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

/** Status is always shown as dot + words, never colour alone. */
export const streamStatusMeta: Record<StreamStatus, { label: string; dot: string; tone: string; pulse?: boolean }> = {
  live: { label: 'Live', dot: 'bg-success ring-2 ring-success/25', tone: 'bg-success/15 text-success', pulse: true },
  connecting: { label: 'Connecting', dot: 'bg-info', tone: 'bg-info/15 text-info', pulse: true },
  reconnecting: { label: 'Reconnecting', dot: 'bg-warning', tone: 'bg-warning/15 text-warning', pulse: true },
  error: { label: 'Error', dot: 'bg-destructive', tone: 'bg-destructive/15 text-destructive' },
  'paused (GPU busy)': { label: 'Paused (GPU busy)', dot: 'bg-info', tone: 'bg-info/15 text-info' },
  stopped: { label: 'Stopped', dot: 'bg-muted-foreground', tone: 'bg-secondary text-secondary-foreground' },
}

const metaOf = (status: StreamStatus) => streamStatusMeta[status] ?? streamStatusMeta.stopped

export const isStreamLive = (status: StreamStatus) => status !== 'stopped' && status !== 'error'

export function StreamStatusChip({ status, className }: { status: StreamStatus; className?: string }) {
  const meta = metaOf(status)
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium', meta.tone, className)}>
      <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', meta.dot, meta.pulse && 'animate-pulse')} aria-hidden />
      {meta.label}
    </span>
  )
}

const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1024 ** 2 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 ** 2).toFixed(1)} MB`)
const fmtInt = (n: number) => (Number.isFinite(n) ? n.toLocaleString() : '—')

/** Camera URLs often embed credentials; every project member can open this page, so never render them.
 *  Greedy through the last @ before the path: a raw @ inside the password must be masked too. */
export const displaySource = (source: string) =>
  source.replace(/^([a-z][a-z0-9+.-]*:\/\/)[^/\s]*@/i, '$1•••@')

/** Trained models run through their family adapter, so only ultralytics/tensorrt refs are accepted by the API. */
const isStreamModel = (m: RegistryItem) => m.family === 'ultralytics' || m.family === 'tensorrt'

function NewStreamDialog({ open, onClose, ws, project }: { open: boolean; onClose: () => void; ws: string; project: string }) {
  const qc = useQueryClient()
  const nav = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const registry = useQuery({ queryKey: ['registry', ws], queryFn: () => api.registry(ws), enabled: open })
  const [name, setName] = useState('')
  const [modelRef, setModelRef] = useState('')
  const [source, setSource] = useState('')
  const [fps, setFps] = useState(5)
  const [uploaded, setUploaded] = useState<{ name: string; bytes: number } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)

  const candidates = useMemo(() => (registry.data ?? []).filter(isStreamModel), [registry.data])

  useEffect(() => {
    if (!open) return
    setModelRef((cur) => (cur && candidates.some((m) => m.ref === cur && m.available)
      ? cur
      : candidates.find((m) => m.available)?.ref ?? ''))
  }, [open, candidates])

  const upload = async (file: File) => {
    setUploading(true)
    try {
      const r = await api.uploadStreamVideo(ws, project, file)
      setSource(r.source)
      setUploaded({ name: file.name, bytes: file.size })
      setName((n) => n || file.name.replace(/\.[^.]+$/, ''))
      toast.ok('Video uploaded')
    } catch (e) { toast.err(e as Error) } finally { setUploading(false) }
  }

  const create = async () => {
    if (!name.trim() || !source.trim() || !modelRef || busy) return
    setBusy(true)
    try {
      const created = await api.createStream(ws, project, {
        name: name.trim(), source: source.trim(), model_ref: modelRef,
        sample_fps: Math.min(30, Math.max(1, Number.isFinite(fps) ? fps : 5)),
      })
      await qc.invalidateQueries({ queryKey: ['streams', ws, project] })
      toast.ok('Stream created')
      setName(''); setSource(''); setUploaded(null); setFps(5)
      onClose()
      nav(`/${ws}/${project}/streams/${created.id}`)
    } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  const ready = !!name.trim() && !!source.trim() && candidates.some((m) => m.ref === modelRef && m.available)

  return (
    <Modal open={open} onClose={onClose} title="New stream">
      <div className="space-y-4">
        <Field label="Name" hint="Shown on the stream wall and in the event timeline.">
          <Input autoFocus placeholder="Gate 3 — entrance" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>

        <Field label="Model" hint="Only trained models and edge runtimes (Ultralytics, TensorRT) can process a stream.">
          <Select className="w-full" value={modelRef} onChange={(e) => setModelRef(e.target.value)}
            disabled={registry.isLoading || !candidates.length}>
            {registry.isLoading && <option value="">Loading models…</option>}
            {!registry.isLoading && !candidates.length && <option value="">No streaming model available</option>}
            {!registry.isLoading && !!candidates.length && !candidates.some((m) => m.available) && <option value="">No available streaming model</option>}
            {candidates.map((m) => (
              <option key={m.ref} value={m.ref} disabled={!m.available}>
                {m.name} — {m.ref}{m.kind === 'trained' ? ' · trained' : ''}{m.available ? '' : ` (${m.reason || 'unavailable'})`}
              </option>
            ))}
          </Select>
        </Field>
        {registry.isError && <p className="text-xs text-destructive" role="alert">Could not load the model registry. Train a model first.</p>}

        <Field label="Camera source" hint="RTSP or HTTP stream URL, or the uploaded video path. Nothing is opened until you start the stream.">
          <Input placeholder="rtsp://user:pass@192.168.1.20:554/stream1" value={source} onChange={(e) => setSource(e.target.value)} spellCheck={false} />
        </Field>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" disabled={uploading} onClick={() => fileRef.current?.click()}>
            {uploading ? <><Spinner /> Uploading…</> : <><Upload className="h-4 w-4" /> Upload demo video</>}
          </Button>
          <input ref={fileRef} type="file" accept="video/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.currentTarget.value = '' }} />
          {uploaded && <span className="min-w-0 truncate text-xs text-muted-foreground" title={uploaded.name}>{uploaded.name} · {fmtBytes(uploaded.bytes)}</span>}
        </div>

        <Field label="Sample rate (FPS)" hint="How many frames per second are analysed. 5 keeps CPU cost low for most cameras.">
          <Input type="number" min={1} max={30} step={1} value={fps} onChange={(e) => setFps(Number(e.target.value))} inputMode="numeric" />
        </Field>

        {!ready && <p className="text-xs text-muted-foreground">A name, a model and a source are required.</p>}

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button disabled={!ready || busy} onClick={create}>{busy ? <><Spinner /> Creating…</> : 'Create stream'}</Button>
        </div>
      </div>
    </Modal>
  )
}

function StreamCard({ stream, admin, busy, onStart, onStop, onDelete }: {
  stream: StreamItem; admin: boolean; busy: boolean
  onStart: () => void; onStop: () => void; onDelete: () => void
}) {
  const nav = useNavigate()
  const { ws = '', project = '' } = useParams()
  const detail = `/${ws}/${project}/streams/${stream.id}`
  const meta = metaOf(stream.status)
  return (
    <Card className="flex min-w-0 flex-col">
      <div className="flex min-w-0 flex-1 items-start gap-3 p-4">
        <span className={cn('mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full', meta.dot, meta.pulse && 'animate-pulse')} aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link to={detail} className="min-w-0 truncate text-sm font-semibold hover:underline">{stream.name}</Link>
            <span className="text-[11px] font-medium text-muted-foreground">{meta.label}</span>
          </div>
          <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{displaySource(stream.source)}</p>

          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] sm:grid-cols-3">
            <div className="col-span-2 min-w-0 sm:col-span-1">
              <dt className="text-muted-foreground">Model</dt>
              <dd className="truncate font-mono" title={stream.modelRef}>{stream.modelRef}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Capture</dt>
              <dd className="tabular-nums">{stream.fps.toFixed(1)} fps</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Sample</dt>
              <dd className="tabular-nums">{stream.sampleFps} fps</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Events</dt>
              <dd className="tabular-nums">{fmtInt(stream.events)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Zones</dt>
              <dd className="tabular-nums">{stream.zones.length}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Rules</dt>
              <dd className="tabular-nums">{stream.rules.length}</dd>
            </div>
          </dl>

          {stream.lastError && (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-destructive">
              <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="min-w-0 [overflow-wrap:anywhere]">{stream.lastError}</span>
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 border-t px-3 py-2">
        <Button variant="outline" size="sm" onClick={() => nav(detail)}><Eye className="h-3.5 w-3.5" /> Open</Button>
        {admin && (
          isStreamLive(stream.status)
            ? <Button variant="outline" size="sm" disabled={busy} onClick={onStop}>{busy ? <Spinner /> : <><Square className="h-3.5 w-3.5" /> Stop</>}</Button>
            : <Button variant="outline" size="sm" disabled={busy} onClick={onStart}>{busy ? <Spinner /> : <><Play className="h-3.5 w-3.5" /> Start</>}</Button>
        )}
        {admin && (
          <span className="ml-auto">
            <Dropdown align="right" trigger={
              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground" aria-label={`Actions for ${stream.name}`}>
                <MoreVertical className="h-4 w-4" />
              </Button>
            } items={[{ label: <><Trash2 className="h-3.5 w-3.5" /> Delete stream</>, onClick: onDelete, danger: true }]} />
          </span>
        )}
      </div>
    </Card>
  )
}

/** Dense NVR-style list for md+; phones keep the stacked cards above. */
function StreamTable({ streams, admin, busyId, onStart, onStop, onDelete }: {
  streams: StreamItem[]; admin: boolean; busyId: string | null
  onStart: (stream: StreamItem) => void; onStop: (stream: StreamItem) => void; onDelete: (stream: StreamItem) => void
}) {
  const { ws = '', project = '' } = useParams()
  const detail = (id: string) => `/${ws}/${project}/streams/${id}`
  return (
    <Card className="hidden overflow-hidden md:block">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <th scope="col" className="w-32 px-3 py-2 font-medium">Status</th>
              <th scope="col" className="px-3 py-2 font-medium">Stream</th>
              <th scope="col" className="px-3 py-2 font-medium">Model</th>
              <th scope="col" className="px-3 py-2 text-right font-medium" title="Capture fps / configured sample fps">Capture / sample</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Rules</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Events</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {streams.map((stream) => {
              const meta = metaOf(stream.status)
              const live = isStreamLive(stream.status)
              const busy = busyId === stream.id
              return (
                <tr key={stream.id} className="border-b last:border-0 hover:bg-muted/40">
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-2 text-xs">
                      <span className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot, meta.pulse && 'animate-pulse')} aria-hidden />
                      <span className={cn(stream.status === 'error' && 'text-destructive', stream.status === 'stopped' && 'text-muted-foreground')}>{meta.label}</span>
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Link to={detail(stream.id)} className="block max-w-[24ch] truncate font-medium hover:underline" title={stream.name}>{stream.name}</Link>
                    <span className="block max-w-[32ch] truncate font-mono text-[11px] text-muted-foreground" title={stream.source}>
                      {displaySource(stream.source)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className="block max-w-[22ch] truncate font-mono text-[11px] text-muted-foreground" title={stream.modelRef}>{stream.modelRef}</span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">
                    {stream.fps.toFixed(1)} <span className="text-muted-foreground">/ {stream.sampleFps}</span>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{stream.rules.length}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmtInt(stream.events)}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-end gap-0.5">
                      <Link to={detail(stream.id)}>
                        <Button variant="ghost" size="sm" className="h-7 px-2"><Eye className="h-3.5 w-3.5" /> Open</Button>
                      </Link>
                      {admin && (
                        <Button variant="ghost" size="sm" className="h-7 px-2" disabled={busy}
                          aria-label={`${live ? 'Stop' : 'Start'} ${stream.name}`}
                          onClick={() => (live ? onStop(stream) : onStart(stream))}>
                          {busy ? <Spinner /> : live ? <><Square className="h-3.5 w-3.5" /> Stop</> : <><Play className="h-3.5 w-3.5" /> Start</>}
                        </Button>
                      )}
                      {admin && (
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
                          aria-label={`Delete ${stream.name}`} disabled={busy} onClick={() => onDelete(stream)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

export default function Streams() {
  const { ws = '', project = '' } = useParams()
  const can = useApp((s) => s.can)
  const qc = useQueryClient()
  const admin = can('admin')
  const [newOpen, setNewOpen] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ['streams', ws, project],
    queryFn: () => api.streams(ws, project),
    enabled: !!ws && !!project,
    refetchInterval: 3000,
  })
  const streams = q.data ?? []
  const running = streams.filter((s) => isStreamLive(s.status)).length

  const refresh = () => qc.invalidateQueries({ queryKey: ['streams', ws, project] })

  const act = async (stream: StreamItem, action: 'start' | 'stop') => {
    setBusyId(stream.id)
    try {
      const updated = action === 'start' ? await api.startStream(ws, project, stream.id) : await api.stopStream(ws, project, stream.id)
      qc.setQueryData(['stream', ws, project, stream.id], updated)
      await refresh()
      toast.ok(action === 'start' ? `Started ${stream.name}` : `Stopped ${stream.name}`)
    } catch (e) { toast.err(e as Error) } finally { setBusyId(null) }
  }

  const remove = async (stream: StreamItem) => {
    if (!confirm(`Delete “${stream.name}”? Its captured events are removed too.`)) return
    setBusyId(stream.id)
    try {
      await api.deleteStream(ws, project, stream.id)
      await refresh()
      toast.ok(`Deleted ${stream.name}`)
    } catch (e) { toast.err(e as Error) } finally { setBusyId(null) }
  }

  return (
    <div className="anim-page">
      <PageHeader
        title="Streams"
        desc={streams.length
          ? `${streams.length} stream${streams.length === 1 ? '' : 's'} · ${running} live`
          : 'Connect a camera to a trained model. Events are captured as snapshots you can review.'}
        actions={admin && <Button onClick={() => setNewOpen(true)}><Plus className="h-4 w-4" /> New stream</Button>}
      />

      <div className="px-4 pb-10 sm:px-8">
        {q.isLoading ? (
          <div className="flex justify-center py-20"><Spinner /></div>
        ) : q.isError ? (
          <Card className="p-10">
            <EmptyState icon={<TriangleAlert className="h-7 w-7 text-destructive" />} title="Could not load streams"
              hint={(q.error as Error)?.message} action={<Button size="sm" onClick={() => q.refetch()}>Try again</Button>} />
          </Card>
        ) : !streams.length ? (
          <Card className="p-10">
            <EmptyState
              icon={<Cctv className="h-8 w-8 text-muted-foreground/60" />}
              title="No streams yet"
              hint={admin
                ? 'Point a camera at a trained model, or upload a demo video to try the rules without hardware.'
                : 'Ask a project admin to connect a camera. Events will appear here once it runs.'}
              action={admin ? <Button size="sm" onClick={() => setNewOpen(true)}><Plus className="h-4 w-4" /> Create your first stream</Button> : undefined}
            />
          </Card>
        ) : (
          <>
            <ul className="grid gap-3 md:hidden">
              {streams.map((stream) => (
                <li key={stream.id} className="min-w-0">
                  <StreamCard
                    stream={stream}
                    admin={admin}
                    busy={busyId === stream.id}
                    onStart={() => act(stream, 'start')}
                    onStop={() => act(stream, 'stop')}
                    onDelete={() => remove(stream)}
                  />
                </li>
              ))}
            </ul>
            <StreamTable
              streams={streams}
              admin={admin}
              busyId={busyId}
              onStart={(stream) => act(stream, 'start')}
              onStop={(stream) => act(stream, 'stop')}
              onDelete={remove}
            />
          </>
        )}
      </div>

      <NewStreamDialog open={newOpen} onClose={() => setNewOpen(false)} ws={ws} project={project} />
    </div>
  )
}
