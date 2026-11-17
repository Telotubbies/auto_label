/**
 * T-483 — the project overview's pure model: five stages, their state, one sentence and one
 * action each. No React, so `tests/overview.test.mjs` executes it under Node's type stripping.
 *
 * The counts use the one vocabulary the API already ships: uploaded = `images`,
 * approved = `statusCounts.done`, to label = `unassigned + annotating`, in review = `review`.
 * `null` means the call behind a count failed; the card then shows `—` and a Retry, never `0`.
 * State precedence is blocked, then needs-you, then done, so a failed run never reads as finished.
 */
import type { Job, ModelItem, Status, Version } from '../../lib/types.ts'

export const STAGE_ORDER = ['upload', 'annotate', 'dataset', 'train', 'deploy'] as const
export type StageId = (typeof STAGE_ORDER)[number]
export type StageState = 'done' | 'needs-you' | 'blocked' | 'not-started' | 'unknown'

export interface StageFact {
  state: StageState
  /** The number the card shows. `null` means the call failed. */
  count: number | null
  sentence: string
  /** Stable action id, so a test can assert the branch without reading the label. */
  action: string
  actionLabel: string
  /** A project-relative target, resolved through `projectPath` by the view. */
  to?: string
  locked?: boolean
}

export interface StageCardView extends Omit<StageFact, 'count'> {
  id: StageId
  number: number
  title: string
  chip: string
  count: string
}

export interface OverviewInput {
  images: number
  statusCounts?: Partial<Record<Status, number>>
  /** `null` = the call failed; the card degrades to a Retry instead of a zero. */
  versions: Version[] | null
  models: ModelItem[] | null
  jobs: Job[] | null
  canTrain: boolean
  canDeploy: boolean
}

export interface OverviewFacts {
  stages: Record<StageId, StageFact>
  primary: { label: string; to: string }
}

const TITLES: Record<StageId, string> = {
  upload: 'Upload', annotate: 'Annotate', dataset: 'Dataset', train: 'Train', deploy: 'Deploy',
}

const STATE_WORD: Record<StageState, string> = {
  done: 'done', 'needs-you': 'needs you', blocked: 'blocked', 'not-started': 'not started', unknown: 'unknown',
}

const plural = (n: number, one: string) => `${one}${n === 1 ? '' : 's'}`
const epochOf = (error: string) => {
  const m = /epoch\s+(\d+)/i.exec(error)
  return m ? Number(m[1]) : null
}

/** One card from one fact; a failed count owns the action, so it can never look loadable. */
export function card(id: StageId, fact: StageFact): StageCardView {
  const failed = fact.count === null && !fact.locked
  const state: StageState = failed ? 'unknown' : fact.state
  return {
    ...fact,
    id,
    number: STAGE_ORDER.indexOf(id) + 1,
    title: TITLES[id],
    state,
    chip: STATE_WORD[state],
    count: fact.count === null ? '—' : String(fact.count),
    action: failed ? 'retry' : fact.action,
    actionLabel: failed ? 'Retry' : fact.actionLabel,
    to: failed ? undefined : fact.to,
  }
}

/** All five, in pipeline order, whatever the input omits. */
export function board(stages: Partial<Record<StageId, StageFact>>): StageCardView[] {
  return STAGE_ORDER.map((id) => card(id, stages[id] ?? {
    state: 'unknown', count: null, sentence: 'This stage has not loaded', action: 'retry', actionLabel: 'Retry',
  }))
}

const requestAccess = (fact: StageFact, allowed: boolean): StageFact =>
  allowed ? fact : { ...fact, locked: true, action: 'request-access', actionLabel: 'Request access', to: 'settings?tab=access' }

