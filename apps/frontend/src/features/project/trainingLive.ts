/** What the Models page can show while a model trains. Pure, so a node test covers the maths.
 *  The worker posts one history row per epoch; ultralytics names its columns `metrics/mAP50(M)`,
 *  `train/box_loss` and `val/seg_loss`, so the page reads columns by shape rather than by one fixed name. */
export type HistoryRow = Record<string, number>

export interface LiveScores {
  epoch: number
  map50?: number
  map5095?: number
  precision?: number
  recall?: number
  top1?: number
  top5?: number
}

export function liveScores(task: 'detect' | 'segment' | 'classify', history: HistoryRow[]): LiveScores | null {
  const last = history[history.length - 1]
  if (!last) return null
  if (task === 'classify') return { epoch: last.epoch, top1: last['metrics/accuracy_top1'], top5: last['metrics/accuracy_top5'] }
  const k = task === 'segment' ? '(M)' : '(B)'
  const pick = (name: string, other: string) => last[`metrics/${name}${k}`] ?? last[other]
  return {
    epoch: last.epoch,
    map50: pick('mAP50', 'val/map50'),
    map5095: pick('mAP50-95', 'val/map5095'),
    precision: pick('precision', 'val/precision'),
    recall: pick('recall', 'val/recall'),
  }
}

export interface LossKey { key: string; label: string }

const LOSS = /(^|[/_])loss$/

/** Every loss column in the history, train before val, named for a legend ("val seg"). */
export function lossSeries(history: HistoryRow[]): { keys: LossKey[] } {
  const seen = new Set<string>()
  for (const row of history) for (const key of Object.keys(row)) if (LOSS.test(key)) seen.add(key)
  const keys = [...seen]
    .sort((a, b) => Number(a.startsWith('val')) - Number(b.startsWith('val')) || a.localeCompare(b))
    .map((key) => ({ key, label: key.replace(/_?loss$/, '').replace('/', ' ').replace(/\s+$/, '') || key }))
  return { keys }
}

/** Seconds left: the average epoch so far times the epochs still to run. Null until one epoch is done. */
export function trainingEta({ started, now, done, total }: { started: number | null; now: number; done: number; total: number }): number | null {
  if (started == null || done <= 0 || total <= done) return null
  return Math.round(((now - started) / done) * (total - done))
}
