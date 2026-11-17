import type { InferenceCatalog } from '../types'
import { get } from './client'

/** Engine pins and GPU presets for the Inference hub (T-1002). */
export const inferenceCatalog = (ws: string) => get<InferenceCatalog>(`/ws/${ws}/inference/catalog`)
