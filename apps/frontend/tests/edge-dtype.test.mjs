// The Edge export panel picks a dtype per preset and names each built artifact ("NCNN · FP16").
import test from 'node:test'
import assert from 'node:assert/strict'
import { pickDtype, artifactLabel, buildBody } from '../src/features/project/edgeDtype.ts'

const dt = (...ids) => ids.map((id, i) => ({ id, label: id.toUpperCase(), default: i === 0, needs_data: id === 'int8' }))
const ncnn = { id: 'ncnn', label: 'NCNN', dtypes: dt('fp32', 'fp16') }
const hailo = { id: 'hailo', label: 'Hailo-8', dtypes: dt('int8') }

test('the picked dtype is kept when the preset offers it and falls back to the default when it does not', () => {
  assert.equal(pickDtype(ncnn, 'fp16'), 'fp16')
  assert.equal(pickDtype(ncnn, 'int8'), 'fp32')
  assert.equal(pickDtype(ncnn, ''), 'fp32')
  assert.equal(pickDtype(undefined, 'fp16'), '')
})

test('the request names the dtype only when it is not the preset default', () => {
  assert.deepEqual(buildBody(ncnn, 'fp32'), { preset: 'ncnn' })
  assert.deepEqual(buildBody(ncnn, 'fp16'), { preset: 'ncnn', dtype: 'fp16' })
  assert.deepEqual(buildBody(hailo, 'int8'), { preset: 'hailo' })
})

test('a built artifact is named by its preset and dtype', () => {
  const list = [ncnn, hailo]
  assert.equal(artifactLabel(list, 'ncnn'), 'NCNN · FP32')
  assert.equal(artifactLabel(list, 'ncnn:fp16'), 'NCNN · FP16')
  assert.equal(artifactLabel(list, 'hailo'), 'Hailo-8')
  assert.equal(artifactLabel(list, 'gone:fp16'), 'gone · FP16')
})
