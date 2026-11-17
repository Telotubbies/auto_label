// T-483 — the project overview: five pipeline cards, their state copy and one action each.
// The card copy and the state precedence are pure, so they run here; the heading order and the
// single primary are source assertions because this suite has no DOM renderer.
//   node --test tests/overview.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { board, card, overviewFacts, STAGE_ORDER } from '../src/features/project/overviewModel.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const overviewSrc = source('../src/features/project/Overview.tsx')
const stageCardSrc = source('../src/features/project/StageCard.tsx')

const project = (over = {}) => ({
  id: 'p1', slug: 'ppe', name: 'PPE Detection', type: 'object-detection', visibility: 'private',
  license: '', annotationGroup: '', multilabel: false, folderId: null, images: 40, models: 0,
  created: 0, updated: 0, thumbnail: null, settings: {},
  statusCounts: { unassigned: 0, annotating: 0, review: 0, done: 24 },
  ...over,
})
const version = (n = 1, over = {}) => ({
  id: `v${n}`, number: n, name: `v${n}`, settings: {}, status: 'ready', stats: {},
  created: n, job: null, exports: {}, ...over,
})
const model = (over = {}) => ({
  id: 'm1', name: 'PPE Detector', arch: 'yolo26n', task: 'detect', status: 'ready', metrics: {},
  history: [], classes: [], versionId: 'v1', created: 2, weightsUrl: null, ...over,
})
const job = (kind, status, over = {}) => ({
  id: 'j1', kind, status, progress: 100, params: {}, result: {}, error: '',
  created: 3, started: 3, finished: 4, ...over,
})
const input = (over = {}) => ({
  images: project().images,
  statusCounts: project().statusCounts,
  versions: [version(1)],
  models: [model()],
  jobs: [],
  canTrain: true,
  canDeploy: true,
  ...over,
})

test('test_board_has_five_cards_in_order', () => {
  const facts = overviewFacts(input())
  const cards = board(facts.stages)
  assert.deepEqual(cards.map((c) => c.id), ['upload', 'annotate', 'dataset', 'train', 'deploy'])
  assert.deepEqual(cards.map((c) => c.number), [1, 2, 3, 4, 5])
  assert.deepEqual([...STAGE_ORDER], ['upload', 'annotate', 'dataset', 'train', 'deploy'])
})

test('test_card_copy_matches_the_state', () => {
  // 16 in review: needs you, the count, the sentence and the review action.
  const review = card('annotate', overviewFacts(input({
    statusCounts: { unassigned: 24, annotating: 0, review: 16, done: 0 },
  })).stages.annotate)
  assert.equal(review.chip, 'needs you')
  assert.equal(review.count, '16')
  assert.equal(review.sentence, '16 labels are waiting for approval')
  assert.equal(review.action, 'review')
  assert.equal(review.actionLabel, 'Review 16')

  // A failed run is blocked even when a version and a ready model exist: blocked beats done.
  const train = card('train', overviewFacts(input({
    versions: [version(2)],
    models: [model()],
    jobs: [job('train', 'failed', { error: 'CUDA out of memory at epoch 4' })],
  })).stages.train)
  assert.equal(train.chip, 'blocked')
  assert.match(train.sentence, /The last run failed at epoch 4 — open the run to read the log/)
  assert.equal(train.action, 'open-run')
  assert.equal(train.actionLabel, 'Open run')

  // Everything approved: the annotate card is done, with its approved count.
  const done = card('annotate', overviewFacts(input({
    statusCounts: { unassigned: 0, annotating: 0, review: 0, done: 24 },
  })).stages.annotate)
  assert.equal(done.chip, 'done')
  assert.equal(done.count, '24')
  assert.equal(done.sentence, '24 labels approved')
})

test('test_failed_facts_degrade_to_a_retry', () => {
  const broken = card('dataset', overviewFacts(input({ versions: null })).stages.dataset)
  assert.equal(broken.count, '—')
  assert.equal(broken.count === '0', false, 'a failed count is never shown as zero')
  assert.equal(broken.action, 'retry')
  assert.equal(broken.actionLabel, 'Retry')
})

