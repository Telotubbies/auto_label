// T-1015: the Segmentation tab's rules — which row may hand off to auto-label, the URL that carries
// the ref, the state copy that names the env to fix, the licence badge and the two VRAM figures.
// node --test tests/inference-segmentation.test.mjs (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NO_PROJECT, action, handoffHref, licenceTone, ready, stateCopy, vramCopy,
} from '../src/features/inference/segRows.ts'

const row = (over = {}) => ({
  id: 'sam3.1',
  name: 'SAM 3.1',
  family: 'SAM',
  params_m: 848,
  engine: 'sam3',
  source_url: 'https://github.com/facebookresearch/sam3',
  note: 'Reference figure for one image at fp16.',
  licence: { name: 'SAM License', url: 'https://example.invalid/sam', non_commercial: false },
  vram: { 512: 4300, 1024: 8100 },
  provisioned: { ok: true, reason: '' },
  auto_label: { ref: 'sam3:sam3.1', engine_hint: 'sam3', classes_required: true },
  ...over,
})

test('test_only_a_ready_row_offers_the_action', () => {
  const missing = row({
    provisioned: { ok: false, reason: 'Missing checkpoint: set LD_SAM_ROOT to a sam3_auto_label checkout.' },
  })
  assert.equal(ready(missing), false)
  assert.deepEqual(action(missing, 'acme', 'ppe'), {
    disabled: true,
    href: null,
    reason: 'Missing checkpoint: set LD_SAM_ROOT to a sam3_auto_label checkout.',
  })

  const ok = row()
  assert.equal(ready(ok), true)
  assert.deepEqual(action(ok, 'acme', 'ppe'), {
    disabled: false,
    href: '/acme/p/ppe/dataset?autolabel=sam3%3Asam3.1',
    reason: '',
  })

  // A verdict with no ref cannot hand off: the dialog only accepts a registry ref, so it is not ready.
  const noRef = row({ auto_label: { ref: null, engine_hint: 'mask2former', classes_required: true } })
  assert.equal(ready(noRef), false)
  assert.equal(action(noRef, 'acme', 'ppe').href, null)
})

test('test_handoff_href_encodes_the_ref', () => {
  assert.equal(handoffHref('acme', 'ppe', 'sam3:sam3.1'), '/acme/p/ppe/dataset?autolabel=sam3%3Asam3.1')
  // The value is encoded once, by URLSearchParams: no raw ':' and no double encoding.
  const href = handoffHref('acme', 'ppe', 'ultralytics:yolo26n-seg')
  assert.ok(href.endsWith('autolabel=ultralytics%3Ayolo26n-seg'), href)
  const q = new URLSearchParams(href.split('?')[1])
  assert.equal(q.get('autolabel'), 'ultralytics:yolo26n-seg')
  // A slug that needs encoding survives as a path segment, not as a broken string.
  assert.equal(handoffHref('a b', 'p&p', 'x:y'), '/a%20b/p/p%26p/dataset?autolabel=x%3Ay')
})

test('test_state_copy_names_the_env_to_fix', () => {
  const sam = row({
    provisioned: {
      ok: false,
      reason: 'Missing checkpoint: set LD_SAM_ROOT to a sam3_auto_label checkout that contains '
        + 'checkpoints/sam3.1_multiplex.pt.',
    },
  })
  const samCopy = stateCopy(sam)
  assert.equal(samCopy.label, 'Missing checkpoint')
  assert.match(samCopy.detail, /LD_SAM_ROOT/)
  assert.match(samCopy.detail, /checkpoints\/sam3\.1_multiplex\.pt/)

  const yolo = row({
    id: 'yolo26n-seg',
    provisioned: {
      ok: false,
      reason: 'Missing checkpoint: set LD_PRETRAINED_DIR to a folder holding a yolo26*-seg.pt weight.',
    },
  })
  assert.match(stateCopy(yolo).detail, /LD_PRETRAINED_DIR/)

  const cpu = row({
    provisioned: {
      ok: false,
      reason: 'Not supported on this OS: this host reports no GPU, and every segmentation model in '
        + 'this catalogue runs on one.',
    },
  })
  const cpuCopy = stateCopy(cpu)
  assert.equal(cpuCopy.label, 'Not supported on this OS')
  assert.match(`${cpuCopy.label} ${cpuCopy.detail}`, /Not supported on this OS/)

  // Ready has nothing to fix: one word, no detail.
  assert.deepEqual(stateCopy(row()), { label: 'Ready', detail: '' })
})

test('test_licence_tone_marks_agpl_and_non_commercial', () => {
  const yolo = licenceTone(row({
    licence: { name: 'AGPL-3.0', url: 'https://example.invalid/agpl', non_commercial: false },
  }))
  assert.equal(yolo.tone, 'warning')
  assert.match(`${yolo.label} ${yolo.note ?? ''}`, /AGPL/)

  const mask2former = licenceTone(row({
    licence: { name: 'CC-BY-NC-4.0', url: 'https://example.invalid/nc', non_commercial: true },
  }))
  assert.equal(mask2former.tone, 'warning')
  assert.equal(mask2former.note, 'Non-commercial')

  const apache = licenceTone(row({
    licence: { name: 'Apache-2.0', url: 'https://example.invalid/apache', non_commercial: false },
  }))
  assert.equal(apache.tone, 'neutral')
  assert.equal(apache.note, null)
  // The label is the licence's own name, always printed next to the badge.
  assert.equal(apache.label, 'Apache-2.0')
})

test('test_vram_copy_is_two_resolutions', () => {
  const copy = vramCopy(row({ vram: { 512: 4300, 1024: 8100 } }))
  assert.match(copy, /512 px/)
  assert.match(copy, /1024 px/)
  assert.match(copy, /4\.2 GB/)
  assert.match(copy, /7\.9 GB/)
  // An unknown figure says so instead of printing a zero.
  assert.match(vramCopy(row({ vram: { 512: 0, 1024: 1900 } })), /512 px: unknown/)
})

test('test_no_project_disables_every_action', () => {
  const rows = [
    row(),
    row({ id: 'yolo26n-seg', provisioned: { ok: false, reason: 'Missing checkpoint: set LD_PRETRAINED_DIR.' } }),
    row({ id: 'mask2former-swin-l', provisioned: { ok: true, reason: '' } }),
  ]
  for (const item of rows) {
    const result = action(item, 'acme', null)
    assert.equal(result.disabled, true, `${item.id} must not offer a handoff without a project`)
    assert.equal(result.href, null)
    assert.equal(result.reason, NO_PROJECT)
  }
  assert.equal(action(rows[0], 'acme', '').reason, 'Choose a project first.')
})
