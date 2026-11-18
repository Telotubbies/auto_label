import { P, post } from './client'

/** What a publish or unpublish answers: the switch, the licence, and the derived visitor address. */
export interface PublishingResult {
  visibility: 'public' | 'private'
  license: string
  publicPath: string | null
}

/** Publishing a project (T-033): a licence and an explicit content check, or nothing public. */
export const publishingApi = {
  publish: (ws: string, project: string, body: { license: string; pii_ack: boolean }) =>
    post<PublishingResult>(`${P(ws, project)}/publish`, body),
  unpublish: (ws: string, project: string) => post<PublishingResult>(`${P(ws, project)}/unpublish`, {}),
}
