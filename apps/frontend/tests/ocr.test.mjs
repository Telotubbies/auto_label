// Pure OCR helpers used by the editor panel. Runs with the built-in runner:
//   node --test tests/ocr.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { convertOcr, maskPii, resizeCells } from '../src/lib/ocr.ts'

test('maskPii hides a Thai ID written with dashes', () => {
  const id = '1-2345-67890-12-3'
  assert.equal(maskPii(`เลขบัตร ${id}`), `เลขบัตร ${'*'.repeat(id.length)}`)
})

test('maskPii hides a Thai ID written with spaces', () => {
  const id = '1 2345 67890 12 3'
  assert.equal(maskPii(`เลขบัตร ${id}`), `เลขบัตร ${'*'.repeat(id.length)}`)
})

test('maskPii hides a 13-digit ID and a Thai phone number', () => {
  assert.equal(maskPii('1234567890123'), '*'.repeat(13))
  assert.equal(maskPii('โทร 081-234-5678'), `โทร ${'*'.repeat('081-234-5678'.length)}`)
  assert.equal(maskPii('โทร 081 234 5678'), `โทร ${'*'.repeat('081 234 5678'.length)}`)
})

test('maskPii hides an email address', () => {
  assert.equal(maskPii('somchai@example.co.th'), '*'.repeat('somchai@example.co.th'.length))
})

test('maskPii leaves document numbers alone', () => {
  assert.equal(maskPii('เลขที่ INV-2569-001 ยอด 1,250.00'), 'เลขที่ INV-2569-001 ยอด 1,250.00')
})

test('resizeCells keeps typed cells and pads the new grid with blanks', () => {
  assert.deepEqual(resizeCells([['a', 'b']], 2, 3), [['a', 'b', ''], ['', '', '']])
  assert.deepEqual(resizeCells([['a', 'b', 'c']], 1, 2), [['a', 'b']])
  assert.deepEqual(resizeCells(undefined, 1, 2), [['', '']])
})

test('convertOcr carries the text into a key-value field', () => {
  assert.deepEqual(convertOcr({ kind: 'text', text: 'สมชาย' }, 'keyvalue'), {
    kind: 'keyvalue',
    key: '',
    value: 'สมชาย',
  })
})

test('convertOcr carries the value back into a text line', () => {
  assert.deepEqual(convertOcr({ kind: 'keyvalue', key: 'ชื่อ', value: 'สมชาย' }, 'text'), {
    kind: 'text',
    text: 'สมชาย',
  })
})

test('convertOcr turns a text line into a table with the text in the first cell', () => {
  assert.deepEqual(convertOcr({ kind: 'text', text: 'รายการ' }, 'table'), {
    kind: 'table',
    rows: 2,
    cols: 3,
    cells: [['รายการ', '', ''], ['', '', '']],
  })
})

test('convertOcr keeps an existing table grid when toggling kinds and back', () => {
  const cells = [['a', 'b'], ['c', 'd']]
  assert.deepEqual(convertOcr({ kind: 'table', rows: 2, cols: 2, cells }, 'text'), { kind: 'text', text: 'a' })
})

test('convertOcr returns the same payload for the active kind', () => {
  const ocr = { kind: 'table', rows: 1, cols: 1, cells: [['x']] }
  assert.equal(convertOcr(ocr, 'table'), ocr)
})
