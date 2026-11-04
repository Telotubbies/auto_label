import type { WidgetSource } from './widgetModel'

export const SOURCE_LABELS: Record<WidgetSource, string> = {
  dataset: 'Dataset',
  version: 'Version',
  model: 'Model eval',
  streams: 'Stream events',
}

const MEASURE_LABELS: Record<string, string> = {
  annotations: 'annotations',
  images: 'images',
  ap: 'AP',
  events: 'events',
  dwell_seconds: 'dwell time',
}

const DIMENSION_LABELS: Record<string, string> = {
  class: 'class',
  split: 'split',
  source: 'label source',
  batch: 'upload batch',
  tag: 'tag',
  none: 'total',
  day: 'day',
  hour: 'hour',
  rule: 'rule',
  zone: 'zone',
  stream: 'camera',
}

export function sourceLabel(source: WidgetSource): string {
  return SOURCE_LABELS[source] ?? source
}

export function measureLabel(measure: string, source?: WidgetSource): string {
  if (source === 'model' && measure === 'ap') return 'AP'
  return MEASURE_LABELS[measure] ?? measure.replace(/_/g, ' ')
}

export function dimensionLabel(dimension: string): string {
  return DIMENSION_LABELS[dimension] ?? dimension
}
