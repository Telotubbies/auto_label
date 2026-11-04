import { useMemo } from 'react'
import { useQueries, useQuery, type QueryKey } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { WidgetRefs } from './WidgetEditor'
import { cleanFilters, type WidgetData, type WidgetFilters, type WidgetSpec } from './widgetModel'

/** Viewer offset east of UTC in minutes; stream widgets bucket days and hours in local time. */
export function browserTzOffset(): number {
  return -new Date().getTimezoneOffset()
}

/** Request filters: saved filters plus the viewer-local stream offset (never persisted in the spec). */
export function widgetFilters(spec: WidgetSpec): WidgetFilters {
  const filters = cleanFilters(spec.filters)
  if (spec.source === 'streams') filters.tz_offset = browserTzOffset()
  return filters
}

function widgetBody(spec: WidgetSpec) {
  return {
    source: spec.source,
    measure: spec.measure,
    dimension: spec.dimension,
    dimension2: spec.dimension2,
    filters: widgetFilters(spec),
  }
}

/** Query identity: everything that changes the numbers, including the cleaned filters. */
export function widgetQueryKey(ws: string, slug: string, spec: WidgetSpec, token?: string): QueryKey {
  return ['widget', ws, slug, token ?? '', JSON.stringify(widgetBody(spec))]
}

/** A shared link queries through its token route; the normal editor uses the reviewer route. */
export function fetchWidget(ws: string, slug: string, spec: WidgetSpec, token?: string): Promise<WidgetData> {
  return token
    ? api.sharedWidgetQuery(ws, slug, token, widgetBody(spec))
    : api.widgetQuery(ws, slug, widgetBody(spec))
}

/** One aggregate request per widget, in dashboard order. */
export function useWidgetQueries(ws: string, slug: string, widgets: WidgetSpec[], token?: string) {
  return useQueries({
    queries: widgets.map((spec) => ({
      queryKey: widgetQueryKey(ws, slug, spec, token),
      queryFn: () => fetchWidget(ws, slug, spec, token),
      staleTime: 60_000,
      retry: false,
    })),
  })
}

/** Project class order: one stable palette index shared by every widget, editors and shared views alike. */
export function useClassOrder(ws: string, slug: string): string[] {
  const classes = useQuery({ queryKey: ['classes', ws, slug], queryFn: () => api.classes(ws, slug) })
  return useMemo(() => (classes.data ?? []).map((c) => c.name), [classes.data])
}

/** Everything the widget editor offers in its filter pickers; one shared cache per project. */
export function useWidgetRefs(ws: string, slug: string, enabled = true): WidgetRefs {
  const versions = useQuery({ queryKey: ['versions', ws, slug], queryFn: () => api.versions(ws, slug), enabled })
  const models = useQuery({ queryKey: ['models', ws, slug], queryFn: () => api.models(ws, slug), enabled })
  const classes = useQuery({ queryKey: ['classes', ws, slug], queryFn: () => api.classes(ws, slug), enabled })
  const batches = useQuery({ queryKey: ['batches', ws, slug], queryFn: () => api.batches(ws, slug), enabled })
  const streams = useQuery({ queryKey: ['streams', ws, slug], queryFn: () => api.streams(ws, slug), enabled })
  const tags = useQuery({ queryKey: ['tags', ws, slug], queryFn: () => api.tags(ws, slug), enabled })
  const empty: WidgetRefs = { versions: [], models: [], classes: [], batches: [], streams: [], tags: [] }
  return useMemo(() => enabled ? {
    versions: (versions.data ?? []).map((v) => ({ id: v.id, number: v.number, name: v.name })),
    models: (models.data ?? []).map((m) => ({ id: m.id, name: m.name })),
    classes: (classes.data ?? []).map((c) => ({ id: c.id, name: c.name })),
    batches: (batches.data ?? []).map((b) => ({ id: b.id, name: b.name })),
    streams: (streams.data ?? []).map((s) => ({ id: s.id, name: s.name })),
    tags: (tags.data ?? []).map((t) => ({ name: t.name })),
  } : empty, [enabled, versions.data, models.data, classes.data, batches.data, streams.data, tags.data])
}
