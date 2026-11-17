// Stage manifest (T-477): five numbered stages inside three purpose groups, their state, count
// and one line of text, derived from the payload the project shell already loads.
// Runs with the built-in Node test runner: node --test tests/stage-manifest.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  GROUPS, SECONDARY, STAGES, groupSummary, nextStage, primaryLabel, railItem, stageCount, stageFacts,
  stageLine, stageState, stageWord,
} from '../src/lib/nav/project/stages.ts'
import { visibleStageGroups } from '../src/lib/nav/visibility.ts'

const project = (over = {}) => ({
  slug: 'ppe', images: 40, models: 0, classes: [], statusCounts: {}, ...over,
})
const version = (number, status = 'ready') => ({
  id: `v${number}`, number, name: `v${number}`, settings: {}, status, stats: {}, created: number, job: null, exports: {},
})
const train = (status, created = 1) => ({
  id: `j${created}`, kind: 'train', status, progress: 100, params: {}, result: {}, error: '',
  created, started: 1, finished: 2, project: 'ppe',
})
const facts = (over = {}, versions = [], jobs = []) => stageFacts({ project: project(over), versions, jobs })

const perms = (...granted) => {
  const set = new Set(granted)
  return (p) => set.has(p)
}
const MANAGER = perms('project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.train', 'project.models', 'project.infer', 'project.settings', 'project.streams')
const LABELER = perms('project.read', 'project.annotate', 'project.classes', 'project.infer')

const ids = (groups) => groups.flatMap((g) => g.items.map((i) => i.id))

test('test_five_stages_in_pipeline_order', () => {
  assert.deepEqual(STAGES.map((s) => s.id), ['upload', 'annotate', 'dataset', 'train', 'deploy'])
  assert.deepEqual(STAGES.map((s) => s.number), [1, 2, 3, 4, 5])
  assert.deepEqual(STAGES.map((s) => s.label), ['Upload', 'Annotate', 'Dataset', 'Train', 'Deploy'])
  // Only the five stage ids are numbered; every other destination is an unnumbered row.
  const numbered = GROUPS.flatMap((g) => g.items).filter((id) => STAGES.some((s) => s.id === id))
  assert.deepEqual(numbered, ['upload', 'annotate', 'dataset', 'train', 'deploy'])
  assert.deepEqual(SECONDARY.filter((i) => 'number' in i), [])
  for (const id of ['insights', 'classes', 'models', 'model-search', 'active-learning']) {
    assert.equal('number' in railItem(id), false, `${id} must stay unnumbered`)
  }
})

test('test_groups_hold_every_destination_once', () => {
  const all = GROUPS.flatMap((g) => g.items)
  assert.equal(new Set(all).size, all.length, 'a destination is listed twice')
  assert.deepEqual(all, [
    'upload', 'annotate', 'dataset', 'insights', 'classes',
    'train', 'models', 'model-search',
    'deploy', 'active-learning',
  ])
  assert.deepEqual(GROUPS.map((g) => g.label), ['Data', 'Models', 'Deploy'])
  // Project settings closes the rail below a rule, outside the three groups.
  assert.equal(all.includes('settings'), false)
  assert.deepEqual(SECONDARY.map((i) => i.to), ['settings'])
  assert.equal(SECONDARY[0].label, 'Project settings')
  // Sentence case, never ALL-CAPS.
  for (const g of GROUPS) assert.notEqual(g.label, g.label.toUpperCase(), `${g.label} shouts`)
  assert.notEqual(SECONDARY[0].label, SECONDARY[0].label.toUpperCase())
})

test('test_state_precedence', () => {
  const uploaded = facts({ statusCounts: { unassigned: 40 } }, [], [])
  assert.equal(stageState(uploaded, 'annotate'), 'needs-you')
  assert.equal(stageState(uploaded, 'dataset'), 'blocked')
  assert.equal(stageState(uploaded, 'train'), 'not-started')
  assert.equal(stageLine(uploaded, 'dataset'), 'blocked by annotate')

  // A failed run reads as blocked even though a version exists — it never reads as finished.
  const failed = facts({ statusCounts: { done: 24 } }, [version(1)], [train('failed')])
  assert.equal(stageState(failed, 'train'), 'blocked')
  assert.equal(stageLine(failed, 'train'), 'last run failed')

  // A ready run later than the failed one wins: the newest run decides the stage.
  const recovered = facts({ statusCounts: { done: 24 } }, [version(1)], [train('failed', 1), train('done', 2)])
  assert.equal(stageState(recovered, 'train'), 'done')
  assert.equal(stageState(recovered, 'deploy'), 'not-started')
  assert.equal(nextStage(recovered), 'deploy')
  assert.equal(nextStage(uploaded), 'annotate')
})

