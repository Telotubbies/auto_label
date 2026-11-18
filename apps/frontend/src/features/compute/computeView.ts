/** The Compute page's pure parts: the andon look of a state, time left, memory share, a job's one line. */
export type ComputeStateName = 'training' | 'working' | 'idle' | 'offline'

/** One word, one tone and one shape per state: the colour only repeats what the word and the shape say. */
export const STATE_VIEW: Record<ComputeStateName, { word: string; tone: 'primary' | 'success' | 'destructive' | 'warning'; shape: 'pulse' | 'ring' | 'bar' | 'cross' }> = {
  training: { word: 'Training', tone: 'primary', shape: 'pulse' },
  working: { word: 'Working', tone: 'warning', shape: 'pulse' },
  idle: { word: 'Idle', tone: 'success', shape: 'ring' },
  offline: { word: 'Offline', tone: 'destructive', shape: 'cross' },
}

export const fmtLeft = (s: number | null | undefined): string => {
  if (s == null) return '—'
  if (s < 60) return `${s} s`
  const min = Math.round(s / 60)
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60} min` : ''}`
}

export const vramShare = (used: number, budget: number): number => (budget > 0 ? Math.min(100, Math.round((used / budget) * 100)) : 0)

const KIND: Record<string, string> = { train: 'Training', autolabel: 'Auto-label', batch_infer: 'Batch inference', anomaly_train: 'Anomaly training', insights_embedding: 'Embeddings', export_engine: 'Engine build' }
export const kindLabel = (kind: string) => KIND[kind] ?? kind

export interface JobLike { kind: string; name: string; project: string; progress: number; epochs: number | null; status: string }

export function jobLine(j: JobLike): string {
  if (j.kind === 'train') {
    const who = j.name || 'Model'
    if (j.status === 'queued') return `${who} · waiting for a worker`
    return j.epochs ? `${who} · epoch ${Math.round((j.progress / 100) * j.epochs)} of ${j.epochs}` : who
  }
  return j.project ? `${kindLabel(j.kind)} · ${j.project}` : kindLabel(j.kind)
}

/** GET /api/ws/{ws}/compute */
export interface ComputeData {
  state: ComputeStateName
  label: string
  workers: { online: number; total: number; busy: number }
  gpus: { name: string; vram_mb?: number }[]
  api_gpu: { holder: string | null; used_mb: number; budget_mb: number; models: { key: string; vram_mb: number }[] }
  queue: { running: number; queued: number; oldest_wait_s: number | null }
  jobs: (JobLike & { id: string; eta_s: number | null; started: number | null; created: number })[]
}
