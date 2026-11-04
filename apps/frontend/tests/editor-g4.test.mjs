// Class search + editable shortcuts: pure rules for the editor panels.
//   node --test tests/editor-g4.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { classListQuery, classResultText, hotkeyClass, isClassListVisible, visibleClasses } from '../src/features/editor/classFilter.ts'
import {
  DEFAULT_SHORTCUTS, captureBinding, duplicateIds, isAcceptedBinding, keyLabel, loadShortcuts,
  resolveShortcut, saveShortcuts, validateBinding,
} from '../src/features/editor/shortcuts.ts'

const classes = [
  { id: 'a', name: 'helmet' },
  { id: 'b', name: 'Safety Vest' },
  { id: 'c', name: 'gloves' },
  { id: 'd', name: 'Helmet liner' },
]

test('class search trims, ignores case and keeps the project order', () => {
  assert.deepEqual(visibleClasses(classes, '  HELM ').map((c) => c.id), ['a', 'd'])
  assert.deepEqual(visibleClasses(classes, 'vest').map((c) => c.id), ['b'])
})

test('an empty query shows every class and an unknown query shows none', () => {
  assert.equal(visibleClasses(classes, '').length, 4)
  assert.equal(visibleClasses(classes, '   ').length, 4)
  assert.deepEqual(visibleClasses(classes, 'wizard hat'), [])
})

test('numeric hotkeys pick the visible row, not the project index', () => {
  const filtered = visibleClasses(classes, 'helmet')
  assert.equal(hotkeyClass(filtered, '1')?.id, 'a')
  assert.equal(hotkeyClass(filtered, '2')?.id, 'd')
  assert.equal(hotkeyClass(filtered, '3'), null)
  assert.equal(hotkeyClass(classes, '9'), null)
  assert.equal(hotkeyClass(classes, '0'), null)
})

test('the live status names the count and the empty result', () => {
  assert.equal(classResultText(4, 0, ''), '4 classes')
  assert.equal(classResultText(1, 1, ''), '1 class')
  assert.equal(classResultText(4, 2, 'hel'), '2 of 4 classes')
  assert.equal(classResultText(4, 0, 'zzz'), 'No class matches')
})

test('a filter only narrows the order while the class list is on screen', () => {
  assert.equal(classListQuery('h', true), 'h')
  assert.equal(classListQuery('h', false), '')
  // Classes tab hidden (Objects tab or a closed drawer): the digits fall back to project order.
  const hidden = visibleClasses(classes, classListQuery('h', false))
  assert.equal(hotkeyClass(hidden, '1')?.id, 'a')       // helmet, project index 1
  assert.equal(hotkeyClass(hidden, '2')?.id, 'b')       // Safety Vest, project index 2
  // Classes tab visible: the same digits follow the filtered rows.
  const shown = visibleClasses(classes, classListQuery('h', true))
  assert.deepEqual(shown.map((c) => c.id), ['a', 'd'])
  assert.equal(hotkeyClass(shown, '2')?.id, 'd')        // Helmet liner
})

test('the class list counts as on screen only on the Labels rail, Classes tab, panel open', () => {
  const base = { rail: 'labels', tab: 'classes', panelsOpen: true }
  assert.equal(isClassListVisible(base), true)
  assert.equal(isClassListVisible({ ...base, rail: 'attrs' }), false)
  assert.equal(isClassListVisible({ ...base, tab: 'objects' }), false)
  assert.equal(isClassListVisible({ ...base, panelsOpen: false }), false)
  // Each hidden path falls back to project order: 2 is the project's second class, not the filter's.
  for (const hiddenState of [{ ...base, rail: 'attrs' }, { ...base, tab: 'objects' }, { ...base, panelsOpen: false }]) {
    const query = classListQuery('h', isClassListVisible(hiddenState))
    assert.equal(hotkeyClass(visibleClasses(classes, query), '2')?.id, 'b', JSON.stringify(hiddenState))
  }
  const onScreen = classListQuery('h', isClassListVisible(base))
  assert.equal(hotkeyClass(visibleClasses(classes, onScreen), '2')?.id, 'd')
})

test('defaults resolve their own keys', () => {
  for (const [action, binding] of Object.entries(DEFAULT_SHORTCUTS)) {
    const event = binding.startsWith('ctrl+')
      ? { key: binding.slice(5), ctrlKey: true }
      : { key: binding }
    assert.equal(resolveShortcut(event, DEFAULT_SHORTCUTS), action, `${binding} -> ${action}`)
  }
  assert.equal(keyLabel('v'), 'V')
  assert.equal(keyLabel('ctrl+s'), 'Ctrl + S')
  assert.equal(keyLabel('delete'), 'Delete')
})

