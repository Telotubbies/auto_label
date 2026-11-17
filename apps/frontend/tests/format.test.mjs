// One rounding rule per kind of number (T-055). Every expected value below is what the screens
// showed before the shared module existed, so moving a call site cannot change what a reader sees.
//   node --test tests/format.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fmtClock, fmtBytes, fmtInt, fmtMillis, pct1, pctOf } from '../src/lib/format.ts'

test('fmtInt shows a whole number with separators, and an unknown count as a dash', () => {
  const rows = [
    [1234.6, '1,235'],
    [0, '0'],
    [1234567, '1,234,567'],
    [NaN, '—'],
    [Infinity, '—'],
  ]
  for (const [n, shown] of rows) assert.equal(fmtInt(n), shown, `fmtInt(${n})`)
})

test('fmtBytes keeps the bytes rule the streams screens already used', () => {
  const rows = [
    [0, '0 B'],
    [1023, '1023 B'],
    [1536, '2 KB'],
    [300 * 1024, '300 KB'],
    [5 * 1024 ** 2, '5.0 MB'],
  ]
  for (const [n, shown] of rows) assert.equal(fmtBytes(n), shown, `fmtBytes(${n})`)
})

test('pct1 shows a rate at one decimal and a missing rate as a dash', () => {
  const rows = [
    [0.5, '50.0%'],
    [0.504, '50.4%'],
    [0, '0.0%'],
    [1, '100.0%'],
    [null, '—'],
    [undefined, '—'],
  ]
  for (const [v, shown] of rows) assert.equal(pct1(v), shown, `pct1(${v})`)
})

test('pctOf shows a share of a whole as a whole percent, and a zero whole as a dash', () => {
  const rows = [
    [1, 3, '33%'],
    [0, 5, '0%'],
    [5, 5, '100%'],
    [1, 0, '—'],
    [0, 0, '—'],
  ]
  for (const [part, whole, shown] of rows) assert.equal(pctOf(part, whole), shown, `pctOf(${part}, ${whole})`)
})

test('fmtClock reads its argument as seconds', () => {
  const rows = [
    [65, '1:05'],
    [0, '0:00'],
    [9, '0:09'],
    [3599, '59:59'],
    [3600, '60:00'],
  ]
  for (const [s, shown] of rows) assert.equal(fmtClock(s), shown, `fmtClock(${s})`)
})

test('fmtMillis reads its argument as milliseconds and lands on the same clock', () => {
  const rows = [
    [65_000, '1:05'],
    [0, '0:00'],
    [9_000, '0:09'],
    [3_600_000, '60:00'],
  ]
  for (const [ms, shown] of rows) assert.equal(fmtMillis(ms), shown, `fmtMillis(${ms})`)
})

test('the module is pure and exports exactly the six formatters', () => {
  const src = readFileSync(new URL('../src/lib/format.ts', import.meta.url), 'utf8')
  assert.doesNotMatch(src, /from ['"]react['"]/, 'no React')
  assert.doesNotMatch(src, /dateLocale|@\/lib\/theme/, 'no locale state; dateLocale() stays in theme.ts')
  assert.doesNotMatch(src, /^\s*import /m, 'nothing imported: the module has no side effects')
  assert.equal(src.match(/^export /gm)?.length, 6, 'six functions and nothing else')
})
