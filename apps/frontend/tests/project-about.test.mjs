// T-023: the description editor is one field with one save, and the public address appears only
// while the project is public. Source-checked like the other UI guards, because the suite has no
// DOM renderer and no server: every state below is pinned by the expression that produces it.
//   node --test tests/project-about.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')
const card = read('../src/features/project/DescriptionCard.tsx')
const settings = read('../src/features/project/ProjectSettings.tsx')
const home = read('../src/features/workspace/Home.tsx')

test('test_counter_and_save_state', () => {
  // The draft is the only state; "changed" is a comparison against the saved value, so 0 changes
  // disables the button and the first keystroke enables it again.
  assert.match(card, /const \[text, setText\] = useState\(project\.description\)/,
    'the draft starts from the saved description')
  assert.match(card, /const dirty = text !== project\.description/,
    'dirty means the draft differs from the saved text')
  assert.match(card, /disabled=\{!dirty \|\| saving\}/,
    'Save description is disabled at 0 changes and while a save runs')

  // 12 characters of draft render as 12/600: the count is the draft's own length, the cap is 600.
  assert.match(card, /maxLength=\{MAX\}/, 'the textarea refuses more than the cap')
  assert.match(card, /const MAX = 600/, 'the cap is 600')
  assert.match(card, /\{text\.length\}\/\{MAX\}/, 'the counter renders <draft length>/600')
  assert.match(card, /rows=\{6\}/, 'the textarea is six rows tall')
  assert.match(card, /What is this dataset for, and what is in it\?/, 'the empty state is a placeholder')
})

test('test_public_row_visibility', () => {
  // Public: the derived address plus a copy button. Private: one sentence, no address at all.
  assert.match(card, /project\.visibility === 'public'/, 'the row branches on the saved visibility')
  assert.match(card, /\{project\.publicPath\}/, 'the public branch shows the derived address')
  assert.match(card, /copy\(project\.publicPath/, 'the copy button copies the derived address')
  assert.match(card, /Private\. Make it public from the project menu\./,
    'the private branch is one sentence with no URL')
  assert.match(card, /Public link/, 'the row is labelled Public link')
})

test('the failure keeps the text and offers a retry', () => {
  assert.match(card, /Could not save — your text is kept\./, 'the failed save says the text is kept')
  assert.match(card, /<Button[^>]*onClick=\{save\}[^>]*>\s*Retry\s*<\/Button>/, 'Retry re-runs the same save')
  assert.match(card, /aria-hidden/, 'the loading skeleton is decorative')
})

test('the hint and the mount are the ones the card names', () => {
  assert.match(card, /Visitors and teammates read this first\./, 'the hint is the card copy')
  assert.match(settings, /<DescriptionCard ws=\{ws\}/, 'ProjectSettings mounts the block once')
  assert.match(settings, /\{active === 'general' && \([\s\S]*?<DescriptionCard ws=\{ws\}/,
    'the block sits on the general tab, above the name card')
  assert.doesNotMatch(settings, /<textarea/, 'the settings page keeps no second description editor')
})

test('the description reaches the workspace card as one line with an explicit more', () => {
  assert.match(home, /\{p\.description && \(/, 'the card renders a subtitle only when there is text')
  assert.match(home, /\{p\.description\.split\('\\n'\)\[0\]\}/, 'the subtitle is the first line')
  assert.match(home, /clamp-2/, 'the subtitle clamps at two lines')
  assert.match(home, /…more/, 'the clamp carries an explicit more')
})

test('the string is rendered as text, never as markup', () => {
  // No HTML path: the value goes through JSX children, so React escapes it.
  assert.doesNotMatch(card, /dangerouslySetInnerHTML/, 'no raw-HTML sink')
  assert.match(card, /value=\{text\}/, 'the draft is a controlled textarea value')
})