test('a remapped key replaces the old one and leaves the rest alone', () => {
  const map = { ...DEFAULT_SHORTCUTS, pan: 'h' }
  assert.equal(resolveShortcut({ key: 'h' }, map), 'pan')
  assert.equal(resolveShortcut({ key: 'v' }, map), null)
  assert.equal(resolveShortcut({ key: 'b' }, map), 'bbox')
})

test('a duplicate binding is reported and blocks the change', () => {
  const map = { ...DEFAULT_SHORTCUTS, pan: 'b' }
  assert.deepEqual(duplicateIds(map).sort(), ['bbox', 'pan'])
  assert.match(validateBinding('b', map, 'pan') ?? '', /already used by Bounding box/)
  assert.equal(validateBinding('h', map, 'pan'), null)
})

test('digits stay reserved for the class hotkeys', () => {
  assert.match(validateBinding('3', DEFAULT_SHORTCUTS, 'pan') ?? '', /reserved for class hotkeys/)
})

test('protected keys never get shadowed', () => {
  const events = [
    { key: 'Enter' }, { key: 'Escape' }, { key: '?' }, { key: 'ArrowLeft' },
    { key: 'ArrowRight' }, { key: 'z', ctrlKey: true }, { key: 'z', metaKey: true },
  ]
  for (const event of events) assert.equal(resolveShortcut(event, DEFAULT_SHORTCUTS), null, event.key)
  for (const event of events) assert.equal(captureBinding(event), null, event.key)
})

test('capture records one key, with ctrl when held, and rejects modifier-only presses', () => {
  assert.equal(captureBinding({ key: 'A', shiftKey: true }), 'a')
  assert.equal(captureBinding({ key: 's', ctrlKey: true }), 'ctrl+s')
  assert.equal(captureBinding({ key: 'S', metaKey: true }), 'ctrl+s')
  assert.equal(captureBinding({ key: 'Delete' }), 'delete')
  assert.equal(captureBinding({ key: 'Backspace' }), 'backspace')
  assert.equal(captureBinding({ key: 'Shift' }), null)
  assert.equal(captureBinding({ key: 'Tab' }), null)
})

test('storage round-trips, and damaged storage falls back to defaults', () => {
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) }
  const custom = { ...DEFAULT_SHORTCUTS, smart: 'g' }
  assert.equal(saveShortcuts(custom, storage), true)
  assert.deepEqual(loadShortcuts(storage), custom)

  storage.setItem('ld:editor-shortcuts', '{not json')
  assert.deepEqual(loadShortcuts(storage), DEFAULT_SHORTCUTS)
  storage.setItem('ld:editor-shortcuts', JSON.stringify({ v: 1, keys: { pan: 'enter', ghost: 'x' } }))
  const loaded = loadShortcuts(storage)
  assert.equal(loaded.pan, DEFAULT_SHORTCUTS.pan, 'a protected binding must not load')
  assert.equal(loaded.bbox, DEFAULT_SHORTCUTS.bbox)
  assert.deepEqual(loadShortcuts(null), DEFAULT_SHORTCUTS)
})

test('every symbol the panel accepts survives save -> load', () => {
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) }
  const symbols = ['.', ',', ';', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '-', '=', '[', ']', '\\', '`', "'", '"', '<', '>', '0']
  for (const symbol of symbols) {
    assert.equal(captureBinding({ key: symbol }), symbol, `capture ${symbol}`)
    assert.equal(isAcceptedBinding(symbol), true, `accepted ${symbol}`)
    assert.equal(validateBinding(symbol, DEFAULT_SHORTCUTS, 'bbox'), null, `validate ${symbol}`)
    const map = { ...DEFAULT_SHORTCUTS, bbox: symbol }
    assert.equal(saveShortcuts(map, storage), true, `save ${symbol}`)
    assert.equal(loadShortcuts(storage).bbox, symbol, `load ${symbol}`)
  }
  // Shifted symbols normalise to the same single character.
  assert.equal(captureBinding({ key: '?', shiftKey: true }), null)
  assert.equal(captureBinding({ key: '!', shiftKey: true }), '!')
})

test('"/" is reserved for the class search and never persists', () => {
  assert.equal(captureBinding({ key: '/' }), '/')
  assert.equal(isAcceptedBinding('/'), false)
  assert.match(validateBinding('/', DEFAULT_SHORTCUTS, 'pan') ?? '', /class search/)
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) }
  assert.equal(saveShortcuts({ ...DEFAULT_SHORTCUTS, pan: '/' }, storage), false, 'save must refuse "/"')
  storage.setItem('ld:editor-shortcuts', JSON.stringify({ v: 1, keys: { pan: '/', bbox: '1' } }))
  const loaded = loadShortcuts(storage)
  assert.equal(loaded.pan, DEFAULT_SHORTCUTS.pan, 'a stored "/" must not load')
  assert.equal(loaded.bbox, DEFAULT_SHORTCUTS.bbox, 'a stored digit must not load')
})
