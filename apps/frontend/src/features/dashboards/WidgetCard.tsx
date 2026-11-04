import { useMemo } from 'react'
import { ChevronLeft, ChevronRight, Pencil, Trash2 } from 'lucide-react'
import type { EChartsOption } from 'echarts'
import { Button, Card } from '@/components/ui'
import { classColor, viridis } from '@/lib/theme'
import { cn } from '@/lib/utils'
import {
  ChartCard, ChartSkeleton, DataTable, EChart, chartBase, toRgb, useChartTheme,
} from '@/features/insights/charts'
import { buildWidgetOption, widgetCsv, widgetView, type WidgetData, type WidgetSpec } from './widgetModel'
import { dimensionLabel, measureLabel, sourceLabel } from './labels'

function description(spec: WidgetSpec): string {
  const dim = spec.dimension === 'none' ? 'total' : `by ${dimensionLabel(spec.dimension)}`
  const second = spec.dimension2 ? ` × ${dimensionLabel(spec.dimension2)}` : ''
  return `${sourceLabel(spec.source)} · ${measureLabel(spec.measure, spec.source)} ${dim}${second}`
}

/** One saved widget: chart or table, its export menu, and the layout controls when the dashboard is editable. */
export function WidgetCard({ spec, data, loading, error, editable, classOrder = [], onEdit, onRemove, onMove }: {
  spec: WidgetSpec
  data?: WidgetData
  loading: boolean
  error?: string
  editable: boolean
  /** Project class order, so one class keeps one colour across every widget. */
  classOrder?: string[]
  onEdit: () => void
  onRemove: () => void
  onMove: (delta: number) => void
}) {
  const theme = useChartTheme()
  const option = useMemo(() => {
    if (!data) return null
    const heat = Array.from({ length: 10 }, (_, i) => toRgb(viridis(i / 9)))
    return chartBase(theme, buildWidgetOption(spec, data, theme, (i) => toRgb(classColor(i)), heat, classOrder) as EChartsOption)
  }, [spec, data, theme, classOrder])

  const rows = data ? widgetCsv(spec, data) : []
  const head = rows[0] ?? []
  const table = (
    <DataTable caption={`${spec.title}. ${description(spec)}.`} head={head} rows={rows.slice(1)} />
  )
  const controls = editable ? (
    <div className="flex items-center gap-0.5">
      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Move ${spec.title} earlier`} onClick={() => onMove(-1)}>
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Move ${spec.title} later`} onClick={() => onMove(1)}>
        <ChevronRight className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Edit ${spec.title}`} onClick={onEdit}>
        <Pencil className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" aria-label={`Remove ${spec.title}`} onClick={onRemove}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  ) : null

  if (spec.chart === 'kpi') {
    const value = data?.total ?? 0
    return (
      <Card className="flex min-w-0 flex-col p-4">
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">{spec.title}</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{description(spec)}</p>
          </div>
          {controls}
        </div>
        <div className="flex flex-1 items-center py-4">
          {loading ? <ChartSkeleton height={60} /> : error ? (
            <p role="alert" className="text-xs text-destructive">{error}</p>
          ) : (
            <p className="text-4xl font-semibold tabular-nums tracking-tight">
              {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              <span className="ml-2 text-xs font-normal text-muted-foreground">{data?.unit}</span>
            </p>
          )}
        </div>
      </Card>
    )
  }

  return (
    <ChartCard
      title={spec.title}
      description={description(spec)}
      summary={data ? `${spec.title}: ${spec.measure} by ${spec.dimension}${spec.dimension2 ? ` and ${spec.dimension2}` : ''}, ${rows.length - 1} rows.` : `${spec.title} is loading.`}
      exportName={spec.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'widget'}
      csvRows={rows.length > 1 ? rows : undefined}
      jsonData={data}
      actions={controls}
      table={table}
      className={cn(spec.w >= 12 && 'min-h-[320px]')}
      initialView={widgetView(spec.chart)}
      chartView={spec.chart !== 'table'}
    >
      {loading ? <ChartSkeleton height={240} /> : error ? (
        <p role="alert" className="py-10 text-center text-sm text-destructive">{error}</p>
      ) : option ? (
        <EChart option={option} height={260} ariaLabel={`${spec.title}. ${description(spec)}. Switch to the table view for the same values.`} />
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">No data for this widget.</p>
      )}
    </ChartCard>
  )
}
