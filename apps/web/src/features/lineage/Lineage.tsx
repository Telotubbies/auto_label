import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Network, X } from 'lucide-react'
import { Badge, Button, Card, EmptyState, PageHeader } from '@/components/ui'
import { api } from '@/lib/api'
import type { LineageEdge, LineageKind, LineageNode } from '@/lib/types'
import { cn } from '@/lib/utils'
import {
  DataTable, EChart, ErrorState, PageSkeleton, axisLine, axisText, chartBase, splitLine,
  useChartTheme, type ChartOption, type ChartTheme,
} from '../insights/charts'
import { useProject } from '../project/ProjectLayout'

const KINDS: LineageKind[] = ['batch', 'version', 'run', 'model', 'stream']
const KIND_ONE: Record<LineageKind, string> = {
  batch: 'Batch', version: 'Version', run: 'Training run', model: 'Model', stream: 'Stream',
}
const KIND_MANY: Record<LineageKind, string> = {
  batch: 'Batches', version: 'Versions', run: 'Training runs', model: 'Models', stream: 'Streams',
}
const TONE: Record<LineageKind, 'info' | 'primary' | 'warning' | 'success' | 'fg'> = {
  batch: 'info', version: 'primary', run: 'warning', model: 'success', stream: 'fg',
}
const EDGE_KINDS: LineageEdge['kind'][] = ['images', 'training', 'deployment']

// Fixed geometry keeps the SVG edge layer aligned with the CSS grid without a ResizeObserver.
const COL_W = 160
const COL_GAP = 20
const GRAPH_W = COL_W * KINDS.length + COL_GAP * (KINDS.length - 1)
const NODE_H = 76
const NODE_GAP = 12
const HEADER_H = 32

const fmt = (n: number) => n.toLocaleString()
const prettyKey = (key: string) => key.replace(/_/g, ' ')
const kindTone = (kind: LineageKind, theme: ChartTheme) => theme[TONE[kind]]
const edgeTone = (kind: LineageEdge['kind'], theme: ChartTheme) =>
  kind === 'images' ? theme.info : kind === 'training' ? theme.warning : theme.success

function countSummary(node: LineageNode): string {
  const entries = Object.entries(node.counts).filter(([, value]) => Number.isFinite(value))
  if (!entries.length) return 'No counts'
  return entries.slice(0, 2).map(([key, value]) => `${fmt(value)} ${prettyKey(key)}`).join(' · ')
}

