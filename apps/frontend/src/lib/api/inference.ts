import type {
  EngineAvailability, EngineInstallIn, EnginePlan, InferenceCatalog, InferenceEstimate, InferenceEstimateIn,
  InferenceHost, InferenceJob, InferenceModels, Job, ModelPlan, ModelPlanIn,
} from '../types'
import { del, get, post, qs } from './client'

/** Inference hub (T-1001): the hosts this deployment can install engines on. Later hub cards append. */
export const inferenceApi = {
  hosts: (ws: string) => get<{ hosts: InferenceHost[] }>(`/ws/${ws}/inference/hosts`),
}

/** Engine pins and GPU presets for the Inference hub (T-1002). */
export const inferenceCatalog = (ws: string) => get<InferenceCatalog>(`/ws/${ws}/inference/catalog`)

/** One verdict per engine for one host (T-1003); a blocked row cannot be selected. */
export const inferenceEngines = (ws: string, host: string) =>
  get<{ host: InferenceHost; engines: EngineAvailability[] }>(
    `/ws/${ws}/inference/engines?host=${encodeURIComponent(host)}`)

/** The pure VRAM / throughput answer; T-1005's calculator is the only caller (T-1004). */
export const inferenceEstimate = (ws: string, body: InferenceEstimateIn) =>
  post<InferenceEstimate>(`/ws/${ws}/inference/estimate`, body)

/** The dry run (T-1006): exact argv, bytes and disk after; it changes nothing. */
export const inferencePlanEngines = (ws: string, body: Omit<EngineInstallIn, 'plan_id' | 'confirm'>) =>
  post<EnginePlan>(`/ws/${ws}/inference/engines/plan`, body)

/** Queue one confirmed install for one host; a stale plan or a busy host comes back as a 409. */
export const inferenceInstallEngines = (ws: string, body: EngineInstallIn) =>
  post<{ job: Job }>(`/ws/${ws}/inference/engines/install`, body)

/** Queue the removal of one installed engine; a second confirm is required. */
export const inferenceUninstallEngine = (ws: string, body: { host: string; id: string; confirm: boolean }) =>
  post<{ job: Job }>(`/ws/${ws}/inference/engines/uninstall`, body)

/** The workspace's engine jobs still on the wire, newest first (T-1009). */
export const inferenceJobs = (ws: string) =>
  get<InferenceJob[]>(`/ws/${ws}/inference/jobs?status=active`)

/** One job, re-read once it leaves the active list so the card can say how it ended. */
export const inferenceJob = (ws: string, id: string) =>
  get<InferenceJob>(`/ws/${ws}/inference/jobs/${id}`)

/** Ask the worker to stop; a terminal job is a no-op and a foreign id is 404. */
export const inferenceCancelJob = (ws: string, id: string) =>
  post<InferenceJob>(`/ws/${ws}/inference/jobs/${id}/cancel`, {})
/** The model catalogue joined with one host's installed state, fit verdict and blocks (T-1010). */
export const inferenceModels = (ws: string, host: string) =>
  get<InferenceModels>(`/ws/${ws}/inference/models?host=${encodeURIComponent(host)}`)

/** The download dry run: files, bytes, disk after, the gate and every block reason (T-1010). */
export const inferencePlanModel = (ws: string, body: ModelPlanIn) =>
  post<ModelPlan>(`/ws/${ws}/inference/models/plan`, body)

/** Queue the removal of one installed model (T-1011); a model the host no longer reports is a 404. */
export const inferenceRemoveModel = (ws: string,
  body: { host: string; id: string; variant: string; confirm: boolean }) =>
  del<{ job: Job }>(`/ws/${ws}/inference/models/${encodeURIComponent(body.id)}`
    + qs({ host: body.host, variant: body.variant, confirm: body.confirm }))

/** Queue one confirmed download (T-1012); a busy host or an installed variant comes back as a 409. */
export const inferenceDownloadModel = (ws: string, body: ModelPlanIn) =>
  post<{ job: Job }>(`/ws/${ws}/inference/models/download`, { ...body, confirm: true })
