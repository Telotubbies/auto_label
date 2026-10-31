import { MapPin, Sparkles } from 'lucide-react'
import { Glass } from '@/components/glass'
import { CornerMarks, DotGrid, Reveal, SectionShell, TagPill } from '../primitives'

const primaryCta =
  'inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90'
const secondaryCta =
  'inline-flex h-11 items-center justify-center rounded-md border border-input bg-card px-5 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground'

const footerLink =
  'inline-flex min-h-6 items-center rounded-sm text-sm text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline'

const PRODUCT_LINKS = [
  { label: 'Capabilities', href: '#capabilities' },
  { label: 'Model families', href: '#models' },
  { label: 'Workflow', href: '#workflow' },
  { label: 'Pricing', href: '#pricing' },
] as const

const RESOURCE_LINKS = [
  { label: 'Getting started', href: '#product' },
  { label: 'Auto-label', href: '#models' },
  { label: 'Streams', href: '#workflow' },
] as const

const ACCOUNT_LINKS = [
  { label: 'Log in', href: '/login' },
  { label: 'Create account', href: '/signup' },
] as const

/** Closing glass band: the last of the four allowed glass surfaces on the page. */
export function CtaSection() {
  return (
    <SectionShell id="pricing" aria-labelledby="pricing-title" className="py-16 sm:py-20">
      <Reveal>
        <Glass className="relative overflow-hidden rounded-3xl px-6 py-12 sm:px-12 sm:py-16">
          <span
            aria-hidden
            className="pointer-events-none absolute -top-24 left-1/2 h-48 w-[36rem] -translate-x-1/2 rounded-full bg-primary/20 blur-3xl"
          />
          <DotGrid className="text-primary" />
          <CornerMarks className="text-primary" />

          <div className="relative mx-auto flex max-w-2xl flex-col items-center text-center">
            <TagPill icon={<Sparkles aria-hidden className="h-3.5 w-3.5" />}>Free plan</TagPill>

            <h2
              id="pricing-title"
              className="mt-5 text-balance text-3xl font-semibold leading-[1.02] tracking-[-0.04em] [font-stretch:88%] sm:text-5xl"
            >
              Start labeling free
            </h2>

            <p className="mt-4 max-w-xl text-pretty text-base leading-relaxed text-muted-foreground">
              Bring a folder of images or point a camera. Your first project is ready in minutes.
            </p>

            <div className="mt-8 flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
              <a href="/signup" className={`${primaryCta} w-full sm:w-auto`}>Create free account</a>
              <a href="/login" className={`${secondaryCta} w-full sm:w-auto`}>Sign in</a>
            </div>

            <div className="mt-8 flex w-full max-w-md items-center gap-3">
              <span aria-hidden className="hidden h-px flex-1 bg-border sm:block" />
              <p className="text-xs text-muted-foreground">
                3 projects · 10,000 images · no card required
              </p>
              <span aria-hidden className="hidden h-px flex-1 bg-border sm:block" />
            </div>
          </div>
        </Glass>
      </Reveal>
    </SectionShell>
  )
}

function FooterLinks({ id, title, links }: {
  id: string
  title: string
  links: readonly { label: string; href: string }[]
}) {
  return (
    <nav id={id} aria-labelledby={`${id}-title`} className="scroll-mt-24">
      <h2 id={`${id}-title`} className="text-xs font-semibold text-foreground">{title}</h2>
      <ul className="mt-3 space-y-2">
        {links.map((link) => (
          <li key={link.label}>
            <a href={link.href} className={footerLink}>{link.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export function FooterSection() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="mx-auto w-full max-w-6xl px-5 py-14 sm:px-8">
        <div className="flex flex-col gap-12 lg:flex-row lg:items-start lg:justify-between lg:gap-16">
          <div className="w-full max-w-sm lg:w-[17.5rem] lg:max-w-none lg:flex-none">
            <a href="/" className="inline-flex items-center gap-2.5 rounded-md">
              <span
                aria-hidden
                className="grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-semibold text-primary-foreground [font-stretch:88%]"
              >
                L
              </span>
              <span className="text-[15px] font-semibold tracking-[-0.02em] text-foreground">LabelDesk</span>
            </a>
            <p className="mt-4 max-w-xs text-pretty text-sm leading-relaxed text-muted-foreground">
              Computer vision, labelled and deployed from one desk.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4 sm:gap-x-8 lg:min-w-0 lg:flex-1 lg:gap-x-6 lg:border-l lg:border-border/70 lg:pl-8 xl:gap-x-10 xl:pl-12">
            <FooterLinks id="footer-product" title="Product" links={PRODUCT_LINKS} />
            <FooterLinks id="docs" title="Resources" links={RESOURCE_LINKS} />
            <FooterLinks id="footer-account" title="Account" links={ACCOUNT_LINKS} />

            <div>
              <h2 id="footer-company-title" className="text-xs font-semibold text-foreground">Company</h2>
              <ul aria-labelledby="footer-company-title" className="mt-3 space-y-2">
                <li className="flex min-h-6 items-start gap-2 text-sm text-muted-foreground">
                  <MapPin aria-hidden className="mt-1 h-4 w-4 shrink-0" />
                  <span>Built for teams in Thailand</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-4 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted-foreground">© 2026 LabelDesk</p>
        </div>
      </div>
    </footer>
  )
}

export default function CtaFooterSection() {
  return (
    <>
      <CtaSection />
      <FooterSection />
    </>
  )
}
