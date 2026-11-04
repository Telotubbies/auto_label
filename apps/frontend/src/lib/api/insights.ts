import type {
  DashboardSummary, InsightDistribution, InsightEmbedding, InsightGeometry, InsightImageStats, InsightLabeling,
  InsightLeakage, InsightSelection, InsightSelectionRef, InsightSummary, InsightVersionDiff, Job, Lineage,
  StreamAnalytics, WidgetData,
} from '../types'
import { del, get, P, patch, post } from './client'

/** Project insights studio: dataset health, quality, embeddings and version diffs. */
export const insightsApi = {
  summary: (ws: string, p: string, version?: string) =>
    get<InsightSummary>(`${P(ws, p)}/insights/summary${version ? `?version=${encodeURIComponent(version)}` : ''}`),
  distribution: (ws: string, p: string, version?: string) =>
    get<InsightDistribution>(`${P(ws, p)}/insights/distribution${version ? `?version=${encodeURIComponent(version)}` : ''}`),
  geometry: (ws: string, p: string, version?: string) =>
    get<InsightGeometry>(`${P(ws, p)}/insights/geometry${version ? `?version=${encodeURIComponent(version)}` : ''}`),
  imageStats: (ws: string, p: string) => get<InsightImageStats>(`${P(ws, p)}/insights/image-stats`),
  scanImageStats: (ws: string, p: string) => post<Job>(`${P(ws, p)}/insights/image-stats/scan`, {}),
  leakage: (ws: string, p: string, version?: string) =>
    get<InsightLeakage>(`${P(ws, p)}/insights/leakage${version ? `?version=${encodeURIComponent(version)}` : ''}`),
  scanLeakage: (ws: string, p: string, version?: string) =>
    post<Job>(`${P(ws, p)}/insights/leakage/scan${version ? `?version=${encodeURIComponent(version)}` : ''}`, {}),
  embedding: (ws: string, p: string) => get<InsightEmbedding>(`${P(ws, p)}/insights/embedding`),
  scanEmbedding: (ws: string, p: string) => post<Job>(`${P(ws, p)}/insights/embedding/scan`, {}),
  versionDiff: (ws: string, p: string, base: string, target: string) =>
    get<InsightVersionDiff>(`${P(ws, p)}/insights/version-diff?base=${encodeURIComponent(base)}&target=${encodeURIComponent(target)}`),
  labeling: (ws: string, p: string) => get<InsightLabeling>(`${P(ws, p)}/insights/labeling`),
  /** Persist the lasso's image ids server-side and hand back a short-lived token for the URL. */
  saveSelection: (ws: string, p: string, imageIds: string[]) =>
    post<InsightSelectionRef>(`${P(ws, p)}/insights/selections`, { image_ids: imageIds }),
  selection: (ws: string, p: string, token: string) =>
    get<InsightSelection>(`${P(ws, p)}/insights/selections/${encodeURIComponent(token)}`),
}

/** Insights Studio (Task 20c): lineage, stream analytics, dashboard builder. */
export const studioApi = {
  lineage: (ws: string, p: string) => get<Lineage>(`${P(ws, p)}/insights/lineage`),
  streamAnalytics: (ws: string, p: string, days = 30, tzOffset = 0) =>
    get<StreamAnalytics>(`${P(ws, p)}/insights/streams?days=${days}&tz_offset=${tzOffset}`),
  widgetQuery: (ws: string, p: string,
    body: { source: string; measure: string; dimension: string; dimension2?: string | null; filters?: Record<string, string | number | undefined> }) =>
    post<WidgetData>(`${P(ws, p)}/insights/query`, body),
  sharedWidgetQuery: (ws: string, p: string, token: string,
    body: { source: string; measure: string; dimension: string; dimension2?: string | null; filters?: Record<string, string | number | undefined> }) =>
    post<WidgetData>(`${P(ws, p)}/dashboards/shared/${encodeURIComponent(token)}/query`, body),
  dashboards: (ws: string, p: string) => get<DashboardSummary[]>(`${P(ws, p)}/dashboards`),
  dashboard: (ws: string, p: string, id: string) => get<DashboardSummary>(`${P(ws, p)}/dashboards/${id}`),
  createDashboard: (ws: string, p: string, body: { name: string; widgets: unknown[] }) =>
    post<DashboardSummary>(`${P(ws, p)}/dashboards`, body),
  updateDashboard: (ws: string, p: string, id: string, body: { name?: string; widgets?: unknown[] }) =>
    patch<DashboardSummary>(`${P(ws, p)}/dashboards/${id}`, body),
  deleteDashboard: (ws: string, p: string, id: string) => del<{ ok: boolean }>(`${P(ws, p)}/dashboards/${id}`),
  shareDashboard: (ws: string, p: string, id: string) =>
    post<{ token: string; path: string }>(`${P(ws, p)}/dashboards/${id}/share`, {}),
  sharedDashboard: (ws: string, p: string, token: string) =>
    get<DashboardSummary>(`${P(ws, p)}/dashboards/shared/${encodeURIComponent(token)}`),
}
