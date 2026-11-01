import { useState, type KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Job } from '@/lib/types'
import { Card, PageHeader, Select } from '@/components/ui'
import { useProject } from './ProjectLayout'
import { ChartSkeleton, PanelError } from './insights/Chart'
import { Overview } from './insights/Overview'
import { DataQuality } from './insights/DataQuality'
import { Leakage } from './insights/Leakage'
import { Embeddings } from './insights/Embeddings'
import { VersionsOps } from './insights/VersionsOps'

type TabId = 'overview' | 'quality' | 'leakage' | 'embeddings' | 'versions'

const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'quality', label: 'Data quality' },
  { id: 'leakage', label: 'Leakage' },
  { id: 'embeddings', label: 'Embeddings' },
  { id: 'versions', label: 'Versions & ops' },
]

const ACTIVE = new Set<Job['status']>(['queued', 'running'])
const poll = (job?: Job | null) => (job && ACTIVE.has(job.status) ? 3000 : false)

function PageSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-busy="true" aria-label="Loading insights">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="p-4">
            <div className="skeleton h-3 w-16" />
            <div className="skeleton mt-3 h-7 w-24" />
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartSkeleton /><ChartSkeleton />
      </div>
    </div>
  )
}

export default function Insights() {
  const { project, ws } = useProject()
  const slug = project.slug
  const [tab, setTab] = useState<TabId>('overview')
  const [versionId, setVersionId] = useState('')
  const [diffBase, setDiffBase] = useState('')
  const [diffTarget, setDiffTarget] = useState('')

  const versions = useQuery({ queryKey: ['versions', ws, slug], queryFn: () => api.versions(ws, slug) })
  // Newest two versions by default: newest is the target, the one before it the base.
  const known = (id: string) => !!versions.data?.some((v) => v.id === id)
  const base = known(diffBase) ? diffBase : (versions.data?.[1] ?? versions.data?.[0])?.id ?? ''
  const target = known(diffTarget) ? diffTarget : versions.data?.[0]?.id ?? ''
  const summary = useQuery({
    queryKey: ['insights', 'summary', ws, slug, versionId],
    queryFn: () => api.insights.summary(ws, slug, versionId || undefined),
  })
  const distribution = useQuery({
    queryKey: ['insights', 'distribution', ws, slug, versionId],
    queryFn: () => api.insights.distribution(ws, slug, versionId || undefined),
    enabled: tab === 'overview',
  })
  const geometry = useQuery({
    queryKey: ['insights', 'geometry', ws, slug, versionId],
    queryFn: () => api.insights.geometry(ws, slug, versionId || undefined),
    enabled: tab === 'quality',
  })
  const imageStats = useQuery({
    queryKey: ['insights', 'image-stats', ws, slug],
    queryFn: () => api.insights.imageStats(ws, slug),
    enabled: tab === 'quality',
    refetchInterval: (q) => poll(q.state.data?.job),
  })
  const leakage = useQuery({
    queryKey: ['insights', 'leakage', ws, slug, versionId],
    queryFn: () => api.insights.leakage(ws, slug, versionId || undefined),
    enabled: tab === 'leakage',
    refetchInterval: (q) => poll(q.state.data?.job),
  })
  const embedding = useQuery({
    queryKey: ['insights', 'embedding', ws, slug],
    queryFn: () => api.insights.embedding(ws, slug),
    enabled: tab === 'embeddings',
    refetchInterval: (q) => poll(q.state.data?.job),
  })
  const labeling = useQuery({
    queryKey: ['insights', 'labeling', ws, slug],
    queryFn: () => api.insights.labeling(ws, slug),
    enabled: tab === 'versions',
  })
  const diff = useQuery({
    queryKey: ['insights', 'version-diff', ws, slug, base, target],
    queryFn: () => api.insights.versionDiff(ws, slug, base, target),
    enabled: tab === 'versions' && !!base && !!target,
  })

  const versionName = versions.data?.find((v) => v.id === versionId)?.name

  /** Roving tab index keeps the tab list on one Tab stop and moves with the arrow keys. */
  const onTabKey = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return
    e.preventDefault()
    const next = e.key === 'Home' ? 0
      : e.key === 'End' ? TABS.length - 1
        : (index + (e.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length
    setTab(TABS[next].id)
    document.getElementById(`insights-tab-${TABS[next].id}`)?.focus()
  }

  const body = () => {
    if (summary.isLoading) return <PageSkeleton />
    if (summary.error) return <PanelError error={summary.error} />

    if (tab === 'overview') {
      if (distribution.isLoading) return <PageSkeleton />
      if (distribution.error) return <PanelError error={distribution.error} />
      return summary.data && distribution.data ? <Overview summary={summary.data} distribution={distribution.data} /> : null
    }

    if (tab === 'quality') {
      if (geometry.isLoading || imageStats.isLoading) return <PageSkeleton />
      if (geometry.error) return <PanelError error={geometry.error} />
      if (imageStats.error) return <PanelError error={imageStats.error} />
      return summary.data && geometry.data && imageStats.data
        ? <DataQuality ws={ws} slug={slug} summary={summary.data} geometry={geometry.data} stats={imageStats.data} />
        : null
    }

    if (tab === 'leakage') {
      if (leakage.isLoading) return <PageSkeleton />
      if (leakage.error) return <PanelError error={leakage.error} />
      return leakage.data ? <Leakage ws={ws} slug={slug} leakage={leakage.data} versionLabel={versionName} /> : null
    }

    if (tab === 'embeddings') {
      if (embedding.isLoading) return <PageSkeleton />
      if (embedding.error) return <PanelError error={embedding.error} />
      return summary.data && embedding.data
        ? <Embeddings ws={ws} slug={slug} summary={summary.data} embedding={embedding.data} />
        : null
    }

    if (versions.isLoading || labeling.isLoading || (!!base && diff.isLoading)) return <PageSkeleton />
    if (versions.error) return <PanelError error={versions.error} />
    if (labeling.error) return <PanelError error={labeling.error} />
    return versions.data && labeling.data
      ? <VersionsOps ws={ws} slug={slug} versions={versions.data} base={base} target={target}
        onBase={setDiffBase} onTarget={setDiffTarget} diff={diff.data ?? null} diffError={diff.error} labeling={labeling.data} />
      : null
  }

  return (
    <div className="anim-page">
      <PageHeader
        title="Insights Studio"
        desc="Class balance, label geometry, split leakage, embeddings and pipeline health — without leaving LabelDesk."
        actions={(
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Version
            <Select value={versionId} onChange={(e) => setVersionId(e.target.value)}
              aria-label="Limit insights to a dataset version" title="Applies to Overview, Data quality and Leakage"
              className="w-40 sm:w-52">
              <option value="">All images</option>
              {versions.data?.map((v) => <option key={v.id} value={v.id}>v{v.number} · {v.name}</option>)}
            </Select>
          </label>
        )}
      />
      <div className="px-4 pb-10 sm:px-8">
        <div className="mb-4 overflow-x-auto border-b" role="tablist" aria-label="Insights sections">
          <div className="flex min-w-max">
            {TABS.map((t) => (
              <button key={t.id} type="button" role="tab" id={`insights-tab-${t.id}`}
                aria-selected={tab === t.id} tabIndex={tab === t.id ? 0 : -1}
                onClick={() => setTab(t.id)} onKeyDown={(e) => onTabKey(e, TABS.indexOf(t))}
                className={cn('whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors',
                  tab === t.id ? 'border-primary font-medium text-primary' : 'border-transparent text-muted-foreground hover:text-foreground')}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div role="tabpanel" id={`insights-panel-${tab}`} aria-labelledby={`insights-tab-${tab}`} className="anim-fade">
          {body()}
        </div>
      </div>
    </div>
  )
}
