import type { InferenceHost } from '../types'
import { get } from './client'

/** Inference hub (T-1001): the hosts this deployment can install engines on. Later hub cards append. */
export const inferenceApi = {
  hosts: (ws: string) => get<{ hosts: InferenceHost[] }>(`/ws/${ws}/inference/hosts`),
}
