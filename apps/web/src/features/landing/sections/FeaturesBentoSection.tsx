import type { ReactNode } from 'react'
import {
  Boxes, Gauge, Radio, Sparkles, Timer, TriangleAlert, User, UserCheck, type LucideIcon,
} from 'lucide-react'
import { classColor } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { DotGrid, Reveal, SectionHeading, SectionShell, TagPill } from '../primitives'

// A precise instrument, not generic SaaS: solid data surfaces, hairline rules,
// class-colour chips and tabular numerals. The accent panel is the one bold surface.

const CARD = 'group relative flex flex-col gap-4 overflow-hidden rounded-3xl border bg-card p-5 lift sm:p-6'
const H3 = 'text-xl font-semibold tracking-[-0.03em] [font-stretch:90%] sm:text-2xl'

/** Framed mock panel. `tone` carries the container role and the text colour the dot grid inherits. */
function MockPanel({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <div className={cn('relative mt-auto overflow-hidden rounded-2xl border p-3 sm:p-4', tone)}>
      <DotGrid />
      <div className="relative">{children}</div>
    </div>
  )
}

function CardHeading({ title, body }: { title: string; body: string }) {
  return (
    <div className="space-y-2">
      <h3 className={H3}>{title}</h3>
      <p className="text-pretty text-sm leading-relaxed text-muted-foreground">{body}</p>
    </div>
  )
}

// ---------- (a) auto-label review table -------------------------------------

type Source = 'AI' | 'Human'

const LABEL_ROWS: { name: string; count: number; confidence: number; source: Source; colour: string }[] = [
  { name: 'Helmet', count: 412, confidence: 0.94, source: 'AI', colour: classColor(0) },
  { name: 'Vest', count: 388, confidence: 0.91, source: 'AI', colour: classColor(1) },
  { name: 'Person', count: 301, confidence: 0.97, source: 'Human', colour: classColor(2) },
  { name: 'No-helmet', count: 96, confidence: 0.72, source: 'AI', colour: classColor(5) },
]

function SourceChip({ source }: { source: Source }) {
  if (source === 'AI') {
    return (
      <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
        <Sparkles className="size-3" aria-hidden />
        AI
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border bg-card px-1.5 py-0.5 text-[10px] font-medium text-foreground">
      <User className="size-3" aria-hidden />
      Human
    </span>
  )
}

/** Three-block confidence meter: value is always printed next to it, so the blocks are redundant encoding. */
function ConfidenceMeter({ value }: { value: number }) {
  const filled = Math.max(1, Math.round(value * 3))
  return (
    <span aria-hidden className="inline-flex items-end gap-[2px]">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cn('h-2.5 w-1 rounded-[1px]', i < filled ? 'bg-primary' : 'bg-border')} />
      ))}
    </span>
  )
}

