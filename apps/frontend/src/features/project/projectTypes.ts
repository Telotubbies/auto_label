/**
 * The eight project types, worded by what you get (T-017). One catalogue feeds the New project
 * grid, the Home type filter and `typeLabel` in the project rail, so a rename is a one-line edit.
 * An outcome sentence never names a model family: a buyer picks by the result, not by a checkpoint.
 */
export type ProjectTypeIcon = 'box' | 'shapes' | 'layers' | 'scan' | 'tags' | 'video' | 'activity'

export type ProjectType = {
  id: string
  label: string
  /** One sentence, ending in a full stop. */
  outcome: string
  /** Exactly two capability chips. */
  chips: readonly [string, string]
  icon: ProjectTypeIcon
  /** The card shows only while this workspace flag is on. */
  flag?: string
  /** One of the five types that shipped before `task_a1_types`. */
  original?: boolean
}

export const PROJECT_TYPES: readonly ProjectType[] = [
  { id: 'object-detection', label: 'Object detection', outcome: 'Draw a box around each object.',
    chips: ['Boxes', 'Counts'], icon: 'box', original: true },
  { id: 'instance-segmentation', label: 'Instance segmentation', outcome: 'Outline each separate object.',
    chips: ['Polygons', 'Measuring'], icon: 'shapes', original: true },
  { id: 'semantic-segmentation', label: 'Semantic segmentation', outcome: 'Colour every pixel of a class, one mask per class.',
    chips: ['Masks', 'Area'], icon: 'layers' },
  { id: 'classification', label: 'Classification (one label)', outcome: 'Give the whole image one label.',
    chips: ['One label', 'Sorting'], icon: 'scan', original: true },
  { id: 'multi-label-classification', label: 'Classification (many labels)', outcome: 'Give the whole image several labels.',
    chips: ['Tags', 'Sorting'], icon: 'tags' },
  { id: 'keypoint-detection', label: 'Keypoints', outcome: 'Place named points and link them into a skeleton.',
    chips: ['Points', 'Pose'], icon: 'scan', original: true },
  { id: 'action-recognition', label: 'Action recognition', outcome: 'Mark when an action starts and ends in a video.',
    chips: ['Video', 'Segments'], icon: 'video' },
  { id: 'anomaly-detection', label: 'Anomaly detection', outcome: 'Learn what good looks like and flag deviations.',
    chips: ['Good-only', 'Heatmap'], icon: 'activity', flag: 'task_29', original: true },
]

/**
 * The cards to show. With `task_a1_types` the whole catalogue; without it, today's five, and each
 * card still obeys its own flag (anomaly needs `task_29`, which kept it off by default).
 */
export function availableTypes(flags: ReadonlySet<string>): ProjectType[] {
  const all = flags.has('task_a1_types')
  return PROJECT_TYPES.filter((t) => (all || t.original) && (!t.flag || flags.has(t.flag)))
}

/** The one label for a type id; an unknown id (an old row) falls back to itself. */
export const typeLabel = (id: string) => PROJECT_TYPES.find((t) => t.id === id)?.label ?? id
