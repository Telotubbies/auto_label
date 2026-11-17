// T-1105: the upload page's empty state states the size cap, offers the demo set and shows the batch
// and split controls before a file is picked. The cap is enforced by the upload route, so its sentence
// must read the same constant through the same public endpoint — never a second copy in the bundle.
// Source-checked like the other parity guards, because the suite has no DOM renderer.
//   node --test tests/upload-empty-state.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const config = read('../../backend/app/config.py')
const auth = read('../../backend/app/routers/auth.py')
const images = read('../../backend/app/routers/images.py')
const core = read('../src/lib/api/core.ts')
const upload = read('../src/features/project/Upload.tsx')

test('test_the_cap_sentence_reads_the_constant_the_upload_route_enforces', () => {
  const declared = config.match(/^MAX_UPLOAD_MB\s*=\s*int\(_env\("LD_MAX_UPLOAD_MB",\s*"(\d+)"\)\)/m)
  assert.ok(declared, 'config.py declares the one upload cap')
  const cap = declared[1]

  // The route refuses a payload over this constant...
  assert.match(images, /from \.\.config import MAX_UPLOAD_MB/, 'the upload route imports the cap')
  assert.match(images, /budget = MAX_UPLOAD_MB \* 1024 \* 1024/, 'the route budgets with the cap')
  assert.match(images, new RegExp(`upload larger than \\{MAX_UPLOAD_MB\\} MB`), 'the refusal names the cap')

  // ...and the same constant is what `/config` publishes to the page.
  assert.match(auth, /from \.\.config import [^\n]*\bMAX_UPLOAD_MB\b/, 'the config endpoint imports the cap')
  assert.match(auth, /"max_upload_mb": MAX_UPLOAD_MB,/, 'config publishes max_upload_mb from the constant')
  assert.match(core, /max_upload_mb: number/, 'the config client type carries the field')
  assert.match(upload, /max_upload_mb/, 'the empty state reads the cap from /config')
  assert.doesNotMatch(upload, new RegExp(`\\b${cap}\\s?MB\\b`), 'the cap value is not copied into the page')
  assert.doesNotMatch(upload, /\b200\s?MB\b/, 'no stale second cap')
})

test('test_the_demo_shortcut_reuses_the_existing_sample_path', () => {
  // The card forbids a new demo endpoint: the shortcut consumes the sample path the app already ships.
  assert.match(upload, /playgroundSamples\(/, 'the shortcut reads the workspace sample path')
  assert.doesNotMatch(upload, /\/demo|demo-images|seed-demo/, 'no second demo endpoint')
})