function detailValue(value: unknown): ReactNode {
  if (value == null) return '—'
  if (typeof value === 'string') return value || '—'
  if (typeof value === 'number') return Number.isFinite(value) ? fmt(value) : String(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) {
    if (!value.length) return '—'
    return value
      .map((item) => (item !== null && typeof item === 'object' ? JSON.stringify(item) : String(item)))
      .join(', ')
  }
  if (typeof value === 'object') {
    return (
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-muted/40 p-1.5 text-[11px]">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }
  return String(value)
}

function countsOption(node: LineageNode, theme: ChartTheme): ChartOption {
  const entries = Object.entries(node.counts)
  return chartBase(theme, {
    grid: { left: 4, right: 16, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value',
      axisLabel: axisText(theme),
      axisLine: axisLine(theme),
      splitLine: splitLine(theme),
    },
    yAxis: {
      type: 'category',
      data: entries.map(([key]) => prettyKey(key)),
      axisLabel: { ...axisText(theme), width: 84, overflow: 'truncate' },
      axisLine: axisLine(theme),
    },
    series: [{
      type: 'bar',
      barMaxWidth: 16,
      data: entries.map(([, value]) => value),
      itemStyle: { color: kindTone(node.kind, theme), borderRadius: [0, 3, 3, 0] },
    }],
  })
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
}

function NodePanel({ node, onClose }: { node: LineageNode; onClose: () => void }) {
  const theme = useChartTheme()
  const counts = Object.entries(node.counts)
  const metrics = Object.entries(node.metrics)
  const detail = Object.entries(node.detail)
  const tone = kindTone(node.kind, theme)

  return (
    <aside aria-label={`${KIND_ONE[node.kind]} ${node.label} details`} className="min-w-0">
      <Card className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <Badge className="border" style={{ borderColor: tone }}>
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: tone }} aria-hidden="true" />
              {KIND_ONE[node.kind]}
            </Badge>
            <h2 className="mt-2 break-words text-base font-semibold">{node.label}</h2>
            {node.sub ? <p className="mt-0.5 break-words text-xs text-muted-foreground">{node.sub}</p> : null}
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" aria-label="Close panel" onClick={onClose}>
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        {counts.length ? (
          <>
            <SectionTitle>Counts</SectionTitle>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {counts.map(([key, value]) => (
                <div key={key} className="rounded-md border bg-muted/30 px-2.5 py-2">
                  <div className="text-sm font-semibold tabular-nums">{fmt(value)}</div>
                  <div className="mt-0.5 text-[11px] capitalize text-muted-foreground">{prettyKey(key)}</div>
                </div>
              ))}
            </div>
            <div className="mt-2">
              <EChart option={countsOption(node, theme)} ariaLabel={`Bar chart of ${node.label} counts: ${counts.map(([key, value]) => `${fmt(value)} ${prettyKey(key)}`).join(', ')}.`}
                height={Math.max(120, Math.min(220, counts.length * 26 + 32))} />
              <details className="mt-1">
                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">View counts as a table</summary>
                <div className="mt-2 max-h-56 overflow-auto">
                  <DataTable caption={`Counts for ${node.label}.`} head={['Measure', 'Count']}
                    rows={counts.map(([key, value]) => [prettyKey(key), fmt(value)])} />
                </div>
              </details>
            </div>
          </>
        ) : null}

        {metrics.length ? (
          <>
            <SectionTitle>Metrics</SectionTitle>
            <dl className="mt-1.5 divide-y">
              {metrics.map(([key, value]) => (
                <div key={key} className="flex items-baseline justify-between gap-3 py-1.5">
                  <dt className="text-xs uppercase text-muted-foreground">{key}</dt>
                  <dd className="text-xs font-medium tabular-nums">{value == null ? '—' : value.toFixed(3)}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}

        {detail.length ? (
          <>
            <SectionTitle>Detail</SectionTitle>
            <dl className="mt-1.5 space-y-1.5">
              {detail.map(([key, value]) => (
                <div key={key} className="grid grid-cols-[minmax(0,6.5rem)_minmax(0,1fr)] gap-2 border-b pb-1.5 last:border-0 last:pb-0">
                  <dt className="break-words text-[11px] text-muted-foreground">{prettyKey(key)}</dt>
                  <dd className="min-w-0 break-words text-xs">{detailValue(value)}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}

        {node.artifacts.length ? (
          <>
            <SectionTitle>Artefacts</SectionTitle>
            <ul className="mt-1.5 space-y-1">
              {node.artifacts.map((artifact, index) => (
                <li key={`${artifact.label}-${index}`} className="flex items-start gap-1.5 text-xs">
                  <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="min-w-0 break-words">{artifact.label}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {node.log.trim() ? (
          <>
            <SectionTitle>Log</SectionTitle>
            <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-2 text-[11px] leading-relaxed">{node.log}</pre>
          </>
        ) : null}
      </Card>
    </aside>
  )
}

export default function Lineage() {
  const { ws, project } = useProject()
  const theme = useChartTheme()
  const q = useQuery({ queryKey: ['lineage', ws, project.slug], queryFn: () => api.lineage(ws, project.slug) })
  const [kind, setKind] = useState<LineageKind | 'all'>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const nodes = useMemo(() => q.data?.nodes ?? [], [q.data])
  const edges = useMemo(() => q.data?.edges ?? [], [q.data])
  const byKind = useMemo(() => {
    const totals: Record<LineageKind, number> = { batch: 0, version: 0, run: 0, model: 0, stream: 0 }
    for (const node of nodes) totals[node.kind] += 1
    return totals
  }, [nodes])
  const visible = useMemo(() => (kind === 'all' ? nodes : nodes.filter((node) => node.kind === kind)), [nodes, kind])
  const selected = selectedId ? visible.find((node) => node.id === selectedId) ?? null : null

  useEffect(() => {
    if (!selectedId) return
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setSelectedId(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId])

  const header = (
    <PageHeader title="Lineage" desc="Every batch, version, training run, model and stream, connected by the data that produced it." />
  )

  if (q.isLoading) {
    return (
      <div className="anim-page">
        {header}
        <div className="space-y-4 px-4 pb-10 sm:px-8"><PageSkeleton /></div>
      </div>
    )
  }

  if (q.isError) {
    return (
      <div className="anim-page">
        {header}
        <div className="space-y-4 px-4 pb-10 sm:px-8">
          <ErrorState title="Lineage could not be loaded" message={(q.error as Error).message} onRetry={() => q.refetch()} />
        </div>
      </div>
    )
  }

  if (!nodes.length) {
    return (
      <div className="anim-page">
        {header}
        <div className="space-y-4 px-4 pb-10 sm:px-8">
          <Card className="p-6">
            <EmptyState icon={<Network className="h-8 w-8 text-muted-foreground/50" aria-hidden="true" />}
              title="No pipeline history yet"
              hint="Upload images to create a batch, label them into a version, then train a model — the whole chain will appear here." />
          </Card>
        </div>
      </div>
    )
  }

  const position = new Map<string, { x: number; y: number }>()
  for (const nodeKind of KINDS) {
    const column = KINDS.indexOf(nodeKind)
    visible.filter((node) => node.kind === nodeKind).forEach((node, index) => {
      position.set(node.id, { x: column * (COL_W + COL_GAP), y: HEADER_H + index * (NODE_H + NODE_GAP) })
    })
  }

  const rows = Math.max(1, ...KINDS.map((nodeKind) => visible.filter((node) => node.kind === nodeKind).length))
  const graphHeight = HEADER_H + rows * (NODE_H + NODE_GAP) - NODE_GAP
  const shownEdges = edges.filter((edge) => position.has(edge.source) && position.has(edge.target))
  const filters: (LineageKind | 'all')[] = ['all', ...KINDS]

  const pickKind = (next: LineageKind | 'all') => {
    setKind(next)
    setSelectedId(null)
  }

  return (
    <div className="anim-page">
      {header}
      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <Card className="p-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-xs font-medium text-muted-foreground">Show</span>
            <div role="group" aria-label="Filter lineage by node kind" className="flex flex-wrap gap-1.5">
              {filters.map((filter) => {
                const count = filter === 'all' ? nodes.length : byKind[filter]
                const active = kind === filter
                return (
                  <button key={filter} type="button" aria-pressed={active} disabled={!count && filter !== 'all'}
                    onClick={() => pickKind(filter)}
                    className={cn('min-h-8 cursor-pointer rounded-full border px-2.5 py-1 text-xs transition-colors',
                      active ? 'border-primary bg-accent font-medium text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      !count && filter !== 'all' && 'cursor-not-allowed opacity-40')}>
                    {filter === 'all' ? 'All' : KIND_ONE[filter]} <span className="tabular-nums">{count}</span>
                  </button>
                )
              })}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground" aria-label="Edge legend">
              {EDGE_KINDS.map((edgeKind) => (
                <span key={edgeKind} className="inline-flex items-center gap-1">
                  <svg width={16} height={6} aria-hidden="true" className="shrink-0">
                    <line x1={0} y1={3} x2={16} y2={3} stroke={edgeTone(edgeKind, theme)} strokeWidth={2} />
                  </svg>
                  {edgeKind}
                </span>
              ))}
            </div>
          </div>
        </Card>

        <div className={cn('grid gap-4', selected && 'lg:grid-cols-12')}>
          <div className={cn('min-w-0', selected && 'lg:col-span-8')}>
            <Card className="min-w-0 p-4">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h2 className="text-sm font-semibold">Pipeline</h2>
                <p className="text-xs text-muted-foreground">Batches flow left to right into versions, runs, models and streams.</p>
              </div>
              <div className="overflow-x-auto pb-1">
                <div className="relative mx-auto" style={{ width: GRAPH_W }}>
                  <svg width={GRAPH_W} height={graphHeight} className="pointer-events-none absolute left-0 top-0" aria-hidden="true" focusable="false">
                    {shownEdges.map((edge, index) => {
                      const from = position.get(edge.source)
                      const to = position.get(edge.target)
                      if (!from || !to) return null
                      const sx = from.x + COL_W
                      const sy = from.y + NODE_H / 2
                      const tx = to.x
                      const ty = to.y + NODE_H / 2
                      const dx = Math.max(24, Math.abs(tx - sx) * 0.45)
                      return (
                        <path key={`${edge.source}-${edge.target}-${index}`}
                          d={`M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`}
                          fill="none" stroke={edgeTone(edge.kind, theme)} strokeWidth={1.5} strokeOpacity={0.55} />
                      )
                    })}
                  </svg>
                  <div className="relative grid" style={{ gridTemplateColumns: `repeat(${KINDS.length}, ${COL_W}px)`, columnGap: COL_GAP }}>
                    {KINDS.map((nodeKind) => {
                      const columnNodes = visible.filter((node) => node.kind === nodeKind)
                      return (
                        <div key={nodeKind} className="min-w-0">
                          <h3 className="mb-2 flex h-6 items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                            <span className="h-2 w-2 rounded-full" style={{ background: kindTone(nodeKind, theme) }} aria-hidden="true" />
                            <span className="truncate">{KIND_MANY[nodeKind]}</span>
                            <span className="tabular-nums">{columnNodes.length}</span>
                          </h3>
                          <div className="flex flex-col gap-3">
                            {columnNodes.map((node) => {
                              const isSelected = selectedId === node.id
                              return (
                                <button key={node.id} type="button" aria-pressed={isSelected}
                                  onClick={() => setSelectedId(isSelected ? null : node.id)}
                                  style={{ height: NODE_H, borderLeftColor: kindTone(node.kind, theme) }}
                                  className={cn('flex w-full min-w-0 cursor-pointer flex-col justify-center gap-0.5 rounded-lg border border-l-[3px] bg-card px-3 py-2 text-left transition-colors hover:bg-accent/40',
                                    isSelected && 'border-primary bg-accent/50 ring-2 ring-primary/50')}>
                                  <span className="sr-only">{KIND_ONE[node.kind]}: </span>
                                  <span className="w-full truncate text-sm font-medium">{node.label}</span>
                                  <span className="w-full truncate text-[11px] text-muted-foreground">{node.sub || '—'}</span>
                                  <span className="w-full truncate text-[11px] tabular-nums text-muted-foreground">{countSummary(node)}</span>
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
              <p className="sr-only">The graph shows {visible.length} nodes and {shownEdges.length} connections.</p>
            </Card>
          </div>
          {selected ? (
            <div className="min-w-0 lg:col-span-4">
              <NodePanel node={selected} onClose={() => setSelectedId(null)} />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
