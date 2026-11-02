// I14 regression: landing copy must not promise SAM 3.1 / VLM when the deployment does not
// expose them. The sections read the public capability endpoint and label the add-on as
// operator setup instead of an included feature.
//   node --test tests/landing-claims.test.mjs   (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { landingAddonState } from '../src/features/landing/addons.ts'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

test('an unavailable deployment labels SAM/VLM as operator setup', () => {
  const off = landingAddonState(false)
  assert.match(off.label, /requires operator setup/i)
  assert.match(off.detail, /operator/i)
  assert.doesNotMatch(off.detail, /is connected/i)
})

test('a provisioned deployment may describe the connected add-on', () => {
  const on = landingAddonState(true)
  assert.match(on.label, /connected/i)
  assert.match(on.detail, /SAM 3\.1/)
})

test('every cited claim reads the same capability state', () => {
  for (const file of ['CapabilitiesSection', 'FeaturesBentoSection', 'WorkflowDarkSection']) {
    const src = read(`../src/features/landing/sections/${file}.tsx`)
    assert.match(src, /useCapabilities/, `${file} must read the capability endpoint`)
    assert.match(src, /landingAddonState/, `${file} must use the shared add-on copy`)
  }
})
