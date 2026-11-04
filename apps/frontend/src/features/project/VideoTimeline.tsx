import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, ExternalLink, Film, Flag, UploadCloud } from 'lucide-react'
import { api, fileUrl, get, put, upload } from '@/lib/api'
import type { Annotation, Job, LabelClass, Shape, Skeleton, VideoFrame, VideoItem } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Progress, Select, Spinner, StatusPill, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

const PAGE = 120
const FALLBACK_COLOR = '#8b5cf6'
const ACTIVE = new Set<VideoItem['status']>(['queued', 'extracting'])
const STATUS_DOT: Record<VideoFrame['status'], string> = {
  unassigned: 'bg-muted-foreground', annotating: 'bg-warning', review: 'bg-info', done: 'bg-success',
}
const SHAPE_LABEL: Record<Shape['kind'], string> = { bbox: 'Box', polygon: 'Polygon', obb: 'Oriented box', keypoints: 'Keypoints', class: 'Class' }

const fmtDur = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`

/** Keypoints arrive as flat [x, y, visibility, …] triples. */
function joints(points: number[]) {
  const out: { x: number; y: number; v: number }[] = []
  for (let i = 0; i + 2 < points.length; i += 3) out.push({ x: points[i], y: points[i + 1], v: points[i + 2] })
  return out
}

function obbPoints(s: Extract<Shape, { kind: 'obb' }>, width: number, height: number) {
  const cx = s.cx * width, cy = s.cy * height, hw = (s.w * width) / 2, hh = (s.h * height) / 2
  const cos = Math.cos(s.angle), sin = Math.sin(s.angle)
  return [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]
    .map(([x, y]) => `${cx + x * cos - y * sin},${cy + x * sin + y * cos}`).join(' ')
}

/** Display-only geometry: the annotation list is the accessible equivalent. */
function ShapeOverlay({ frame, width, height, colorOf, skeletonOf }: {
  frame: VideoFrame; width: number; height: number
  colorOf: (classId: string) => string; skeletonOf: (classId: string) => Skeleton | null
}) {
  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {frame.annotations.map((a) => {
        const s = a.shape, color = colorOf(a.classId)
        if (s.kind === 'bbox') {
          return <rect key={a.id} x={s.x * width} y={s.y * height} width={s.w * width} height={s.h * height} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
        }
        if (s.kind === 'polygon') {
          return <polygon key={a.id} points={s.points.map((v, i) => v * (i % 2 ? height : width)).join(' ')} fill={color} fillOpacity={0.16} stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
        }
        if (s.kind === 'obb') {
          return <polygon key={a.id} points={obbPoints(s, width, height)} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
        }
        if (s.kind === 'keypoints') {
          const pts = joints(s.points)
          const sk = skeletonOf(a.classId)
          return (
            <g key={a.id}>
              {sk?.edges.map(([i, j], n) => pts[i] && pts[j] && pts[i].v > 0 && pts[j].v > 0 && (
                <line key={n} x1={pts[i].x * width} y1={pts[i].y * height} x2={pts[j].x * width} y2={pts[j].y * height} stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
              ))}
              {pts.map((p, n) => p.v > 0 && (
                <circle key={n} cx={p.x * width} cy={p.y * height} r={Math.max(2.5, Math.min(width, height) * 0.007)} fill={color} stroke="var(--background)" strokeWidth={1} />
              ))}
            </g>
          )
        }
        return null
      })}
    </svg>
  )
}

export default function VideoTimeline() {
  const { project, ws } = useProject()
  const base = api.P(ws, project.slug)
  const qc = useQueryClient()
  const videos = useQuery({
    queryKey: ['videos', ws, project.slug],
    queryFn: () => api.videos(ws, project.slug),
    refetchInterval: (q) => ((q.state.data ?? []).some((v) => ACTIVE.has(v.status)) ? 2000 : false),
  })
  const classes = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug) })
  const clsById = useMemo<Record<string, LabelClass>>(
    () => Object.fromEntries((classes.data ?? []).map((c): [string, LabelClass] => [c.id, c])), [classes.data])
  const colorOf = (classId: string) => clsById[classId]?.color || FALLBACK_COLOR
  const skeletonOf = (classId: string) => clsById[classId]?.skeleton ?? null

  const [videoId, setVideoId] = useState('')
  useEffect(() => {
    if (!videos.data?.length) return
    if (videoId && videos.data.some((v) => v.id === videoId)) return
    setVideoId((videos.data.find((v) => v.status === 'ready') ?? videos.data[0]).id)
  }, [videos.data, videoId])
  const selected = videos.data?.find((v) => v.id === videoId)

  const timeline = useInfiniteQuery({
    queryKey: ['video-timeline', ws, project.slug, videoId],
    enabled: !!videoId && selected?.status === 'ready',
    queryFn: ({ pageParam }) => api.videoTimeline(ws, project.slug, videoId, pageParam, PAGE),
    initialPageParam: 0,
    getNextPageParam: (last, all) => {
      const n = all.reduce((s, p) => s + p.frames.length, 0)
      return n < last.total ? n : undefined
    },
  })
  const frames = useMemo(() => timeline.data?.pages.flatMap((p) => p.frames) ?? [], [timeline.data])
  const total = timeline.data?.pages[0]?.total ?? selected?.frameCount ?? 0

  const [sel, setSel] = useState(0)
  const stripRef = useRef<HTMLDivElement>(null)
  useEffect(() => { setSel(0) }, [videoId])
  useEffect(() => { if (sel > frames.length - 1) setSel(Math.max(0, frames.length - 1)) }, [frames.length, sel])
  // A refetch can briefly return fewer pages than the current index points at.
  const activeSel = frames.length ? Math.min(sel, frames.length - 1) : 0
  const frame = frames[activeSel]

  const selectFrame = (i: number, focus = false) => {
    if (!frames.length) return
    const n = Math.max(0, Math.min(frames.length - 1, i))
    setSel(n)
    if (focus) requestAnimationFrame(() => {
      const el = stripRef.current?.querySelector<HTMLButtonElement>(`[data-frame="${n}"]`)
      el?.focus()
      el?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    })
  }
  const onStripKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); selectFrame(activeSel - 1, true) }
    else if (e.key === 'ArrowRight') { e.preventDefault(); selectFrame(activeSel + 1, true) }
    else if (e.key === 'Home') { e.preventDefault(); selectFrame(0, true) }
    else if (e.key === 'End') { e.preventDefault(); selectFrame(frames.length - 1, true) }
  }

  // --- upload -----------------------------------------------------------------
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [batch, setBatch] = useState('')
  const [mode, setMode] = useState<'every' | 'fps' | 'scene'>('every')
  const [num, setNum] = useState({ fps: '1', every: '1', scene: '0.35' })
  const [prog, setProg] = useState(0)
  const [uploading, setUploading] = useState(false)
  const numOk = mode === 'fps' ? Number(num.fps) > 0 : mode === 'every' ? Number(num.every) > 0 : Number(num.scene) >= 0 && Number(num.scene) <= 1
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['videos', ws, project.slug] })
    if (videoId) qc.invalidateQueries({ queryKey: ['video-timeline', ws, project.slug, videoId] })
  }

  const submit = async () => {
    if (!file) return toast.err('Choose a video file first.')
    if (!numOk) return toast.err('Check the extraction setting.')
    const form = new FormData()
    form.append('file', file)
    form.append('batch_name', batch.trim() || file.name.replace(/\.[^.]+$/, ''))
    form.append('mode', mode)
    if (mode === 'fps') form.append('target_fps', num.fps)
    else if (mode === 'every') form.append('every_s', num.every)
    else form.append('scene_threshold', num.scene)
    setUploading(true)
    setProg(0)
    try {
      const r = await upload<{ video: VideoItem; job: Job }>(`${base}/videos`, form, setProg)
      toast.ok(`Uploaded ${r.video.name} — extracting frames`)
      qc.setQueryData<VideoItem[]>(['videos', ws, project.slug], (old) => [r.video, ...(old ?? []).filter((v) => v.id !== r.video.id)])
      setVideoId(r.video.id)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      invalidate()
    } catch (e) { toast.err(e as Error) } finally { setUploading(false) }
  }

  // --- keyframes, marks, tracking ---------------------------------------------
  const [savingKf, setSavingKf] = useState(false)
  const [interpolating, setInterpolating] = useState(false)
  const [tracking, setTracking] = useState<string | null>(null)
  const [mark, setMark] = useState<{ start?: string; end?: string }>({})
  useEffect(() => { setMark({}) }, [videoId])

  const markKeyframe = () => {
    if (!frame) return
    setSavingKf(true)
    put(`/images/${frame.id}/annotations`, { annotations: frame.annotations.map((a) => ({ ...a, keyframe: true })) })
      .then(() => { toast.ok('Keyframe marked'); invalidate() })
      .catch((e) => toast.err(e as Error))
      .finally(() => setSavingKf(false))
  }
  const startIdx = mark.start ? frames.findIndex((f) => f.id === mark.start) : -1
  const endIdx = mark.end ? frames.findIndex((f) => f.id === mark.end) : -1
  const canInterpolate = startIdx >= 0 && endIdx >= 0 && startIdx < endIdx

  const interpolate = () => {
    if (!videoId || !mark.start || !mark.end) return
    setInterpolating(true)
    api.interpolate(ws, project.slug, videoId, mark.start, mark.end)
      .then((r) => {
        toast.ok(r.annotations ? `${r.frames} frames · ${r.annotations} annotations`
          : 'Nothing written — those frames already hold human edits')
        setMark({})
        invalidate()
      })
      .catch((e) => toast.err(e as Error))
      .finally(() => setInterpolating(false))
  }

  const track = async (a: Annotation) => {
    if (!frame || !videoId) return
    setTracking(a.id)
    try {
      const job = await api.trackForward(frame.id, { annotation_id: a.id, frames: 30 })
      toast.ok('Tracking 30 frames…')
      // Track-forward is a job: poll it so the timeline refreshes when the boxes land.
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500))
        const j = await get<Job>(`/ws/${ws}/projects/${project.slug}/jobs/${job.id}`)
        if (j.status === 'done') {
          toast.ok(`Tracked ${Number(j.result?.tracked ?? 0)} frames`)
          invalidate()
          break
        }
        if (j.status === 'failed' || j.status === 'cancelled') {
          toast.err(j.error || 'Tracking failed')
          invalidate()
          break
        }
      }
    } catch (e) { toast.err(e as Error) } finally { setTracking(null) }
  }

  const active = (videos.data ?? []).filter((v) => ACTIVE.has(v.status))
  const framesSoFar = active.reduce((s, v) => s + (v.frameCount || 0), 0)

  return (
    <div className="anim-page max-w-6xl">
      <PageHeader title="Video" desc="Extract frames from a video, then annotate, keyframe and track objects across the timeline." />
      <div className="space-y-4 px-8 pb-10">
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <Film className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            <h2 className="font-semibold">Upload a video</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Video file" hint="MP4, MOV, AVI, MKV or WebM">
              <input ref={fileRef} type="file" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full cursor-pointer rounded-md border border-input bg-card p-1.5 text-xs file:mr-2 file:cursor-pointer file:rounded file:border-0 file:bg-secondary file:px-2 file:py-1 file:text-xs file:text-secondary-foreground" />
            </Field>
            <Field label="Batch name">
              <Input value={batch} onChange={(e) => setBatch(e.target.value)} placeholder="e.g. dashcam-day" />
            </Field>
            <Field label="Frame extraction">
              <Select className="w-full" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
                <option value="every">Every N seconds</option>
                <option value="fps">Target FPS</option>
                <option value="scene">Scene change</option>
              </Select>
            </Field>
            <Field label={mode === 'fps' ? 'Frames per second' : mode === 'every' ? 'Seconds per frame' : 'Scene threshold'}
              hint={mode === 'scene' ? 'Lower is more sensitive · default 0.35' : mode === 'fps' ? 'Default 1' : 'Default 1'}>
              {mode === 'scene' ? (
                <span className="flex h-9 items-center gap-2">
                  <input type="range" min={0.05} max={0.95} step={0.05} value={num.scene} aria-label="Scene change threshold"
                    onChange={(e) => setNum({ ...num, scene: e.target.value })} className="w-full accent-primary" />
                  <span className="w-10 text-right text-sm tabular-nums">{num.scene}</span>
                </span>
              ) : (
                <Input type="number" min="0.01" step="0.01" inputMode="decimal" aria-invalid={!numOk}
                  value={mode === 'fps' ? num.fps : num.every}
                  onChange={(e) => setNum(mode === 'fps' ? { ...num, fps: e.target.value } : { ...num, every: e.target.value })} />
              )}
            </Field>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button onClick={submit} disabled={uploading || !file || !numOk}>
              <UploadCloud className="h-4 w-4" /> Upload & extract
            </Button>
            {uploading && (
              <span className="flex min-w-40 flex-1 items-center gap-2 sm:max-w-xs">
                <Progress value={prog * 100} />
                <span className="text-xs tabular-nums text-muted-foreground">{Math.round(prog * 100)}%</span>
              </span>
            )}
            <span className="text-xs text-muted-foreground">Frames land in a new batch, ready to annotate.</span>
          </div>
        </Card>

        {videos.isError && (
          <Card className="p-4">
            <p role="alert" className="text-sm text-destructive">Couldn't load videos: {(videos.error as Error).message}</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={() => videos.refetch()}>Retry</Button>
          </Card>
        )}
        {videos.isLoading && (
          <Card className="space-y-2 p-4" aria-label="Loading videos">
            <div className="skeleton h-5 w-40" />
            <div className="skeleton h-14 w-full" />
            <div className="skeleton h-14 w-full" />
          </Card>
        )}
        {videos.isSuccess && !videos.data.length && (
          <EmptyState title="No videos yet." hint="Upload an MP4, MOV, AVI, MKV or WebM file above — frames are extracted on the worker."
            action={<Button size="sm" variant="outline" onClick={() => fileRef.current?.click()}>Choose a file</Button>} />
        )}

        {active.length > 0 && (
          <div role="status" className="flex flex-wrap items-center gap-2 rounded-lg border bg-accent/40 px-3 py-2 text-sm">
            <Spinner />
            <span>Extracting frames… {framesSoFar} frames</span>
            <span className="ml-auto text-xs text-muted-foreground">{active.length} video{active.length === 1 ? '' : 's'} in progress</span>
          </div>
        )}

        {(videos.data?.length ?? 0) > 0 && (
          <Card className="p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="flex-1 font-semibold">Videos</h2>
              <span className="text-xs text-muted-foreground">{videos.data?.length} total</span>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {videos.data?.map((v) => (
                <button key={v.id} type="button" onClick={() => setVideoId(v.id)} aria-pressed={v.id === videoId}
                  className={cn('w-full cursor-pointer rounded-lg border p-3 text-left transition-colors hover:bg-accent/40',
                    v.id === videoId ? 'border-primary bg-accent/30' : 'bg-card')}>
                  <span className="flex min-w-0 flex-wrap items-center gap-2">
                    <Film className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate font-medium">{v.name}</span>
                    <StatusPill status={v.status} />
                  </span>
                  <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    <span>{v.width}×{v.height}</span>
                    <span>{v.fps.toFixed(2)} fps</span>
                    <span>{v.frameCount} frames</span>
                    <span>{fmtDur(v.duration)}</span>
                  </span>
                  {v.status === 'failed' && <span className="mt-1 block text-xs text-destructive">{v.error || 'Frame extraction failed — re-upload the file.'}</span>}
                </button>
              ))}
            </div>
          </Card>
        )}

        {selected && !ACTIVE.has(selected.status) && selected.status !== 'ready' && (
          <EmptyState title="Extraction failed" hint={selected.error || 'Re-upload the file to try again.'} />
        )}
        {selected && ACTIVE.has(selected.status) && (
          <EmptyState title="Frames are still being extracted" hint="This page refreshes every 2 seconds. The timeline appears as soon as the video is ready." />
        )}

        {selected?.status === 'ready' && (
          <>
            {timeline.isError && (
              <Card className="p-4">
                <p role="alert" className="text-sm text-destructive">Couldn't load the timeline: {(timeline.error as Error).message}</p>
                <Button size="sm" variant="outline" className="mt-2" onClick={() => timeline.refetch()}>Retry</Button>
              </Card>
            )}
            {timeline.isLoading && (
              <Card className="space-y-2 p-4" aria-label="Loading timeline">
                <div className="skeleton h-5 w-32" />
                <div className="skeleton h-24 w-full" />
              </Card>
            )}
            {timeline.isSuccess && !frames.length && (
              <EmptyState title="No frames yet" hint="Frame extraction finished without producing frames for this video." />
            )}
            {frames.length > 0 && (
              <>
                <Card className="p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <h2 className="font-semibold">Timeline</h2>
                    <span className="text-xs text-muted-foreground">{frames.length} of {total} frames loaded</span>
                    <span className="ml-auto hidden items-center gap-3 text-xs text-muted-foreground sm:flex">
                      <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-warning" aria-hidden="true" /> keyframe</span>
                      <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" /> done</span>
                    </span>
                  </div>
                  <div ref={stripRef} role="group" aria-label="Video frames" onKeyDown={onStripKey} className="flex snap-x gap-2 overflow-x-auto pb-2">
                    {frames.map((f, i) => {
                      const kf = f.annotations.some((a) => a.keyframe)
                      return (
                        <button key={f.id} type="button" data-frame={i} aria-pressed={i === activeSel}
                          aria-label={`Frame ${f.frameIndex + 1} at ${f.time.toFixed(2)} s, ${f.status}${kf ? ', keyframe' : ''}`}
                          onClick={() => selectFrame(i)}
                          className={cn('w-28 shrink-0 snap-start cursor-pointer overflow-hidden rounded-md border-2 bg-card text-left transition-colors',
                            i === activeSel ? 'border-primary ring-2 ring-primary/40' : 'border-transparent hover:border-input')}>
                          <span className="relative block">
                            <img src={fileUrl(f.thumbnail || f.url)} alt="" loading="lazy" className="block h-16 w-full object-cover" />
                            <span aria-hidden="true" className={cn('absolute left-1 top-1 h-2.5 w-2.5 rounded-full border border-card', STATUS_DOT[f.status] ?? 'bg-muted-foreground')} />
                            {kf && <span aria-hidden="true" className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full border border-card bg-warning" />}
                          </span>
                          <span className="flex items-center justify-between px-1.5 py-1 text-[10px] tabular-nums text-muted-foreground">
                            <span>#{f.frameIndex + 1}</span><span>{f.time.toFixed(2)}s</span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Arrow keys move between frames; Home and End jump to the first and last loaded frame.</p>
                  {timeline.hasNextPage && (
                    <div className="mt-2 flex justify-center">
                      <Button size="sm" variant="outline" onClick={() => timeline.fetchNextPage()} disabled={timeline.isFetchingNextPage}>
                        {timeline.isFetchingNextPage && <Spinner />} Load more frames
                      </Button>
                    </div>
                  )}
                </Card>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
                  <Card className="p-3">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <h2 className="font-semibold">Frame {frame.frameIndex + 1}</h2>
                      <span className="text-xs tabular-nums text-muted-foreground">{frame.time.toFixed(2)} s</span>
                      <div className="ml-auto flex flex-wrap gap-1.5">
                        <Button size="sm" variant="outline" onClick={() => selectFrame(activeSel - 1, true)} disabled={activeSel <= 0} aria-label="Previous frame"><ChevronLeft className="h-4 w-4" /> Prev</Button>
                        <Button size="sm" variant="outline" onClick={() => selectFrame(activeSel + 1, true)} disabled={activeSel >= frames.length - 1} aria-label="Next frame">Next <ChevronRight className="h-4 w-4" /></Button>
                      </div>
                    </div>
                    <div className="relative mx-auto w-full overflow-hidden rounded-md bg-muted">
                      <img src={fileUrl(frame.url)} alt={`Frame ${frame.frameIndex + 1} at ${frame.time.toFixed(2)} seconds`} className="block h-auto w-full" />
                      <ShapeOverlay frame={frame} width={selected.width || 16} height={selected.height || 9} colorOf={colorOf} skeletonOf={skeletonOf} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Link to={`/${ws}/${project.slug}/images/${frame.id}`}
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-input bg-card px-3 text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground">
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Open in editor
                      </Link>
                      <span className="text-xs text-muted-foreground">{frame.annotations.length} annotation{frame.annotations.length === 1 ? '' : 's'} on this frame</span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
                      <Button size="sm" variant="outline" onClick={markKeyframe} disabled={savingKf}>
                        <Flag className="h-3.5 w-3.5" /> Mark keyframe
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setMark((m) => ({ ...m, start: frame.id }))}>Set start</Button>
                      <Button size="sm" variant="outline" onClick={() => setMark((m) => ({ ...m, end: frame.id }))}>Set end</Button>
                      {startIdx >= 0 && <Badge className="bg-warning/15 text-warning">Start · frame {frames[startIdx].frameIndex + 1}</Badge>}
                      {endIdx >= 0 && <Badge className="bg-info/15 text-info">End · frame {frames[endIdx].frameIndex + 1}</Badge>}
                      <Button size="sm" onClick={interpolate} disabled={!canInterpolate || interpolating}>
                        {interpolating && <Spinner />} Interpolate
                      </Button>
                      <p className="w-full text-xs text-muted-foreground">Interpolation is linear between the start and end keyframes.</p>
                    </div>
                  </Card>

                  <Card className="p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <h2 className="font-semibold">Annotations</h2>
                      <span className="text-xs tabular-nums text-muted-foreground">{frame.annotations.length}</span>
                    </div>
                    {frame.annotations.length ? (
                      <ul className="divide-y">
                        {frame.annotations.map((a) => (
                          <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colorOf(a.classId) }} aria-hidden="true" />
                            <span className="font-medium">{clsById[a.classId]?.name ?? 'Unknown class'}</span>
                            <Badge>{SHAPE_LABEL[a.shape.kind]}</Badge>
                            <Badge>{a.source ?? 'human'}</Badge>
                            {a.keyframe && <Badge className="bg-success/15 text-success">Keyframe</Badge>}
                            {a.trackId && <span className="font-mono text-[10px] text-muted-foreground" title={a.trackId}>Track {a.trackId.slice(0, 8)}</span>}
                            <Button size="sm" variant="outline" className="ml-auto" disabled={!videoId || tracking === a.id}
                              aria-label={`Track ${clsById[a.classId]?.name ?? 'annotation'} forward 30 frames`} onClick={() => track(a)}>
                              {tracking === a.id && <Spinner />} Track 30 →
                            </Button>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-sm text-muted-foreground">No annotations on this frame yet.</p>}
                  </Card>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
