import { useState } from 'react'
import { PageHeader, Tabs } from '@/components/ui'
import { useProjectPermissions } from '@/lib/perms'
import { useProject } from './ProjectLayout'
import Workforce from './qa/Workforce'
import ReviewQueue from './qa/ReviewQueue'
import Consensus from './qa/Consensus'
import Honeypots from './qa/Honeypots'

export default function QA() {
  const { project, ws } = useProject()
  const { can } = useProjectPermissions(ws, project.slug)
  const [tab, setTab] = useState('workforce')
  // Review-backed tabs follow the effective project role, not the workspace rank (I5).
  const tabs = can('project.review')
    ? [
        { id: 'workforce', label: 'Workforce' },
        { id: 'review', label: 'Review queue' },
        { id: 'consensus', label: 'Consensus' },
        { id: 'honeypots', label: 'Honeypots' },
      ]
    : [{ id: 'workforce', label: 'Workforce' }]
  const active = tabs.some((t) => t.id === tab) ? tab : 'workforce'

  return (
    <div className="anim-page">
      <PageHeader title="QA & Workforce"
        desc="Consensus labeling compares K drafts per image, honeypots score labelers against hidden ground truth, and the review queue surfaces the most contested images first." />
      <div className="px-4 pb-10 sm:px-8">
        <div className="overflow-x-auto" role="region" aria-label="QA sections" tabIndex={0}>
          <Tabs tabs={tabs} active={active} onChange={setTab} />
        </div>
        <div className="mt-4">
          {active === 'workforce' && <Workforce ws={ws} slug={project.slug} />}
          {active === 'review' && <ReviewQueue ws={ws} slug={project.slug} />}
          {active === 'consensus' && <Consensus ws={ws} slug={project.slug} />}
          {active === 'honeypots' && <Honeypots ws={ws} slug={project.slug} />}
        </div>
      </div>
    </div>
  )
}