test('test_heading_structure', () => {
  // One PageHeader (its own <h1>) and five card <h2>s inside an ordered list.
  assert.equal((overviewSrc.match(/<PageHeader/g) ?? []).length, 1, 'the page owns exactly one header')
  assert.match(source('../src/components/ui.tsx'), /<h1 /, 'PageHeader renders the h1')
  assert.equal((stageCardSrc.match(/<h2/g) ?? []).length, 1, 'each card has one h2 title')
  assert.match(overviewSrc, /<ol[^>]*aria-label="Project pipeline"/, 'the board is an ordered list')
  assert.match(overviewSrc, /board\(/, 'the ordered list renders the five-card model, not ad-hoc cards')
})

test('test_no_second_primary', () => {
  const primaries = (src) => (src.match(/variant="primary"/g) ?? []).length
  assert.equal(primaries(overviewSrc), 1, 'the page renders exactly one primary button')
  assert.equal(primaries(stageCardSrc), 0, 'a card action is a link, never a second primary')
})

test('test_empty_project_starts_at_upload', () => {
  const facts = overviewFacts(input({ images: 0, statusCounts: undefined, versions: [], models: [], jobs: [] }))
  const cards = board(facts.stages)
  assert.equal(cards[0].chip, 'needs you')
  assert.equal(cards[0].action, 'upload')
  for (const c of cards.slice(1)) {
    assert.equal(c.chip, 'not started', `${c.id} waits for upload`)
    assert.equal(c.actionLabel, 'After upload')
  }
})

test('test_labeler_sees_all_five_with_two_locked', () => {
  const facts = overviewFacts(input({ canTrain: false, canDeploy: false }))
  const cards = board(facts.stages)
  assert.equal(cards.length, 5, 'no card is hidden from a role')
  assert.deepEqual(cards.filter((c) => c.locked).map((c) => c.id), ['train', 'deploy'])
  for (const c of cards.filter((c) => c.locked)) {
    assert.equal(c.actionLabel, 'Request access')
    assert.equal(c.chip === 'needs you' || c.chip === 'not started' || c.chip === 'done' || c.chip === 'blocked', true)
  }
})

test('test_primary_label_follows_the_earliest_open_step', () => {
  const label = (over) => overviewFacts(input(over)).primary.label
  assert.equal(label({ statusCounts: { unassigned: 40, annotating: 0, review: 0, done: 0 } }), 'Label 40 images')
  assert.equal(label({ statusCounts: { unassigned: 24, annotating: 0, review: 16, done: 0 } }), 'Review 16 labels')
  assert.equal(label({ statusCounts: { unassigned: 0, annotating: 0, review: 0, done: 24 }, versions: [] }), 'Create a version')
  assert.equal(label({ statusCounts: { unassigned: 0, annotating: 0, review: 0, done: 24 }, models: [], jobs: [] }), 'Train on v1')
  assert.equal(label({ statusCounts: { unassigned: 0, annotating: 0, review: 0, done: 24 } }), 'Test the model')
})

test('test_board_cards_keep_a_readable_width_at_1440', () => {
  // T-1109 / Q1-A1-04: at 1440 two 232 px rails, 64 px of page padding, the 360 px aside and its
  // 24 px gap leave ~513 px for five cards — 93 px each, so the sentences wrap one word per line.
  // The aside may only share the row once the board still gives every card 160 px and 12 px gaps:
  // 2·232 + 64 + 360 + 24 + 5·160 + 4·12 = 1768. The chosen 1800 px clears that floor.
  const beside = overviewSrc.match(/min-\[(\d+)px\]:grid-cols-\[/)
  assert.ok(beside, 'the aside sits beside the board only above an explicit breakpoint')
  assert.ok(Number(beside[1]) >= 1768, `the side-by-side breakpoint is ${beside[1]}px, below 1768 px, so cards fall under 160 px`)
  assert.match(overviewSrc, /mt-6 min-\[\d+px\]:mt-0/, 'the aside only loses its top margin when it sits beside the board')
  assert.match(overviewSrc, /md:grid-cols-5/, 'the pipeline stays five cards in one row from md up')
})

test('test_loading_paints_five_skeletons_of_one_height', () => {
  // The loading branch builds one skeleton per stage from the same order, at a fixed height.
  assert.match(overviewSrc, /isPending/)
  assert.match(overviewSrc, /STAGE_ORDER\.map\(/)
  assert.match(overviewSrc, /h-\[168px\]/)
})