/** Derive the five facts and the header's one primary action from the four existing calls. */
export function overviewFacts(input: OverviewInput): OverviewFacts {
  const images = input.images
  const counts = input.statusCounts
  const countsKnown = counts != null
  const approved = counts?.done ?? 0
  const inReview = counts?.review ?? 0
  const toLabel = (counts?.unassigned ?? 0) + (counts?.annotating ?? 0)
  const versions = input.versions
  const latest = versions?.length ? [...versions].sort((a, b) => b.number - a.number)[0] : null
  const latestLabel = `v${latest?.number ?? 1}`
  const runs = [...(input.jobs ?? [])].filter((j) => j.kind === 'train').sort((a, b) => b.created - a.created)
  const lastRun = runs[0] ?? null
  const readyModels = (input.models ?? []).filter((m) => m.status === 'ready')

  let annotate: StageFact
  if (images === 0) {
    annotate = { state: 'not-started', count: 0, sentence: 'Nothing to label until images are uploaded', action: 'none', actionLabel: 'After upload' }
  } else if (!countsKnown) {
    annotate = { state: 'unknown', count: null, sentence: 'Could not load label counts', action: 'retry', actionLabel: 'Retry' }
  } else if (inReview > 0) {
    annotate = { state: 'needs-you', count: inReview, sentence: `${inReview} labels are waiting for approval`, action: 'review', actionLabel: `Review ${inReview}`, to: 'annotate' }
  } else if (toLabel > 0) {
    annotate = { state: 'needs-you', count: toLabel, sentence: `${toLabel} ${plural(toLabel, 'image')} ${toLabel === 1 ? 'has' : 'have'} no labels yet`, action: 'label', actionLabel: `Label ${toLabel}`, to: 'annotate' }
  } else {
    annotate = { state: 'done', count: approved, sentence: `${approved} labels approved`, action: 'open-annotate', actionLabel: 'Open labels', to: 'annotate' }
  }

  let dataset: StageFact
  if (images === 0) {
    dataset = { state: 'not-started', count: 0, sentence: 'Nothing to version until images are labelled', action: 'none', actionLabel: 'After upload' }
  } else if (versions === null || !countsKnown) {
    dataset = { state: 'unknown', count: null, sentence: `Could not load ${versions === null ? 'versions' : 'label counts'}`, action: 'retry', actionLabel: 'Retry' }
  } else if (approved === 0) {
    dataset = { state: 'blocked', count: versions.length, sentence: 'Blocked by annotate — no approved labels yet', action: 'annotate', actionLabel: 'Go to annotate', to: 'annotate' }
  } else if (versions.length === 0) {
    dataset = { state: 'needs-you', count: 0, sentence: `${approved} approved, no version yet`, action: 'create-version', actionLabel: 'Create a version', to: 'dataset?tab=versions' }
  } else {
    dataset = { state: 'done', count: versions.length, sentence: `${versions.length} ${plural(versions.length, 'version')} · ${approved} approved`, action: 'open-versions', actionLabel: 'Open versions', to: 'dataset?tab=versions' }
  }

  let train: StageFact
  if (images === 0) {
    train = { state: 'not-started', count: 0, sentence: 'Nothing to train until images are uploaded', action: 'none', actionLabel: 'After upload' }
  } else if (input.jobs === null) {
    train = { state: 'unknown', count: null, sentence: 'Could not load training runs', action: 'retry', actionLabel: 'Retry' }
  } else if (!versions || versions.length === 0) {
    train = { state: 'not-started', count: 0, sentence: 'Create a version before training', action: 'none', actionLabel: 'After dataset' }
  } else if (lastRun?.status === 'failed') {
    const epoch = epochOf(lastRun.error)
    train = { state: 'blocked', count: runs.length, sentence: `The last run failed${epoch ? ` at epoch ${epoch}` : ''} — open the run to read the log`, action: 'open-run', actionLabel: 'Open run', to: 'train' }
  } else if (lastRun && (lastRun.status === 'running' || lastRun.status === 'queued')) {
    train = { state: 'needs-you', count: runs.length, sentence: 'Training is running — open the run to follow it', action: 'open-run', actionLabel: 'Open run', to: 'train' }
  } else if (readyModels.length > 0) {
    train = { state: 'done', count: readyModels.length, sentence: `${readyModels.length} ${plural(readyModels.length, 'model')} ready`, action: 'open-models', actionLabel: 'Open models', to: 'models' }
  } else {
    train = { state: 'needs-you', count: runs.length, sentence: `Version ${latestLabel} is ready to train`, action: 'train', actionLabel: `Train on ${latestLabel}`, to: 'train' }
  }

  let deploy: StageFact
  if (images === 0) {
    deploy = { state: 'not-started', count: 0, sentence: 'No endpoint until a model is trained', action: 'none', actionLabel: 'After upload' }
  } else if (input.models === null) {
    deploy = { state: 'unknown', count: null, sentence: 'Could not load models', action: 'retry', actionLabel: 'Retry' }
  } else if (readyModels.length === 0) {
    deploy = { state: 'not-started', count: 0, sentence: 'No endpoint yet', action: 'none', actionLabel: 'After training' }
  } else {
    deploy = { state: 'done', count: readyModels.length, sentence: `${readyModels.length} ${plural(readyModels.length, 'model')} ready to deploy`, action: 'deploy', actionLabel: 'Open deploy', to: 'deploy' }
  }

  const upload: StageFact = images > 0
    ? { state: 'done', count: images, sentence: `${images} ${plural(images, 'image')} uploaded`, action: 'open-images', actionLabel: 'Open images', to: 'dataset' }
    : { state: 'needs-you', count: 0, sentence: 'No images yet — upload to start the pipeline', action: 'upload', actionLabel: 'Upload images', to: 'upload' }

  // The header's one primary follows the earliest open step, in the same order as the board.
  let primary = { label: 'Open dataset', to: 'dataset' }
  if (images === 0) primary = { label: 'Upload images', to: 'upload' }
  else if (!countsKnown) primary = { label: 'Open dataset', to: 'dataset' }
  else if (inReview > 0) primary = { label: `Review ${inReview} labels`, to: 'annotate' }
  else if (toLabel > 0) primary = { label: `Label ${toLabel} images`, to: 'annotate' }
  else if (!versions || versions.length === 0) primary = { label: 'Create a version', to: 'dataset?tab=versions' }
  else if (readyModels.length > 0) primary = { label: 'Test the model', to: 'deploy' }
  else if (input.canTrain) primary = { label: `Train on ${latestLabel}`, to: 'train' }

  return {
    stages: {
      upload,
      annotate,
      dataset,
      train: requestAccess(train, input.canTrain),
      deploy: requestAccess(deploy, input.canDeploy),
    },
    primary,
  }
}
