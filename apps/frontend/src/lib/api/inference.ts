import type { InferenceCatalog, InferenceEstimate, InferenceEstimateIn } from '../types'
import { get, post } from './client'

/** Engine pins and GPU presets for the Inference hub (T-1002). */
export const inferenceCatalog = (ws: string) => get<InferenceCatalog>(`/ws/${ws}/inference/catalog`)

/** The pure VRAM / throughput answer; T-1005's calculator is the only caller (T-1004). */
export const inferenceEstimate = (ws: string, body: InferenceEstimateIn) =>
  post<InferenceEstimate>(`/ws/${ws}/inference/estimate`, body)
