import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Boxes, Check, Download, ImageOff, Info, Rocket, Trash2, X } from 'lucide-react'
import { api, del, fileUrl, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { JobStage, LeaderboardRow, ModelEval, ModelEvalDetection, ModelItem } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Modal, PageHeader, Progress, Spinner, Stat, StatusPill, Tabs, fmtDate, toast } from '@/components/ui'
import { classColor, viridis } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

export const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export function headline(m: ModelItem) {
  return m.task === 'classify' ? pct(m.metrics.accuracy_top1) : pct(m.metrics.map50)
}

const num3 = (v?: number | null) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(3))

// ---------- training stages ---------------------------------------------------
const STAGES = [
  { key: 'queue', label: 'Queued' },
  { key: 'acquire_gpu', label: 'GPU' },
  { key: 'materialise', label: 'Dataset' },
  { key: 'resolve_weights', label: 'Weights' },
  { key: 'build_config', label: 'Config' },
  { key: 'train', label: 'Train' },
  { key: 'evaluate', label: 'Evaluate' },
  { key: 'register', label: 'Register' },
  { key: 'release', label: 'Release' },
] as const

const fmtSeconds = (t: number) => (t < 60 ? `${t.toFixed(1)}s` : `${Math.floor(t / 60)}m ${Math.round(t % 60)}s`)

