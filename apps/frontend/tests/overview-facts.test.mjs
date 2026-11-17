// T-484 — the overview's one dynamic primary and the truthful aside.
// The header sentence, the run line, the blockers and the ring are pure, so they run here;
// the aside's sources are calls the page already makes.
//   node --test tests/overview-facts.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { blockedBy, healthRing, primary, runLine } from '../src/features/project/overviewFacts.ts'
import { overviewFacts } from '../src/features/project/overviewModel.ts'

const counts = (over = {}) => ({ unassigned: 0, annotating: 0, review: 0, done: 24, ...over })
const version = (n = 1) => ({
  id: `v${n}`, number: n, name: `v${n}`, settings: {}, status: 'ready', stats: {}, created: n, job: null, exports: {},
})
const model = (over = {}) => ({
  id: 'm1', name: 'PPE Detector', arch: 'yolo26n', task: 'detect', status: 'ready', metrics: {},
  history: [], classes: [], versionId: 'v1', created: 2, weightsUrl: null, ...over,
})
/** The five states T-477 pins, as the page assembles them for the model. */
const input = (over = {}) => ({
  images: 40, statusCounts: counts(), versions: [version(1)], models: [model()], jobs: [],
  canTrain: true, canDeploy: true, ...over,
})
const facts = (over = {}) => overviewFacts(input(over))
const FIVE = {
  unlabelled: { statusCounts: counts({ unassigned: 40, done: 0 }) },
  inReview: { statusCounts: counts({ unassigned: 24, review: 16, done: 0 }) },
  noVersion: { versions: [] },
  noRun: { models: [], jobs: [] },
  readyRun: {},
}

test('test_primary_names_the_next_task', () => {
  const label = (over) => primary(facts(over), 'manager').label
  assert.equal(label(FIVE.unlabelled), 'Label 40 images')
  assert.equal(label(FIVE.inReview), 'Review 16 labels')
  assert.equal(label(FIVE.noVersion), 'Create a version')
  assert.equal(label(FIVE.noRun), 'Train on v1')
  assert.equal(label(FIVE.readyRun), 'Test the model')
  // A project with no images names the first batch and opens the upload stage.
  const empty = primary(facts({ images: 0, statusCounts: undefined, versions: [], models: [], jobs: [] }), 'manager')
  assert.equal(empty.label, 'Upload 20 images')
  assert.equal(empty.to, 'upload')
  // A labeler never gets the pipeline's sentence: their next task is the board.
  for (const [name, over] of Object.entries(FIVE)) {
    assert.equal(primary(facts(over), 'labeler').label, 'Start labelling', `${name}: a labeler starts labelling`)
    assert.equal(primary(facts(over), 'labeler').to, 'annotate', `${name}: the primary opens the board`)
  }
})

test('test_primary_never_offers_train_before_a_version', () => {
  for (const [name, over] of Object.entries(FIVE)) {
    const next = primary(facts(over), 'manager')
    if (input(over).versions.length === 0) {
      assert.equal(/^Train on/.test(next.label), false, `${name}: no version, no train`)
    }
  }
  // A version with no run does offer train, and names the version.
  assert.equal(primary(facts(FIVE.noRun), 'manager').label, 'Train on v1')
})

test('test_run_line_shows_the_delta', () => {
  const line = runLine({ mAP50: 0.81 }, { mAP50: 0.77 })
  assert.equal(line.delta, '+0.04 vs previous')
  assert.equal(line.label, 'mAP50 0.81')
  assert.equal(runLine({ mAP50: 0.81, version: 1 }, { mAP50: 0.77, version: 2 }).delta, '+0.04 vs v2')
  assert.equal(runLine({ mAP50: 0.7 }, { mAP50: 0.81 }).delta, '-0.11 vs previous')
  assert.equal(runLine({ mAP50: 0.81 }, null).delta, 'first run')
  assert.equal(runLine({ mAP50: 0.81, version: 2 }, null).label, 'v2 · mAP50 0.81')
  assert.equal(runLine(null, null), null, 'no run is the empty sentence, not a zero')
})

test('test_blocked_by_is_capped_and_ordered', () => {
  const all = blockedBy({ toLabel: 0, review: 16, approved: 24, labelIssues: 3, missingBoxes: 2, healthStale: true })
  assert.equal(all.length, 3, 'at most three rows')
  assert.deepEqual(all.map((b) => b.id), ['review', 'label-quality', 'missing-boxes'], 'version readiness before health')
  assert.equal(all[0].text, '16 labels are waiting for review')
  assert.equal(all[0].to, 'annotate')
  for (const b of all) assert.match(b.to, /\S/, `${b.id} links to the screen that fixes it`)

  // Without approved labels the review backlog is the blocker; health warnings come after it.
  const order = blockedBy({ toLabel: 40, review: 0, approved: 0, labelIssues: 5, missingBoxes: 0, healthStale: false })
  assert.deepEqual(order.map((b) => b.id), ['no-approved', 'label-quality'])

  // Nothing wrong is empty, so the card can say "Nothing is blocked."
  assert.deepEqual(blockedBy({ toLabel: 0, review: 0, approved: 24, labelIssues: 0, missingBoxes: 0, healthStale: false }), [])
})

test('test_health_ring_never_shows_zero_for_missing_data', () => {
  assert.deepEqual(healthRing(null), { value: null, label: 'Unavailable', tone: 'muted' })
  assert.notEqual(healthRing(null).value, 0, 'a failed call is not a zero percent ring')
  const ring = healthRing({ approved: 24, total: 40 })
  assert.equal(ring.value, 60)
  assert.equal(ring.label, '24 approved of 40')
  assert.equal(ring.tone, 'warning')
  assert.equal(healthRing({ approved: 38, total: 40 }).tone, 'success')
  assert.equal(healthRing({ approved: 4, total: 40 }).tone, 'destructive')
  assert.deepEqual(healthRing({ approved: 0, total: 0 }), { value: 0, label: 'No images yet', tone: 'muted' })
})
