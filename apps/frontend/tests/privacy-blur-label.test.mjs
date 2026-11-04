// Face-blur copy: the switch must name every source the API anonymises, and the DPA must not
// keep claiming video-only coverage. Runs with the built-in Node test runner:
//   node --test tests/privacy-blur-label.test.mjs   (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const privacyUi = read('../src/features/governance/Privacy.tsx')
const dpaSource = read('../../backend/app/routers/privacy.py')

test('the face-blur switch names uploaded images and video frames', () => {
  assert.match(privacyUi, /Blur faces in uploaded images and video frames of \$\{project\.name\}/)
  // The visible on/off state next to the switch stays as-is.
  assert.match(privacyUi, /Blur faces \{v\.face_blur \? 'on' : 'off'\}/)
})

test('the DPA promises uploaded images and video frames, not video only', () => {
  assert.match(dpaSource, /faces in uploaded images and in video frames are blurred/)
  assert.match(dpaSource, /Stream-frame coverage follows the stream manager/)
  assert.doesNotMatch(dpaSource, /uploaded video frames/i)
  assert.doesNotMatch(dpaSource, /video frames only/i)
})
