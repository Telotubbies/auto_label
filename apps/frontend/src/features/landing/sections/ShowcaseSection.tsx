import { BadgeCheck, ScanLine, ZoomIn } from 'lucide-react'
import { classColor } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { CornerMarks, MockWindow, Reveal, SectionHeading, SectionShell, TagPill } from '../primitives'

// ---------------------------------------------------------------------------
// Local mock data. Everything here is illustrative UI, not a live query.
// ---------------------------------------------------------------------------

const CHIPS = [
  { label: 'All', count: '12,480', selected: true },
  { label: 'Unlabeled', count: '214', selected: false },
]

const THUMBNAILS = [
  [{ x: 12, y: 24, w: 34, h: 58, cls: 0 }, { x: 50, y: 14, w: 20, h: 20, cls: 1 }],
  [{ x: 22, y: 16, w: 38, h: 66, cls: 0 }, { x: 28, y: 44, w: 28, h: 26, cls: 2 }],
  [{ x: 10, y: 32, w: 30, h: 50, cls: 0 }],
  [{ x: 32, y: 10, w: 34, h: 38, cls: 1 }, { x: 18, y: 40, w: 52, h: 44, cls: 0 }],
  [{ x: 16, y: 20, w: 26, h: 30, cls: 1 }, { x: 30, y: 50, w: 44, h: 36, cls: 2 }],
  [{ x: 26, y: 18, w: 44, h: 64, cls: 0 }],
]

const SPLITS = [
  { label: 'train', count: '9,984', pct: 80, bar: 'bg-primary' },
  { label: 'valid', count: '1,497', pct: 12, bar: 'bg-secondary-foreground/40' },
  { label: 'test', count: '999', pct: 8, bar: 'bg-muted-foreground/30' },
]

/** Segmentation masks in the 400 x 300 frame coordinate space. */
const MASKS: Array<{ cls: number; points: string; handles: Array<[number, number]> }> = [
  {
    cls: 0,
    points: '102,238 96,150 106,108 132,96 156,110 164,170 158,238',
    handles: [[102, 238], [96, 150], [132, 96], [164, 170], [158, 238]],
  },
  {
    cls: 1,
    points: '116,120 118,102 134,94 150,102 150,120 134,126',
    handles: [[116, 120], [134, 94], [150, 120], [134, 126]],
  },
  {
    cls: 2,
    points: '106,150 158,150 154,200 132,208 104,198',
    handles: [[106, 150], [158, 150], [132, 208], [104, 198]],
  },
]

const LABELS = [
  { text: 'helmet 0.94', cls: 1, pos: 'left-[38%] top-[27%]' },
  { text: 'vest 0.91', cls: 2, pos: 'left-[35%] top-[45%]' },
  { text: 'person 0.97', cls: 0, pos: 'left-[40%] top-[63%]' },
]

const STATS = [
  { value: '0.874', label: 'mAP50' },
  { value: '41 ms', label: 'p95 latency' },
  { value: '12,480', label: 'images' },
]

const HEALTH = [
  { label: 'Helmet', pct: 96, bar: 'bg-primary' },
  { label: 'Vest', pct: 93, bar: 'bg-tertiary' },
  { label: 'Person', pct: 98, bar: 'bg-primary/60' },
  { label: 'No-helmet', pct: 71, bar: 'bg-muted-foreground/40' },
]

// ---------------------------------------------------------------------------
// Small drawing helpers
// ---------------------------------------------------------------------------

/** Worker silhouette: head, torso and two legs from rounded blocks. */
function Figure({ className, tone = 'bg-foreground/20' }: { className?: string; tone?: string }) {
  return (
    <div aria-hidden className={cn('absolute', className)}>
      <div className={cn('absolute left-1/2 top-0 h-[21%] w-[50%] -translate-x-1/2 rounded-full', tone)} />
      <div className={cn('absolute left-1/2 top-[23%] h-[45%] w-[84%] -translate-x-1/2 rounded-t-[42%] rounded-b-[12%]', tone)} />
      <div className={cn('absolute bottom-0 left-[14%] h-[34%] w-[24%] rounded-b-sm', tone)} />
      <div className={cn('absolute bottom-0 right-[14%] h-[34%] w-[24%] rounded-b-sm', tone)} />
    </div>
  )
}

const THUMB_FIGURES = [
  { left: 12, height: 56 },
  { left: 46, height: 62 },
  null,
  { left: 52, height: 54 },
  { left: 10, height: 50 },
  null,
]

