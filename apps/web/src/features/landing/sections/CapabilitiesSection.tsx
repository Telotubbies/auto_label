import type { ReactNode } from 'react'
import { ArrowRight, Cctv, ScanSearch, Spline, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CornerMarks, Reveal, SectionHeading, SectionShell } from '../primitives'

/** Three offset annotation rectangles, one with corner handles, over a crosshair. */
function DetectVisual() {
  return (
    <>
      <svg aria-hidden viewBox="0 0 300 128" fill="none" className="h-full w-full">
        <rect x="12" y="26" width="104" height="68" rx="8" stroke="currentColor" strokeOpacity=".28" strokeWidth="1.5" />
        <rect x="40" y="16" width="124" height="92" rx="8" stroke="currentColor" strokeOpacity=".5" strokeWidth="1.5" />
        <rect x="68" y="32" width="128" height="82" rx="8" stroke="currentColor" strokeOpacity=".9" strokeWidth="1.5" />
        {[[68, 32], [196, 32], [68, 114], [196, 114]].map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x - 4.5} y={y - 4.5} width="9" height="9" fill="currentColor" fillOpacity=".9" />
        ))}
        <path d="M216 84h56M244 56v56" stroke="currentColor" strokeOpacity=".35" strokeDasharray="3 4" />
        <circle cx="244" cy="84" r="5" stroke="currentColor" strokeOpacity=".85" strokeWidth="1.5" />
        <circle cx="244" cy="84" r="1.5" fill="currentColor" />
      </svg>
      <span className="absolute right-0 top-0 rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium tabular-nums text-card-foreground shadow-sm">
        3 boxes · 0.96
      </span>
    </>
  )
}

/** A mask polygon with vertex handles, plus a loupe on one edge. */
function SegmentVisual() {
  const vertices = [[18, 48], [92, 20], [178, 40], [166, 108], [56, 118]]
  return (
    <svg aria-hidden viewBox="0 0 300 128" fill="none" className="h-full w-full">
      <path
        d="M18 48 92 20 178 40 166 108 56 118Z"
        fill="currentColor"
        fillOpacity=".14"
        stroke="currentColor"
        strokeOpacity=".85"
        strokeWidth="1.5"
        strokeDasharray="5 4"
        strokeLinejoin="round"
      />
      {vertices.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="4" fill="currentColor" />
      ))}
      <path d="M180 40 200 32" stroke="currentColor" strokeOpacity=".35" strokeDasharray="2 3" />
      <rect x="200" y="26" width="84" height="76" rx="10" stroke="currentColor" strokeOpacity=".5" strokeWidth="1.5" />
      <path d="M212 92 240 82 262 44" stroke="currentColor" strokeOpacity=".9" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="212" cy="92" r="3" fill="currentColor" />
      <circle cx="262" cy="44" r="3" fill="currentColor" />
    </svg>
  )
}

/** Camera viewport with a zone, a person trail, timestamp ticks and one event row. */
function MonitorVisual() {
  return (
    <>
      <svg aria-hidden viewBox="0 0 300 128" fill="none" className="h-full w-full">
        <rect x="6" y="6" width="288" height="80" rx="10" stroke="currentColor" strokeOpacity=".55" strokeWidth="1.5" />
        <circle cx="24" cy="22" r="2" fill="currentColor" />
        <path d="M32 22h22" stroke="currentColor" strokeOpacity=".35" strokeWidth="2" strokeLinecap="round" />
        <path d="M20 44 110 36" stroke="currentColor" strokeOpacity=".35" strokeDasharray="4 4" />
        <path d="M20 40v8M110 32v8" stroke="currentColor" strokeOpacity=".35" strokeWidth="1.5" />
        <path d="M150 30 238 44 228 74 140 62Z" fill="currentColor" fillOpacity=".12" stroke="currentColor" strokeOpacity=".7" strokeWidth="1.5" strokeDasharray="4 4" />
        <text x="184" y="58" textAnchor="middle" fontSize="9" fill="currentColor" fillOpacity=".9">A</text>
        <path d="M34 74C64 78 82 60 110 55s18-3 26-5" stroke="currentColor" strokeOpacity=".3" strokeDasharray="2 4" />
        <circle cx="34" cy="74" r="2" fill="currentColor" fillOpacity=".25" />
        <circle cx="70" cy="68" r="2.5" fill="currentColor" fillOpacity=".4" />
        <circle cx="104" cy="58" r="3" fill="currentColor" fillOpacity=".6" />
        <circle cx="136" cy="50" r="4" fill="currentColor" fillOpacity=".9" />
        <circle cx="136" cy="50" r="8" stroke="currentColor" strokeOpacity=".25" />
        {Array.from({ length: 12 }, (_, i) => 18 + i * 24).map((x, i) => (
          <path
            key={x}
            d={`M${x} ${i % 3 === 0 ? 78 : 81}v${i % 3 === 0 ? 7 : 4}`}
            stroke="currentColor"
            strokeOpacity={i % 3 === 0 ? '.45' : '.25'}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        ))}
      </svg>
      <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-[11px] text-card-foreground shadow-sm">
        <span className="h-1.5 w-1.5 rounded-full bg-current" />
        <span className="font-medium tabular-nums">14:02</span>
        <span aria-hidden className="text-muted-foreground">·</span>
        <span>Zone A</span>
      </div>
    </>
  )
}

