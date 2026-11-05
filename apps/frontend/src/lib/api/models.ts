import type {
  Analytics, AnomalyResult, AnomalyStation, CompareInsights, DeploymentAlias, DeploymentOverview, EdgePreset, Job,
  LeaderboardRow, ModelDetections, ModelInsights, ModelItem, PlaygroundResult, PlaygroundRuntime,
  PlaygroundSample, TrainingInsights, VideoFrame, VideoItem,
} from '../types'
import { get, P, patch, post, put } from './client'

/** Model lifecycle: training, the model registry, insights, video authoring, playground and deploy. */
export const modelApi = {
  models: (ws: string, p: string) => get<ModelItem[]>(`${P(ws, p)}/models`),
  model: (ws: string, p: string, id: string) => get<ModelItem>(`${P(ws, p)}/models/${id}`),
  /** What this backend can build for edge devices; 404 while the flag is off. */
  edgePresets: (ws: string, p: string) => get<EdgePreset[]>(`${P(ws, p)}/models/edge-presets`),
  leaderboard: (ws: string, p: string) => get<LeaderboardRow[]>(`${P(ws, p)}/leaderboard`),
  jobs: (ws: string, p: string, kind = '') => get<Job[]>(`${P(ws, p)}/jobs${kind ? `?kind=${kind}` : ''}`),
  analytics: (ws: string, p: string) => get<Analytics>(`${P(ws, p)}/analytics`),
  insightsTraining: (ws: string, p: string, runs?: string[]) =>
    get<TrainingInsights>(`${P(ws, p)}/insights/training${runs?.length ? `?runs=${encodeURIComponent(runs.join(','))}` : ''}`),
  insightsModel: (ws: string, p: string, id: string) => get<ModelInsights>(`${P(ws, p)}/insights/models/${id}`),
  insightsDetections: (ws: string, p: string, id: string, files: string[]) =>
    get<ModelDetections>(`${P(ws, p)}/insights/models/${id}/detections?files=${encodeURIComponent(files.join(','))}`),
  insightsCompare: (ws: string, p: string, models: string[]) =>
    get<CompareInsights>(`${P(ws, p)}/insights/compare?models=${encodeURIComponent(models.join(','))}`),
  videos: (ws: string, p: string) => get<VideoItem[]>(`${P(ws, p)}/videos`),
  video: (ws: string, p: string, id: string) => get<VideoItem>(`${P(ws, p)}/videos/${id}`),
  videoTimeline: (ws: string, p: string, id: string, from = 0, limit = 120) =>
    get<{ video: VideoItem; total: number; frames: VideoFrame[] }>(`${P(ws, p)}/videos/${id}/timeline?from=${from}&limit=${limit}`),
  interpolate: (ws: string, p: string, id: string, fromImageId: string, toImageId: string) =>
    post<{ frames: number; annotations: number }>(`${P(ws, p)}/videos/${id}/interpolate`,
      { from_image_id: fromImageId, to_image_id: toImageId }),
  trackForward: (imageId: string, body: { annotation_id: string; frames: number }) =>
    post<Job>(`/images/${imageId}/track-forward`, body),
  playgroundPredict: (ws: string, form: FormData) => post<{ results: PlaygroundResult[] }>(`/ws/${ws}/playground/predict`, form),
  playgroundPreflight: (ws: string, refs: string[]) =>
    post<{ models: PlaygroundRuntime[] }>(`/ws/${ws}/playground/preflight`, { model_refs: refs }),
  playgroundSamples: (ws: string, limit = 6) => get<{ samples: PlaygroundSample[] }>(`/ws/${ws}/playground/samples?limit=${limit}`),
  deployments: (ws: string) => get<DeploymentOverview>(`/ws/${ws}/deployments`),
  setDeployment: (ws: string, p: string, alias: string, model_id: string) =>
    put<DeploymentAlias>(`${P(ws, p)}/deployments/${encodeURIComponent(alias)}`, { model_id }),
  rollbackDeployment: (ws: string, p: string, alias: string) =>
    post<DeploymentAlias>(`${P(ws, p)}/deployments/${encodeURIComponent(alias)}/rollback`, {}),
  sendDriftToLabeling: (ws: string, p: string, runId: string) =>
    post<{ sent: number }>(`${P(ws, p)}/drift/${encodeURIComponent(runId)}/send-to-labeling`, {}),

  // --- good-only anomaly detection ---
  anomalyStations: (ws: string, p: string) => get<AnomalyStation[]>(`${P(ws, p)}/anomaly/stations`),
  createAnomalyStation: (ws: string, p: string, body: { name: string; threshold?: number }) =>
    post<AnomalyStation>(`${P(ws, p)}/anomaly/stations`, body),
  updateAnomalyStation: (ws: string, p: string, id: string, body: { name?: string; threshold?: number }) =>
    patch<AnomalyStation>(`${P(ws, p)}/anomaly/stations/${id}`, body),
  trainAnomalyStation: (ws: string, p: string, id: string) =>
    post<{ station: AnomalyStation; job: Job }>(`${P(ws, p)}/anomaly/stations/${id}/train`, {}),
  predictAnomaly: (ws: string, p: string, id: string, body: { image_id: string; compare_vlm?: boolean }) =>
    post<AnomalyResult>(`${P(ws, p)}/anomaly/stations/${id}/predict`, body),
}
