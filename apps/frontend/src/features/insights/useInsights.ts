// TanStack Query hooks for the read-only Insights endpoints. No polling: analytics are cached
// server-side by data signature, so a tab focus refetch is enough.
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

const STALE = 60_000

export function useTrainingInsights(ws: string, slug: string, runs?: string[], enabled = true) {
  const key = runs?.length ? runs.join(',') : 'all'
  return useQuery({
    queryKey: ['insights', 'training', ws, slug, key],
    queryFn: () => api.insightsTraining(ws, slug, runs),
    enabled,
    staleTime: STALE,
  })
}

export function useModelInsights(ws: string, slug: string, modelId?: string) {
  return useQuery({
    queryKey: ['insights', 'model', ws, slug, modelId ?? ''],
    queryFn: () => api.insightsModel(ws, slug, modelId!),
    enabled: !!modelId,
    staleTime: STALE,
  })
}

export function useCompareInsights(ws: string, slug: string, modelIds: string[]) {
  const key = modelIds.join(',')
  return useQuery({
    queryKey: ['insights', 'compare', ws, slug, key],
    queryFn: () => api.insightsCompare(ws, slug, modelIds),
    enabled: modelIds.length >= 2,
    staleTime: STALE,
    // A 400 explains why the set is invalid (mixed versions/tasks); retrying cannot fix it.
    retry: false,
  })
}
