// Anonymous public dataset surface (T-035). No token is required; the API answers 404 for
// every unpublished, private or flag-off project, so the page cannot tell them apart.
import { get } from './client'

export type PublicDataset = {
  name: string
  description: string
  type: string
  workspace: string
  license: string
  images: number
  classes: { name: string; count: number }[]
  citation: string
  samples: { id: string; width: number; height: number; url: string }[]
}

export const publicApi = {
  dataset: (ws: string, project: string) =>
    get<PublicDataset>(`/public/datasets/${encodeURIComponent(ws)}/${encodeURIComponent(project)}`),
}
