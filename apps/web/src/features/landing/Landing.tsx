import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import HeroSection from './sections/HeroSection'
import ShowcaseSection from './sections/ShowcaseSection'
import CapabilitiesSection from './sections/CapabilitiesSection'
import FeaturesBentoSection from './sections/FeaturesBentoSection'
import WorkflowDarkSection from './sections/WorkflowDarkSection'
import CtaFooterSection, { CtaSection, FooterSection } from './sections/CtaFooterSection'

/** Public marketing page. Logged-out visitors land here; the app itself lives under /:workspace. */
export default function Landing() {
  useEffect(() => {
    const previous = document.title
    document.title = 'LabelDesk — label, train and deploy vision models'
    return () => { document.title = previous }
  }, [])

  return (
    <div className="app-bg min-h-screen text-foreground">
      <a
        href="#main"
        className="sr-only rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200]"
      >
        Skip to content
      </a>
      <HeroSection />
      <main id="main">
        <ShowcaseSection />
        <CapabilitiesSection />
        <FeaturesBentoSection />
        <WorkflowDarkSection />
        <CtaSection />
      </main>
      <FooterSection />
    </div>
  )
}

const PREVIEWS = {
  hero: HeroSection,
  showcase: ShowcaseSection,
  capabilities: CapabilitiesSection,
  bento: FeaturesBentoSection,
  workflow: WorkflowDarkSection,
  cta: CtaFooterSection,
}

/** Dev-only route: /__preview/:section renders one section in isolation for screenshots. */
export function LandingPreview() {
  const { section = 'hero' } = useParams()
  const Section = PREVIEWS[section as keyof typeof PREVIEWS] ?? HeroSection
  return (
    <div className="app-bg min-h-screen text-foreground">
      <Section />
    </div>
  )
}
