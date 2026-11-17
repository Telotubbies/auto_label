/**
 * The calculator's pure half (T-1005): the form, its validation, the request and every string the
 * screen prints. No React, no fetch, no maths of its own — the endpoint (T-1004) is the only place
 * the formulas live. The range sentences here mirror the server's 422 text one for one.
 */
import type { InferenceEstimate, InferenceEstimateIn, InferenceQuant } from '../../lib/types'

/** A preset's geometry is fixed: choosing one fills these five fields and locks them. */
export type CalcSource = 'preset' | 'custom'

/** Numeric inputs stay strings: what the admin typed is what the field holds, empty included. */
export type CalcForm = {
  preset: string
  source: CalcSource
  params: string
  activeParams: string
  layers: string
  kvHeads: string
  headDim: string
  context: string
  quant: InferenceQuant
  batch: string
  users: string
  promptTokens: string
  outputTokens: string
  gpuPreset: string
  gpuCount: string
  tensorParallel: string
  vramGb: string
  bwGbs: string
  fp16Tflops: string
  engine: string
  usable: string
}

/** The four models the calculator ships with until the model catalogue lands (T-1010). */
export const MODEL_PRESETS = [
  { id: 'qwen2.5-vl-7b', name: 'Qwen2.5-VL 7B', params: '7.6', layers: '28', kvHeads: '4', headDim: '128', context: '8192' },
  { id: 'llama-3.1-8b', name: 'Llama 3.1 8B', params: '8.0', layers: '32', kvHeads: '8', headDim: '128', context: '8192' },
  { id: 'gemma-2-9b', name: 'Gemma 2 9B', params: '9.2', layers: '42', kvHeads: '8', headDim: '256', context: '8192' },
  { id: 'llama-3.1-70b', name: 'Llama 3.1 70B', params: '70.6', layers: '80', kvHeads: '8', headDim: '128', context: '8192' },
] as const

export const QUANTS: { id: InferenceQuant; label: string }[] = [
  { id: 'bf16', label: 'BF16' },
  { id: 'fp16', label: 'FP16' },
  { id: 'fp32', label: 'FP32' },
  { id: 'fp8', label: 'FP8' },
  { id: 'int8', label: 'INT8' },
  { id: 'int4', label: 'INT4' },
  { id: 'gguf_q8', label: 'GGUF Q8_0 (8.5-bit)' },
  { id: 'gguf_q4_k_m', label: 'GGUF Q4_K_M (4.8-bit)' },
]

/** The four engines the card names; each one's overhead is the server's (T-1004), never sent here. */
export const ENGINES = [
  { id: 'vllm', label: 'vLLM' },
  { id: 'llamacpp', label: 'llama.cpp' },
  { id: 'sglang', label: 'SGLang' },
  { id: 'tensorrtllm', label: 'TensorRT-LLM' },
]

const BASE_FORM: CalcForm = {
  preset: 'qwen2.5-vl-7b', source: 'preset',
  params: '7.6', activeParams: '', layers: '28', kvHeads: '4', headDim: '128', context: '8192',
  quant: 'bf16', batch: '4', users: '1', promptTokens: '', outputTokens: '',
  gpuPreset: 'rtx4090', gpuCount: '1', tensorParallel: '1',
  vramGb: '', bwGbs: '', fp16Tflops: '',
  engine: 'vllm', usable: '',
}

/** The preset row, or undefined for `custom`. */
export function presetRow(id: string) {
  return MODEL_PRESETS.find((row) => row.id === id)
}

/** A preset fills params, layers, KV heads, head dim and context; `custom` keeps what is there. */
export function presetToForm(id: string, base: CalcForm = BASE_FORM): CalcForm {
  const row = presetRow(id)
  if (!row) return { ...base, preset: 'custom', source: 'custom' }
  return {
    ...base, preset: row.id, source: 'preset',
    params: row.params, layers: row.layers, kvHeads: row.kvHeads, headDim: row.headDim, context: row.context,
  }
}

/** `Edit as custom` keeps every value and hands the geometry back to the admin. */
export function detach(form: CalcForm): CalcForm {
  return { ...form, source: 'custom' }
}

/**
 * The server's `{value:,.0f}` range text, so a browser sentence and its 422 read the same. Python
 * rounds half to even and JavaScript does not, which is visible on the usable fraction's 0.5.
 */
const rounded = (value: number) => {
  const floor = Math.floor(value)
  const rest = value - floor
  if (rest > 0.5) return floor + 1
  if (rest < 0.5) return floor
  return floor % 2 === 0 ? floor : floor + 1
}
const range = (label: string, low: number, high: number) =>
  `${label} must be between ${rounded(low).toLocaleString('en-US')} ` +
  `and ${rounded(high).toLocaleString('en-US')}.`

const number = (value: string) => (value.trim() === '' ? Number.NaN : Number(value))

