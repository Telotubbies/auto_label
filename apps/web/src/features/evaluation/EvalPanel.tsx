import { Fragment, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ImageOff } from 'lucide-react'
import { fileUrl } from '@/lib/api'
import type { ModelEval, ModelEvalDetection, ModelItem } from '@/lib/types'
import { Badge, Card, EmptyState, Modal } from '@/components/ui'
import { classColor, viridis } from '@/lib/theme'
import { cn } from '@/lib/utils'

const num3 = (v?: number | null) => (v == null || Number.isNaN(v) ? '—' : v.toFixed(3))

// ---------- evaluation --------------------------------------------------------
const COCO_METRICS: [keyof ModelEval['coco'], string][] = [
  ['AP', 'AP'], ['AP50', 'AP50'], ['AP75', 'AP75'],
  ['APs', 'AP small'], ['APm', 'AP medium'], ['APl', 'AP large'],
  ['AR1', 'AR@1'], ['AR10', 'AR@10'], ['AR100', 'AR@100'],
  ['ARs', 'AR small'], ['ARm', 'AR medium'], ['ARl', 'AR large'],
]

const TIDE_ERRORS = [
  ['cls', 'Cls', 'Classification'],
  ['loc', 'Loc', 'Localisation'],
  ['both', 'Both', 'Class and box'],
  ['dupe', 'Dupe', 'Duplicate'],
  ['bkg', 'Bkg', 'Background'],
  ['missed', 'Missed', 'Missed GT'],
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

/** Bar-end label: 3-decimal ΔAP50, plus a "largest" hint when one bucket alone leads. */
function TideValueLabel({ viewBox, value, peak, uniquePeak }: TideLabelProps) {
  const end = (viewBox?.x ?? 0) + (viewBox?.width ?? 0)
  const y = (viewBox?.y ?? 0) + (viewBox?.height ?? 0) / 2
  const negative = typeof value === 'number' && value < 0
  const largest = !!uniquePeak && typeof value === 'number' && value === peak
  const text = typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : '0.000'
  // The halo keeps the number legible where it crosses a gridline.
  return (
    <text x={negative ? end - TIDE_LABEL_OFFSET : end + TIDE_LABEL_OFFSET} y={y}
      textAnchor={negative ? 'end' : 'start'} dominantBaseline="middle" fontSize={11}
      stroke="var(--card)" strokeWidth={3} strokeLinejoin="round" paintOrder="stroke"
      fill={largest ? 'var(--foreground)' : 'var(--muted-foreground)'}>
      {text}
      {largest ? <tspan dx={4} fontSize={9} fill="var(--muted-foreground)">largest</tspan> : null}
    </text>
  )
}

// Plain toFixed(2) would print a 0.035 gridline as "0.04"; explicit two-decimal steps avoid that.
const TIDE_TICK_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1]

function TideCard({ tide }: { tide: NonNullable<ModelEval['tide']> }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  const { rows, peak, uniquePeak, floor } = useMemo(() => {
    const next = TIDE_ERRORS.map(([key, label, long]) => {
      const raw = tide[key]
      return { key, label, long, value: Number.isFinite(raw) ? raw : 0 }
    })
    const top = Math.max(...next.map((r) => r.value))
    // Ties must not crown one arbitrary bucket: every maximum is emphasised, only a lone one is labelled.
    const atPeak = top > 0 ? next.filter((r) => r.value === top).length : 0
    return { rows: next, peak: top, uniquePeak: atPeak === 1, floor: Math.min(0, ...next.map((r) => r.value)) }
  }, [tide])
  // A fixed 0..1 axis would flatten typical 0.0x values into invisible slivers; a fix that hurts
  // is reported as a negative delta, so the domain keeps a floor below zero.
  const domainMin = floor < 0 ? floor * 1.15 : 0
  const domainMax = Math.max(0.05, peak * 1.1)
  const ticks = useMemo(() => {
    const step = TIDE_TICK_STEPS.find((s) => (domainMax - domainMin) / s <= 5) ?? 1
    const out: number[] = []
    for (let v = Math.ceil(domainMin / step - 1e-9) * step; v <= domainMax + 1e-9; v += step)
      out.push(Number(v.toFixed(2)))
    return out
  }, [domainMin, domainMax])
  const empty = rows.every((r) => r.value === 0)

  return (
    <Card className="min-w-0 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">TIDE error breakdown</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">AP50 recoverable by fixing each error type (oracle).</p>
        </div>
        <div role="group" aria-label="TIDE view" className="flex shrink-0 rounded-md border p-0.5">
          {(['chart', 'table'] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
              className={cn('cursor-pointer rounded px-2 py-1 text-xs transition-colors',
                view === v ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {v === 'chart' ? 'Chart' : 'Table'}
            </button>
          ))}
        </div>
      </div>

      {view === 'table' ? (
        <figure className="mt-3 min-w-0">
          <table className="w-full text-sm">
            <caption className="sr-only">TIDE delta AP50 by error type</caption>
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th scope="col" className="py-1.5 font-medium">Error type</th>
                <th scope="col" className="py-1.5 text-right font-medium">ΔAP50</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-b last:border-0">
                  <th scope="row" className="py-1.5 text-left font-normal">{r.long}</th>
                  <td className={cn('py-1.5 text-right tabular-nums', peak > 0 && r.value === peak && 'font-semibold')}>
                    {r.value.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      ) : empty ? (
        <p className="mt-3 text-sm text-muted-foreground">No AP50 recoverable at this threshold.</p>
      ) : (
        <figure className="mt-3 min-w-0">
          <div className="relative h-56">
            <div className="h-full" aria-hidden="true">
              <ResponsiveContainer>
                <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 78, bottom: 0, left: 0 }}>
                  <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 3" />
                  <XAxis type="number" domain={[domainMin, domainMax]} ticks={ticks} height={18}
                    tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                    tickLine={false} axisLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
                  <YAxis type="category" dataKey="label" width={52}
                    tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} />
                  {domainMin < 0 ? <ReferenceLine x={0} stroke="var(--border)" /> : null}
                  <Tooltip cursor={{ fill: 'var(--muted)' }} formatter={(v: number) => [v.toFixed(3), 'ΔAP50']} />
                  <Bar dataKey="value" barSize={14} radius={[0, 3, 3, 0]} isAnimationActive={false}>
                    {rows.map((r) => (
                      <Cell key={r.key} fill="var(--primary)" fillOpacity={r.value === peak ? 1 : 0.32} />
                    ))}
                    <LabelList dataKey="value" content={<TideValueLabel peak={peak} uniquePeak={uniquePeak} />} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <span aria-hidden="true" className="pointer-events-none absolute bottom-0 right-0 text-[10px] text-muted-foreground">ΔAP50</span>
          </div>
          <figcaption className="mt-2">
            <ul className="sr-only">
              {rows.map((r) => <li key={r.key}>{r.long}: {r.value.toFixed(3)} AP50 recoverable</li>)}
            </ul>
            <p className="text-[11px] text-muted-foreground">
              Every scored detection is classified. Larger deltas are the errors worth fixing first.
            </p>
          </figcaption>
        </figure>
      )}
    </Card>
  )
}

export function EvalPanel({ ev, images, task }: { ev: ModelEval; images?: Record<string, string>; task: ModelItem['task'] }) {
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

      {ev.tide ? <TideCard tide={ev.tide} /> : null}

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
