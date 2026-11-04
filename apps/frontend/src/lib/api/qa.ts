import type {
  Annotation, ConsensusJob, ConsensusJobDetail, ConsensusSubmitResult, HoneypotItem, HoneypotList, LabelingDashboard,
  MyTask, ReviewQueueItem,
} from '../types'
import { del, get, P, post } from './client'

/** Labeling QA and workforce (Task 23): dashboard, queues, consensus and honeypots. */
export const qaApi = {
  labelingDashboard: (ws: string, p: string, days = 30) => get<LabelingDashboard>(`${P(ws, p)}/labeling/dashboard?days=${days}`),
  labelingTasks: (ws: string, p: string) => get<{ tasks: MyTask[] }>(`${P(ws, p)}/labeling/my-tasks`),
  labelingReviewQueue: (ws: string, p: string, limit = 50) =>
    get<{ items: ReviewQueueItem[] }>(`${P(ws, p)}/labeling/review-queue?limit=${limit}`),
  labelingJobs: (ws: string, p: string) => get<{ jobs: ConsensusJob[] }>(`${P(ws, p)}/labeling/consensus`),
  labelingJob: (ws: string, p: string, id: string) => get<ConsensusJobDetail>(`${P(ws, p)}/labeling/consensus/${id}`),
  createConsensus: (ws: string, p: string, body: { image_ids?: string[]; count?: number; k?: number; iou_threshold?: number }) =>
    post<ConsensusJob>(`${P(ws, p)}/labeling/consensus`, body),
  mergeConsensus: (ws: string, p: string, id: string) =>
    post<{ merged: number; skipped: number; status: 'merged' }>(`${P(ws, p)}/labeling/consensus/${id}/merge`, {}),
  // Autosave only writes the caller's private draft; this is the only call that submits it.
  submitConsensus: (ws: string, p: string, jobId: string, imageId: string, annotations?: Annotation[]) =>
    post<ConsensusSubmitResult>(`${P(ws, p)}/labeling/consensus/${jobId}/images/${imageId}/submit`, { annotations }),
  honeypots: (ws: string, p: string) => get<HoneypotList>(`${P(ws, p)}/labeling/honeypots`),
  createHoneypot: (ws: string, p: string, body: { image_id: string; annotations?: Annotation[] }) =>
    post<HoneypotItem>(`${P(ws, p)}/labeling/honeypots`, body),
  deleteHoneypot: (ws: string, p: string, id: string) => del<{ ok: true }>(`${P(ws, p)}/labeling/honeypots/${id}`),
}
