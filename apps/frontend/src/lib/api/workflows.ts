import type { Workflow, WorkflowBlock, WorkflowRunResult, WorkflowVersion } from '../types'
import { get, P, post, put } from './client'

/** No-code workflow builder: versioned block chains run on one project image. */
export const workflowApi = {
  workflows: (ws: string, p: string) => get<Workflow[]>(`${P(ws, p)}/workflows`),
  workflow: (ws: string, p: string, id: string) => get<Workflow>(`${P(ws, p)}/workflows/${id}`),
  createWorkflow: (ws: string, p: string, body: { name: string; blocks: WorkflowBlock[] }) =>
    post<Workflow>(`${P(ws, p)}/workflows`, body),
  updateWorkflow: (ws: string, p: string, id: string, body: { name?: string; blocks?: WorkflowBlock[] }) =>
    put<Workflow>(`${P(ws, p)}/workflows/${id}`, body),
  workflowVersions: (ws: string, p: string, id: string) =>
    get<WorkflowVersion[]>(`${P(ws, p)}/workflows/${id}/versions`),
  restoreWorkflow: (ws: string, p: string, id: string, version: number) =>
    post<Workflow>(`${P(ws, p)}/workflows/${id}/restore`, { version }),
  runWorkflow: (ws: string, p: string, id: string, imageId: string) =>
    post<WorkflowRunResult>(`${P(ws, p)}/workflows/${id}/run`, { image_id: imageId }),
}
