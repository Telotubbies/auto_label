// Project sidebar layout: spec order, relabels, no dropped or duplicated destinations.
import test from 'node:test'
import assert from 'node:assert/strict'
import { panelSections } from '../src/lib/nav/project/panelLayout.ts'

const it = (to, label = to) => ({ to, label })
const groups = [
  { group: 'DATA', items: [it('upload'), it('browse'), it('versions'), it('classes'), it('insights'), it('search')] },
  { group: 'LABEL', items: [it('annotate')] },
  { group: 'MODELS', items: [it('train'), it('models'), it('workflows')] },
  { group: 'DEPLOY', items: [it('deploy', 'Deploy & Test'), it('streams')] },
  { group: 'SETTINGS', items: [it('settings')] },
]

test('orders DATA/MODELS/DEPLOY, relabels, and keeps every item once', () => {
  const s = panelSections(groups, it('/w/deployments', 'Deployments'))
  assert.deepEqual(s.map((x) => x.label), ['DATA', 'MODELS', 'DEPLOY', 'SETTINGS'])
  assert.deepEqual(s[0].entries.map((e) => (e === 'divider' ? '|' : e.to)),
    ['upload', 'annotate', 'browse', 'versions', '|', 'insights', 'classes', 'search'])
  assert.equal(s[0].entries[0].label, 'Upload Data')
  assert.equal(s[1].entries[2].label, 'Test')
  assert.deepEqual(s[2].entries.map((e) => e.to), ['/w/deployments', 'streams'])
  const flat = s.flatMap((x) => x.entries).filter((e) => e !== 'divider')
  assert.equal(flat.length, 14)
})

test('drops the divider when one side is empty', () => {
  const s = panelSections([{ group: 'DATA', items: [it('upload')] }])
  assert.deepEqual(s[0].entries.map((e) => e.to), ['upload'])
})
