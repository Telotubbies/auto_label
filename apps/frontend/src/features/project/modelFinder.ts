/** Models > Search: pure find-and-sort over a project's trained models. */
import type { ModelItem } from '@/lib/types'

export const MODEL_TABS = ['evaluation', 'leaderboard', 'search'] as const
export type ModelTab = (typeof MODEL_TABS)[number]

/** `?tab=search` opens the Search tab; anything unknown is the default tab. */
export function tabFromParams(params: URLSearchParams): ModelTab {
  const t = params.get('tab')
  return (MODEL_TABS as readonly string[]).includes(t ?? '') ? (t as ModelTab) : 'evaluation'
}

export interface ModelQuery { q?: string; status?: string; task?: string }

export const headlineScore = (m: Pick<ModelItem, 'task' | 'metrics'>): number | null =>
  (m.task === 'classify' ? m.metrics.accuracy_top1 : m.metrics.map50) ?? null

/** Filter by text (name, architecture, class names), status and task; best headline score first, unscored last. */
export function searchModels(models: ModelItem[], { q = '', status = '', task = '' }: ModelQuery): ModelItem[] {
  const needle = q.trim().toLowerCase()
  const hit = (m: ModelItem) =>
    (!status || m.status === status) && (!task || m.task === task) &&
    (!needle || [m.name, m.arch, m.variant ?? '', ...(m.classes ?? [])].some((x) => x.toLowerCase().includes(needle)))
  return models.filter(hit).sort((a, b) => (headlineScore(b) ?? -1) - (headlineScore(a) ?? -1))
}