function Thumbnail({ index, boxes }: { index: number; boxes: Array<{ x: number; y: number; w: number; h: number; cls: number }> }) {
  const figure = THUMB_FIGURES[index]
  return (
    <div className="relative aspect-[4/3] overflow-hidden rounded-md border border-border/70 bg-gradient-to-br from-muted to-accent/25">
      <div aria-hidden className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-background/40 to-transparent" />
      {figure ? (
        <div className="absolute" style={{ left: `${figure.left}%`, bottom: '12%', width: '30%', height: `${figure.height}%` }}>
          <Figure className="inset-0" tone="bg-foreground/10" />
        </div>
      ) : (
        <div aria-hidden className="absolute bottom-[12%] left-[16%] h-[38%] w-[40%]">
          <div className="absolute inset-x-0 bottom-0 h-1/2 rounded-sm bg-foreground/10" />
          <div className="absolute bottom-1/2 left-[18%] h-[38%] w-[54%] rounded-sm bg-foreground/10" />
        </div>
      )}
      {boxes.map((box) => (
        <span
          key={`${box.x}-${box.y}-${box.cls}`}
          aria-hidden
          className="absolute rounded-[2px] border-[1.5px]"
          style={{
            left: `${box.x}%`,
            top: `${box.y}%`,
            width: `${box.w}%`,
            height: `${box.h}%`,
            borderColor: classColor(box.cls),
          }}
        />
      ))}
      <span className="absolute left-1 top-1 rounded-[3px] bg-card px-1 text-[11px] font-medium leading-[1.35] tabular-nums text-foreground">
        {String(index + 1).padStart(2, '0')}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// The three panels of the app window
// ---------------------------------------------------------------------------

function DatasetPanel() {
  return (
    <div className="order-3 flex flex-col gap-4 p-4 sm:p-5 lg:order-1 lg:border-r lg:border-border">
      <h3 className="text-sm font-semibold tracking-[-0.01em] [font-stretch:90%]">Dataset</h3>

      <div className="flex flex-wrap gap-1.5">
        {CHIPS.map((chip) => (
          <span
            key={chip.label}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums',
              chip.selected
                ? 'border-foreground/25 bg-muted text-foreground'
                : 'border-border bg-card text-muted-foreground',
            )}
          >
            {chip.selected && <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-primary" />}
            {chip.label} · {chip.count}
          </span>
        ))}
      </div>

      <div aria-hidden className="grid grid-cols-3 gap-1.5 lg:grid-cols-2">
        {THUMBNAILS.map((boxes, i) => <Thumbnail key={i} index={i} boxes={boxes} />)}
      </div>

      <div className="space-y-2.5">
        {SPLITS.map((split) => (
          <div key={split.label}>
            <div className="flex items-baseline justify-between gap-2 text-[11px]">
              <span className="text-muted-foreground">{split.label}</span>
              <span className="font-medium tabular-nums text-foreground">{split.count}</span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
              <div className={cn('h-full rounded-full', split.bar)} style={{ width: `${split.pct}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border pt-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-primary" />
          Auto-label on
        </span>
        <span className="tabular-nums">Synced 14:02</span>
      </div>
    </div>
  )
}

function FramePanel() {
  return (
    <div className="order-1 flex flex-col gap-3 border-b border-border p-4 sm:p-5 lg:order-2 lg:border-b-0 lg:border-r lg:border-border">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-[-0.01em] [font-stretch:90%]">Frame 0142</h3>
        <div className="flex flex-wrap items-center gap-1.5">
          <TagPill icon={<ScanLine size={16} aria-hidden />}>SAM 3.1</TagPill>
          <TagPill icon={<BadgeCheck size={16} aria-hidden />}>VLM verified</TagPill>
        </div>
      </div>

      <div
        role="img"
        aria-label="Annotated frame: a worker in a hard hat and high-visibility vest on a factory floor, with segmentation masks for person, helmet and vest drawn beside a labeling machine."
        className="relative aspect-[4/3] w-full select-none overflow-hidden rounded-lg border border-border/70 bg-gradient-to-b from-muted via-accent/20 to-accent/50"
      >
        <div aria-hidden className="absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_-10%,var(--color-card),transparent_70%)]" />
        <div aria-hidden className="absolute inset-0 bg-[radial-gradient(var(--color-border)_1px,transparent_1px)] opacity-50 [background-size:14px_14px]" />
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-[22%] bg-gradient-to-b from-transparent to-muted/80" />
        <div aria-hidden className="absolute inset-x-0 bottom-[22%] h-px bg-border" />

        <div aria-hidden className="absolute bottom-[22%] left-[6%] h-[13%] w-[11%] rounded-sm border border-border bg-secondary/50" />
        <div aria-hidden className="absolute bottom-[35%] left-[8%] h-[9%] w-[7%] rounded-sm border border-border bg-secondary/40" />
        <div aria-hidden className="absolute bottom-[22%] left-[55%] h-[34%] w-[20%] rounded-md border border-border bg-secondary/60">
          <div className="absolute inset-x-[12%] top-[10%] h-[42%] rounded-sm border border-border bg-card/70" />
          <div className="absolute inset-x-[12%] bottom-[10%] h-[18%] rounded-sm bg-tertiary/30" />
          <div className="absolute right-[10%] top-[62%] h-1.5 w-1.5 rounded-full bg-primary/60" />
        </div>
        <Figure className="bottom-[22%] left-[24%] h-[46%] w-[14%]" />
        <Figure className="bottom-[22%] left-[80%] h-[27%] w-[8%]" tone="bg-foreground/12" />

        <svg viewBox="0 0 400 300" className="absolute inset-0 h-full w-full" aria-hidden>
          {MASKS.map((mask) => {
            const color = classColor(mask.cls)
            return (
              <g key={mask.cls}>
                <polygon points={mask.points} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.75} strokeLinejoin="round" />
                {mask.handles.map(([x, y]) => (
                  <rect
                    key={`${x}-${y}`}
                    x={x - 3}
                    y={y - 3}
                    width={6}
                    height={6}
                    rx={1}
                    stroke={color}
                    strokeWidth={1.5}
                    style={{ fill: 'var(--card)' }}
                  />
                ))}
              </g>
            )
          })}
        </svg>

        {LABELS.map((label) => (
          <div key={label.text} className={cn('absolute z-10 flex items-center', label.pos)}>
            <span aria-hidden className="h-px w-3 bg-foreground/30 sm:w-4" />
            <span className="flex items-center gap-1 rounded-[5px] border border-border bg-card px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-foreground shadow-sm">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: classColor(label.cls) }} />
              {label.text}
            </span>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        <ZoomIn size={16} aria-hidden className="text-muted-foreground" />
        {['SAM 3.1', '0.94 confidence', '12/12 reviewed'].map((item) => (
          <span
            key={item}
            className="rounded-md border border-border/70 bg-muted/60 px-1.5 py-0.5 font-medium tabular-nums text-muted-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function MetricsPanel() {
  return (
    <div className="order-2 flex flex-col gap-5 border-b border-border p-4 sm:p-5 lg:order-3 lg:border-b-0">
      <div className="space-y-4">
        {STATS.map((stat) => (
          <div key={stat.label}>
            <div className="text-2xl font-semibold leading-none tracking-[-0.03em] tabular-nums [font-stretch:88%]">{stat.value}</div>
            <div className="mt-1 text-[11px] font-medium text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="mt-auto">
        <div className="h-px bg-border" />
        <h3 className="mt-4 text-xs font-semibold [font-stretch:90%]">Class health</h3>
        <div className="mt-3 space-y-2.5">
          {HEALTH.map((row) => (
            <div key={row.label}>
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="font-medium tabular-nums text-foreground">{row.pct}%</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                <div className={cn('h-full rounded-full', row.bar)} style={{ width: `${row.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------

export default function ShowcaseSection() {
  return (
    <SectionShell id="product" aria-labelledby="product-title" className="py-20 sm:py-28 lg:py-32">
      <SectionHeading
        id="product-title"
        tag="The workspace"
        title="One window for the whole loop"
        intro="Dataset, canvas, versions and metrics share one screen — and one source of truth."
        align="center"
      />

      <div className="relative isolate mt-12 sm:mt-14 lg:mt-16">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 -bottom-12 -z-10 flex justify-center">
          <div className="h-20 w-2/3 rounded-full bg-primary/30 blur-3xl" />
        </div>
        <div aria-hidden className="pointer-events-none absolute inset-x-[8%] -bottom-4 -z-10 h-px bg-gradient-to-r from-transparent via-primary/70 to-transparent" />

        <Reveal className="relative">
          <CornerMarks className="-inset-3 text-foreground" />
          <MockWindow
            title="PPE Detection · v3"
            meta="12,480 images · 8 classes"
            bodyClassName="grid grid-cols-1 lg:min-h-[28rem] lg:grid-cols-[15rem_minmax(0,1fr)_13rem]"
          >
            <DatasetPanel />
            <FramePanel />
            <MetricsPanel />
          </MockWindow>
        </Reveal>
      </div>
    </SectionShell>
  )
}
