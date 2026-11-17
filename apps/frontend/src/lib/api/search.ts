import type {
  CollectionPage, CollectionSummary, EventSearchFrame, EventSearchResult, Job, SearchResponse,
} from '../types'
import { del, get, patch, post, P, qs } from './client'

/** Task 27/38: semantic search, saved collections and natural-language event search. */
export const searchApi = {
  search: (ws: string, p: string, q: Record<string, string | number> = {}) =>
    get<SearchResponse>(`${P(ws, p)}/search${qs(q)}`),
  collections: (ws: string, p: string) => get<{ collections: CollectionSummary[] }>(`${P(ws, p)}/collections`),
  collection: (ws: string, p: string, id: string, limit = 24, offset = 0) =>
    get<CollectionPage>(`${P(ws, p)}/collections/${id}${qs({ limit, offset })}`),
  createCollection: (ws: string, p: string, body: { name: string; image_ids?: string[]; query?: string }) =>
    post<CollectionSummary>(`${P(ws, p)}/collections`, body),
  renameCollection: (ws: string, p: string, id: string, name: string) =>
    patch<CollectionSummary>(`${P(ws, p)}/collections/${id}`, { name }),
  deleteCollection: (ws: string, p: string, id: string) => del<{ ok: true }>(`${P(ws, p)}/collections/${id}`),
  removeCollectionItems: (ws: string, p: string, id: string, image_ids: string[]) =>
    del<CollectionSummary>(`${P(ws, p)}/collections/${id}/items`, { image_ids }),

  job: (ws: string, p: string, id: string) => get<Job>(`${P(ws, p)}/jobs/${id}`),
  eventSearch: (ws: string, p: string, body: {
    query: string; from_ts?: number; to_ts?: number; limit?: number; sample?: number
  }) => post<Job>(`${P(ws, p)}/event-search`, body),
  confirmEventSearch: (ws: string, p: string, frameId: string, confirmed: boolean) =>
    post<EventSearchFrame>(`${P(ws, p)}/event-search/frames/${frameId}/confirm`, { confirmed }),
}