function CapabilityCard({ tone, icon: Icon, title, lead, detail, href, linkLabel, visual }: {
  tone: string
  icon: LucideIcon
  title: string
  lead: string
  detail: string
  href: string
  linkLabel: string
  visual: ReactNode
}) {
  return (
    <article
      className={cn(
        'group relative flex h-full min-h-[24rem] flex-col overflow-hidden rounded-3xl p-6 transition-[transform,box-shadow] duration-200 ease-out lift sm:p-7',
        tone,
      )}
    >
      <CornerMarks />
      <span aria-hidden className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-current/25">
        <Icon size={20} strokeWidth={1.75} />
      </span>
      <h3 className="mt-6 text-2xl font-semibold leading-[1.1] tracking-[-0.03em] [font-stretch:90%]">{title}</h3>
      <p className="mt-3 text-pretty text-[15px] leading-relaxed">
        {lead}
        <span className="mt-1 block opacity-85">{detail}</span>
      </p>
      <div aria-hidden className="mt-auto pt-8">
        <div className="relative h-32">{visual}</div>
      </div>
      <a
        href={href}
        aria-label={linkLabel}
        className="mt-5 inline-flex w-fit items-center gap-1.5 rounded-md border border-current/30 px-3 py-2 text-sm font-medium underline-offset-4 hover:underline"
      >
        Learn more
        <ArrowRight aria-hidden size={14} strokeWidth={1.75} className="transition-transform group-hover:translate-x-0.5" />
      </a>
    </article>
  )
}

export default function CapabilitiesSection() {
  return (
    <SectionShell id="capabilities" aria-labelledby="capabilities-title" className="py-20 sm:py-28 lg:py-32">
      <SectionHeading
        id="capabilities-title"
        tag="Capabilities"
        title="What can you build?"
        intro="Three jobs, one pipeline. Start from boxes, masks or a camera feed — the whole recipe stays in one project."
        className="[&>span]:self-start"
      />

      <div className="mt-10 grid gap-4 sm:mt-12 lg:grid-cols-3">
        <Reveal className="h-full">
          <CapabilityCard
            tone="bg-accent text-accent-foreground"
            icon={ScanSearch}
            title="Detect"
            lead="Draw boxes once, or let the model propose them. Review a queue built for speed, not clicks."
            detail="Every class keeps its own colour and confidence."
            href="#models"
            linkLabel="Learn more about detection"
            visual={<DetectVisual />}
          />
        </Reveal>
        <Reveal delay={70} className="h-full">
          <CapabilityCard
            tone="bg-tertiary-container text-foreground"
            icon={Spline}
            title="Segment"
            lead="Turn rough boxes into tight masks, then move a vertex when the edge matters."
            detail="Connect SAM 3.1 for the first pass; you handle the last 5%."
            href="#models"
            linkLabel="Learn more about segmentation"
            visual={<SegmentVisual />}
          />
        </Reveal>
        <Reveal delay={140} className="h-full">
          <CapabilityCard
            tone="bg-secondary text-secondary-foreground"
            icon={Cctv}
            title="Monitor"
            lead="Point a stream at a trained model and get events with zones, lines and dwell time."
            detail="One camera or forty, the rules read the same."
            href="#workflow"
            linkLabel="Learn more about monitoring"
            visual={<MonitorVisual />}
          />
        </Reveal>
      </div>
    </SectionShell>
  )
}
