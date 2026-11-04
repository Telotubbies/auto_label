import { useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button, Field, Input, Modal, Select } from '@/components/ui'
import {
  CHARTS, DIMENSIONS, MEASURES, WIDGET_SIZES, defaultWidget, validateWidgetDraft,
  type ChartKind, type WidgetSpec, type WidgetSource,
} from './widgetModel'
import { dimensionLabel, measureLabel, sourceLabel } from './labels'

export interface WidgetRefs {
  versions: { id: string; number: number; name: string }[]
  models: { id: string; name: string }[]
  classes: { id: string; name: string }[]
  batches: { id: string; name: string }[]
  streams: { id: string; name: string }[]
  tags: { name: string }[]
}

const CHART_LABELS: Record<ChartKind, string> = {
  bar: 'Bar', line: 'Line', scatter: 'Scatter', heatmap: 'Heatmap',
  pie: 'Pie', donut: 'Donut', table: 'Table', kpi: 'KPI',
}

const WIDTH_LABELS: Record<number, string> = { 3: 'Quarter', 4: 'Third', 6: 'Half', 12: 'Full' }

const clean = (filters: WidgetSpec['filters']) => Object.fromEntries(
  Object.entries(filters).filter(([, value]) => value !== '' && value !== undefined),
)

/** Add/edit dialog for one widget: source, measure, dimension(s), chart, filters and width. */
export function WidgetEditor({ initial, refs, onSave, onClose }: {
  initial: WidgetSpec
  refs: WidgetRefs
  onSave: (spec: WidgetSpec) => void
  onClose: () => void
}) {
  const [draft, setDraft] = useState<WidgetSpec>(initial)
  const [errors, setErrors] = useState<string[]>([])
  const filter = (key: string) => draft.filters[key]
  const setFilter = (key: string, value: string | number | undefined) =>
    setDraft((d) => ({ ...d, filters: { ...d.filters, [key]: value } }))

  const dimensions = DIMENSIONS[draft.source]
  const secondOptions = useMemo(
    () => dimensions.filter((d) => d !== 'none' && d !== draft.dimension),
    [dimensions, draft.dimension],
  )
  const isStreams = draft.source === 'streams'
  const isDataset = draft.source === 'dataset' || draft.source === 'version'

  const changeSource = (source: WidgetSource) => {
    const fresh = defaultWidget(source)
    setDraft((d) => ({ ...fresh, id: d.id, title: d.title, w: d.w }))
  }

  const changeChart = (chart: ChartKind) => {
    setDraft((d) => {
      if (chart === 'kpi') return { ...d, chart, dimension: 'none', dimension2: null }
      if (chart !== 'heatmap') return { ...d, chart, dimension2: null }
      const dimension2 = d.dimension2 && d.dimension2 !== d.dimension
        ? d.dimension2
        : secondOptions[0] ?? null
      return { ...d, chart, dimension2 }
    })
  }

  const submit = () => {
    const spec = { ...draft, title: draft.title.trim(), filters: clean(draft.filters) }
    const found = validateWidgetDraft(spec)
    setErrors(found)
    if (!found.length) onSave(spec)
  }

  return (
    <Modal open onClose={onClose} title={initial.title ? 'Edit widget' : 'Add widget'} wide>
      <div className="space-y-4">
        <Field label="Title" hint="Shown above the chart on the dashboard and in exports.">
          <Input value={draft.title} maxLength={120} autoFocus
            onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))} />
        </Field>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Source">
            <Select value={draft.source} onChange={(e) => changeSource(e.target.value as WidgetSource)}>
              {(Object.keys(MEASURES) as WidgetSource[]).map((s) => (
                <option key={s} value={s}>{sourceLabel(s)}</option>
              ))}
            </Select>
          </Field>
          <Field label="Measure">
            <Select value={draft.measure}
              onChange={(e) => setDraft((d) => ({ ...d, measure: e.target.value }))}>
              {MEASURES[draft.source].map((m) => (
                <option key={m} value={m}>{measureLabel(m, draft.source)}</option>
              ))}
            </Select>
          </Field>
          <Field label="Dimension">
            <Select value={draft.dimension} disabled={draft.chart === 'kpi'}
              onChange={(e) => setDraft((d) => {
                const dimension = e.target.value
                const dimension2 = d.dimension2 === dimension ? null : d.dimension2
                return { ...d, dimension, dimension2 }
              })}>
              {dimensions.map((d) => <option key={d} value={d}>{dimensionLabel(d)}</option>)}
            </Select>
          </Field>
          <Field label="Chart">
            <Select value={draft.chart} onChange={(e) => changeChart(e.target.value as ChartKind)}>
              {CHARTS.map((c) => <option key={c} value={c}>{CHART_LABELS[c]}</option>)}
            </Select>
          </Field>
          {draft.chart === 'heatmap' && (
            <Field label="Second dimension" hint="The heatmap rows. It must differ from the first dimension.">
              <Select value={draft.dimension2 ?? ''}
                onChange={(e) => setDraft((d) => ({ ...d, dimension2: e.target.value || null }))}>
                {secondOptions.map((d) => <option key={d} value={d}>{dimensionLabel(d)}</option>)}
              </Select>
            </Field>
          )}
          <Field label="Width" hint="How many of the 12 grid columns this widget spans on wide screens.">
            <Select value={draft.w} onChange={(e) => setDraft((d) => ({ ...d, w: Number(e.target.value) }))}>
              {WIDGET_SIZES.map((w) => <option key={w} value={w}>{WIDTH_LABELS[w]}</option>)}
            </Select>
          </Field>
        </div>

        <fieldset className="rounded-lg border p-3">
          <legend className="px-1 text-xs font-medium text-muted-foreground">Filters</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {draft.source === 'version' && (
              <Field label="Version (required)">
                <Select value={String(filter('version') ?? '')} onChange={(e) => setFilter('version', e.target.value)}>
                  <option value="">Choose a version…</option>
                  {refs.versions.map((v) => (
                    <option key={v.id} value={v.id}>{v.name || `v${v.number}`}</option>
                  ))}
                </Select>
              </Field>
            )}
            {draft.source === 'model' && (
              <Field label="Model (required)">
                <Select value={String(filter('model') ?? '')} onChange={(e) => setFilter('model', e.target.value)}>
                  <option value="">Choose a model…</option>
                  {refs.models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </Select>
              </Field>
            )}
            {(isDataset || draft.source === 'model') && (
              <Field label="Class">
                <Select value={String(filter('class') ?? '')} onChange={(e) => setFilter('class', e.target.value)}>
                  <option value="">Any class</option>
                  {refs.classes.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </Select>
              </Field>
            )}
            {isDataset && (
              <>
                <Field label="Split">
                  <Select value={String(filter('split') ?? '')} onChange={(e) => setFilter('split', e.target.value)}>
                    <option value="">Any split</option>
                    <option value="train">Train</option>
                    <option value="valid">Valid</option>
                    <option value="test">Test</option>
                  </Select>
                </Field>
                <Field label="Label source">
                  <Select value={String(filter('source') ?? '')} onChange={(e) => setFilter('source', e.target.value)}>
                    <option value="">Any source</option>
                    <option value="human">Human</option>
                    <option value="sam3">SAM 3.1</option>
                    <option value="vlm+sam3">VLM + SAM</option>
                  </Select>
                </Field>
                <Field label="Upload batch">
                  <Select value={String(filter('batch') ?? '')} onChange={(e) => setFilter('batch', e.target.value)}>
                    <option value="">Any batch</option>
                    {refs.batches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                  </Select>
                </Field>
                <Field label="Tag">
                  <Select value={String(filter('tag') ?? '')} onChange={(e) => setFilter('tag', e.target.value)}>
                    <option value="">Any tag</option>
                    {refs.tags.map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}
                  </Select>
                </Field>
              </>
            )}
            {isStreams && (
              <>
                <Field label="Camera">
                  <Select value={String(filter('stream') ?? '')} onChange={(e) => setFilter('stream', e.target.value)}>
                    <option value="">Any camera</option>
                    {refs.streams.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </Select>
                </Field>
                <Field label="Rule label">
                  <Input value={String(filter('rule') ?? '')} maxLength={120} placeholder="Any rule"
                    onChange={(e) => setFilter('rule', e.target.value)} />
                </Field>
                <Field label="Window">
                  <Select value={String(filter('days') ?? 30)} onChange={(e) => setFilter('days', Number(e.target.value))}>
                    <option value="7">Last 7 days</option>
                    <option value="30">Last 30 days</option>
                    <option value="90">Last 90 days</option>
                    <option value="365">Last 365 days</option>
                  </Select>
                </Field>
              </>
            )}
            {isStreams && (
              <Field label="Class">
                <Select value={String(filter('class') ?? '')} onChange={(e) => setFilter('class', e.target.value)}>
                  <option value="">Any class</option>
                  {refs.classes.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </Select>
              </Field>
            )}
          </div>
        </fieldset>

        {errors.length > 0 && (
          <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
            <p className="flex items-center gap-1.5 text-sm font-medium text-destructive">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" /> Check this widget
            </p>
            <ul className="mt-1 list-inside list-disc text-xs text-destructive">
              {errors.map((e) => <li key={e}>{e}</li>)}
            </ul>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit}>Save widget</Button>
        </div>
      </div>
    </Modal>
  )
}
