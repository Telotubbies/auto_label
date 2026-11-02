import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Image as KImage, Label, Layer, Line, Rect, Stage, Tag, Text } from 'react-konva'
import { Camera, ImageUp, Play, Sparkles, TriangleAlert } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { PlaygroundPrediction, PlaygroundResult, PlaygroundSample, RegistryItem } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Spinner, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { RuntimeStates } from './RuntimeStates'
import { SampleStrip } from './SampleStrip'
import { useCamera } from './useCamera'

const MAX_MODELS = 3
const COLORS = ['#8b5cf6', '#22c55e', '#3b82f6', '#f97316', '#ec4899', '#eab308', '#14b8a6', '#ef4444']

/** Konva needs a decoded HTML image, not an <img> element. */
function useHtmlImage(src: string) {
  const [img, setImg] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    if (!src) { setImg(null); return }
    const i = new window.Image()
    i.onload = () => setImg(i)
    i.src = src
    return () => { i.onload = null }
  }, [src])
  return img
}

const latencyTone = (ms: number) =>
  ms < 300 ? 'bg-green-100 text-green-800' : ms < 1000 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'

/** Overlay one model's boxes on the uploaded image. Solid surface, no glass. */
function PredictionCanvas({ pred, img, threshold }: { pred: PlaygroundPrediction; img: HTMLImageElement | null; threshold: number }) {
  const [box, setBox] = useState<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    if (!box) return
    const ro = new ResizeObserver(() => setWidth(box.clientWidth))
    ro.observe(box)
    setWidth(box.clientWidth)
    return () => ro.disconnect()
  }, [box])

  const shown = pred.top ? [] : pred.predictions.filter((p) => p.confidence >= threshold)
  const k = width / pred.image.width
  const height = Math.round(pred.image.height * k)
  return (
    <div ref={setBox} className="relative w-full bg-muted">
      {width > 0 && (
        <Stage width={width} height={height} listening={false}>
          <Layer listening={false}>{img && <KImage image={img} width={width} height={height} />}</Layer>
          <Layer listening={false}>
            {shown.map((p, i) => {
              const color = COLORS[p.class_id % COLORS.length]
              return p.points
                ? <Line key={i} points={p.points.flatMap((q) => [q.x * k, q.y * k])} closed fill={color + '40'} stroke={color} strokeWidth={2} />
                : <Rect key={i} x={(p.x - p.width / 2) * k} y={(p.y - p.height / 2) * k}
                    width={p.width * k} height={p.height * k} stroke={color} strokeWidth={2} />
            })}
            {shown.map((p, i) => {
              const color = COLORS[p.class_id % COLORS.length]
              const x = p.points ? Math.min(...p.points.map((q) => q.x)) * k : (p.x - p.width / 2) * k
              const y = p.points ? Math.min(...p.points.map((q) => q.y)) * k : (p.y - p.height / 2) * k
              return (
                <Label key={i} x={Math.max(0, x)} y={Math.max(0, y - 16)}>
                  <Tag fill={color} cornerRadius={3} />
                  <Text text={`${p.class} ${Math.round(p.confidence * 100)}%`} fill="#fff" fontSize={11} padding={3} />
                </Label>
              )
            })}
          </Layer>
        </Stage>
      )}
    </div>
  )
}

function ResultCard({ result, img, threshold, name }: {
  result: PlaygroundResult; img: HTMLImageElement | null; threshold: number; name: string
}) {
  const pred = result.prediction
  const shown = pred?.predictions.filter((p) => p.confidence >= threshold) ?? []
  const top = pred?.top ? [...pred.predictions].sort((a, b) => b.confidence - a.confidence).slice(0, 3) : []
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={result.ref}>{name}</span>
        <Badge className={latencyTone(result.latency_ms)}>{Math.round(result.latency_ms)} ms</Badge>
      </div>
      {result.error ? (
        <div className="flex min-h-44 flex-col items-center justify-center gap-2 px-6 py-8 text-center">
          <TriangleAlert className="h-5 w-5 text-destructive" />
          <p className="text-sm text-destructive">{result.error}</p>
          <p className="text-xs text-muted-foreground">The other models still ran.</p>
        </div>
      ) : (
        <>
          {pred && (img ? <PredictionCanvas pred={pred} img={img} threshold={threshold} /> : <div className="h-40 animate-pulse bg-muted" />)}
          <div className="space-y-2 p-3">
            {pred?.text && (
              <p className="flex gap-2 rounded-md bg-muted p-2 text-sm"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{pred.text}</p>
            )}
            {pred?.top && (
              <ul className="space-y-1 text-sm">
                {top.map((p) => (
                  <li key={p.class_id} className="flex items-center justify-between gap-2">
                    <span>{p.class}</span><span className="text-muted-foreground">{Math.round(p.confidence * 100)}%</span>
                  </li>
                ))}
              </ul>
            )}
            {!pred?.top && !!pred?.predictions.length && (
              <p className="text-xs text-muted-foreground">
                {shown.length} of {pred.predictions.length} boxes ≥ {Math.round(threshold * 100)}%
                {' · '}{pred.time.toFixed(2)} s on the server
              </p>
            )}
          </div>
        </>
      )}
    </Card>
  )
}

