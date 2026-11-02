import { useMemo } from 'react'
import { useQueries, useQuery, type QueryKey } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { WidgetRefs } from './WidgetEditor'
import { cleanFilters, type WidgetData, type WidgetSpec } from './widgetModel'

/** Query identity: everything that changes the numbers, including the cleaned filters. */
export function widgetQueryKey(ws: string, slug: string, spec: WidgetSpec): QueryKey {
  return ['widget', ws, slug, JSON.stringify({
    source: spec.source,
    measure: spec.measure,
    dimension: spec.dimension,
    dimension2: spec.dimension2,
    filters: cleanFilters(spec.filters),
  })]
}

export function fetchWidget(ws: string, slug: string, spec: WidgetSpec): Promise<WidgetData> {
  return api.widgetQuery(ws, slug, {
    source: spec.source,
    measure: spec.measure,
    dimension: spec.dimension,
    dimension2: spec.dimension2,
    filters: cleanFilters(spec.filters),
  })
}

/** One aggregate request per widget, in dashboard order. */
export function useWidgetQueries(ws: string, slug: string, widgets: WidgetSpec[]) {
  return useQueries({
    queries: widgets.map((spec) => ({
      queryKey: widgetQueryKey(ws, slug, spec),
      queryFn: () => fetchWidget(ws, slug, spec),
      staleTime: 60_000,
      retry: false,
    })),
  })
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