test('test_counts_come_from_one_vocabulary', () => {
  const f = stageFacts({
    project: project({ images: 40, models: 3, classes: [{ id: 'c1' }, { id: 'c2' }], statusCounts: { unassigned: 20, annotating: 4, review: 16, done: 24 } }),
    versions: [version(1), version(2)],
    jobs: [train('done')],
  })
  assert.equal(f.uploaded, 40)
  assert.equal(f.approved, 24)
  assert.equal(f.toLabel, 24)
  assert.equal(f.inReview, 16)
  assert.equal(stageCount(f, 'upload'), 40)
  assert.equal(stageCount(f, 'annotate'), 40, 'annotate counts the work still at that stage')
  assert.equal(stageCount(f, 'dataset'), 2)
  // No deployment record exists today: the count is null, never a zero we made up.
  assert.equal(stageCount(f, 'deploy'), null)
  assert.equal(f.deployed, null)
  assert.equal(stageCount(f, 'models'), 3)
  assert.equal(stageCount(f, 'classes'), 2)
  for (const id of ['insights', 'model-search', 'active-learning']) assert.equal(stageCount(f, id), null)
  // The fact object carries exactly that vocabulary and no invented number.
  assert.deepEqual(Object.keys(f).sort(), [
    'approved', 'classes', 'deployed', 'inReview', 'lastRun', 'latestVersion', 'models', 'runs', 'toLabel',
    'uploaded', 'versions',
  ])
})

test('test_primary_label_follows_the_earliest_open_stage', () => {
  assert.equal(primaryLabel(facts({ statusCounts: { unassigned: 40 } }), 'manager'), 'Label 40 images')
  assert.equal(primaryLabel(facts({ statusCounts: { review: 16, done: 24 } }), 'manager'), 'Review 16 labels')
  assert.equal(primaryLabel(facts({ statusCounts: { done: 40 } }), 'manager'), 'Create a version')
  assert.equal(primaryLabel(facts({ statusCounts: { done: 40 } }, [version(1)]), 'manager'), 'Train on v1')
  assert.equal(primaryLabel(facts({ statusCounts: { done: 40 } }, [version(1)], [train('done')]), 'manager'),
    'Test the model')
})

test('test_labeler_sees_three_stages_and_two_locks', () => {
  const groups = visibleStageGroups(LABELER, 'labeler')
  // Nothing is filtered out of the five numbered stages: train and deploy stay, dimmed.
  for (const id of ['upload', 'annotate', 'dataset', 'train', 'deploy']) {
    assert.ok(ids(groups).includes(id), `${id} must stay in the rail for a labeler`)
  }
  assert.deepEqual(groups.flatMap((g) => g.items).filter((i) => i.locked).map((i) => i.id), ['train', 'deploy'])
  // Upload is readable by a labeler even without project.upload, so it is not locked.
  const upload = groups.flatMap((g) => g.items).find((i) => i.id === 'upload')
  assert.equal(upload.locked, false)
  // Secondary destinations they cannot open are dropped as before (insights, classes, models …).
  assert.deepEqual(ids(groups), ['upload', 'annotate', 'dataset', 'train', 'deploy'])

  const manager = visibleStageGroups(MANAGER, 'manager')
  assert.deepEqual(manager.flatMap((g) => g.items).filter((i) => i.locked), [])
  assert.deepEqual(ids(manager), GROUPS.flatMap((g) => g.items))
})

test('test_unknown_numbers_never_read_as_zero', () => {
  // statusCounts is missing while the payload loads: the count is null (a skeleton), not 0.
  const loading = stageFacts({ project: project({ statusCounts: undefined }), versions: [], jobs: [] })
  assert.equal(stageCount(loading, 'annotate'), null)
  assert.equal(stageState(loading, 'annotate'), 'unknown')
  assert.equal(stageLine(loading, 'annotate'), null)
  // A failed /versions call is unknown, not "0 versions".
  const noVersions = facts({ statusCounts: { done: 24 } }, null, [])
  assert.equal(stageState(noVersions, 'dataset'), 'unknown')
  assert.equal(stageCount(noVersions, 'dataset'), null)
  assert.notEqual(stageLine(noVersions, 'dataset'), '0 versions')
  // A failed jobs call leaves the train stage unknown too.
  const noJobs = facts({ statusCounts: { done: 24 } }, [version(1)], null)
  assert.equal(stageState(noJobs, 'train'), 'unknown')

  // An empty project: stage 1 is the one that needs you, stages 2–5 have not started.
  const empty = facts({ images: 0, statusCounts: {} }, [], [])
  assert.equal(stageState(empty, 'upload'), 'needs-you')
  for (const id of ['annotate', 'dataset', 'train', 'deploy']) assert.equal(stageState(empty, id), 'not-started')
  assert.equal(stageLine(empty, 'upload'), 'no images yet')
  assert.equal(primaryLabel(empty, 'manager'), 'Upload images')
})

test('test_group_summary_counts_what_is_waiting', () => {
  // Approved images exist and some are still unlabelled: two Data rows need the member.
  const f = facts({ statusCounts: { unassigned: 16, done: 24 } }, [], [])
  assert.equal(groupSummary(f, 'data'), '2 need you')
  assert.equal(groupSummary(f, 'models'), null)
  assert.equal(groupSummary(f, 'deploy'), null)
  const one = facts({ statusCounts: { unassigned: 40 } }, [], [])
  assert.equal(groupSummary(one, 'data'), '1 needs you')
  assert.equal(stageWord('needs-you'), 'needs you')
  assert.equal(stageWord('not-started'), 'not started')
})
