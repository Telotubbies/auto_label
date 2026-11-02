// Section 5 — the inverted "workflow" band plus the light rounded-top sentence + preview tabs.
// The orbit is the only decorative flourish on the page: everything else here is rules and numbers.
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { Cpu, Rocket, Tag } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CornerMarks, DotGrid, Reveal, TagPill } from '../primitives'

// ---------- data ---------------------------------------------------------------

const STEPS = [
  { n: '01', title: 'Label', body: 'Upload a folder, let SAM 3.1 draft masks when you connect it, and review only what the VLM marks uncertain.' },
  { n: '02', title: 'Train', body: 'Freeze a version, pick a family, and watch loss and mAP without leaving the page.' },
  { n: '03', title: 'Deploy', body: 'Attach the model to a stream, draw zones, and read events as they land.' },
]

/** Dot positions are polar → percentages of the orbit square (f = radius fraction). Chip side avoids the centre node. */
const ORBIT_NODES = [
  { label: 'SAM 3.1', left: 82.1, top: 11.7, chip: 'left' },
  { label: 'YOLO', left: 70.2, top: 82.4, chip: 'above' },
  { label: 'RT-DETR', left: 12.6, top: 42.1, chip: 'above' },
  { label: 'CCTV', left: 3.0, top: 67.1, chip: 'right' },
  { label: 'VLM', left: 74.0, top: 38.8, chip: 'right' },
] as const

const CHIP_SIDE = {
  left: 'right-full top-1/2 mr-2 -translate-y-1/2',
  right: 'left-full top-1/2 ml-2 -translate-y-1/2',
  above: 'bottom-full left-1/2 mb-2 -translate-x-1/2',
  below: 'top-full left-1/2 mt-2 -translate-x-1/2',
} as const

const TAB_IDS = ['label', 'train', 'deploy'] as const
type TabId = (typeof TAB_IDS)[number]

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))

// ---------- section ------------------------------------------------------------