function StageStepper({ stages }: { stages?: Record<string, JobStage> }) {
  return (
    <div className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-start" aria-label="Training stages">
        {STAGES.map((s, i) => {
          const st = stages?.[s.key]
          const state = st?.status ?? 'pending'
          const prevDone = stages?.[STAGES[i - 1]?.key]?.status === 'done'
          return (
            <li key={s.key} className="flex w-[62px] shrink-0 flex-col items-center gap-1" title={st?.note || s.label}>
              <div className="flex w-full items-center">
                <span className={cn('h-px flex-1', i === 0 ? 'bg-transparent' : prevDone ? 'bg-primary/50' : 'bg-border')} />
                <span className={cn('grid h-5 w-5 shrink-0 place-items-center rounded-full',
                  state === 'done' && 'bg-primary text-primary-foreground',
                  state === 'running' && 'animate-pulse bg-primary/20 text-primary ring-2 ring-primary',
                  state === 'failed' && 'bg-destructive text-destructive-foreground',
                  state === 'pending' && 'border border-border bg-card')}>
                  {state === 'done' ? <Check className="h-3 w-3" /> : state === 'failed' ? <X className="h-3 w-3" /> : null}
                  <span className="sr-only">{state === 'pending' ? 'not started' : state}</span>
                </span>
                <span className={cn('h-px flex-1', i === STAGES.length - 1 ? 'bg-transparent' : state === 'done' ? 'bg-primary/50' : 'bg-border')} />
              </div>
              <span className={cn('text-center text-[10px] leading-tight', state === 'pending' ? 'text-muted-foreground' : 'font-medium')}>{s.label}</span>
              <span className="text-[10px] tabular-nums text-muted-foreground">{st ? fmtSeconds(st.t) : '—'}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// ---------- evaluation --------------------------------------------------------
const COCO_METRICS: [keyof ModelEval['coco'], string][] = [
  ['AP', 'AP'], ['AP50', 'AP50'], ['AP75', 'AP75'],
  ['APs', 'AP small'], ['APm', 'AP medium'], ['APl', 'AP large'],
  ['AR1', 'AR@1'], ['AR10', 'AR@10'], ['AR100', 'AR@100'],
  ['ARs', 'AR small'], ['ARm', 'AR medium'], ['ARl', 'AR large'],
]

const TIDE_ERRORS = [
  ['cls', 'Cls'],
  ['loc', 'Loc'],
  ['both', 'Both'],
  ['dupe', 'Dupe'],
  ['bkg', 'Bkg'],
  ['missed', 'Missed'],
] as const

type Box = { cls: string; bbox: number[]; conf?: number }
type ViewerState = { title: string; files: string[] } | null

const iou = (a: number[], b: number[]) => {
  const ax2 = a[0] + a[2], ay2 = a[1] + a[3], bx2 = b[0] + b[2], by2 = b[1] + b[3]
  const iw = Math.max(0, Math.min(ax2, bx2) - Math.max(a[0], b[0]))
  const ih = Math.max(0, Math.min(ay2, by2) - Math.max(a[1], b[1]))
  const inter = iw * ih
  const union = a[2] * a[3] + b[2] * b[3] - inter
  return union > 0 ? inter / union : 0
}

/**
 * Re-derive the confusion matrix at an arbitrary confidence threshold from the stored per-image
 * detections. Matrix cells use class-agnostic IoU >= 0.5 matching (a helmet box predicted as a
 * vest belongs in the helmet→vest cell); F1 uses class-aware matching, like the server sweep.
 */
function recompute(ev: ModelEval, conf: number) {
  if (!ev.detections?.length) return null
  const labels = ev.confusion.labels
  const index = new Map(labels.map((l, i) => [l, i]))
  const n = labels.length
  const bg = n - 1
  const matrix = Array.from({ length: n }, () => Array<number>(n).fill(0))
  const files: string[][][] = Array.from({ length: n }, () => Array.from({ length: n }, () => [] as string[]))
  let tp = 0, fp = 0, fn = 0
  const match = (d: ModelEvalDetection, p: ModelEvalDetection['pred'][number], used: Set<number>, sameClass: boolean) => {
    let best = -1, bestIou = 0.5
    for (let gi = 0; gi < d.gt.length; gi++) {
      if (used.has(gi) || (sameClass && d.gt[gi].cls !== p.cls)) continue
      const v = iou(d.gt[gi].bbox, p.bbox)
      if (v >= bestIou) { bestIou = v; best = gi }
    }
    return best
  }
  for (const d of ev.detections) {
    const preds = d.pred.filter((p) => p.conf >= conf).sort((a, b) => b.conf - a.conf)
    // matrix pass: class-agnostic, so wrong-class boxes land on the off-diagonal
    const taken = new Set<number>()
    for (const p of preds) {
      const pc = index.get(p.cls)
      if (pc == null) continue
      const gi = match(d, p, taken, false)
      const row = gi >= 0 ? index.get(d.gt[gi].cls) ?? bg : bg
      if (gi >= 0) taken.add(gi)
      matrix[row][pc]++
      files[row][pc].push(d.file)
    }
    for (let gi = 0; gi < d.gt.length; gi++) {
      if (taken.has(gi)) continue
      const row = index.get(d.gt[gi].cls)
      if (row == null) continue
      matrix[row][bg]++
      files[row][bg].push(d.file)
    }
    // F1 pass: class-aware, matching the server's confidence sweep
    const used = new Set<number>()
    for (const p of preds) {
      const gi = match(d, p, used, true)
      if (gi >= 0) { used.add(gi); tp++ } else fp++
    }
    fn += d.gt.length - used.size
  }
  const f1 = 2 * tp + fp + fn > 0 ? (2 * tp) / (2 * tp + fp + fn) : 0
  return { matrix, files, f1 }
}

function BoxPanel({ label, src, alt, w, h, boxes, colorOf, dashed }: {
  label: string; src: string; alt: string; w?: number; h?: number
  boxes: Box[]; colorOf: (cls: string) => string; dashed?: boolean
}) {
  const sw = w ? Math.max(1.5, w / 400) : 2
  return (
    <div className="min-w-0 space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-[11px] font-medium">
        <span>{label}</span>
        <span className="text-muted-foreground">{boxes.length} {boxes.length === 1 ? 'box' : 'boxes'}</span>
      </div>
      <div className="relative overflow-hidden rounded-md border bg-muted">
        <img src={src} alt={alt} loading="lazy" className="block w-full" />
        {w != null && h != null ? (
          <>
            <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true"
              className="pointer-events-none absolute inset-0 h-full w-full">
              {boxes.map((b, i) => (
                <rect key={i} x={b.bbox[0]} y={b.bbox[1]} width={b.bbox[2]} height={b.bbox[3]} fill="none"
                  stroke={colorOf(b.cls)} strokeWidth={sw} strokeDasharray={dashed ? `${sw * 3} ${sw * 2}` : undefined} />
              ))}
            </svg>
            {boxes.map((b, i) => {
              const top = (b.bbox[1] / h) * 100
              return (
                <span key={i} className="absolute flex items-center gap-1 rounded-sm bg-black/70 px-1 py-px text-[10px] font-medium leading-tight text-white"
                  style={{ left: `${(b.bbox[0] / w) * 100}%`, top: `${top}%`, transform: top < 6 ? 'none' : 'translateY(-100%)' }}>
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: colorOf(b.cls) }} />
                  {b.cls}{b.conf != null ? ` ${b.conf.toFixed(2)}` : ''}
                </span>
              )
            })}
          </>
        ) : null}
      </div>
    </div>
  )
}

function EvalPair({ file, url, det, conf, colorOf }: {
  file: string; url?: string; det?: ModelEvalDetection; conf: number; colorOf: (cls: string) => string
}) {
  if (!url) return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">Preview unavailable for {file}.</p>
  const src = fileUrl(url)
  const preds = det ? det.pred.filter((p) => p.conf >= conf) : []
  return (
    <figure className="space-y-1.5">
      <figcaption className="truncate text-xs font-medium text-muted-foreground">{file}</figcaption>
      <div className="grid grid-cols-2 gap-2 sm:gap-3">
        <BoxPanel label="Ground truth" src={src} alt={file} w={det?.width} h={det?.height} boxes={det?.gt ?? []} colorOf={colorOf} />
        <BoxPanel label="Prediction" src={src} alt={file} w={det?.width} h={det?.height} boxes={preds} colorOf={colorOf} dashed />
      </div>
      {!det ? <p className="text-[11px] text-muted-foreground">Boxes weren’t stored for this run — showing the image only.</p> : null}
    </figure>
  )
}

function GalleryViewer({ viewer, onClose, images, dets, conf, colorOf }: {
  viewer: ViewerState; onClose: () => void; images?: Record<string, string>
  dets: Map<string, ModelEvalDetection>; conf: number; colorOf: (cls: string) => string
}) {
  const files = viewer?.files ?? []
  return (
    <Modal open={!!viewer} onClose={onClose} wide title={viewer?.title}>
      {!files.length ? (
        <EmptyState icon={<ImageOff className="h-7 w-7 text-muted-foreground/50" />} title="No images for this cell"
          hint="Nothing matched this ground-truth / prediction pair at the current confidence threshold." />
      ) : (
        <div className="space-y-6">
          {files.map((f) => <EvalPair key={f} file={f} url={images?.[f]} det={dets.get(f)} conf={conf} colorOf={colorOf} />)}
        </div>
      )}
    </Modal>
  )
}

function ConfusionCard({ ev, matrix, cellFiles, conf, onConf, f1, onOpen }: {
  ev: ModelEval; matrix: number[][]; cellFiles: string[][][]
  conf: number; onConf: (v: number) => void; f1: number | null
  onOpen: (v: ViewerState) => void
}) {
  const sampled = ev.detections?.length && ev.split_images && ev.detections.length < ev.split_images
    ? `${ev.detections.length} of ${ev.split_images}` : null
  const labels = ev.confusion.labels
  const n = labels.length
  const maxCount = Math.max(1, ...matrix.flat())
  const hasDet = !!ev.detections?.length
  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Confusion matrix</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Rows are ground truth, columns are predictions. Click any cell to see its images.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="conf-threshold" className="text-xs font-medium">Confidence</label>
          <input id="conf-threshold" type="range" min={0.05} max={0.95} step={0.05} value={conf}
            aria-label="Confidence threshold" aria-valuetext={conf.toFixed(2)} disabled={!hasDet}
            onChange={(e) => onConf(+e.target.value)}
            className="h-1.5 w-36 cursor-pointer accent-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-50" />
          <span className="w-9 text-xs tabular-nums">{conf.toFixed(2)}</span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="grid gap-0.5" style={{
          gridTemplateColumns: `minmax(96px, 140px) repeat(${n}, minmax(44px, 1fr))`,
          minWidth: `${140 + n * 44}px`, maxWidth: `${140 + n * 72}px`,
        }}>
          <div className="flex items-end justify-end px-1 pb-1 text-right text-[10px] leading-tight text-muted-foreground">
            Actual ↓<br />Predicted →
          </div>
          {labels.map((l) => (
            <div key={l} className="px-0.5 pb-1 text-center text-[10px] leading-tight text-muted-foreground [overflow-wrap:anywhere]">{l}</div>
          ))}
          {matrix.map((row, r) => (
            <Fragment key={r}>
              <div className="flex items-center justify-end gap-1 pr-1 text-right text-[11px] leading-tight">
                <span className="truncate">{labels[r]}</span>
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: classColor(r) }} />
              </div>
              {row.map((v, c) => {
                const t = v / maxCount
                const label = `${labels[r]} predicted as ${labels[c]}: ${v}`
                return (
                  <button key={c} type="button" title={label} aria-label={label}
                    onClick={() => onOpen({ title: `${labels[r]} → ${labels[c]}`, files: cellFiles[r]?.[c] ?? [] })}
                    className="grid h-11 min-w-11 place-items-center rounded-sm text-[11px] font-medium tabular-nums transition-[filter] hover:brightness-110"
                    style={{ background: v ? viridis(t) : 'var(--muted)', color: v ? (t >= 0.55 ? '#111827' : '#ffffff') : 'var(--muted-foreground)' }}>
                    {v || ''}
                  </button>
                )
              })}
            </Fragment>
          ))}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-[11px] text-muted-foreground">
        <div className="flex items-center gap-2">
          <span>0</span>
          <span className="h-2 w-24 rounded-full" style={{ background: `linear-gradient(90deg, ${viridis(0)}, ${viridis(0.5)}, ${viridis(1)})` }} />
          <span>{maxCount}</span>
        </div>
        <p>
          {f1 != null
            ? <>F1 at {conf.toFixed(2)}: <b className="font-semibold text-foreground tabular-nums">{f1.toFixed(3)}</b></>
            : <>F1 at the stored threshold: <b className="font-semibold text-foreground tabular-nums">{ev.f1_best.f1.toFixed(3)}</b></>}
          {' · '}best {ev.f1_best.f1.toFixed(3)} at {ev.f1_best.conf.toFixed(2)}
        </p>
      </div>
      {!hasDet && <p className="mt-1 text-[11px] text-muted-foreground">Per-image detections weren’t stored for this run, so the matrix is fixed at the best-F1 threshold.</p>}
      {sampled && <p className="mt-1 text-[11px] text-muted-foreground">The slider recomputes from {sampled} stored images; the full split matrix is shown at the best threshold.</p>}
    </Card>
  )
}

// ---------- TIDE error breakdown ----------------------------------------------
type TideLabelProps = {
  viewBox?: { x?: number; y?: number; width?: number; height?: number; cx?: number; cy?: number }
  value?: number | string
  peak?: number
  uniquePeak?: boolean
}

const TIDE_LABEL_OFFSET = 6

/** Bar-end label: 3-decimal ΔAP, plus a "largest" hint when one bucket alone leads. */
function TideValueLabel({ viewBox, value, peak, uniquePeak }: TideLabelProps) {
  const x = (viewBox?.x ?? 0) + (viewBox?.width ?? 0) + TIDE_LABEL_OFFSET
  const y = (viewBox?.y ?? 0) + (viewBox?.height ?? 0) / 2
  const largest = !!uniquePeak && typeof value === 'number' && value === peak
  const text = typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : '0.000'
  // The halo keeps the number legible where it crosses a gridline.
  return (
    <text x={x} y={y} dominantBaseline="middle" fontSize={11} stroke="var(--card)" strokeWidth={3} strokeLinejoin="round"
      paintOrder="stroke" fill={largest ? 'var(--foreground)' : 'var(--muted-foreground)'}>
      {text}
      {largest ? <tspan dx={4} fontSize={9} fill="var(--muted-foreground)">largest</tspan> : null}
    </text>
  )
}

// Plain toFixed(2) would print a 0.035 gridline as "0.04"; explicit two-decimal steps avoid that.
const TIDE_TICK_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]

