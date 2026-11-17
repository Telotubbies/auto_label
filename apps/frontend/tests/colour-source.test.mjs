// T-495: one colour source for split, status and class chips. A split, a status and a class each
// resolve through one helper in lib/theme.ts, so `test` cannot be orange on one screen and blue on
// another, and no screen invents a raw Tailwind hue. Source-checked like the other parity guards,
// because the suite has no DOM renderer.
//   node --test tests/colour-source.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'

// lib/theme.ts imports @material/material-color-utilities, whose published ESM uses extensionless
// internal paths Node cannot resolve. Stub only that colour engine, like chart-series.test.mjs; the
// helpers under test are the real ones.
const stub = 'data:text/javascript,' + encodeURIComponent(
  'export const Hct=0, MaterialDynamicColors=0, SchemeExpressive=0, SchemeTonalSpot=0, SchemeVibrant=0, TonalPalette=0, argbFromHex=0')
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@material/material-color-utilities') return { url: stub, shortCircuit: true }
    return nextResolve(specifier, context)
  },
})

const { splitColor, statusTone } = await import('../src/lib/theme.ts')

const src = (rel) => readFileSync(new URL(`../src/${rel}`, import.meta.url), 'utf8')
const dataset = src('features/project/Dataset.tsx')

test('test_split_colours_are_three_distinct_tones', () => {
  const tones = ['train', 'valid', 'test'].map(splitColor)
  assert.equal(new Set(tones).size, 3, 'train, valid and test get three different token classes')
  for (const tone of tones) assert.match(tone, /\bbg-/, `"${tone}" carries a background variant`)
  for (const tone of tones) assert.doesNotMatch(tone, /^bg-(red|green|blue|violet|orange|amber|pink)-/,
    `"${tone}" is a role, not a raw Tailwind palette class`)
})

test('test_unknown_status_is_neutral_but_labelled', () => {
  assert.deepEqual(statusTone('archived'), {
    label: 'archived',
    className: 'bg-secondary text-secondary-foreground',
  })
})

test('test_the_four_status_roles_print_their_word', () => {
  for (const [status, role] of Object.entries({
    done: 'success', running: 'info', queued: 'warning', failed: 'destructive',
  })) {
    const tone = statusTone(status)
    assert.equal(tone.label, status, `${status} is printed, never colour alone`)
    assert.match(tone.className, new RegExp(`^(bg-${role}/15 text-${role})$`), `${status} uses the ${role} role`)
  }
})

test('test_dataset_uses_split_color', () => {
  assert.doesNotMatch(dataset, /bg-(violet|blue|orange)-600|bg-orange-500/,
    'Dataset.tsx keeps no local split palette')
  assert.match(dataset, /import \{[^}]*\bsplitColor\b[^}]*\} from '@\/lib\/theme'/,
    'Dataset.tsx imports the one split helper')
  assert.match(dataset, /splitColor\(im\.split\)/, 'the chip resolves its tone through splitColor')
})

test('test_deploy_has_one_colour_source', (t) => {
  const pane = 'features/deploy/TestPane.tsx'
  if (!existsSync(new URL(`../src/${pane}`, import.meta.url))) {
    t.skip('T-314 has not landed: Deploy.tsx still owns the local eight-colour array')
    return
  }
  for (const rel of ['features/project/Deploy.tsx', pane]) {
    assert.doesNotMatch(src(rel), /(?:const|let)\s+\w*(?:COLOR|PALETTE)\w*\s*=\s*\[/i,
      `${rel} declares no local colour array`)
    assert.match(src(rel), /classColor\(/, `${rel} resolves colours through classColor`)
  }
})

// Raw hue classes per workspace screen, frozen after T-495's swaps. AnnotateBoard keeps one
// `bg-red-50` alert and Playground/AutoLabelDialog/Settings keep theirs; the map may only shrink,
// and a new screen cannot add one.
const FROZEN = {
  'features/playground/Playground.tsx': 3,
  'features/project/AnnotateBoard.tsx': 1,
  'features/project/AutoLabelDialog.tsx': 1,
  'features/settings/Settings.tsx': 1,
}
const rawPalette = (text) => (text.match(/bg-(?:red|green|blue|violet|orange|amber|pink)-/g) ?? []).length

test('test_no_new_raw_palette_classes', () => {
  const features = readdirSync(new URL('../src/features/', import.meta.url), { recursive: true })
    .map((f) => f.replaceAll('\\', '/'))
    .filter((f) => /\.(ts|tsx)$/.test(f))
  for (const f of features) {
    const rel = `features/${f}`
    assert.ok(rawPalette(src(rel)) <= (FROZEN[rel] ?? 0),
      `${rel} adds a raw Tailwind hue; a chip resolves through splitColor, statusTone or classColor`)
  }
  for (const f of Object.keys(FROZEN)) assert.ok(features.includes(f.replace('features/', '')), `${f} is listed but no longer exists`)
})
