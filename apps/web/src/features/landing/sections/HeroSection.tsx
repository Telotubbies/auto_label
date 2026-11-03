import { useEffect, useRef, useState } from 'react'
import { Camera, Menu, ScanLine, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Glass } from '@/components/glass'
import { classColor } from '@/lib/theme'
import { CornerMarks, Reveal, TagPill } from '../primitives'

const NAV_LINKS = [
  { label: 'Product', href: '#product' },
  { label: 'Models', href: '#models' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Docs', href: '#docs' },
]

/** Tiny class swatch + name, borrowed from the annotation class list. */
function ClassChip({ color, children }: { color: string; children: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-card px-1.5 py-0.5 text-[10px] leading-none text-foreground">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {children}
    </span>
  )
}

/** Annotation card: a SAM-style mask polygon with its editable vertices. */
function AnnotateCard({ className }: { className?: string }) {
  const mask = classColor(0)
  const helmet = classColor(1)
  const vertices = [[16, 24], [70, 14], [92, 44], [74, 78], [24, 72]]
  return (
    <Glass className={cn('rounded-xl p-3', className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[11px] font-medium text-foreground">Annotate · frame 0142</span>
        <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: mask }} />
      </div>
      <div className="relative mt-2 overflow-hidden rounded-md border border-border/60 bg-muted">
        <div className="aspect-[4/3]">
          <svg viewBox="0 0 120 90" className="h-full w-full" aria-hidden focusable="false">
            <polygon
              points={vertices.map((p) => p.join(',')).join(' ')}
              fill={mask}
              fillOpacity={0.25}
              stroke={mask}
              strokeWidth={2}
              strokeLinejoin="round"
            />
            {vertices.map(([x, y]) => (
              <rect
                key={`${x}-${y}`}
                x={x - 3}
                y={y - 3}
                width={6}
                height={6}
                fill="var(--card)"
                stroke={mask}
                strokeWidth={2}
              />
            ))}
          </svg>
        </div>
        <CornerMarks className="text-foreground" />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <ClassChip color={mask}>person</ClassChip>
        <ClassChip color={helmet}>helmet</ClassChip>
      </div>
      <div className="mt-2 border-t border-border/60 pt-1.5 text-[10px] leading-none text-muted-foreground">
        saved 2s ago
      </div>
    </Glass>
  )
}

/** Training card: headline metric and a rising mAP sparkline. */
function TrainCard({ className }: { className?: string }) {
  const points = [34, 33, 30, 31, 27, 24, 22, 19, 16, 12, 9, 6]
  const line = points.map((y, i) => `${(i * 120) / (points.length - 1)},${y}`).join(' ')
  return (
    <Glass className={cn('rounded-xl p-3', className)}>
      <div className="truncate text-[11px] font-medium text-foreground">Training · yolo26m</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold leading-none tracking-[-0.03em] tabular-nums text-foreground">0.874</span>
        <span className="text-[10px] text-muted-foreground">mAP50</span>
      </div>
      <svg viewBox="0 0 120 44" className="mt-2 h-12 w-full" aria-hidden focusable="false" preserveAspectRatio="none">
        <path d={`M0,44 L${line.replaceAll(' ', ' L')} L120,44 Z`} className="text-primary" fill="currentColor" fillOpacity={0.1} />
        <polyline
          points={line}
          className="text-primary"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <g className="text-muted-foreground/50">
          {[0, 24, 48, 72, 96, 120].map((x) => (
            <line key={x} x1={x} y1={40} x2={x} y2={44} stroke="currentColor" strokeWidth={1} vectorEffect="non-scaling-stroke" />
          ))}
        </g>
        <circle cx={120} cy={6} r={2.5} className="text-primary" fill="currentColor" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1.5 border-t border-border/60 pt-1.5 text-[10px] leading-none text-muted-foreground">
        GPU · 41 ms/img
      </div>
    </Glass>
  )
}

/** CCTV event card: one gate event and a non-colour-only live status. */
function CctvCard({ className }: { className?: string }) {
  return (
    <Glass className={cn('rounded-xl p-3', className)}>
      <div className="flex items-center gap-1.5">
        <Camera aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate text-[11px] font-medium text-foreground">Gate 2 · live</span>
      </div>
      <div className="mt-2 text-[11px] font-medium leading-snug text-foreground">Person entered Zone A</div>
      <div className="mt-0.5 text-[10px] leading-none tabular-nums text-muted-foreground">14:02 · camera 04</div>
      <div className="mt-2 flex items-center gap-1.5 border-t border-border/60 pt-1.5 text-[10px] leading-none text-muted-foreground">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-success" />
        live
      </div>
    </Glass>
  )
}

/** Class balance card: label, count and a thin proportional bar. */
function BalanceCard({ className }: { className?: string }) {
  const rows = [
    { label: 'Helmet', count: 412, bar: 'bg-primary' },
    { label: 'Vest', count: 388, bar: 'bg-tertiary' },
    { label: 'Person', count: 301, bar: 'bg-primary/55' },
    { label: 'No-helmet', count: 96, bar: 'bg-muted-foreground/35' },
  ]
  return (
    <Glass className={cn('rounded-xl p-3', className)}>
      <div className="truncate text-[11px] font-medium text-foreground">Class balance</div>
      <div className="mt-2 space-y-1.5">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-baseline justify-between gap-2 text-[10px] leading-none">
              <span className="truncate text-muted-foreground">{row.label}</span>
              <span className="shrink-0 tabular-nums text-foreground">{row.count}</span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
              <div className={cn('h-full rounded-full', row.bar)} style={{ width: `${(row.count / 412) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 border-t border-border/60 pt-1.5 text-[10px] leading-none text-muted-foreground">
        34.0k boxes · 4 classes
      </div>
    </Glass>
  )
}

/** Background layer: soft tiled grid, faded out with a radial mask. */
function TileField() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0"
      style={{
        maskImage: 'radial-gradient(ellipse at center, black, transparent 72%)',
        WebkitMaskImage: 'radial-gradient(ellipse at center, black, transparent 72%)',
      }}
    >
      <div className="grid h-full w-full content-center grid-cols-4 gap-2 p-2 sm:grid-cols-7 sm:gap-3 sm:p-3">
        {Array.from({ length: 35 }, (_, i) => (
          <div key={i} className="aspect-square rounded-2xl border border-border/60 bg-card/50" />
        ))}
      </div>
    </div>
  )
}

export default function HeroSection() {
  const [menuOpen, setMenuOpen] = useState(false)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const cardRefs = useRef<Array<HTMLDivElement | null>>([])

  // Escape closes the mobile menu and returns focus to its trigger.
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMenuOpen(false)
        toggleRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  // Parallax: at most 12px of drift, xl only, disabled under reduced motion.
  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const wide = matchMedia('(min-width: 1280px)')
    const speeds = [-1, 0.7, -0.6, 1]
    let frame = 0
    const apply = () => {
      frame = 0
      const drift = wide.matches ? Math.min(12, window.scrollY * 0.035) : 0
      cardRefs.current.forEach((el, i) => {
        if (!el) return
        el.style.transform = drift ? `translate3d(0, ${(drift * (speeds[i] ?? 0)).toFixed(1)}px, 0)` : ''
      })
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(apply) }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    apply()
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <>
      <header className="sticky top-0 z-50 px-3 sm:px-4">
        <Glass
          as="nav"
          aria-label="Main"
          className="mx-auto mt-3 flex max-w-6xl items-center gap-2 rounded-2xl px-3 py-2 sm:px-4"
        >
          <a href="/" className="flex shrink-0 items-center gap-2 rounded-md focus-visible:outline-offset-4">
            <span
              aria-hidden
              className="grid h-7 w-7 place-items-center rounded-md bg-primary text-[13px] font-semibold leading-none text-primary-foreground"
            >
              L
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-foreground">LabelDesk</span>
          </a>

          <div className="ml-2 hidden items-center gap-0.5 md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <a
              href="/login"
              className="hidden items-center rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
            >
              Log in
            </a>
            <a
              href="/signup"
              className="inline-flex h-9 items-center whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Start free
            </a>
            <button
              ref={toggleRef}
              type="button"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              aria-controls="hero-mobile-menu"
              onClick={() => setMenuOpen((v) => !v)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-card text-foreground transition-colors hover:bg-accent hover:text-accent-foreground md:hidden"
            >
              {menuOpen
                ? <X aria-hidden className="h-4 w-4" />
                : <Menu aria-hidden className="h-4 w-4" />}
            </button>
          </div>
        </Glass>

        {menuOpen && (
          <Glass
            id="hero-mobile-menu"
            className="absolute left-3 right-3 top-full mt-1 rounded-2xl p-2 md:hidden sm:left-4 sm:right-4"
          >
            <div className="flex flex-col">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  {link.label}
                </a>
              ))}
              <a
                href="/login"
                onClick={() => setMenuOpen(false)}
                className="mt-1 rounded-lg border-t border-border/70 px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Log in
              </a>
            </div>
          </Glass>
        )}
      </header>

      <section aria-labelledby="hero-title" className="relative overflow-hidden pb-12 pt-14 sm:pb-16 sm:pt-20">
        <TileField />

        <div className="relative mx-auto w-full max-w-[1400px] px-5 sm:px-8 xl:flex xl:min-h-[500px] xl:flex-col xl:justify-center">
          {/* Floating instrument cards — xl and up only. */}
          <div aria-hidden className="pointer-events-none absolute inset-0 hidden xl:block">
            <div ref={(el) => { cardRefs.current[0] = el }} className="absolute left-5 top-[6%] w-56 min-[1400px]:left-8 min-[1400px]:w-60">
              <AnnotateCard />
            </div>
            <div ref={(el) => { cardRefs.current[1] = el }} className="absolute bottom-[6%] left-5 w-56 min-[1400px]:left-8 min-[1400px]:w-60">
              <TrainCard />
            </div>
            <div ref={(el) => { cardRefs.current[2] = el }} className="absolute right-5 top-[14%] w-56 min-[1400px]:right-8 min-[1400px]:w-60">
              <CctvCard />
            </div>
            <div ref={(el) => { cardRefs.current[3] = el }} className="absolute bottom-[14%] right-5 w-56 min-[1400px]:right-8 min-[1400px]:w-60">
              <BalanceCard />
            </div>
          </div>

          <Reveal className="relative mx-auto flex w-full max-w-3xl flex-col items-center text-center">
            <TagPill icon={<ScanLine aria-hidden className="h-3.5 w-3.5" />}>
              SAM 3.1 &amp; VLM add-ons · CCTV
            </TagPill>

            <h1
              id="hero-title"
              className="mt-6 text-balance text-[2.1rem] font-semibold leading-[0.98] tracking-[-0.04em] [font-stretch:88%] sm:text-6xl lg:text-[4rem]"
            >
              <span className="block">Label, train and deploy</span>
              <span className="block lg:inline">vision models</span>{' '}
              <span className="block lg:inline">— in one place.</span>
            </h1>

            <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
              SAM 3.1 and a VLM can draft and check masks when an operator connects them, and every model family the
              connected worker supports — YOLO, <span className="whitespace-nowrap">RT-DETR</span>,{' '}
              <span className="whitespace-nowrap">D-FINE</span> — trains on your data and reaches your cameras.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <a
                href="/signup"
                className="inline-flex h-11 items-center rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Start free
              </a>
              <a
                href="#product"
                className="inline-flex h-11 items-center rounded-md border border-input bg-card px-5 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                See a demo
              </a>
            </div>

            <p className="mt-4 text-xs text-muted-foreground">Free plan · 3 projects · 10,000 images</p>
          </Reveal>

          {/* Same four cards, smaller, under the CTAs below xl. */}
          <div aria-hidden className="mx-auto mt-10 grid max-w-2xl grid-cols-2 items-start gap-3 sm:max-w-lg xl:hidden">
            <AnnotateCard />
            <TrainCard />
            <CctvCard />
            <BalanceCard />
          </div>
        </div>
      </section>
    </>
  )
}
