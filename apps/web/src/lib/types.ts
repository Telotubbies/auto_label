export type Role = 'admin' | 'reviewer' | 'annotator'
export type ProjectType = 'object-detection' | 'instance-segmentation' | 'classification'
export type Split = 'train' | 'valid' | 'test'
export type Status = 'unassigned' | 'annotating' | 'review' | 'done'

export interface WorkspaceRef { id: string; slug: string; name: string; role: Role; plan: string; plan_label: string; owner: boolean; mfa_required: boolean }
export interface Me { id: string; email: string; name: string; email_verified: number | null; mfa_enabled: boolean; workspaces: WorkspaceRef[] }
export interface SessionRow { id: string; created: number; last_seen: number; ip: string; user_agent: string }
export interface LoginEvent { method: 'password' | 'mfa' | 'oidc'; ok: boolean; ip: string; user_agent: string; created: number }
export interface MfaSetup { secret: string; otpauth: string; qr: string }

export interface Usage {
  plan: string; plan_label: string; limits: { projects: number; images: number; seats: number; credits: number; label: string }
  credits_used: number; credits_left: number; period: string; projects: number; images: number; seats: number; models: number
  daily?: Record<string, number | string>[]
}
export interface WorkspaceInfo { id: string; slug: string; name: string; role: Role; owner_id: string; require_mfa: boolean; usage: Usage }

export interface LabelClass { id: string; name: string; color: string; count: number }
export interface Project {
  id: string; slug: string; name: string; type: ProjectType; visibility: 'public' | 'private'; license: string
  annotationGroup: string; multilabel: boolean; folderId: string | null; images: number; models: number
  created: number; updated: number; thumbnail: string | null; settings: Record<string, any>
  classes?: LabelClass[]; statusCounts?: Partial<Record<Status, number>>; role?: Role
}

export type Shape =
  | { kind: 'bbox'; x: number; y: number; w: number; h: number }
  | { kind: 'polygon'; points: number[] }
  | { kind: 'class' }
export interface Annotation {
  id: string; classId: string; shape: Shape; attributes?: Record<string, boolean>; confidence?: number
  /** 'human' | 'sam3' | 'vlm+sam3' | 'trained:<id>' | '<family>:<variant>' */
  source?: string
}

export interface ImageItem {
  id: string; name: string; width: number; height: number; split: Split; status: Status; assigneeId: string | null
  review: 'approved' | 'rejected' | null; tags: string[]; batchId: string | null; annotated: boolean
  annotationCount: number; created: number; thumbnail: string; url: string; classIds: string[]
}
export interface Batch { id: string; name: string; source: string; created: number; images: number }

export interface BoardCard { batchId: string | null; batchName: string; created: number; assigneeId: string | null; assignee: string | null; images: number; annotated: number }
export interface Board { columns: Record<Status, BoardCard[]>; members: { id: string; name: string }[] }