export default function WorkflowDarkSection() {
  const bandRef = useRef<HTMLElement>(null)
  const [activeStep, setActiveStep] = useState(0)

  // Scroll progress through the band drives the current step. One passive listener, one rAF, one state
  // update per index change (React bails out when the value is unchanged).
  useEffect(() => {
    const el = bandRef.current
    if (!el) return
    let raf = 0
    const compute = () => {
      raf = 0
      const rect = el.getBoundingClientRect()
      const travel = Math.max(1, rect.height * 0.55)
      const progress = clamp01(-rect.top / travel)
      const next = progress < 0.34 ? 0 : progress < 0.67 ? 1 : 2
      setActiveStep((prev) => (prev === next ? prev : next))
    }
    const schedule = () => { if (!raf) raf = requestAnimationFrame(compute) }
    compute()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <>
      {/* -------- inverted band -------- */}
      <section
        id="workflow"
        ref={bandRef}
        aria-labelledby="workflow-title"
        className="relative overflow-hidden bg-foreground pb-28 pt-20 text-background dark:bg-popover dark:text-foreground sm:pb-36 sm:pt-28"
      >
        <span
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-1/3 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/20 blur-3xl"
        />
        <DotGrid className="text-background/30 dark:text-foreground/15" />

        <div className="relative mx-auto w-full max-w-6xl px-5 sm:px-8">
          <Reveal>
            <div className="flex flex-col items-start gap-4">
              <TagPill className="border-background/25 bg-background/10 text-background dark:border-foreground/25 dark:bg-foreground/10 dark:text-foreground">Workflow</TagPill>
              <h2
                id="workflow-title"
                className="max-w-2xl text-balance text-3xl font-semibold leading-[1.05] tracking-[-0.035em] text-background [font-stretch:88%] dark:text-foreground sm:text-4xl md:text-5xl"
              >
                From raw images to live cameras
              </h2>
              <p className="max-w-lg text-pretty text-base leading-relaxed text-background/75 dark:text-foreground/75 sm:text-lg">
                Three steps, no export scripts. The same project moves from first mask to live event.
              </p>
            </div>
          </Reveal>

          <Reveal delay={120} className="mt-12">
            <div className="grid gap-10 lg:grid-cols-2 lg:gap-16">
              {/* progressive step list — read-only, the sequence is the content */}
              <div className="lg:sticky lg:top-24 lg:self-start">
                <ol className="space-y-3">
                  {STEPS.map((step, i) => {
                    const current = i === activeStep
                    return (
                      <li
                        key={step.n}
                        aria-current={current ? 'step' : undefined}
                        className={cn(
                          'rounded-xl border border-l-2 px-4 py-3.5 transition-colors duration-300',
                          current
                            ? 'border-background/60 border-l-primary bg-background/10 dark:border-foreground/60 dark:bg-foreground/10'
                            : 'border-background/15 border-l-transparent bg-background/[0.04] dark:border-foreground/15 dark:bg-foreground/[0.04]',
                        )}
                      >
                        <div className="flex items-baseline gap-3">
                          <span
                            className={cn(
                              'text-[11px] font-medium tabular-nums tracking-[0.08em] transition-colors duration-300',
                              current ? 'text-background dark:text-foreground' : 'text-background/65 dark:text-foreground/65',
                            )}
                          >
                            {step.n}
                          </span>
                          <h3
                            className={cn(
                              'text-lg font-semibold leading-tight tracking-[-0.02em] [font-stretch:90%] transition-colors duration-300',
                              current ? 'text-background dark:text-foreground' : 'text-background/70 dark:text-foreground/70',
                            )}
                          >
                            {step.title}
                          </h3>
                        </div>
                        <p className="mt-1.5 text-sm leading-relaxed text-background/75 dark:text-foreground/75">{step.body}</p>
                      </li>
                    )
                  })}
                </ol>
                <p className="mt-4 text-xs leading-relaxed text-background/70 dark:text-foreground/70">
                  SAM 3.1 and the VLM are optional add-ons: connect them to the worker and step 01 drafts and checks
                  masks for you. Without them, labeling stays manual.
                </p>
              </div>

              {/* orbit */}
              <div aria-hidden="true" className="relative flex min-h-[26rem] items-center justify-center lg:min-h-[34rem]">
                <div className="relative aspect-square w-full max-w-[34rem]">
                  <CornerMarks className="text-background dark:text-foreground" />

                  {/* reticle */}
                  <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-background/10 dark:bg-foreground/10" />
                  <span className="pointer-events-none absolute inset-y-0 left-1/2 w-px bg-background/10 dark:bg-foreground/10" />

                  {/* rings: outer 17rem, middle 13rem (dashed), inner 9rem at full size */}
                  <span className="absolute inset-0 rounded-full border border-background/10 dark:border-foreground/10" />
                  <span className="absolute left-1/2 top-1/2 h-[76%] w-[76%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-background/20 dark:border-foreground/20" />
                  <span className="absolute left-1/2 top-1/2 h-[53%] w-[53%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-background/15 dark:border-foreground/15" />

                  {/* one static arc sweep with an arrowhead at its end */}
                  <svg viewBox="0 0 400 400" className="pointer-events-none absolute inset-0 h-full w-full">
                    <path d="M74.8 112.4A152.8 152.8 0 0 1 226.5 49.5" fill="none" strokeWidth={5} strokeLinecap="round" className="stroke-background/20 dark:stroke-foreground/20" />
                    <path d="M74.8 112.4A152.8 152.8 0 0 1 226.5 49.5" fill="none" strokeWidth={1.75} strokeLinecap="round" className="stroke-primary/60" />
                  </svg>
                  <span className="absolute left-[56.6%] top-[12.4%] flex h-5 w-5 -translate-x-1/2 -translate-y-1/2 rotate-[10deg] items-center justify-center rounded-full border border-primary/50 bg-background/10 dark:bg-foreground/10">
                    <span className="h-0 w-0 border-y-[4.5px] border-y-transparent border-l-[7px] border-l-primary/70" />
                  </span>

                  {/* hub */}
                  <div className="absolute left-1/2 top-1/2 flex w-max -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-2xl border border-background/25 bg-background/10 px-4 py-3 text-center dark:border-foreground/25 dark:bg-foreground/10">
                    <span className="h-2 w-2 rounded-full bg-primary shadow-[0_0_16px_4px] shadow-primary/50 ring-1 ring-background/30 dark:ring-foreground/30" />
                    <span className="text-sm font-semibold leading-none tracking-[-0.02em] text-background [font-stretch:90%] dark:text-foreground">LabelDesk</span>
                    <span className="text-[11px] leading-none text-background/70 dark:text-foreground/70">vision loop</span>
                  </div>

                  {/* nodes + labels */}
                  {ORBIT_NODES.map((node) => (
                    <span
                      key={node.label}
                      className="absolute -translate-x-1/2 -translate-y-1/2"
                      style={{ left: `${node.left}%`, top: `${node.top}%` }}
                    >
                      <span className="block h-2.5 w-2.5 rounded-full bg-primary shadow-[0_0_18px_4px] shadow-primary/50 ring-1 ring-background/30 dark:ring-foreground/30" />
                      <span
                        className={cn(
                          'absolute whitespace-nowrap rounded-full border border-background/25 bg-background/[0.06] px-2 py-0.5 text-[11px] font-medium leading-none text-background/80 dark:border-foreground/25 dark:bg-foreground/[0.06] dark:text-foreground/80',
                          CHIP_SIDE[node.chip],
                        )}
                      >
                        {node.label}
                      </span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* -------- light rounded-top block -------- */}
      <section
        aria-labelledby="moves-title"
        className="relative z-10 -mt-8 rounded-t-[2rem] bg-background pb-20 pt-16 sm:rounded-t-[2.5rem] sm:pb-28 sm:pt-20"
      >
        <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
          <Reveal>
            <h2
              id="moves-title"
              className="max-w-4xl text-2xl font-semibold leading-[1.25] tracking-[-0.03em] text-foreground [font-stretch:88%] sm:text-3xl lg:text-4xl"
            >
              With LabelDesk, teams{' '}
              <WordPill icon={<Tag aria-hidden className="size-4" />}>label</WordPill>{' '}
              data in minutes,{' '}
              <WordPill icon={<Cpu aria-hidden className="size-4" />}>train</WordPill>{' '}
              <span className="whitespace-nowrap">the right model,</span> and{' '}
              <WordPill icon={<Rocket aria-hidden className="size-4" />}>deploy</WordPill>{' '}
              it to every camera.
            </h2>
          </Reveal>

          <Reveal delay={90} className="mt-8">
            <WorkflowTabs />
          </Reveal>
        </div>
      </section>
    </>
  )
}

// ---------- sentence pill ------------------------------------------------------

function WordPill({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-0.5 align-middle text-accent-foreground">
      {icon}
      {children}
    </span>
  )
}

// ---------- tabs ---------------------------------------------------------------

function WorkflowTabs() {
  const [tab, setTab] = useState<TabId>('label')
  const tabRefs = useRef<Record<TabId, HTMLButtonElement | null>>({ label: null, train: null, deploy: null })

  const select = (next: TabId) => {
    setTab(next)
    tabRefs.current[next]?.focus()
  }

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const i = TAB_IDS.indexOf(tab)
    let next: TabId | null = null
    if (e.key === 'ArrowRight') next = TAB_IDS[(i + 1) % TAB_IDS.length]
    else if (e.key === 'ArrowLeft') next = TAB_IDS[(i + TAB_IDS.length - 1) % TAB_IDS.length]
    else if (e.key === 'Home') next = TAB_IDS[0]
    else if (e.key === 'End') next = TAB_IDS[TAB_IDS.length - 1]
    if (!next) return
    e.preventDefault()
    select(next)
  }

  return (
    <div>
      <div role="tablist" aria-label="Workflow preview" className="inline-flex rounded-full border bg-muted p-1">
        {TAB_IDS.map((id) => (
          <button
            key={id}
            ref={(el) => { tabRefs.current[id] = el }}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => setTab(id)}
            onKeyDown={onKeyDown}
            className={cn(
              'rounded-full px-4 py-1.5 text-sm font-medium transition-colors duration-150',
              tab === id
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {id === 'label' ? 'Label' : id === 'train' ? 'Train' : 'Deploy'}
          </button>
        ))}
      </div>

      <div className="mt-6 max-w-3xl">
        <div id="panel-label" role="tabpanel" aria-labelledby="tab-label" tabIndex={0} hidden={tab !== 'label'} className="min-h-[19rem]">
          <LabelPanel />
        </div>
        <div id="panel-train" role="tabpanel" aria-labelledby="tab-train" tabIndex={0} hidden={tab !== 'train'} className="min-h-[19rem]">
          <TrainPanel />
        </div>
        <div id="panel-deploy" role="tabpanel" aria-labelledby="tab-deploy" tabIndex={0} hidden={tab !== 'deploy'} className="min-h-[19rem]">
          <DeployPanel />
        </div>
      </div>
    </div>
  )
}

// ---------- panel chrome -------------------------------------------------------

/** Solid card with a fixed body height so swapping tabs never moves the page. */
function PanelCard({ title, meta, children }: { title: string; meta: string; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border bg-card text-card-foreground">
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <span className="truncate text-xs font-medium text-foreground">{title}</span>
        <span className="ml-auto shrink-0 text-[11px] tabular-nums text-muted-foreground">{meta}</span>
      </div>
      <div className="flex h-[17rem] flex-col p-4">{children}</div>
    </div>
  )
}

function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full border bg-muted px-2 py-0.5 text-[11px] font-medium text-foreground', className)}>
      {children}
    </span>
  )
}

// ---------- label panel --------------------------------------------------------

function LabelPanel() {
  return (
    <PanelCard title="Annotate · frame 0142" meta="SAM 3.1">
      <div className="relative h-[11rem] overflow-hidden rounded-lg border bg-muted">
        {/* back wall, floor, shelving rule */}
        <span className="absolute inset-x-0 top-0 h-[64%] bg-tertiary-container/45" />
        <span className="absolute inset-x-0 bottom-0 h-[36%] bg-secondary/40" />
        <span className="absolute inset-x-0 top-[64%] h-px bg-border" />
        <span className="absolute left-[64%] top-[14%] h-[46%] w-px bg-border" />
        <span className="absolute left-[64%] top-[14%] h-px w-[24%] bg-border" />
        <span className="absolute left-[64%] top-[34%] h-px w-[24%] bg-border" />

        {/* pallet stack + its mask */}
        <span className="absolute bottom-[24%] left-[72%] flex flex-col items-center">
          <span className="h-14 w-16 rounded-[3px] bg-foreground/15" />
          <span className="mt-1 h-1.5 w-20 rounded-full bg-foreground/20" />
          <span className="absolute -inset-2.5 rounded-md border border-dashed border-tertiary bg-tertiary/10" />
        </span>

        {/* person + its mask (mask hugs the figure at any frame width) */}
        <span className="absolute bottom-[24%] left-[27%] flex flex-col items-center">
          <span className="h-3.5 w-3.5 rounded-full bg-foreground/30" />
          <span className="mt-0.5 h-12 w-5 rounded-t-md rounded-b-sm bg-foreground/25" />
          <span className="absolute -inset-2.5 rounded-md border border-primary bg-primary/15" />
        </span>

        <CornerMarks className="text-foreground" />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Chip><span className="h-1.5 w-1.5 rounded-full bg-primary" />Person 0.96</Chip>
        <Chip><span className="h-1.5 w-1.5 rounded-full bg-tertiary" />Pallet 0.91</Chip>
        <Chip className="text-muted-foreground">2 of 27 flagged</Chip>
      </div>
    </PanelCard>
  )
}

// ---------- train panel --------------------------------------------------------

const CURVE = [0.12, 0.24, 0.31, 0.4, 0.44, 0.52, 0.58, 0.61, 0.67, 0.7, 0.74, 0.79, 0.82, 0.85, 0.874]
const POINTS = CURVE.map((v, i) => `${(1 + (i / (CURVE.length - 1)) * 278).toFixed(1)},${(60 - v * 52).toFixed(1)}`)
const LAST = POINTS[POINTS.length - 1].split(',')

const CLASS_SCORES = [
  { name: 'person', score: '0.91' },
  { name: 'helmet', score: '0.88' },
]

function TrainPanel() {
  return (
    <PanelCard title="Training · yolo26m" meta="epoch 24/60">
      <div className="flex h-24 items-end">
        <svg viewBox="0 0 280 64" preserveAspectRatio="none" className="h-24 w-full" aria-hidden="true">
          <line x1="1" y1="18" x2="279" y2="18" className="stroke-border" strokeWidth={1} strokeDasharray="3 4" />
          <line x1="1" y1="40" x2="279" y2="40" className="stroke-border" strokeWidth={1} strokeDasharray="3 4" />
          <polygon points={`1,60 ${POINTS.join(' ')} 279,60`} className="fill-primary/10" />
          <polyline points={POINTS.join(' ')} fill="none" strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" className="stroke-primary" />
          <circle cx={LAST[0]} cy={LAST[1]} r={2.6} className="fill-primary" />
        </svg>
      </div>
      <p className="mt-2 text-xs tabular-nums text-muted-foreground">epoch 24/60 · mAP50 0.874 · loss 0.41</p>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <span className="block h-full w-[40%] rounded-full bg-primary" />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Chip>yolo26m</Chip>
        <Chip className="text-muted-foreground">imgsz 640</Chip>
        <Chip className="text-muted-foreground">4 classes</Chip>
      </div>
      <ul className="mt-auto space-y-1.5 pt-4">
        {CLASS_SCORES.map(({ name, score }) => (
          <li key={name} className="flex items-center gap-2 text-[11px]">
            <span className="w-14 shrink-0 text-muted-foreground">{name}</span>
            <span className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
              <span className="block h-full rounded-full bg-foreground/25" style={{ width: `${Number(score) * 100}%` }} />
            </span>
            <span className="w-8 shrink-0 text-right tabular-nums text-foreground">{score}</span>
          </li>
        ))}
      </ul>
    </PanelCard>
  )
}

// ---------- deploy panel -------------------------------------------------------

const EVENTS = [
  { label: 'Person entered Zone A', time: '14:02:11' },
  { label: 'Vehicle crossed Gate 2', time: '14:03:47' },
]

function DeployPanel() {
  return (
    <PanelCard title="Gate 2 · live" meta="RTSP · 12 fps">
      <div className="relative h-[9.5rem] overflow-hidden rounded-lg border bg-muted">
        <span className="absolute inset-x-0 top-0 h-[44%] bg-tertiary-container/40" />
        <span className="absolute inset-x-0 bottom-0 h-[56%] bg-secondary/40" />
        <span className="absolute inset-x-0 top-[44%] h-px bg-border" />

        <div className="absolute bottom-[10%] left-[8%] h-[62%] w-[34%] rounded-md border-2 border-dashed border-primary/70 bg-primary/10">
          <span className="absolute -top-2.5 left-2 rounded bg-background px-1.5 py-0.5 text-[10px] font-medium text-foreground">Zone A</span>
        </div>
        <span className="absolute bottom-[18%] left-[19%] flex flex-col items-center">
          <span className="h-3 w-3 rounded-full bg-foreground/30" />
          <span className="mt-0.5 h-9 w-4 rounded-t-[5px] rounded-b-sm bg-foreground/25" />
        </span>

        <div className="absolute bottom-[10%] right-[6%] h-[46%] w-[26%] rounded-md border border-border bg-background/40">
          <span className="absolute -top-2.5 left-2 rounded bg-background px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Zone B</span>
        </div>
        <span className="absolute bottom-[16%] right-[12%] h-5 w-12 rounded-[4px] bg-foreground/15">
          <span className="absolute -top-2 left-2.5 h-2.5 w-6 rounded-t-[3px] bg-foreground/15" />
        </span>
      </div>
      <ul className="mt-3 space-y-1.5">
        {EVENTS.map((ev) => (
          <li key={ev.time} className="flex items-center gap-2 rounded-lg border bg-muted/60 px-2.5 py-1.5 text-[11px]">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span className="truncate font-medium text-foreground">{ev.label}</span>
            <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{ev.time}</span>
          </li>
        ))}
      </ul>
    </PanelCard>
  )
}
