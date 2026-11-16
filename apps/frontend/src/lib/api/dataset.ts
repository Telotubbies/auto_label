import type {
  Annotation, AutoLabelInput, AutoLabelPreview, Batch, Board, ImageItem, Job, LabelClass, OcrTemplate,
  SuspectQueue, SuspectStats, SuspectVerdict, Version,
} from '../types'
import { get, P, post, put } from './client'

/** Dataset surface: ontology, batches, image grid and the board the editor reads. */
export const datasetApi = {
  classes: (ws: string, p: string) => get<LabelClass[]>(`${P(ws, p)}/classes`),
  tags: (ws: string, p: string) => get<{ name: string; count: number }[]>(`${P(ws, p)}/tags`),
  batches: (ws: string, p: string) => get<Batch[]>(`${P(ws, p)}/batches`),
  images: (ws: string, p: string, q: Record<string, string | number> = {}) =>
    // `selection` is a saved lasso token; the ids themselves never go in the URL.
    get<{ total: number; items: ImageItem[] }>(`${P(ws, p)}/images?${new URLSearchParams(q as Record<string, string>)}`),
  image: (id: string) => get<ImageItem & { annotations: Annotation[] }>(`/images/${id}`),
  board: (ws: string, p: string) => get<Board>(`${P(ws, p)}/board`),
  versions: (ws: string, p: string) => get<Version[]>(`${P(ws, p)}/versions`),
  formats: (ws: string, p: string) => get<{ id: string; label: string }[]>(`${P(ws, p)}/versions/formats`),
  healthCheck: (ws: string, p: string, imgsz?: number) => post<Job>(`${P(ws, p)}/health`, imgsz ? { imgsz } : {}),
  suspects: (ws: string, p: string, limit = 50) => get<SuspectQueue>(`${P(ws, p)}/suspect-labels?limit=${limit}`),
  suspectFeedback: (ws: string, p: string, annotationId: string, verdict: SuspectVerdict) =>
    post<{ stats: SuspectStats }>(`${P(ws, p)}/suspect-labels/${encodeURIComponent(annotationId)}/feedback`, { verdict }),
  autolabelPreview: (ws: string, p: string, body: AutoLabelInput & { sample?: number }) =>
    post<AutoLabelPreview>(`${P(ws, p)}/autolabel/preview`, body),
  ocrTemplates: (ws: string, p: string) =>
    get<{ templates: OcrTemplate[]; current: string | null }>(`${P(ws, p)}/ocr/templates`),
  ocrTemplate: (ws: string, p: string, template: string) =>
    put<{ current: string }>(`${P(ws, p)}/ocr/template`, { template }),
  ocrExport: (ws: string, p: string, body: { format: 'markdown' | 'json' | 'paddleocr'; mask_pii: boolean }) =>
    post<{ format: string; images: number; annotations: number; url: string }>(`${P(ws, p)}/ocr/export`, body),
}