function TideCard({ tide, conf }: { tide: NonNullable<ModelEval['tide']>; conf: number }) {
  const { rows, peak, uniquePeak } = useMemo(() => {
    const next = TIDE_ERRORS.map(([key, label]) => {
      const raw = tide[key]
      return { key, label, value: Number.isFinite(raw) ? Math.max(0, raw) : 0 }
    })
    const top = Math.max(...next.map((r) => r.value))
    // Ties must not crown one arbitrary bucket: every maximum is emphasised, only a lone one is labelled.
    const atPeak = top > 0 ? next.filter((r) => r.value === top).length : 0
    return { rows: next, peak: top, uniquePeak: atPeak === 1 }
  }, [tide])
  // A fixed 0..1 axis would flatten typical 0.0x values into invisible slivers.
  const domainMax = Math.max(0.05, peak * 1.1)
  const ticks = useMemo(() => {
    const step = TIDE_TICK_STEPS.find((s) => domainMax / s <= 5) ?? 1
    const out: number[] = []
    for (let i = 0; i * step <= domainMax + 1e-9; i++) out.push(Number((i * step).toFixed(2)))
    return out
  }, [domainMax])

  return (
    <Card className="min-w-0 p-4">
      <h3 className="text-sm font-semibold">TIDE error breakdown</h3>
      <p className="mt-0.5 text-xs text-muted-foreground">AP recoverable by fixing each error type at the best-F1 confidence.</p>
      {peak === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">No AP recoverable at this threshold.</p>
      ) : (
        <figure className="mt-3 min-w-0">
          <div className="relative h-56">
            <div className="h-full" aria-hidden="true">
              <ResponsiveContainer>
                <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 78, bottom: 0, left: 0 }}>
                  <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, domainMax]} ticks={ticks} height={18} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                    tickLine={false} axisLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
                  <YAxis type="category" dataKey="label" width={52} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: 'var(--muted)' }} formatter={(v: number) => [v.toFixed(3), 'ΔAP recoverable']} />
                  <Bar dataKey="value" barSize={14} radius={[0, 3, 3, 0]} isAnimationActive={false}>
                    {rows.map((r) => (
                      <Cell key={r.key} fill="var(--primary)" fillOpacity={r.value === peak ? 1 : 0.32} />
                    ))}
                    <LabelList dataKey="value" content={<TideValueLabel peak={peak} uniquePeak={uniquePeak} />} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <span aria-hidden="true" className="pointer-events-none absolute bottom-0 right-0 text-[10px] text-muted-foreground">ΔAP</span>
          </div>
          <figcaption className="mt-2">
            <ul className="sr-only">
              {rows.map((r) => <li key={r.key}>{r.label}: {r.value.toFixed(3)} AP recoverable</li>)}
            </ul>
            <p className="text-[11px] text-muted-foreground">
              Larger bars are the errors worth fixing first. Measured <span className="whitespace-nowrap">at conf <span className="tabular-nums">{conf.toFixed(2)}</span></span>.
            </p>
          </figcaption>
        </figure>
      )}
    </Card>
  )
}

