// T-1005: the calculator's pure helpers. Every sentence the browser prints for a bad field must be the
// one the estimate endpoint's 422 carries, so the two can never disagree about a range.
//   node --test tests/inference-calc.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  copyText, detach, fieldErrors, formatGb, presetToForm, toRequest, verdictCopy,
} from '../src/features/inference/calcModel.ts'

/** A result shaped like POST /inference/estimate's 200 body; only the numbers these tests read. */
const DEFAULT_RESULT = {
  per_gpu: {
    weights_gb: 14.2, kv_gb: 1.75, activations_gb: 0.77, overhead_gb: 2.0,
    total_gb: 18.7, usable_gb: 21.6,
  },
  total_gb: 18.7, fits: true, verdict: '',
  throughput: { memory_bound_tps: 166, compute_bound_tps: 2700, estimate_tps: 133, low_tps: 90, high_tps: 220 },
  ttft_ms: 250, assumptions: [], sources: [],
}
const result = (over = {}) => ({
  ...DEFAULT_RESULT,
  ...over,
  per_gpu: { ...DEFAULT_RESULT.per_gpu, ...(over.per_gpu ?? {}) },
})

test('test_form_errors_mirror_the_server_ranges', () => {
  const base = presetToForm('qwen2.5-vl-7b')
  assert.deepEqual(fieldErrors(base), {}, 'a complete preset with a card is valid')

  assert.equal(fieldErrors({ ...base, context: '0' }).context,
    'Context must be between 128 and 1,000,000.')
  assert.equal(fieldErrors({ ...base, batch: '0' }).batch,
    'Batch must be between 1 and 1,024.')
  // GPU count 4 so tensor parallel 3 is inside its own range first, then the KV-head rule speaks.
  assert.equal(fieldErrors({ ...base, gpuCount: '4', tensorParallel: '3' }).tensorParallel,
    'KV heads (4) must divide by tensor parallel (3).')
  assert.equal(fieldErrors({ ...base, usable: '1.5' }).usable,
    'Usable fraction must be between 0 and 1.')
})

test('test_a_preset_fills_the_geometry_and_can_be_detached', () => {
  const filled = presetToForm('qwen2.5-vl-7b')
  assert.equal(filled.source, 'preset')
  assert.deepEqual([filled.params, filled.layers, filled.kvHeads, filled.headDim, filled.context],
    ['7.6', '28', '4', '128', '8192'])

  // A preset's geometry is fixed: a stale edit cannot change what is sent.
  const tampered = { ...filled, params: '99' }
  assert.equal(toRequest(tampered).model.params_b, 7.6)

  const own = detach(tampered)
  assert.equal(own.source, 'custom', 'Edit as custom detaches the preset')
  assert.deepEqual([own.params, own.layers, own.kvHeads, own.headDim, own.context],
    ['99', '28', '4', '128', '8192'], 'detach keeps every value the admin typed')
  assert.equal(toRequest(own).model.params_b, 99)
})

test('test_verdict_copy_is_a_sentence_not_a_bare_boolean', () => {
  assert.equal(verdictCopy(result()), 'Fits on this card with 2.9 GB spare.')
  assert.equal(verdictCopy(result({ fits: false, per_gpu: { total_gb: 34.0 } })),
    'Does not fit: 12.4 GB short.')
  assert.equal(formatGb(2.94), '2.9 GB', 'one decimal, never a second')
})

test('test_copy_text_includes_every_input_and_the_range', () => {
  const text = copyText(presetToForm('qwen2.5-vl-7b'), result())
  for (const part of ['Context: 8192', 'Batch: 4', 'Tensor parallel: 1', '133 tok/s',
    '90\u2013220 tok/s', '18.7 GB', '21.6 GB']) {
    assert.ok(text.includes(part), `the copied text carries "${part}"`)
  }
  assert.ok(text.trimEnd().endsWith('Estimate, not a benchmark.'),
    'the last line is the same disclaimer as the panel')
})

test('test_custom_gpu_reveals_three_fields', () => {
  const custom = { ...presetToForm('qwen2.5-vl-7b'), gpuPreset: 'custom', vramGb: '', bwGbs: '', fp16Tflops: '' }
  const errors = fieldErrors(custom)
  assert.equal(errors.vramGb, 'Custom VRAM must be a positive number.')
  assert.equal(errors.bwGbs, 'Custom bandwidth must be a positive number.')
  assert.equal(errors.fp16Tflops, 'Custom FP16 TFLOPS must be a positive number.')

  const preset = presetToForm('qwen2.5-vl-7b')
  assert.equal(fieldErrors(preset).vramGb, undefined, 'a preset ignores the custom card numbers')
  assert.equal(fieldErrors(preset).bwGbs, undefined)
  assert.equal(fieldErrors(preset).fp16Tflops, undefined)
})