export interface JobStage { status: 'done' | 'running' | 'failed'; t: number; note?: string }
export interface Job {
  id: string; kind: 'version' | 'export' | 'export_engine' | 'train' | 'autolabel' | 'health' | 'insights_images' | 'insights_leakage' | 'insights_embedding'; status: 'queued' | 'running' | 'cancelling' | 'done' | 'failed' | 'cancelled'
  progress: number; params: Record<string, any>; result: Record<string, any> & { stages?: Record<string, JobStage> }; error: string; created: number
  started: number | null; finished: number | null; project?: string; project_name?: string; url?: string | null
}
export interface Version {
  id: string; number: number; name: string; settings: Record<string, any>; status: 'queued' | 'generating' | 'ready' | 'failed'
  stats: { images?: number; source_images?: number; splits?: Record<string, number>; classes?: Record<string, number>; class_names?: string[] }
  created: number; job: Job | null; exports: Record<string, Job & { url: string | null }>
}
export interface ModelEvalDetection {
  file: string; width: number; height: number
  gt: { cls: string; bbox: number[] }[]
  pred: { cls: string; conf: number; bbox: number[] }[]
}
export interface ModelEval {
  split: 'test' | 'valid'
  note: string
  /** COCOeval iouType: segmentation projects score masks, detection projects score boxes. */
  iou?: 'bbox' | 'segm'
  coco: {
    AP: number; AP50: number; AP75: number; APs: number; APm: number; APl: number
    AR1: number; AR10: number; AR100: number; ARs: number; ARm: number; ARl: number
  }
  per_class: { class: string; AP: number; AP50: number }[]
  f1_best: { conf: number; f1: number }
  /** images[gtRow][predCol] = file names; the last label is "background". */
  confusion: { labels: string[]; matrix: number[][]; images: string[][][] }
  pr_curve: { recall: number; precision: number }[]
  /** Delta-AP50 (can be negative) recoverable per TIDE error type; absent on evals run before this was tracked. */
  tide?: { cls: number; loc: number; both: number; dupe: number; bkg: number; missed: number }
  worst: string[]
  latency_ms: number
  /** Number of images in the evaluated split (detections may be capped below it). */
  split_images?: number
  detections?: ModelEvalDetection[]
}
export interface ModelItem {
  id: string; name: string; arch: string; task: 'detect' | 'segment' | 'classify'; status: 'queued' | 'training' | 'ready' | 'failed'
  metrics: {
    map50?: number; map5095?: number; precision?: number; recall?: number; accuracy_top1?: number; accuracy_top5?: number
    eval?: ModelEval
    /** Evaluation crashed after training: the weights are still usable, the metrics are not. */
    eval_error?: string
  }
  history: Record<string, number>[]; classes: string[]; versionId: string; version?: number; jobId: string | null
  created: number; weightsUrl: string | null; job?: Job | null; project?: string; project_name?: string
  family?: string; variant?: string; license?: string
  /** Exported runtime artifacts: the .pt checkpoint and, once built, the TensorRT engine. */
  runtimeRefs?: { pt?: string; engine?: string }
  /** Detail endpoint only: eval file name -> signed "/api/files/…" path. */
  evalImages?: Record<string, string>
}
export interface LeaderboardRow {
  id: string; name: string; variant: string; task: ModelItem['task']; status: ModelItem['status']
  version: number | null; versionId: string; ap: number | null; latency_ms: number | null
  comparable: boolean; created: number
}
export interface TrainVariant { id: string; label: string; weights: string }
export interface TrainFamily { family: string; label: string; adapter?: string; license: string; available: boolean; reason: string; variants: TrainVariant[] }
export interface TrainOptions { supported: boolean; reason?: string; task?: string; families?: TrainFamily[] }
export interface Member { id: string; name: string; email: string; role: Role; owner: boolean; joined: number }

export type LabelIssueKind = 'tiny' | 'out_of_bounds' | 'zero_area' | 'duplicate'

/** Row data for the Health check cards. Pixel thresholds are COCO at `imgsz`. */
export interface HealthChecks {
  imgsz: number
  size_buckets: { small: number; medium: number; large: number }
  label_quality: { kind: LabelIssueKind; image_id: string; annotation_id: string }[]
  /** `box` is normalized [x, y, w, h]. */
  missing_boxes: { image_id: string; box: [number, number, number, number]; class: string }[]
  leakage_pairs: number
}

export interface HealthRecommendation { key: string; message: string; suggest: Record<string, unknown> }

export interface Analytics {
  images: number; annotations: number; null_images: number; avg_annotations: number; avg_width: number; avg_height: number
  median_size: string; classes: LabelClass[]; imbalance_ratio: number
  annotations_per_image: { n: number | string; images: number }[]; sizes: { bucket: string; images: number }[]
  aspect: { bucket: string; images: number }[]; splits: Record<string, number>; statuses: Record<string, number>; heatmap: number[][]
  /** Always present: size/label/leakage are computed with the analytics scan; missing boxes arrive via the job. */
  checks: HealthChecks
  recommendations: HealthRecommendation[]
  /** Latest kind="health" job, so the page can show progress and failures. */
  health_job: Job | null
  /** The dataset changed after `health_job` ran; results are out of date. */
  health_stale: boolean
}

export interface Prediction { x: number; y: number; width: number; height: number; confidence: number; class: string; class_id: number; points?: { x: number; y: number }[] }

