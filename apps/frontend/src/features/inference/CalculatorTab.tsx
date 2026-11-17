/**
 * The Calculator tab (T-1005): one form, one answer from `POST /inference/estimate` (T-1004) and the
 * defaults that answer used. The formulas live only in the endpoint — this screen never recomputes a
 * number, it formats what came back. Two columns at ≥ 1024 px; at 375 px the form stacks above the
 * results and the results wait behind `Show estimate`.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Glass } from '@/components/glass'
import { Button, Card, EmptyState, Input, Select } from '@/components/ui'
import { ApiError } from '@/lib/api/client'
import { inferenceCatalog, inferenceEstimate } from '@/lib/api/inference'
import { cn } from '@/lib/utils'
import type { InferenceEstimate } from '@/lib/types'
import {
  ENGINES, MODEL_PRESETS, QUANTS, copyText, detach, fieldErrors, formatGb, formatTps,
  presetToForm, toRequest, verdictCopy, type CalcForm,
} from './calcModel'

/** The three sources the endpoint cites, by the name of the document rather than its host. */
const SOURCE_LABELS: Record<string, string> = {
  'blog.eleuther.ai': 'Transformer Math 101',
  'kipp.ly': 'Transformer Inference Arithmetic',
  'docs.vllm.ai': 'vLLM: conserving memory',
}
const sourceLabel = (url: string) => {
  try { return SOURCE_LABELS[new URL(url).hostname] ?? new URL(url).hostname } catch { return url }
}