function EvalPanel({ ev, images, task }: { ev: ModelEval; images?: Record<string, string>; task: ModelItem['task'] }) {
  const mask = (ev.iou ?? (task === 'segment' ? 'segm' : 'bbox')) === 'segm'
  const [conf, setConf] = useState(() => Math.min(0.95, Math.max(0.05, ev.f1_best?.conf ?? 0.25)))
  const [viewer, setViewer] = useState<ViewerState>(null)
  const dets = useMemo(() => new Map((ev.detections ?? []).map((d) => [d.file, d])), [ev.detections])
  const colorMap = useMemo(() => new Map(ev.confusion.labels.map((l, i) => [l, classColor(i)])), [ev.confusion.labels])
  const colorOf = (cls: string) => colorMap.get(cls) ?? 'var(--foreground)'
  const computed = useMemo(() => recompute(ev, conf), [ev, conf])
  const pr = useMemo(() => [...ev.pr_curve].sort((a, b) => a.recall - b.recall), [ev.pr_curve])
  const weakest = useMemo(() => [...ev.per_class].sort((a, b) => a.AP - b.AP)[0], [ev.per_class])
  // at the stored best threshold the server matrix covers the whole split; the slider only has the capped detail
  const atBest = Math.abs(conf - ev.f1_best.conf) < 1e-9
  const matrix = atBest ? ev.confusion.matrix : computed?.matrix ?? ev.confusion.matrix
  const cellFiles = atBest ? ev.confusion.images : computed?.files ?? ev.confusion.images
  const f1 = atBest ? ev.f1_best.f1 : computed?.f1 ?? null

  return (
    <section className="space-y-4" aria-label="Evaluation">
      {ev.split === 'valid' ? (
        <div className="flex items-start gap-2 rounded-lg border border-warning/60 bg-warning/10 px-4 py-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div>
            <p className="font-medium">Evaluated on the validation split</p>
            <p className="mt-0.5 text-muted-foreground">{ev.note}</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge className="bg-success/15 text-success">Test split</Badge>
          <span className="text-muted-foreground">Held out from training{ev.note ? ` · ${ev.note}` : ''}</span>
        </div>
      )}

      <Card className="p-4">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">COCO {mask ? 'mask' : 'box'} metrics</h3>
          <span className="text-xs tabular-nums text-muted-foreground">Inference {ev.latency_ms.toFixed(1)} ms per image</span>
        </div>
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-4 lg:grid-cols-6">
          {COCO_METRICS.map(([key, label]) => (
            <div key={key} className={cn('bg-card px-2.5 py-2', key === 'AP' && 'bg-accent/40')}>
              <div className="text-[10px] leading-tight text-muted-foreground">
                {key === 'AP' ? (mask ? 'Mask AP' : 'Box AP') : key === 'AP50' ? (mask ? 'Mask AP50' : 'Box AP50') : label}
              </div>
              <div className={cn('tabular-nums', key === 'AP' ? 'text-lg font-bold text-primary' : 'text-sm font-semibold')}>{num3(ev.coco[key])}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="min-w-0 p-4">
          <h3 className="mb-2 text-sm font-semibold">Per-class AP</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[220px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-1.5 font-medium">Class</th>
                  <th scope="col" className="py-1.5 text-right font-medium">AP</th>
                  <th scope="col" className="py-1.5 text-right font-medium">AP50</th>
                </tr>
              </thead>
              <tbody>
                {ev.per_class.map((c, i) => (
                  <tr key={`${c.class}-${i}`} className="border-b last:border-0">
                    <td className="py-1.5"><span className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle" style={{ background: classColor(i) }} />{c.class}</td>
                    <td className="py-1.5 text-right tabular-nums">{num3(c.AP)}</td>
                    <td className="py-1.5 text-right tabular-nums text-muted-foreground">{num3(c.AP50)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {weakest && <p className="mt-2 text-[11px] text-muted-foreground">Weakest class: <b className="font-medium text-foreground">{weakest.class}</b> · AP {num3(weakest.AP)}</p>}
        </Card>

        <Card className="min-w-0 p-4">
          <h3 className="mb-3 text-sm font-semibold">Precision–recall</h3>
          <div className="h-56">
            {pr.length ? (
              <ResponsiveContainer>
                <LineChart data={pr} margin={{ left: -18, right: 8, top: 4, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" dataKey="recall" domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => v.toFixed(1)} />
                  <Tooltip formatter={(v: number) => v.toFixed(3)} labelFormatter={(v) => `Recall ${Number(v).toFixed(3)}`} />
                  <Line type="monotone" dataKey="precision" stroke="var(--primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : <p className="grid h-full place-items-center text-xs text-muted-foreground">No detections to plot.</p>}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">Precision vs recall across the confidence sweep (0.05–0.95).</p>
        </Card>
      </div>

      {ev.tide ? <TideCard tide={ev.tide} conf={ev.f1_best.conf} /> : null}

      {ev.confusion.labels.length > 0 && (
        <ConfusionCard ev={ev} matrix={matrix} cellFiles={cellFiles}
          conf={conf} onConf={setConf} f1={f1} onOpen={setViewer} />
      )}

      {ev.worst.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold">Worst images</h3>
          <p className="mb-3 mt-0.5 text-xs text-muted-foreground">Lowest-scoring images at the best confidence. Open one to compare ground truth with predictions.</p>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {ev.worst.slice(0, 12).map((f) => {
              const u = images?.[f]
              return (
                <button key={f} type="button" onClick={() => setViewer({ title: f, files: [f] })}
                  className="relative aspect-video overflow-hidden rounded-md border bg-muted">
                  {u
                    ? <img src={fileUrl(u)} alt={f} loading="lazy" className="h-full w-full object-cover" />
                    : <span className="grid h-full place-items-center px-1 text-center text-[10px] text-muted-foreground">no preview</span>}
                </button>
              )
            })}
          </div>
        </Card>
      )}

      <GalleryViewer viewer={viewer} onClose={() => setViewer(null)} images={images} dets={dets} conf={conf} colorOf={colorOf} />
    </section>
  )
}

// ---------- leaderboard -------------------------------------------------------
function LeaderboardTab({ rows, loading, onPick }: { rows?: LeaderboardRow[]; loading: boolean; onPick: (id: string) => void }) {
  if (loading) return <div className="py-16 text-center"><Spinner /></div>
  if (!rows?.length) return <EmptyState title="No evaluated models yet" hint="A model appears here once training finishes and its evaluation run completes." />
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <th scope="col" className="w-10 px-3 py-2 font-medium">#</th>
              <th scope="col" className="px-3 py-2 font-medium">Model</th>
              <th scope="col" className="px-3 py-2 font-medium">Version</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">AP</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Latency</th>
              <th scope="col" className="px-3 py-2 font-medium">Status</th>
              <th scope="col" className="px-3 py-2 font-medium">Comparable</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} onClick={() => onPick(r.id)}
                className={cn('cursor-pointer border-b transition-colors last:border-0 hover:bg-muted/60', !r.comparable && 'text-muted-foreground')}>
                <td className="px-3 py-2 tabular-nums text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">
                  <button type="button" onClick={(e) => { e.stopPropagation(); onPick(r.id) }}
                    className="block max-w-[22ch] truncate text-left font-medium hover:underline">{r.name}</button>
                  <div className="truncate text-[11px] text-muted-foreground">{r.variant || r.task}</div>
                </td>
                <td className="px-3 py-2 tabular-nums">{r.version == null ? '—' : `v${r.version}`}</td>
                <td className="px-3 py-2 text-right font-semibold tabular-nums">{r.ap == null ? '—' : r.ap.toFixed(3)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.latency_ms == null ? '—' : `${Math.round(r.latency_ms)} ms`}</td>
                <td className="px-3 py-2"><StatusPill status={r.status} /></td>
                <td className="px-3 py-2">
                  {r.ap == null
                    ? <span className="text-[11px] text-muted-foreground">not evaluated</span>
                    : r.comparable
                      ? <Badge className="bg-success/15 text-success">comparable</Badge>
                      : <span className="text-[11px] text-muted-foreground">different version</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// ---------- training curves (unchanged) --------------------------------------
function Charts({ m }: { m: ModelItem }) {
  const k = m.task === 'segment' ? '(M)' : '(B)'
  const series = m.task === 'classify'
    ? [['metrics/accuracy_top1', 'Top-1 acc', '#7c3aed'], ['metrics/accuracy_top5', 'Top-5 acc', '#22c55e']]
    : [[`metrics/mAP50${k}`, 'mAP50', '#7c3aed'], [`metrics/mAP50-95${k}`, 'mAP50-95', '#3b82f6'], [`metrics/precision${k}`, 'Precision', '#22c55e'], [`metrics/recall${k}`, 'Recall', '#f97316']]
  const loss = Object.keys(m.history[0] ?? {}).filter((x) => x.startsWith('val/') && x.endsWith('loss'))
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Accuracy over epochs</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} domain={[0, 1]} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map(([key, name, color]) => <Line key={key} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Validation loss</h3>
        <div className="h-60"><ResponsiveContainer><LineChart data={m.history}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="epoch" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip formatter={(v: number) => v.toFixed(3)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {loss.map((key, i) => <Line key={key} dataKey={key} name={key.replace('val/', '')} stroke={['#ef4444', '#eab308', '#14b8a6'][i % 3]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card>
    </div>
  )
}

export default function Models() {
  const { project, ws } = useProject()
  const [sp, setSp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const can = useApp((s) => s.can)
  const [tab, setTab] = useState('evaluation')

  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug),
    refetchInterval: (q) => (q.state.data?.some((m) => ['queued', 'training'].includes(m.status)) ? 2500 : false) })
  const list = models.data ?? []
  const sel = list.find((m) => m.id === sp.get('model')) ?? list[0]

  const detail = useQuery({
    queryKey: ['model', ws, project.slug, sel?.id ?? ''],
    queryFn: () => api.model(ws, project.slug, sel!.id),
    enabled: !!sel?.id,
    refetchInterval: sel && ['queued', 'training'].includes(sel.status) ? 2500 : false,
  })
  const lb = useQuery({
    queryKey: ['leaderboard', ws, project.slug],
    queryFn: () => api.leaderboard(ws, project.slug),
    enabled: tab === 'leaderboard',
  })

  // The list poll stops the moment the model flips to ready — pull the fresh eval in at that point.
  const prevStatus = useRef(sel?.status)
  useEffect(() => {
    if (sel?.id && prevStatus.current && prevStatus.current !== sel.status && sel.status === 'ready')
      qc.invalidateQueries({ queryKey: ['model', ws, project.slug, sel.id] })
    prevStatus.current = sel?.status
  }, [sel?.id, sel?.status, qc, ws, project.slug])

  const m = detail.data ?? sel
  const ev = m?.metrics.eval

  const pick = (id: string) => { setSp({ model: id }); setTab('evaluation') }

  return (
    <div className="anim-page">
      <PageHeader title="Models" desc="Trained models, their metrics and training curves." actions={can('admin') && <Button onClick={() => nav('../train')}>Train new model</Button>} />
      {models.isSuccess && !list.length ? <EmptyState icon={<Boxes className="h-8 w-8 text-muted-foreground/50" />} title="No models yet." action={can('admin') && <Button size="sm" onClick={() => nav('../train')}>Train your first model</Button>} /> : (
        <div className="flex flex-col gap-6 px-4 pb-10 md:flex-row md:px-8">
          <div className="w-full space-y-1.5 md:w-64 md:shrink-0 md:max-h-[calc(100vh_-_10rem)] md:overflow-y-auto">
            {list.map((x) => (
              <button key={x.id} onClick={() => setSp({ model: x.id })} aria-current={sel?.id === x.id ? 'true' : undefined}
                className={cn('w-full cursor-pointer rounded-lg border px-3 py-2.5 text-left text-sm', sel?.id === x.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
                <div className="flex items-center justify-between gap-2"><span className="truncate font-medium">{x.name}</span><StatusPill status={x.status} /></div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">v{x.version} · {x.arch} · {headline(x)}</div>
              </button>
            ))}
          </div>

          {m && (
            <div className="min-w-0 flex-1 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-bold">{m.name}</h2>
                  <p className="text-sm text-muted-foreground">{m.arch} · trained on v{m.version} · {fmtDate(m.created)} · {m.classes.length} classes</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {m.status === 'ready' && <Button onClick={() => nav(`../deploy?model=${m.id}`)}><Rocket className="h-4 w-4" /> Deploy & Test</Button>}
                  {m.weightsUrl && <a href={fileUrl(m.weightsUrl)}><Button variant="outline"><Download className="h-4 w-4" /> Weights (.pt)</Button></a>}
                  {['queued', 'training'].includes(m.status) && m.jobId && can('reviewer') && <Button variant="outline" onClick={() => post(`${api.P(ws, project.slug)}/jobs/${m.jobId}/cancel`).then(() => toast.ok('Stopping after this epoch')).catch(toast.err)}><X className="h-4 w-4" /> Stop</Button>}
                  {can('admin') && <Button variant="ghost" size="icon" aria-label="Delete model" onClick={() => confirm('Delete this model?') && del(`${api.P(ws, project.slug)}/models/${m.id}`).then(() => qc.invalidateQueries({ queryKey: ['models', ws, project.slug] })).catch(toast.err)}><Trash2 className="h-4 w-4" /></Button>}
                </div>
              </div>

              <Tabs tabs={[{ id: 'evaluation', label: 'Evaluation' }, { id: 'leaderboard', label: 'Leaderboard' }]} active={tab} onChange={setTab} />

              {tab === 'leaderboard' ? (
                <LeaderboardTab rows={lb.data} loading={lb.isLoading} onPick={pick} />
              ) : (
                <>
                  {['queued', 'training'].includes(m.status) && (
                    <Card className="p-4">
                      <StageStepper stages={m.job?.result?.stages} />
                      <div className="mb-2 mt-4 flex items-center justify-between text-sm"><span>{m.status === 'queued' ? 'Waiting for a worker…' : `Epoch ${m.history.length} of ${m.job?.params.options?.epochs ?? '?'}`}</span><span className="tabular-nums">{Math.round(m.job?.progress ?? 0)}%</span></div>
                      <Progress value={m.job?.progress ?? 0} />
                      {m.status === 'queued' && <p className="mt-2 text-xs text-muted-foreground">Training needs a worker: the built-in one, or <code>labeldesk-worker</code> on a GPU machine.</p>}
                    </Card>
                  )}
                  {m.status === 'failed' && <Card className="border-destructive/40 bg-destructive/10 p-4 text-sm">Training failed: {m.job?.error || 'see worker logs'}</Card>}

                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {m.task === 'classify' ? <>
                      <Stat label="Top-1 accuracy" value={pct(m.metrics.accuracy_top1)} />
                      <Stat label="Top-5 accuracy" value={pct(m.metrics.accuracy_top5)} />
                    </> : <>
                      <Stat label="mAP@50" value={pct(m.metrics.map50)} />
                      <Stat label="mAP@50-95" value={pct(m.metrics.map5095)} />
                      <Stat label="Precision" value={pct(m.metrics.precision)} />
                      <Stat label="Recall" value={pct(m.metrics.recall)} />
                    </>}
                  </div>

                  {ev ? (
                    m.task === 'classify' || /not evaluated|skipped/i.test(ev.note)
                      ? <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                          <Info className="h-4 w-4 shrink-0" /> {ev.note || 'COCO evaluation is not available for this model.'}
                        </Card>
                      : <EvalPanel key={m.id} ev={ev} images={detail.data?.evalImages} task={m.task} />
                  ) : m.metrics.eval_error ? (
                    <Card className="flex items-start gap-2 border-warning/60 bg-warning/10 p-4 text-sm">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                      <div>
                        <p className="font-medium">Evaluation failed — the model is still usable</p>
                        <p className="mt-0.5 break-words text-muted-foreground">{m.metrics.eval_error}</p>
                      </div>
                    </Card>
                  ) : m.status === 'ready' && (
                    <Card className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
                      <Info className="h-4 w-4 shrink-0" /> Evaluation runs after training — refresh once the job finishes.
                    </Card>
                  )}

                  {m.history.length > 0 && <Charts m={m} />}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