export interface RegistryItem {
  ref: string; family: string; variant: string; name: string; capabilities: string[]; license: string
  available: boolean; reason: string; kind: 'zoo' | 'vlm' | 'trained'
}
export interface AutoLabelInput {
  model_ref?: string
  prompt?: string | null
  vlm_verify?: boolean
  batch_id?: string | null
  image_ids?: string[]
  class_ids?: string[]
  confidence?: number
  only_unannotated?: boolean
  send_to_review?: boolean
}
export interface AutoLabelPreview {
  images: { id: string; url: string; annotations: Annotation[] }[]
  counts: Record<string, number>
}

export interface PlaygroundPrediction {
  model: string; time: number; image: { width: number; height: number }
  predictions: Prediction[]; text?: string; top?: string
}
export interface PlaygroundResult {
  ref: string; prediction: PlaygroundPrediction | null; latency_ms: number; error: string | null
}

// --- Insights Studio (Task 20a) ---------------------------------------------
// Shapes mirror the read-only /insights/* endpoints; every field stays snake_case on the wire.

export interface InsightSummary {
  project: { id: string; name: string; type: ProjectType }
  version: null | {
    id: string; number: number; name: string; status: string; version_hash: string | null
    splits: Record<string, number>; classes: Record<string, number>; leakage_moved: number | null; created: number
  }
  images: number; annotations: number; null_images: number
  splits: Record<Split, number>
  classes: { id: string; name: string; color: string; count: number; images: number }[]
  sources: { source: string; annotations: number; share: number }[]
}

export interface InsightDistribution {
  split_classes: { class: string; train: number; valid: number; test: number }[]
  instances_vs_images: { class: string; instances: number; images: number }[]
  cooccurrence: { classes: string[]; matrix: number[][] }
  annotations_per_image: { bucket: string; images: number }[]
}

export interface InsightGeometry {
  imgsz: number
  box_scatter: { w: number; h: number; class: string; split: string; area: number }[]
  area_buckets: { small: number; medium: number; large: number }
  aspect: { bucket: string; count: number }[]
  centres: { class: string; cells: number[] }[]
  /** Number of boxes in the scatter, or true when the server capped it. */
  sampled: number | boolean
}

export interface InsightImageStats {
  imgsz: number
  resolution: { w: number; h: number }[]
  brightness: { bin: number | string; count: number }[]
  blur: { bin: number | string; count: number }[]
  scanned: number
  job: Job | null
  stale: boolean
}

export interface InsightLeakImage {
  image_id: string; name: string; split: Split; thumb: string | null; width: number; height: number
}

export interface InsightLeakage {
  pairs: { a: InsightLeakImage; b: InsightLeakImage; distance: number }[]
  split_pairs: { a: string; b: string; count: number }[]
  total_pairs: number
  /** Null when no version exists or the build did not record a move count. */
  leakage_moved: number | null
  job: Job | null
  stale: boolean
}

export interface InsightEmbeddingPoint {
  image_id: string; name: string; x: number; y: number
  split: Split; class: string | null; source: string; error: boolean | string | null; thumb: string | null
}

export interface InsightEmbedding {
  points: InsightEmbeddingPoint[]
  projection: 'umap' | 'pca'
  job: Job | null
  stale: boolean
}

export interface InsightVersionMeta {
  id: string; number: number; name: string; status: string
  version_hash?: string | null; created?: number
  splits?: Record<string, number>; classes?: Record<string, number>; leakage_moved?: number | null
}

export interface InsightVersionDiff {
  base: InsightVersionMeta
  target: InsightVersionMeta
  added: { image_id: string; name: string; split: Split; thumb: string | null }[]
  removed: { image_id: string; name: string; split: Split; thumb: string | null }[]
  class_delta: { class: string; base: number; target: number; delta: number }[]
  split_moves: { image_id: string; name: string; from: Split; to: Split }[]
  summary: { added: number; removed: number; moved: number }
}

export interface InsightLabeling {
  throughput: { date: string; labeler_id: string | null; labeler: string; annotations: number; images: number }[]
  review: { date: string; approved: number; rejected: number; rate: number }[]
  ai: {
    human: number; ai: number; accepted_ai: number; acceptance_rate: number
    by_source: { source: string; count: number }[]
  }
}
