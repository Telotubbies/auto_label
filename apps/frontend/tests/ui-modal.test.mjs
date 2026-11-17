// T-1106: every modal has an accessible name. axe reports `aria-dialog-name` on a dialog with no
// name; the fix is one stable id from useId() wired to the title, and a required aria-label when
// there is no visible title. Source-checked, like the other parity guards, because the node suite
// has no DOM renderer. The type half is src/components/ui.modal-names.test-d.tsx, checked by tsc.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const ui = readFileSync(new URL('../src/components/ui.tsx', import.meta.url), 'utf8')

test('test_modal_points_aria_labelledby_at_its_title_id', () => {
  assert.match(ui, /const titleId = useId\(\)/, 'the title id is stable per dialog instance')
  assert.match(ui, /aria-labelledby=\{title \? titleId : undefined\}/,
    'the panel names itself from the title it renders')
  assert.match(ui, /id=\{titleId\}/, 'the title carries the id the panel points at')
})

test('test_modal_takes_an_aria_label_when_it_has_no_title', () => {
  assert.match(ui, /'aria-label': ariaLabel/, 'the prop is read as aria-label')
  assert.match(ui, /aria-label=\{title \? undefined : ariaLabel\}/,
    'aria-label names the panel only when no visible title does')
  assert.match(ui, /title\?: undefined;\s*'aria-label': string/,
    'the type requires aria-label when title is absent, so tsc catches an unnamed dialog')
})
