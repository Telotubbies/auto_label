import type { OtDelivery, OtOutput, OtOutputInput } from '../types'
import { del, get, P, patch, post } from './client'

/** Plant outputs for the rule-fired reject signal (Task 40). */
export const otApi = {
  otOutputs: (ws: string, p: string) => get<OtOutput[]>(`${P(ws, p)}/ot-outputs`),
  createOtOutput: (ws: string, p: string, body: OtOutputInput) => post<OtOutput>(`${P(ws, p)}/ot-outputs`, body),
  updateOtOutput: (ws: string, p: string, id: string, body: Partial<OtOutputInput>) =>
    patch<OtOutput>(`${P(ws, p)}/ot-outputs/${id}`, body),
  deleteOtOutput: (ws: string, p: string, id: string) => del<{ ok: boolean }>(`${P(ws, p)}/ot-outputs/${id}`),
  testOtOutput: (ws: string, p: string, id: string) => post<OtDelivery>(`${P(ws, p)}/ot-outputs/${id}/test`, {}),
  otDeliveries: (ws: string, p: string, id: string, limit = 50) =>
    get<OtDelivery[]>(`${P(ws, p)}/ot-outputs/${id}/deliveries?limit=${limit}`),
}