function AutoLabelCard() {
  return (
    <Reveal delay={0} className="flex min-w-0 lg:col-span-2">
      <article className={cn(CARD, 'w-full min-w-0')}>
        <TagPill className="self-start" icon={<Sparkles className="size-4" aria-hidden />}>Auto-label</TagPill>
        <CardHeading
          title="Optional SAM 3.1 and VLM checks."
          body="Connect SAM 3.1 and a vision model to the worker and masks arrive with a class and a confidence, marked AI until a person touches them."
        />
        <MockPanel tone="bg-accent text-accent-foreground">
          <div className="mb-2 flex items-baseline justify-between gap-2 text-[10px] font-medium">
            <span>Batch 042 · review queue</span>
            <span className="tabular-nums">1,197 masks · AI 75%</span>
          </div>
          <div className="overflow-hidden rounded-xl border bg-card">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[260px] border-collapse text-left">
                <caption className="sr-only">Sample auto-label review queue with class, count, confidence and source</caption>
                <thead>
                  <tr className="border-b text-[10px] text-muted-foreground">
                    <th scope="col" className="px-2 py-1.5 font-medium sm:px-2.5">Class</th>
                    <th scope="col" className="px-2 py-1.5 text-right font-medium sm:px-2.5">Count</th>
                    <th scope="col" className="px-2 py-1.5 text-right font-medium sm:px-2.5">Confidence</th>
                    <th scope="col" className="px-2 py-1.5 font-medium sm:px-2.5">Source</th>
                  </tr>
                </thead>
                <tbody className="text-[11px] sm:text-xs">
                  {LABEL_ROWS.map((row) => (
                    <tr key={row.name} className="border-b border-border/60 last:border-0">
                      <th scope="row" className="px-2 py-1.5 font-normal sm:px-2.5">
                        <span className="flex items-center gap-1.5 whitespace-nowrap">
                          <span aria-hidden className="size-1.5 shrink-0 rounded-[2px]" style={{ background: row.colour }} />
                          <span className="font-medium text-foreground">{row.name}</span>
                        </span>
                      </th>
                      <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground sm:px-2.5">{row.count}</td>
                      <td className="px-2 py-1.5 sm:px-2.5">
                        <span className="flex items-center justify-end gap-1.5 whitespace-nowrap">
                          <span className="tabular-nums text-foreground">{row.confidence.toFixed(2)}</span>
                          <ConfidenceMeter value={row.confidence} />
                        </span>
                      </td>
                      <td className="px-2 py-1.5 sm:px-2.5">
                        <SourceChip source={row.source} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </MockPanel>
      </article>
    </Reveal>
  )
}

// ---------- (b) model families ----------------------------------------------

const FAMILIES = [
  { name: 'YOLO', licence: 'AGPL-3.0' },
  { name: 'RT-DETR', licence: 'AGPL-3.0' },
  { name: 'YOLO-World', licence: 'AGPL-3.0' },
  { name: 'RF-DETR', licence: 'Apache-2.0' },
  { name: 'D-FINE', licence: 'Apache-2.0' },
  { name: 'RT-DETRv2', licence: 'Apache-2.0' },
]

function TrainingCard() {
  return (
    <Reveal delay={60} className="flex min-w-0 lg:col-span-1">
      <article className={cn(CARD, 'w-full min-w-0')}>
        <TagPill className="self-start" icon={<Boxes className="size-4" aria-hidden />}>Training</TagPill>
        <CardHeading
          title="One trainer, six families."
          body="Which families the trainer can run depends on the connected worker — pick by speed, licence or accuracy, the recipe stays the same."
        />
        <MockPanel tone="bg-secondary text-secondary-foreground">
          <ul className="flex flex-wrap gap-1.5">
            {FAMILIES.map((family) => (
              <li key={family.name}>
                <span className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-2 py-1.5">
                  <span className="text-xs font-medium text-foreground">{family.name}</span>
                  <span className="rounded border border-border px-1 py-px text-[9px] font-medium tabular-nums text-muted-foreground">
                    {family.licence}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] text-muted-foreground">Licences as reported by the model catalog</p>
        </MockPanel>
      </article>
    </Reveal>
  )
}

// ---------- (c) evaluation leaderboard --------------------------------------

const RUNS: { ref: string; model?: string; map: number }[] = [
  { ref: 'trained:842', model: 'D-FINE-M', map: 0.512 },
  { ref: 'yolo26m', map: 0.487 },
  { ref: 'rfdetr-l', map: 0.471 },
]

const LEADERBOARD_COLS = 'grid grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-2.5'

function EvaluationCard() {
  return (
    <Reveal delay={120} className="flex min-w-0 lg:col-span-1">
      <article className={cn(CARD, 'w-full min-w-0')}>
        <TagPill className="self-start" icon={<Gauge className="size-4" aria-hidden />}>Evaluation</TagPill>
        <CardHeading
          title="Numbers you can defend."
          body="Every run is scored by the same pycocotools evaluator on the held-out test split."
        />
        <MockPanel tone="bg-tertiary-container text-foreground">
          <div className={cn(LEADERBOARD_COLS, 'px-2 pb-1.5 text-[10px] text-muted-foreground')}>
            <span aria-hidden>#</span>
            <span>Run</span>
            <span className="text-right">mAP50-95</span>
          </div>
          <ol className="space-y-1.5">
            {RUNS.map((run, i) => (
              <li
                key={run.ref}
                className={cn(
                  LEADERBOARD_COLS,
                  'rounded-lg border bg-card px-2 py-2 text-xs',
                  i === 0 && 'ring-1 ring-primary',
                )}
              >
                <span className="text-center text-[10px] font-semibold tabular-nums text-muted-foreground">{i + 1}</span>
                <span className="flex min-w-0 items-baseline gap-1.5">
                  <span className="truncate font-medium text-foreground">{run.ref}</span>
                  {run.model && <span className="truncate text-[10px] text-muted-foreground">{run.model}</span>}
                </span>
                <span className="text-right font-semibold tabular-nums text-foreground">{run.map.toFixed(3)}</span>
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[10px] text-muted-foreground">test split · 999 images · conf 0.41</p>
        </MockPanel>
      </article>
    </Reveal>
  )
}

// ---------- (d) deploy event timeline ---------------------------------------

type Tone = { dot: string; icon: string }

const TONES: Record<'success' | 'warning' | 'info', Tone> = {
  success: { dot: 'bg-success', icon: 'text-success' },
  warning: { dot: 'bg-warning', icon: 'text-warning' },
  info: { dot: 'bg-info', icon: 'text-info' },
}

const EVENTS: { label: string; time: string; tone: keyof typeof TONES; icon: LucideIcon; state: 'reviewed' | 'auto' }[] = [
  { label: 'Person entered Zone A · Gate 2', time: '14:02', tone: 'success', icon: UserCheck, state: 'auto' },
  { label: 'No-helmet detected · Line 3', time: '14:03', tone: 'warning', icon: TriangleAlert, state: 'reviewed' },
  { label: 'Forklift dwell 24 s · Bay 4', time: '14:07', tone: 'info', icon: Timer, state: 'auto' },
]

function DeployCard() {
  return (
    <Reveal delay={180} className="flex min-w-0 lg:col-span-2">
      <article className={cn(CARD, 'w-full min-w-0')}>
        <TagPill className="self-start" icon={<Radio className="size-4" aria-hidden />}>Deploy</TagPill>
        <CardHeading
          title="Ship to every camera."
          body="Zones, line crossings and dwell rules run in the stream manager, with a 30-second cooldown per event."
        />
        <MockPanel tone="bg-muted text-foreground">
          <div className="overflow-hidden rounded-xl border bg-card">
            <ol className="relative">
              <span aria-hidden className="absolute bottom-4 left-[15px] top-4 w-0.5 bg-border" />
              {EVENTS.map((event) => {
                const Icon = event.icon
                const tone = TONES[event.tone]
                return (
                  <li
                    key={event.time}
                    className="relative flex items-center gap-2 border-b border-border/60 py-2.5 pl-7 pr-2.5 last:border-0 sm:gap-2.5 sm:py-3 sm:pl-8 sm:pr-3"
                  >
                    <span
                      aria-hidden
                      className={cn('absolute left-[12px] top-1/2 size-2 -translate-y-1/2 rounded-full ring-4 ring-card', tone.dot)}
                    />
                    <Icon aria-hidden className={cn('size-4 shrink-0', tone.icon)} />
                    <span className="min-w-0 flex-1 text-[11px] leading-snug sm:text-xs">{event.label}</span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <time dateTime={event.time} className="text-[10px] tabular-nums text-muted-foreground">{event.time}</time>
                      <span className="rounded-full border bg-card px-1.5 py-px text-[9px] font-medium text-muted-foreground">
                        {event.state}
                      </span>
                    </span>
                  </li>
                )
              })}
            </ol>
          </div>
        </MockPanel>
      </article>
    </Reveal>
  )
}

// ---------- section ---------------------------------------------------------

export default function FeaturesBentoSection() {
  return (
    <SectionShell id="models" aria-labelledby="models-title" className="py-20 sm:py-28 lg:py-32">
      <SectionHeading
        id="models-title"
        className="items-start"
        tag="The platform"
        title="Everything from pixels to production"
        intro="Auto-label, train, evaluate and deploy without exporting a ZIP."
      />
      <div className="mt-10 grid gap-4 sm:mt-12 lg:grid-cols-3">
        <AutoLabelCard />
        <TrainingCard />
        <EvaluationCard />
        <DeployCard />
      </div>
    </SectionShell>
  )
}
