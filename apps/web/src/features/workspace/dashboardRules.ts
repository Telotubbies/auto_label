/** Pure rules for the workspace Home dashboard; the page only renders what these return. */

import type { WorkspaceHome } from '@/lib/types'

export type { WorkspaceHome }

export type StepAction = 'create-project' | null

export interface OnboardingFacts {
  ws: string
  projects: number
  images: number
  annotations: number
  models: number
  deployments: number
  teammates: number
  canInvite: boolean
  canCreateProject: boolean
  canUpload: boolean
  canTrain: boolean
  firstProject: string | null
}

export interface OnboardingStep {
  key: 'project' | 'images' | 'labels' | 'model' | 'deploy' | 'team'
  title: string
  hint: string
  done: boolean
  to: string | null
  action: StepAction
}

/** The checklist mirrors the real data lifecycle, so every tick is evidence in the workspace, not a saved flag. */
export function onboardingSteps(f: OnboardingFacts): OnboardingStep[] {
  const project = (path: string) => (f.firstProject ? `/${f.ws}/${f.firstProject}/${path}` : null)
  const steps: OnboardingStep[] = [
    { key: 'project', title: 'Create a project', hint: 'A project holds the images, classes and versions for one model.',
      done: f.projects > 0, to: null, action: f.canCreateProject ? 'create-project' : null },
    { key: 'images', title: 'Upload images', hint: 'JPG, PNG, WebP, TIFF or a ZIP — annotations import too.',
      done: f.images > 0, to: f.canUpload ? project('upload') : null, action: null },
    { key: 'labels', title: 'Label your first images', hint: 'Annotate on the board or let auto-label pre-fill boxes.',
      done: f.annotations > 0, to: project('annotate'), action: null },
    { key: 'model', title: 'Train a model', hint: 'Pick a dataset version and a model family.',
      done: f.models > 0, to: f.canTrain ? project('train') : null, action: null },
    { key: 'deploy', title: 'Deploy a model', hint: 'Ready models are served by the hosted API.',
      done: f.deployments > 0, to: `/${f.ws}/deployments`, action: null },
  ]
  if (f.canInvite) {
    steps.push({ key: 'team', title: 'Invite a teammate', hint: 'Reviewers and labelers can share the queue.',
      done: f.teammates > 0, to: `/${f.ws}/settings/members`, action: null })
  }
  return steps
}

export interface TourStep { target: string; title: string; body: string }

export const TOUR_STEPS: TourStep[] = [
  { target: 'home-stats', title: 'Your workspace at a glance',
    body: 'Projects, images, annotations, models and deployments update as your team works.' },
  { target: 'home-tasks', title: 'Work waiting for you',
    body: 'Anything assigned to you, plus the review and unassigned queues your role can act on.' },
  { target: 'home-checklist', title: 'Getting-started checklist',
    body: 'Six steps from an empty workspace to a served model. Ticks come from real workspace data.' },
  { target: 'home-activity', title: 'Recent activity',
    body: 'Training, auto-labelling and exports appear here with live progress.' },
  { target: 'home-projects', title: 'Your projects',
    body: 'Open a project to upload images, annotate them and train a model.' },
]

export const clampStep = (step: number) => Math.max(0, Math.min(TOUR_STEPS.length - 1, step))
export const nextStep = (step: number) => clampStep(step + 1)
export const prevStep = (step: number) => clampStep(step - 1)

export const tourKey = (ws: string, userId: string) => `ld:tour:home:${ws}:${userId}`

export function hasSeenTour(storage: Pick<Storage, 'getItem'>, key: string): boolean {
  return storage.getItem(key) === '1'
}

export function markTourSeen(storage: Pick<Storage, 'setItem'>, key: string): void {
  storage.setItem(key, '1')
}

const JOB_LABEL: Record<string, string> = {
  train: 'Training', autolabel: 'Auto-label', version: 'Version', export: 'Export',
  export_engine: 'TensorRT export', health: 'Health check', insights_images: 'Image stats',
  insights_leakage: 'Leakage scan', insights_embedding: 'Embedding map',
}

export const jobKindLabel = (kind: string) => JOB_LABEL[kind] ?? kind

export const hasQueue = (t: WorkspaceHome['totals']) => t.to_annotate + t.to_review + t.unassigned > 0
