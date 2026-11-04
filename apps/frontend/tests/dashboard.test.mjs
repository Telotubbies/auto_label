// Pure rules behind the workspace Home dashboard: checklist, tour state and queue helpers.
// Runs with the built-in Node test runner: node --test tests/dashboard.test.mjs (from apps/web).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  TOUR_STEPS, clampStep, hasSeenTour, jobKindLabel, markTourSeen, nextStep, onboardingSteps, prevStep, tourKey,
} from '../src/features/workspace/dashboardRules.ts'

const facts = (over = {}) => ({
  ws: 'acme', projects: 1, images: 10, annotations: 25, models: 2, deployments: 1,
  teammates: 2, canInvite: true, canCreateProject: true, canUpload: true, canTrain: true, canAnnotate: true,
  firstProject: 'ppe', ...over,
})

test('the checklist follows the data lifecycle and marks finished work', () => {
  const steps = onboardingSteps(facts())
  assert.deepEqual(steps.map((s) => s.key), ['project', 'images', 'labels', 'model', 'deploy', 'team'])
  assert.ok(steps.every((s) => s.done))
})

test('an empty workspace starts at create-project and keeps later links unwired', () => {
  const steps = onboardingSteps(facts({ projects: 0, images: 0, annotations: 0, models: 0, deployments: 0, teammates: 0, firstProject: null }))
  assert.equal(steps[0].done, false)
  assert.equal(steps[0].action, 'create-project')
  assert.equal(steps[1].to, null)
  assert.equal(steps[2].to, null)
})

test('image and label steps point at the first project once one exists', () => {
  const steps = onboardingSteps(facts({ images: 0, annotations: 0 }))
  assert.equal(steps[1].to, '/acme/ppe/upload')
  assert.equal(steps[2].to, '/acme/ppe/annotate')
  assert.equal(steps[3].to, '/acme/ppe/train')
})

test('the invite step disappears for roles that cannot invite', () => {
  const steps = onboardingSteps(facts({ canInvite: false, teammates: 0 }))
  assert.equal(steps.some((s) => s.key === 'team'), false)
})

test('a labeler gets no upload or train shortcut the project gate would bounce', () => {
  const steps = onboardingSteps(facts({ canUpload: false, canTrain: false, canInvite: false }))
  assert.equal(steps.find((s) => s.key === 'images').to, null)
  assert.equal(steps.find((s) => s.key === 'model').to, null)
  // Labeling is still their job, so that shortcut stays.
  assert.equal(steps.find((s) => s.key === 'labels').to, '/acme/ppe/annotate')
})

test('a viewer gets no label shortcut the annotate route would bounce', () => {
  const steps = onboardingSteps(facts({ annotations: 0, canAnnotate: false, canUpload: false, canTrain: false, canInvite: false }))
  assert.equal(steps.find((s) => s.key === 'labels').to, null)
})

test('a billing member in an empty workspace gets no create action', () => {
  const steps = onboardingSteps(facts({
    projects: 0, images: 0, annotations: 0, models: 0, deployments: 0, teammates: 0, firstProject: null,
    canCreateProject: false, canUpload: false, canTrain: false, canInvite: false,
  }))
  assert.equal(steps[0].done, false)
  assert.equal(steps[0].action, null)
})

test('the tour key is per user and per workspace', () => {
  assert.notEqual(tourKey('acme', 'u1'), tourKey('acme', 'u2'))
  assert.notEqual(tourKey('acme', 'u1'), tourKey('other', 'u1'))
})

test('tour seen state round-trips through storage', () => {
  const store = new Map()
  const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, v) }
  const key = tourKey('acme', 'u1')
  assert.equal(hasSeenTour(storage, key), false)
  markTourSeen(storage, key)
  assert.equal(hasSeenTour(storage, key), true)
})

test('tour steps clamp at both ends and always target a dashboard section', () => {
  assert.equal(clampStep(-3), 0)
  assert.equal(clampStep(99), TOUR_STEPS.length - 1)
  assert.equal(nextStep(0), 1)
  assert.equal(nextStep(TOUR_STEPS.length - 1), TOUR_STEPS.length - 1)
  assert.equal(prevStep(0), 0)
  assert.ok(TOUR_STEPS.every((s) => s.target && s.title && s.body))
})

test('job labels stay readable for unknown future kinds', () => {
  assert.equal(jobKindLabel('train'), 'Training')
  assert.equal(jobKindLabel('export_engine'), 'TensorRT export')
  assert.equal(jobKindLabel('brand_new_kind'), 'brand_new_kind')
})