function ModelPicker({ items, selected, onToggle }: {
  items: RegistryItem[]; selected: string[]; onToggle: (ref: string) => void
}) {
  return (
    <div role="group" aria-label="Models">
      <div className="mb-1.5 flex w-full items-center justify-between text-sm font-medium">
        Models <span className="text-xs font-normal text-muted-foreground">{selected.length} / {MAX_MODELS}</span>
      </div>
      <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-1.5">
        {items.map((m) => {
          const on = selected.includes(m.ref)
          return (
            <label key={m.ref} title={m.available ? m.name : m.reason}
              className={cn('flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[13px] hover:bg-accent',
                !m.available && 'cursor-not-allowed opacity-50', on && 'bg-accent')}>
              <input type="checkbox" checked={on} disabled={!m.available || (!on && selected.length >= MAX_MODELS)}
                onChange={() => onToggle(m.ref)} className="accent-primary" />
              <span className="flex-1 truncate">{m.name}</span>
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{m.family}</span>
            </label>
          )
        })}
      </div>
    </div>
  )
}

export default function Playground() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const registry = useQuery({ queryKey: ['registry', ws], queryFn: () => api.registry(ws) })
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [sampleId, setSampleId] = useState<string | null>(null)
  const [refs, setRefs] = useState<string[]>([])
  const [classes, setClasses] = useState('')
  const [prompt, setPrompt] = useState('')
  const [confidence, setConfidence] = useState(0.25)
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState<PlaygroundResult[] | null>(null)
  const img = useHtmlImage(preview)

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const pick = (f: File, sample: string | null = null) => {
    setPreview(URL.createObjectURL(f))
    setFile(f)
    setSampleId(sample)
    setResults(null)
  }
  const camera = useCamera((f) => pick(f))
  const toggle = (ref: string) =>
    setRefs((r) => r.includes(ref) ? r.filter((x) => x !== ref) : r.length < MAX_MODELS ? [...r, ref] : r)

  const runtime = useQuery({
    queryKey: ['playground-runtime', ws, refs],
    queryFn: () => api.playgroundPreflight(ws, refs),
    enabled: refs.length > 0,
    staleTime: 5_000,
  })

  const pickSample = async (s: PlaygroundSample) => {
    try {
      const r = await fetch(fileUrl(s.url))
      if (!r.ok) throw new Error('Could not load that sample image.')
      const blob = await r.blob()
      pick(new File([blob], s.name || 'sample.jpg', { type: blob.type || 'image/jpeg' }), s.id)
    } catch (e) {
      toast.err(e as Error)
    }
  }

  const run = async () => {
    if (!file || !refs.length || busy) return
    const fd = new FormData()
    fd.append('file', file)
    fd.append('model_refs', refs.join(','))
    fd.append('confidence', String(confidence))
    if (classes.trim()) fd.append('classes', classes.trim())
    if (prompt.trim()) fd.append('prompt', prompt.trim())
    setBusy(true)
    try { setResults((await api.playgroundPredict(ws, fd)).results) } catch (e) { toast.err(e as Error) } finally {
      setBusy(false)
      qc.invalidateQueries({ queryKey: ['playground-runtime', ws] })
    }
  }

  const nameOf = (ref: string) => registry.data?.find((m) => m.ref === ref)?.name ?? ref
  const picked = refs.map((r) => registry.data?.find((m) => m.ref === r))
  const classesHint = picked.some((m) => m && (m.variant.includes('world') || m.family === 'vlm'))
  const states = (runtime.data?.models ?? []).map((s) => ({ ...s, name: nameOf(s.ref) }))
  const blocked = states.some((s) => s.state === 'unavailable')

  return (
    <div className="anim-page">
      <PageHeader title="Playground" desc="Run up to three models on the same image and compare them. No credits are charged." />
      <div className="grid items-start gap-6 px-4 pb-10 sm:px-8 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card className="space-y-4 p-4">
          <label
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith('image/')) pick(f) }}
            className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed bg-muted/50 px-3 py-4 text-center hover:border-ring focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
            <input type="file" accept="image/*" aria-label="Choose an image" className="sr-only"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) pick(f) }} />
            {preview ? <img src={preview} alt="Selected image preview" className="max-h-32 rounded" />
              : <><ImageUp className="h-5 w-5 text-muted-foreground" /><span className="text-sm">Drop an image or click to choose</span>
                <span className="text-xs text-muted-foreground">PNG, JPEG or WebP up to 20 MB</span></>}
          </label>

          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" aria-pressed={camera.active}
                onClick={() => camera.active ? camera.stop() : camera.start()}>
                <Camera className="h-4 w-4" aria-hidden="true" /> {camera.active ? 'Stop camera' : 'Use camera'}
              </Button>
              {camera.active && (
                <Button type="button" size="sm" onClick={camera.capture}>
                  <Camera className="h-4 w-4" aria-hidden="true" /> Capture frame
                </Button>
              )}
            </div>
            <video ref={camera.videoRef} muted playsInline aria-label="Camera preview"
              className={cn('w-full rounded-md border bg-muted', camera.active ? 'block max-h-48 object-cover' : 'hidden')} />
            {camera.error && <p role="alert" className="text-xs text-destructive">{camera.message}</p>}
          </div>

          <SampleStrip ws={ws} selectedId={sampleId} onPick={pickSample} />

          {registry.isLoading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading models…</p>}
          {registry.isError && <p className="text-sm text-destructive">Could not load the registry.</p>}
          <ModelPicker items={registry.data ?? []} selected={refs} onToggle={toggle} />

          {refs.length > 0 && (
            <div className="rounded-md border bg-muted/30 p-2">
              {runtime.isLoading ? (
                <p className="flex items-center gap-2 text-xs text-muted-foreground"><Spinner /> Checking model status…</p>
              ) : runtime.isError ? (
                <p className="text-xs text-muted-foreground">Could not check model status. You can still run.</p>
              ) : (
                <RuntimeStates states={states} />
              )}
            </div>
          )}

          <Field label="Classes" hint={classesHint
            ? 'Required by open-vocabulary models (YOLO-World, VLM grounding). Use the VLM question box instead to ask a question.'
            : 'Optional, comma-separated. Used for open-vocabulary detection.'}>
            <Input placeholder="helmet, vest, person" value={classes} onChange={(e) => setClasses(e.target.value)} />
          </Field>
          <Field label="VLM question" hint="Optional. Ask a vision-language model about the image.">
            <Input placeholder="How many workers wear a helmet?" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </Field>
          <Field label={`Confidence ${Math.round(confidence * 100)}%`} hint="Sent with the run; also re-filters the boxes below without re-running.">
            <input type="range" min={1} max={99} value={Math.round(confidence * 100)}
              onChange={(e) => setConfidence(+e.target.value / 100)} className="w-full accent-primary" aria-label="Confidence threshold" />
          </Field>
          <Button className="w-full" disabled={!file || !refs.length || busy || blocked} onClick={run}>
            {busy ? <><Spinner /> Running…</> : <><Play className="h-4 w-4" /> Run {refs.length || ''} model{refs.length === 1 ? '' : 's'}</>}
          </Button>
        </Card>

        <div className="min-w-0">
          {!results && (
            <Card className="flex min-h-72 items-center justify-center">
              <EmptyState icon={<ImageUp className="h-6 w-6 text-muted-foreground" />} title="Pick an image and up to three models."
                hint="Results appear side by side, with latency and boxes you can filter by confidence." />
            </Card>
          )}
          {results && (
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {results.map((r) => <ResultCard key={r.ref} result={r} img={img} threshold={confidence} name={nameOf(r.ref)} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
