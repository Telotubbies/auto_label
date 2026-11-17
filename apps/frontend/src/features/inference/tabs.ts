/**
 * The hub's four panels. The URL query owns the selection (`?tab=`), so a refresh, a job
 * notification link and a shared link all land on the same tab. Pure: the node test imports it
 * directly.
 */
export const INFERENCE_TABS = ['engines', 'models', 'calculator', 'segmentation'] as const
export type InferenceTab = (typeof INFERENCE_TABS)[number]

export const INFERENCE_TAB_LABELS: Record<InferenceTab, string> = {
  engines: 'Engines',
  models: 'Models',
  calculator: 'Calculator',
  segmentation: 'Segmentation',
}

/** `?tab=` wins when it names a panel; absent or unknown values fall back to Engines. */
export function tabFrom(search: string): InferenceTab {
  const value = new URLSearchParams(search).get('tab')
  return (INFERENCE_TABS as readonly string[]).includes(value ?? '') ? (value as InferenceTab) : 'engines'
}
