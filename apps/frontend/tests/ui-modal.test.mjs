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

// T-1110 (row 3 of docs/research/inference-hub/ui-qa.md): PLAN §4.4 requires a dialog to take
// focus, keep Tab inside it, and give focus back to the control that opened it. Source-checked for
// the three mechanisms; e2e/inference-hub.spec.ts presses the keys and reads activeElement.
test('test_modal_traps_focus_and_gives_it_back', () => {
  assert.match(ui, /document\.activeElement/, 'the element that opened the dialog is remembered')
  assert.match(ui, /restore\?\.\(\)|restoreTo\.current\?\.focus/, 'and focused again when it closes')
  assert.match(ui, /\[role="dialog"\]/, 'the panel itself takes focus on open')
  assert.match(ui, /tabIndex=\{-1\}/, 'a panel that takes focus must be focusable programmatically')
  assert.match(ui, /e\.key !== 'Tab'/, 'Tab is intercepted, so focus cannot leave the dialog')
  assert.match(ui, /focusable\(/, 'the cycle walks the controls the dialog actually shows')
})
