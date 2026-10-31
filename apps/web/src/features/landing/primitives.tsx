// Shared landing-page primitives. Only things used by three or more sections live here.
import { useEffect, useRef, useState, type ComponentPropsWithoutRef, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Glass } from '@/components/glass'

/** Page section: shared width, gutters and vertical rhythm. */
export function SectionShell({ className, innerClassName, children, ...props }: {
  innerClassName?: string
} & ComponentPropsWithoutRef<'section'>) {
  return (
    <section className={cn('relative', className)} {...props}>
      <div className={cn('mx-auto w-full max-w-6xl px-5 sm:px-8', innerClassName)}>{children}</div>
    </section>
  )
}

/** Small rounded label: icon + sentence-case text. Replaces tracked-out all-caps eyebrows. */
export function TagPill({ icon, children, className }: {
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cn(
      'inline-flex w-fit items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground',
      className,
    )}>
      {icon}
      {children}
    </span>
  )
}

/** Crop marks borrowed from the annotation canvas: four corner brackets around a framed visual. */
export function CornerMarks({ className }: { className?: string }) {
  const mark = 'pointer-events-none absolute h-4 w-4 border-current opacity-30'
  return (
    <span aria-hidden className={cn('pointer-events-none absolute inset-0', className)}>
      <span className={cn(mark, 'left-2 top-2 border-l-2 border-t-2')} />
      <span className={cn(mark, 'right-2 top-2 border-r-2 border-t-2')} />
      <span className={cn(mark, 'bottom-2 left-2 border-b-2 border-l-2')} />
      <span className={cn(mark, 'bottom-2 right-2 border-b-2 border-r-2')} />
    </span>
  )
}

/** Dot grid decoration for coloured mock panels. Inherits currentColor. */
export function DotGrid({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('pointer-events-none absolute inset-0 bg-[radial-gradient(currentColor_1px,transparent_1px)] [background-size:16px_16px] opacity-[0.16]', className)}
    />
  )
}

/** Glass-framed product window. The chrome is glass; the body stays solid. */
export function MockWindow({ title, meta, children, className, bodyClassName }: {
  title: ReactNode
  meta?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <Glass className={cn('overflow-hidden rounded-2xl', className)}>
      <div className="flex items-center gap-2 border-b border-border/70 px-4 py-2.5">
        <span aria-hidden className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
          <span className="h-2 w-2 rounded-full bg-muted-foreground/30" />
        </span>
        <span className="ml-1 truncate text-xs font-medium text-foreground">{title}</span>
        {meta && <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{meta}</span>}
      </div>
      <div className={cn('bg-card', bodyClassName)}>{children}</div>
    </Glass>
  )
}

/** Section heading block: tag pill, h2, optional intro. */
export function SectionHeading({ id, tag, icon, title, intro, align = 'left', className }: {
  id?: string
  tag?: string
  icon?: ReactNode
  title: ReactNode
  intro?: ReactNode
  align?: 'left' | 'center'
  className?: string
}) {
  return (
    <div className={cn('flex flex-col gap-4', align === 'center' ? 'items-center text-center' : 'items-start', className)}>
      {tag && <TagPill icon={icon}>{tag}</TagPill>}
      <h2 id={id} className="max-w-3xl text-balance text-3xl font-semibold leading-[1.05] tracking-[-0.035em] [font-stretch:90%] sm:text-4xl md:text-5xl">
        {title}
      </h2>
      {intro && <p className={cn('max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg', align === 'center' && 'mx-auto')}>{intro}</p>}
    </div>
  )
}

/** Scroll reveal: opacity + 12px lift, 500 ms. Skipped entirely under prefers-reduced-motion. */
export function Reveal({ children, delay = 0, className }: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver !== 'function' || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(true)
      return
    }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setShown(true); io.disconnect() }
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.08 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      style={{ transitionDelay: shown ? `${delay}ms` : undefined }}
      className={cn(
        'transition-[opacity,transform] duration-500 ease-out',
        shown ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0',
        className,
      )}
    >
      {children}
    </div>
  )
}
