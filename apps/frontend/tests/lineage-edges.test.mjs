// The lineage graph draws its edges in an aria-hidden SVG; these rows are the text equivalent.
//   node --test tests/lineage-edges.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { edgeRows, nodeConnections } from '../src/features/lineage/lineageModel.ts'

const node = (id, kind, label) => ({
  id, kind, label, sub: '', created: 0, counts: {}, metrics: {}, detail: {}, artifacts: [], log: '',
})

const nodes = [
  node('batch:1', 'batch', 'Gate camera'),
  node('batch:2', 'batch', 'Yard camera'),
  node('version:1', 'version', 'Ops v1'),
  node('run:1', 'run', 'yolo26 run'),
  node('model:1', 'model', 'ppe-yolo'),
  node('stream:1', 'stream', 'North gate'),
]

const edges = [
  { source: 'batch:1', target: 'version:1', kind: 'images' },
  { source: 'batch:2', target: 'version:1', kind: 'images' },
  { source: 'version:1', target: 'run:1', kind: 'training' },
  { source: 'run:1', target: 'model:1', kind: 'training' },
  { source: 'model:1', target: 'stream:1', kind: 'deployment' },
]

test('edgeRows names both endpoints and humanises the edge kind', () => {
  assert.deepEqual(edgeRows(nodes, edges), [
    { source: 'Gate camera', target: 'Ops v1', kind: 'Images' },
    { source: 'Yard camera', target: 'Ops v1', kind: 'Images' },
    { source: 'Ops v1', target: 'yolo26 run', kind: 'Training' },
    { source: 'yolo26 run', target: 'ppe-yolo', kind: 'Training' },
    { source: 'ppe-yolo', target: 'North gate', kind: 'Deployment' },
  ])
})

test('edgeRows drops a connection whose endpoint is not in the graph', () => {
  const rows = edgeRows(
    nodes,
    [...edges, { source: 'model:1', target: 'stream:deleted', kind: 'deployment' }],
  )
  assert.equal(rows.length, 5)
  assert.ok(!rows.some((row) => row.target === 'stream:deleted'))

  const withoutStreams = edgeRows(nodes.filter((n) => n.kind !== 'stream'), edges)
  assert.ok(!withoutStreams.some((row) => row.target === 'North gate'))
  assert.equal(withoutStreams.length, 4)
})

test('nodeConnections splits the selected node into incoming and outgoing edges', () => {
  const version = nodeConnections(nodes, edges, 'version:1')
  assert.deepEqual(version.incoming.map((row) => row.source), ['Gate camera', 'Yard camera'])
  assert.deepEqual(version.outgoing.map((row) => row.target), ['yolo26 run'])

  const model = nodeConnections(nodes, edges, 'model:1')
  assert.deepEqual(model.incoming.map((row) => row.source), ['yolo26 run'])
  assert.deepEqual(model.outgoing, [{ source: 'ppe-yolo', target: 'North gate', kind: 'Deployment' }])
})