/** One labelled control with the inline sentence the server's 422 would carry. */
function Row({ id, label, error, hint, children }: {
  id: string; label: string; error?: string; hint?: string; children: ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      {children}
      {error
        ? <p id={`${id}-error`} className="mt-1 text-xs text-destructive">{error}</p>
        : hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

export default function CalculatorTab() {
  const { ws = '' } = useParams()
  const catalog = useQuery({
    queryKey: ['inference-catalog', ws],
    queryFn: () => inferenceCatalog(ws),
    staleTime: 300_000,
  })
  const [form, setForm] = useState<CalcForm>(() => presetToForm('qwen2.5-vl-7b'))
  const [result, setResult] = useState<InferenceEstimate | null>(null)
  const [error, setError] = useState<{ status: number; message: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [asked, setAsked] = useState(false)                       // no auto-run on mount
  const [retry, setRetry] = useState(0)
  const [copied, setCopied] = useState(false)
  const [wide] = useState(() => window.matchMedia('(min-width: 1024px)').matches)
  const [visible, setVisible] = useState(wide)                    // the 375 px `Show estimate` gate
  const attempt = useRef(0)

  const errors = fieldErrors(form)
  const valid = Object.keys(errors).length === 0
  const gpus = (catalog.data?.gpus ?? []).filter((row) => row.vram_gb > 0)
  const gpu = gpus.find((row) => row.id === form.gpuPreset)
  const answer = error ? null : result

  useEffect(() => {
    const id = ++attempt.current                     // a newer attempt wins; an older answer is dropped
    if (!asked || !valid || !visible) { setBusy(false); return }
    const timer = window.setTimeout(() => {
      setBusy(true)
      inferenceEstimate(ws, toRequest(form))
        .then((next) => { if (id === attempt.current) { setResult(next); setError(null) } })
        .catch((err: unknown) => {
          if (id !== attempt.current) return
          setError({
            status: err instanceof ApiError ? err.status : 0,
            message: err instanceof ApiError ? err.message : 'Check the connection and try again.',
          })
        })
        .finally(() => { if (id === attempt.current) setBusy(false) })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [form, ws, asked, valid, visible, retry])

  const change = (patch: Partial<CalcForm>) => {
    setAsked(true)
    setForm((current) => ({ ...current, ...patch }))
  }

  /** The mobile button: reveal the results and, when a field is wrong, put the caret on it. */
  const ask = () => {
    setVisible(true)
    setAsked(true)
    const first = Object.keys(fieldErrors(form))[0]
    if (first) document.getElementById(`calc-${first}`)?.focus()
  }

  const copy = async () => {
    if (!result) return
    await navigator.clipboard.writeText(copyText(form, result, gpu?.name ?? form.gpuPreset))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  /** Props every input shares: the error sentence, the red edge and the focusable id. */
  const field = (key: keyof CalcForm, extra?: string) => ({
    id: `calc-${key}`,
    'aria-invalid': Boolean(errors[key]),
    'aria-describedby': errors[key] ? `calc-${key}-error` : undefined,
    className: cn(errors[key] && 'border-destructive', extra),
  })
  const geometry = (key: 'params' | 'layers' | 'kvHeads' | 'headDim' | 'context') =>
    cn(form.source === 'preset' && 'text-muted-foreground')

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="min-w-0 space-y-3 p-4 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <Row id="calc-preset" label="Model source">
            <Select {...field('preset')} value={form.preset}
              onChange={(e) => { setAsked(true); setForm(presetToForm(e.target.value, form)) }}>
              {MODEL_PRESETS.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              <option value="custom">Custom</option>
            </Select>
          </Row>
          <Row id="calc-quant" label="Precision">
            <Select {...field('quant')} value={form.quant}
              onChange={(e) => change({ quant: e.target.value as CalcForm['quant'] })}>
              {QUANTS.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}
            </Select>
          </Row>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Row id="calc-params" label="Parameters (B)" error={errors.params}>
            <Input {...field('params', geometry('params'))} inputMode="decimal" value={form.params}
              readOnly={form.source === 'preset'} onChange={(e) => change({ params: e.target.value })} />
          </Row>
          <Row id="calc-layers" label="Layers" error={errors.layers}>
            <Input {...field('layers', geometry('layers'))} inputMode="numeric" value={form.layers}
              readOnly={form.source === 'preset'} onChange={(e) => change({ layers: e.target.value })} />
          </Row>
          <Row id="calc-kvHeads" label="KV heads" error={errors.kvHeads}>
            <Input {...field('kvHeads', geometry('kvHeads'))} inputMode="numeric" value={form.kvHeads}
              readOnly={form.source === 'preset'} onChange={(e) => change({ kvHeads: e.target.value })} />
          </Row>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Row id="calc-headDim" label="Head dim" error={errors.headDim}>
            <Input {...field('headDim', geometry('headDim'))} inputMode="numeric" value={form.headDim}
              readOnly={form.source === 'preset'} onChange={(e) => change({ headDim: e.target.value })} />
          </Row>
          <Row id="calc-context" label="Context (tokens)" error={errors.context}>
            <Input {...field('context', geometry('context'))} inputMode="numeric" value={form.context}
              readOnly={form.source === 'preset'} onChange={(e) => change({ context: e.target.value })} />
          </Row>
        </div>

        {form.source === 'preset' && (
          <Button variant="ghost" size="sm" onClick={() => change(detach(form))}>
            Edit as custom
          </Button>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Row id="calc-batch" label="Batch" error={errors.batch}>
            <Input {...field('batch')} inputMode="numeric" value={form.batch}
              onChange={(e) => change({ batch: e.target.value })} />
          </Row>
          <Row id="calc-users" label="Concurrent users" error={errors.users}>
            <Input {...field('users')} inputMode="numeric" value={form.users}
              onChange={(e) => change({ users: e.target.value })} />
          </Row>
          <Row id="calc-promptTokens" label="Prompt tokens" error={errors.promptTokens}
            hint="Empty uses the context.">
            <Input {...field('promptTokens')} inputMode="numeric" value={form.promptTokens}
              onChange={(e) => change({ promptTokens: e.target.value })} />
          </Row>
          <Row id="calc-outputTokens" label="Output tokens" error={errors.outputTokens}>
            <Input {...field('outputTokens')} inputMode="numeric" value={form.outputTokens}
              onChange={(e) => change({ outputTokens: e.target.value })} />
          </Row>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Row id="calc-gpuPreset" label="Card" error={errors.gpuPreset}>
            <Select {...field('gpuPreset')} value={form.gpuPreset}
              onChange={(e) => change({ gpuPreset: e.target.value })}>
              {gpus.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              {!gpus.length && (
                <option value={form.gpuPreset}>
                  {catalog.isError ? 'GPU list unavailable' : 'Loading cards…'}
                </option>
              )}
              <option value="custom">Custom</option>
            </Select>
          </Row>
          <Row id="calc-gpuCount" label="GPUs" error={errors.gpuCount}>
            <Input {...field('gpuCount')} inputMode="numeric" value={form.gpuCount}
              onChange={(e) => change({ gpuCount: e.target.value })} />
          </Row>
          <Row id="calc-tensorParallel" label="Tensor parallel" error={errors.tensorParallel}>
            <Input {...field('tensorParallel')} inputMode="numeric" value={form.tensorParallel}
              onChange={(e) => change({ tensorParallel: e.target.value })} />
          </Row>
        </div>

        {form.gpuPreset === 'custom' && (
          <div className="grid gap-3 sm:grid-cols-3">
            <Row id="calc-vramGb" label="VRAM (GB)" error={errors.vramGb}>
              <Input {...field('vramGb')} inputMode="decimal" value={form.vramGb}
                onChange={(e) => change({ vramGb: e.target.value })} />
            </Row>
            <Row id="calc-bwGbs" label="Bandwidth (GB/s)" error={errors.bwGbs}>
              <Input {...field('bwGbs')} inputMode="decimal" value={form.bwGbs}
                onChange={(e) => change({ bwGbs: e.target.value })} />
            </Row>
            <Row id="calc-fp16Tflops" label="FP16 TFLOPS" error={errors.fp16Tflops}>
              <Input {...field('fp16Tflops')} inputMode="decimal" value={form.fp16Tflops}
                onChange={(e) => change({ fp16Tflops: e.target.value })} />
            </Row>
          </div>
        )}

        <Row id="calc-engine" label="Engine">
          <Select {...field('engine')} value={form.engine}
            onChange={(e) => change({ engine: e.target.value })}>
            {ENGINES.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}
          </Select>
        </Row>

        <details className="rounded-md border border-input p-3">
          <summary className="cursor-pointer text-sm font-medium">Advanced</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Row id="calc-activeParams" label="Active parameters (B)" error={errors.activeParams}
              hint="MoE only; empty means every parameter is active.">
              <Input {...field('activeParams')} inputMode="decimal" value={form.activeParams}
                onChange={(e) => change({ activeParams: e.target.value })} />
            </Row>
            <Row id="calc-usable" label="Usable memory (fraction)" error={errors.usable}
              hint="Empty uses the engine's own default.">
              <Input {...field('usable')} inputMode="decimal" value={form.usable}
                onChange={(e) => change({ usable: e.target.value })} />
            </Row>
          </div>
        </details>

        <Button className="w-full lg:hidden" onClick={ask}>Show estimate</Button>
      </Card>

      <div className="min-w-0 space-y-4">
        <div className={cn('space-y-4', !visible && 'hidden lg:block')}>
          {error ? (
            <Card className="p-4 sm:p-6">
              <p role="alert" className="text-sm font-medium">The estimate did not run.</p>
              {error.status === 422 && <p className="mt-1 text-xs text-muted-foreground">{error.message}</p>}
              <Button variant="outline" size="sm" className="mt-3" onClick={() => setRetry((n) => n + 1)}>
                Retry
              </Button>
            </Card>
          ) : answer ? (
            <Card className="space-y-4 p-4 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
                    answer.fits ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning')}>
                    {answer.fits ? 'Fits' : 'Does not fit'}
                  </span>
                  <p className="mt-1.5 text-sm">{verdictCopy(answer)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span aria-live="polite" className="text-xs text-muted-foreground">{busy ? 'Updating…' : ''}</span>
                  <Button variant="outline" size="sm" onClick={copy}>{copied ? 'Copied' : 'Copy as text'}</Button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">
                    Estimated memory per GPU: weights, KV cache, activations, framework overhead, total and usable
                  </caption>
                  <thead>
                    <tr className="text-xs text-muted-foreground">
                      <th scope="col" className="sticky left-0 bg-card py-1.5 pr-3 text-left font-medium">Memory</th>
                      <th scope="col" className="py-1.5 pr-3 text-right font-medium">Weights</th>
                      <th scope="col" className="py-1.5 pr-3 text-right font-medium">KV cache</th>
                      <th scope="col" className="py-1.5 pr-3 text-right font-medium">Activations</th>
                      <th scope="col" className="py-1.5 pr-3 text-right font-medium">Overhead</th>
                      <th scope="col" className="py-1.5 pr-3 text-right font-medium">Total</th>
                      <th scope="col" className="py-1.5 text-right font-medium">Usable</th>
                    </tr>
                  </thead>
                  <tbody className="tabular-nums">
                    <tr className="border-t">
                      <th scope="row" className="sticky left-0 bg-card py-1.5 pr-3 text-left font-medium">Per GPU</th>
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.per_gpu.weights_gb)}</td>
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.per_gpu.kv_gb)}</td>
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.per_gpu.activations_gb)}</td>
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.per_gpu.overhead_gb)}</td>
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.per_gpu.total_gb)}</td>
                      <td className="py-1.5 text-right">{formatGb(answer.per_gpu.usable_gb)}</td>
                    </tr>
                    <tr className="border-t">
                      <th scope="row" className="sticky left-0 bg-card py-1.5 pr-3 text-left font-medium">All GPUs</th>
                      <td colSpan={4} />
                      <td className="py-1.5 pr-3 text-right">{formatGb(answer.total_gb)}</td>
                      <td className="py-1.5 text-right text-muted-foreground">—</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-muted-foreground">Decode, estimate</dt>
                  <dd className="font-medium">
                    {formatTps(answer.throughput.estimate_tps)}{' '}
                    <span className="text-xs font-normal text-muted-foreground">
                      {Math.round(answer.throughput.low_tps)}–{Math.round(answer.throughput.high_tps)} tok/s
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Time to first token</dt>
                  <dd className="font-medium">{Math.round(answer.ttft_ms)} ms</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Memory-bound ceiling</dt>
                  <dd>{formatTps(answer.throughput.memory_bound_tps)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Compute-bound ceiling</dt>
                  <dd>{formatTps(answer.throughput.compute_bound_tps)}</dd>
                </div>
              </dl>
            </Card>
          ) : busy ? (
            <Card className="space-y-2 p-4 sm:p-6" aria-busy="true">
              <p className="text-sm text-muted-foreground">Estimating…</p>
              {[0, 1, 2].map((row) => <div key={row} className="h-8 animate-pulse rounded bg-muted" />)}
            </Card>
          ) : (
            <Card className="p-4 sm:p-6">
              <EmptyState title="Set a model and a card to see whether it fits." />
            </Card>
          )}
        </div>

        <Glass className="rounded-xl p-4">
          <details open={!wide}>
            <summary className="cursor-pointer text-sm font-medium">Assumptions</summary>
            <p className="mt-1.5 text-xs text-muted-foreground">Estimate, not a benchmark.</p>
            {answer ? (
              <>
                <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                  {answer.assumptions.map((line) => <li key={line}>{line}</li>)}
                </ul>
                <p className="mt-3 text-xs">
                  <span className="font-medium">How this is calculated</span>{' '}
                  {answer.sources.map((url, index) => (
                    <span key={url}>
                      {index > 0 && <span className="text-muted-foreground"> · </span>}
                      <a href={url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-foreground">
                        {sourceLabel(url)}
                      </a>
                    </span>
                  ))}
                </p>
              </>
            ) : (
              <p className="mt-2 text-xs text-muted-foreground">Run an estimate to see the factors it used.</p>
            )}
          </details>
        </Glass>
      </div>
    </div>
  )
}