/** Field → sentence for every value the endpoint would refuse; `{}` means "send it". */
export function fieldErrors(form: CalcForm): Record<string, string> {
  const errors: Record<string, string> = {}
  const inRange = (key: keyof CalcForm, label: string, low: number, high: number) => {
    const value = number(form[key] as string)
    if (!Number.isFinite(value) || value < low || value > high) errors[key] = range(label, low, high)
  }

  inRange('params', 'Parameters', 0.01, 2_000)
  if (form.activeParams.trim()) inRange('activeParams', 'Active parameters', 0.01, 2_000)
  inRange('layers', 'Layers', 1, 200)
  inRange('kvHeads', 'KV heads', 1, 256)
  inRange('headDim', 'Head dim', 8, 512)
  inRange('context', 'Context', 128, 1_000_000)
  inRange('batch', 'Batch', 1, 1_024)
  inRange('users', 'Concurrent users', 1, 10_000)
  inRange('gpuCount', 'GPU count', 1, 64)
  inRange('tensorParallel', 'Tensor parallel', 1, number(form.gpuCount))
  if (!errors.kvHeads && !errors.tensorParallel) {
    const kvHeads = Math.trunc(number(form.kvHeads))
    const tp = Math.trunc(number(form.tensorParallel))
    if (kvHeads % tp !== 0) {
      errors.tensorParallel = `KV heads (${kvHeads}) must divide by tensor parallel (${tp}).`
    }
  }
  if (form.promptTokens.trim()) inRange('promptTokens', 'Prompt tokens', 1, 1_000_000)
  if (form.outputTokens.trim()) inRange('outputTokens', 'Output tokens', 1, 1_000_000)
  if (form.gpuPreset === 'custom') {
    for (const [key, label] of [['vramGb', 'Custom VRAM'], ['bwGbs', 'Custom bandwidth'],
      ['fp16Tflops', 'Custom FP16 TFLOPS']] as const) {
      const value = number(form[key])
      if (!Number.isFinite(value) || value <= 0) errors[key] = `${label} must be a positive number.`
    }
  }
  if (form.usable.trim()) inRange('usable', 'Usable fraction', 0.5, 1)
  return errors
}

/** The request body: a preset sends its own geometry, a detached form sends what was typed. */
export function toRequest(form: CalcForm): InferenceEstimateIn {
  const geometry = form.source === 'preset' ? presetRow(form.preset) ?? form : form
  return {
    model: {
      params_b: number(geometry.params),
      active_params_b: form.activeParams.trim() ? number(form.activeParams) : null,
      layers: number(geometry.layers),
      kv_heads: number(geometry.kvHeads),
      head_dim: number(geometry.headDim),
    },
    quant: form.quant,
    context: number(geometry.context),
    batch: number(form.batch),
    users: number(form.users),
    prompt_tokens: form.promptTokens.trim() ? number(form.promptTokens) : null,
    output_tokens: form.outputTokens.trim() ? number(form.outputTokens) : null,
    gpu: form.gpuPreset === 'custom'
      ? { preset: null, vram_gb: number(form.vramGb), bw_gbs: number(form.bwGbs), fp16_tflops: number(form.fp16Tflops) }
      : { preset: form.gpuPreset },
    gpu_count: number(form.gpuCount),
    tensor_parallel: number(form.tensorParallel),
    engine: form.engine,
    usable: form.usable.trim() ? number(form.usable) : null,
  }
}

/** GiB at one decimal: the estimate never implies a precision it does not have. */
export const formatGb = (value: number) => `${value.toFixed(1)} GB`
/** tok/s as a whole number, for the same reason. */
export const formatTps = (value: number) => `${Math.round(value)} tok/s`

/** The chip's sentence: the spare or the shortfall, never a bare boolean. */
export function verdictCopy(result: InferenceEstimate): string {
  const spare = result.per_gpu.usable_gb - result.per_gpu.total_gb
  return result.fits
    ? `Fits on this card with ${formatGb(spare)} spare.`
    : `Does not fit: ${formatGb(-spare)} short.`
}

/** Every input, the table and the range, in one string for a chat or an email. */
export function copyText(form: CalcForm, result: InferenceEstimate, gpuName: string = form.gpuPreset): string {
  const geometry = form.source === 'preset' ? presetRow(form.preset) ?? form : form
  const per = result.per_gpu
  const fol = result.throughput
  const model = presetRow(form.preset)?.name ?? 'Custom model'
  const engine = ENGINES.find((row) => row.id === form.engine)?.label ?? form.engine
  return [
    'LabelDesk inference estimate',
    `Model: ${model} — ${geometry.params}B parameters, ${geometry.layers} layers, ` +
      `${geometry.kvHeads} KV heads × ${geometry.headDim}`,
    `Precision: ${form.quant}`,
    `Context: ${geometry.context} tokens`,
    `Batch: ${form.batch}, concurrent users: ${form.users}`,
    `Prompt / output tokens: ${form.promptTokens || 'context'} / ${form.outputTokens || 'not set'}`,
    `GPU: ${gpuName} × ${form.gpuCount}`,
    `Tensor parallel: ${form.tensorParallel}`,
    `Engine: ${engine}, usable memory ${form.usable ? form.usable : 'engine default'}`,
    '',
    `Per GPU: weights ${formatGb(per.weights_gb)}, KV cache ${formatGb(per.kv_gb)}, ` +
      `activations ${formatGb(per.activations_gb)}, framework overhead ${formatGb(per.overhead_gb)}, ` +
      `total ${formatGb(per.total_gb)}, usable ${formatGb(per.usable_gb)}`,
    `All GPUs: ${formatGb(result.total_gb)}`,
    `Decode: ${formatTps(fol.estimate_tps)}, memory-bound ${formatTps(fol.memory_bound_tps)}, ` +
      `compute-bound ${formatTps(fol.compute_bound_tps)}, range ${Math.round(fol.low_tps)}–` +
      `${Math.round(fol.high_tps)} tok/s`,
    `Time to first token: ${Math.round(result.ttft_ms)} ms`,
    `Verdict: ${verdictCopy(result)}`,
    '',
    'Estimate, not a benchmark.',
  ].join('\n')
}
