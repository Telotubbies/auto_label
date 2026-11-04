// Pure selection/query rules for the Search + Collections page. Runs with the built-in runner:
//   node --test tests/search-state.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCollectionQuery, buildSearchQuery, collectionTargets, selectAll, toggleId,
} from '../src/features/search/searchState.ts'

test('toggleId adds a missing id and removes a present one without mutating the input', () => {
  const before = new Set(['a'])
  const added = toggleId(before, 'b')
  assert.deepEqual([...added].sort(), ['a', 'b'])
  assert.deepEqual([...before], ['a'], 'input set must stay untouched')

  const removed = toggleId(added, 'a')
  assert.deepEqual([...removed], ['b'])
  assert.deepEqual([...added].sort(), ['a', 'b'], 'input set must stay untouched')
})

test('selectAll selects every id when checked and clears the set otherwise', () => {
  assert.deepEqual([...selectAll(['a', 'b', 'c'], true)].sort(), ['a', 'b', 'c'])
  assert.equal(selectAll(['a', 'b'], false).size, 0)
  assert.equal(selectAll([], true).size, 0)
})

test('buildSearchQuery keeps only the filters that are set and trims the query', () => {
  assert.deepEqual(buildSearchQuery({ q: '  safety vest ', class_id: '', tag: '', split: '', status: '', annotated: '' }),
    { q: 'safety vest' })
  assert.deepEqual(
    buildSearchQuery({ q: '', class_id: 'c1', tag: 'ppe', split: 'train', status: 'done', annotated: 'yes' }),
    { class_id: 'c1', tag: 'ppe', split: 'train', status: 'done', annotated: 'yes' },
  )
  assert.deepEqual(buildSearchQuery({ q: '   ', class_id: '', tag: '', split: '', status: '', annotated: '' }), {})
})

test('collectionTargets uses selected ids in display order, else every result id in order', () => {
  const results = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
  assert.deepEqual(collectionTargets(new Set(['c', 'a']), results), ['a', 'c'])
  assert.deepEqual(collectionTargets(new Set(), results), ['a', 'b', 'c'])
  // ids that are no longer in the result set are dropped, never sent to the API
  assert.deepEqual(collectionTargets(new Set(['zzz', 'b']), results), ['b'])
})

test('buildCollectionQuery carries the raw query plus the active filters as text', () => {
  assert.equal(
    buildCollectionQuery('safety vest', { q: '', class_id: 'c1', tag: 'ppe', split: 'train', status: '', annotated: '' }),
    'safety vest class_id:c1 tag:ppe split:train',
  )
  assert.equal(buildCollectionQuery('', { q: '', class_id: '', tag: '', split: '', status: '', annotated: '' }), '')
  assert.equal(buildCollectionQuery('', { q: 'hard hat', class_id: '', tag: '', split: '', status: '', annotated: '' }), 'hard hat')
})
