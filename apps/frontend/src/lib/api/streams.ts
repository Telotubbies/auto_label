import type {
  StreamCreateBody, StreamEventItem, StreamEventPage, StreamItem, StreamPatchBody, StreamVideoUpload,
} from '../types'
import { del, get, P, patch, post, req } from './client'

/** CCTV streams (Task 10b): cameras, lifecycle and the reviewed event list. */
export const streamsApi = {
  streams: (ws: string, p: string) => get<StreamItem[]>(`${P(ws, p)}/streams`),
  stream: (ws: string, p: string, id: string) => get<StreamItem>(`${P(ws, p)}/streams/${id}`),
  createStream: (ws: string, p: string, body: StreamCreateBody) => post<StreamItem>(`${P(ws, p)}/streams`, body),
  updateStream: (ws: string, p: string, id: string, body: StreamPatchBody) => patch<StreamItem>(`${P(ws, p)}/streams/${id}`, body),
  deleteStream: (ws: string, p: string, id: string) => del<{ ok: boolean }>(`${P(ws, p)}/streams/${id}`),
  startStream: (ws: string, p: string, id: string) => post<StreamItem>(`${P(ws, p)}/streams/${id}/start`, {}),
  stopStream: (ws: string, p: string, id: string) => post<StreamItem>(`${P(ws, p)}/streams/${id}/stop`, {}),
  /** Multipart upload: req() leaves Content-Type to the browser, like Playground's predict. */
  uploadStreamVideo: (ws: string, p: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return req<StreamVideoUpload>(`${P(ws, p)}/streams/upload-video`, { method: 'POST', body: form })
  },
  /** Server-side filters: `rule` is the rule index, `class` a class name, `reviewed` yes|no. */
  streamEvents: (ws: string, p: string, id: string, q: { rule?: number; class?: string; reviewed?: 'yes' | 'no'; kind?: string; offset?: number; limit?: number } = {}) => {
    const search = new URLSearchParams()
    for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') search.set(k, String(v))
    const query = search.toString()
    return get<StreamEventPage>(`${P(ws, p)}/streams/${id}/events${query ? `?${query}` : ''}`)
  },
  patchStreamEvent: (ws: string, p: string, id: string, eid: string, reviewed: boolean) =>
    patch<StreamEventItem>(`${P(ws, p)}/streams/${id}/events/${eid}`, { reviewed }),
  eventToDataset: (ws: string, p: string, id: string, eid: string) =>
    post<{ uploaded: number; duplicates: number }>(`${P(ws, p)}/streams/${id}/events/${eid}/to-dataset`, {}),
}
