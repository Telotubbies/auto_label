// T-471: the 13 px text floor. Metadata renders at text-sm (14/20); text-xs (12/16) is allowed only
// inside a chip or a table header; nothing renders below 12 px. There is no off switch, so the guard is
// the guarantee. Source-checked like the other parity guards, because the suite has no DOM renderer.
//   node --test tests/type-floor.test.mjs   (from apps/frontend)
//
// Two mechanisms, as the card specifies:
//   1. the app shell (src/components/**) carries no sub-12 px class at all, and no arbitrary size;
//   2. the workspace screens (src/features/**) are frozen per file and may only shrink. Each file is
//      cleared by the card that owns it — Editor.tsx is T-498, Dataset.tsx is T-062, Settings.tsx is
//      area 7 — and the map entry is dropped when that card clears the file.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'

const srcTree = readdirSync(new URL('../src/', import.meta.url), { recursive: true })
  .map((f) => f.replaceAll('\\', '/'))
const sourceTree = srcTree.filter((f) => /\.(ts|tsx|css)$/.test(f))
const shellTree = sourceTree.filter((f) => f.startsWith('components/'))
const featureTree = sourceTree.filter((f) => f.startsWith('features/'))
const src = (rel) => readFileSync(new URL(`../src/${rel}`, import.meta.url), 'utf8')

/** Sub-13 px Tailwind sizes. Used as a count, so a fresh regex per call. */
const sub12 = (text) => (text.match(/text-\[(?:9|10|11)px\]/g) ?? []).length

/** The four shell files this card edits: the class rail, breadcrumb, project rail and job tray. */
const SHELL_FILES = [
  'components/shell/AppSidebar.tsx',
  'components/shell/TopBar.tsx',
  'components/shell/ProjectPanel.tsx',
  'components/shell/JobTray.tsx',
]

/**
 * Sub-12 px labels per workspace screen, frozen at the branch point. Measured at `fe8ef1a`, the base the
 * card names: 40 files / 232 occurrences. Three files gained a label after that commit (EventSearch,
 * search/CollectionsPanel, settings/SettingsAccount — merged from other lanes) and two shrank
 * (Settings 5 → 1, Playground 1 → 0), so the map below is the branch point's real count: no file may
 * grow, no file may appear, and a file that reaches zero drops out.
 */
const FROZEN = {
  'features/auth/Auth.tsx': 1,
  'features/dashboards/Dashboards.tsx': 1,
  'features/editor/Editor.tsx': 32,
  'features/editor/ObjectList.tsx': 4,
  'features/editor/OcrPanel.tsx': 31,
  'features/editor/Panels.tsx': 9,
  'features/evaluation/EvalPanel.tsx': 16,
  'features/insights/CompareTab.tsx': 6,
  'features/insights/EvaluationTab.tsx': 4,
  'features/insights/charts.tsx': 1,
  'features/landing/primitives.tsx': 1,
  'features/landing/sections/CapabilitiesSection.tsx': 2,
  'features/landing/sections/FeaturesBentoSection.tsx': 14,
  'features/landing/sections/HeroSection.tsx': 13,
  'features/landing/sections/ShowcaseSection.tsx': 8,
  'features/landing/sections/WorkflowDarkSection.tsx': 9,
  'features/lineage/Lineage.tsx': 11,
  'features/project/AnnotateBoard.tsx': 2,
  'features/project/AutoLabelDialog.tsx': 10,
  'features/project/Dataset.tsx': 3,
  'features/project/DatasetHealth.tsx': 1,
  'features/project/Deploy.tsx': 1,
  'features/project/EventSearch.tsx': 1,
  'features/project/HealthCheck.tsx': 1,
  'features/project/Models.tsx': 6,
  'features/project/Upload.tsx': 1,
  'features/project/Versions.tsx': 1,
  'features/project/VideoTimeline.tsx': 2,
  'features/project/WorkflowBlocks.tsx': 1,
  'features/project/Workflows.tsx': 1,
  'features/project/insights/Chart.tsx': 1,
  'features/project/insights/Leakage.tsx': 1,
  'features/project/qa/Consensus.tsx': 3,
  'features/project/qa/ReviewQueue.tsx': 1,
  'features/project/qa/Workforce.tsx': 1,
  'features/search/CollectionsPanel.tsx': 5,
  'features/settings/Settings.tsx': 1,
  'features/settings/SettingsAccount.tsx': 4,
  'features/streams/StreamDetail.tsx': 14,
  'features/streams/Streams.tsx': 6,
  'features/streams/ZoneEditor.tsx': 4,
  'features/workspace/WorkspacePages.tsx': 2,
}

test('test_no_text_below_twelve_px_in_the_shell', () => {
  assert.ok(shellTree.length > 10, 'the shell tree was read')
  for (const f of shellTree) {
    assert.equal(sub12(src(f)), 0,
      `${f} carries a sub-12 px label; metadata is text-sm (14/20) and a chip or table header is text-xs (12/16)`)
  }
})

test('test_frozen_counts_only_shrink', () => {
  assert.ok(featureTree.length > 50, 'the feature tree was read')
  for (const f of featureTree) {
    const n = sub12(src(f))
    const cap = FROZEN[f] ?? 0
    assert.ok(n <= cap,
      `${f} has ${n} sub-12 px labels, frozen at ${cap}: a screen may only shrink, and a new screen cannot add one`)
  }
  // The other direction is the progress signal: a file that reached zero is cleared, and its entry goes.
  for (const f of Object.keys(FROZEN)) assert.ok(featureTree.includes(f), `${f} is listed but no longer exists`)
})

test('test_no_inline_font_size_under_thirteen', () => {
  for (const f of sourceTree) {
    const text = src(f)
    assert.doesNotMatch(text, /style=\{\{[^}]*fontSize:\s*1[01]\b/,
      `${f} sets a DOM font size under 13 px inline; use text-sm or text-xs`)
    assert.doesNotMatch(text, /font-size:\s*1[01]px/, `${f} sets a font-size under 13 px`)
    if (f.startsWith('components/')) {
      assert.doesNotMatch(text, /fontSize:\s*1[01]\b/, `${f} draws text under 13 px in the shell`)
    }
  }
})

test('test_twelve_px_is_chip_or_header_only', () => {
  for (const f of SHELL_FILES) {
    const lines = src(f).split('\n')
    lines.forEach((line, i) => {
      if (!line.includes('text-xs')) return
      assert.doesNotMatch(line, /<p[\s>]|<td[\s>]/,
        `${f}:${i + 1} puts text-xs on a paragraph or cell; a sentence is text-sm`)
      assert.match(line, /rounded|<th[\s>]/,
        `${f}:${i + 1} uses text-xs outside a chip or a table header`)
    })
  }
})

test('test_no_arbitrary_font_size', () => {
  for (const f of sourceTree) {
    assert.doesNotMatch(src(f), /text-\[(?:13|15)px\]/,
      `${f} invents a size; the shipped scale (text-sm / text-xs) is the whole scale`)
  }
})
