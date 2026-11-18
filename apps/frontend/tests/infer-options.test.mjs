// The Playground's inference options become form fields for POST /playground/predict.
// Only what the user turned on is sent, so a default run is byte-identical to before.
import test from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_OPTIONS, optionFields, POSTPROCESS, MATCH_METRICS } from '../src/features/playground/inferOptions.ts'

const fields = (patch = {}) => Object.fromEntries(optionFields({
  slice: { ...DEFAULT_OPTIONS.slice, ...(patch.slice ?? {}) },
  model: { ...DEFAULT_OPTIONS.model, ...(patch.model ?? {}) },
}))

test('a default run sends nothing', () => {
  assert.deepEqual(optionFields(DEFAULT_OPTIONS), [])
})

test('slicing sends separate sizes, overlap ratios and every post-processing choice', () => {
  const f = fields({ slice: { on: true, width: 512, height: 384, overlapW: 25, overlapH: 10, standard: true, minArea: 20,
    post: 'NMM', metric: 'IOS', threshold: 60, agnostic: true } })

  assert.deepEqual(f, {
    slice_width: '512', slice_height: '384', overlap_width_ratio: '0.25', overlap_height_ratio: '0.1',
    perform_standard_pred: 'true', min_area_ratio: '0.2', postprocess_type: 'NMM',
    postprocess_match_metric: 'IOS', postprocess_match_threshold: '0.6', postprocess_class_agnostic: 'true',
  })
})

test('auto slice drops the manual sizes but keeps the rest', () => {
  const f = fields({ slice: { on: true, auto: true, post: 'GREEDYNMM' } })

  assert.equal(f.auto_slice, 'true')
  assert.equal(f.slice_width, undefined)
  assert.equal(f.overlap_width_ratio, undefined)
  assert.equal(f.postprocess_type, 'GREEDYNMM')
})

test('slice settings are ignored while slicing is off', () => {
  assert.deepEqual(optionFields({ slice: { ...DEFAULT_OPTIONS.slice, on: false, width: 999 }, model: DEFAULT_OPTIONS.model }), [])
})

test('inference-time options are sent only when set', () => {
  const f = fields({ model: { imgsz: 1280, maxDet: 50, agnosticNms: true, augment: true, half: false, retina: true, classIds: ' 0, 2 ' } })

  assert.deepEqual(f, { imgsz: '1280', max_det: '50', agnostic_nms: 'true', augment: 'true', retina_masks: 'true', class_ids: '0,2' })
})

test('the choices match what the server accepts', () => {
  assert.deepEqual([...POSTPROCESS], ['NMS', 'NMM', 'GREEDYNMM', 'LSNMS'])
  assert.deepEqual([...MATCH_METRICS], ['IOU', 'IOS'])
})
