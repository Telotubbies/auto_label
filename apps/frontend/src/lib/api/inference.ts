import type {
  EngineAvailability, EngineInstallIn, EnginePlan, InferenceCatalog, InferenceEstimate, InferenceEstimateIn,
  InferenceHost, Job,
} from '../types'
import { get, post } from './client'

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
