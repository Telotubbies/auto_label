// T-1007: the Engines tab's rules, kept out of React so they can be tested without a browser.
// No imports on purpose: the node tests load this file directly, and the shapes are structural.

export type EngineStatus = 'ok' | 'warn' | 'blocked'
export type EngineRowLike = {
  id: string; name: string; version: string; installed: boolean; disk_mb: number; runtimes: string[]
  compatibility: { status: EngineStatus; reasons: string[]; warnings: string[] }
}
export type Selection = { host: string; selected: Set<string>; notice: string | null }
export type Totals = { count: number; diskMb: number }

export const HOST_CHANGED = 'Selection cleared: you changed host.'
export const NO_INSTALL = 'This host has not enabled installs (`LD_ALLOW_ENGINE_INSTALL=1`).'

/** A blocked engine cannot be ticked; a warning one can, with its reason shown beside it. */
export const selectable = (row: EngineRowLike) => row.compatibility.status !== 'blocked'

/** The status cell; only an installed engine offers the row menu's uninstall. */
export function rowStatusCopy(row: { installed: boolean; version: string }) {
  return row.installed
    ? { label: `Installed ${row.version}`, uninstall: true }
    : { label: 'Not installed', uninstall: false }
}

/** Count and bytes of the ticked rows only; the host's free disk is not this function's to spend. */
export function totals(rows: EngineRowLike[], selected: Set<string>): Totals {
  const picked = rows.filter((row) => selected.has(row.id))
  return { count: picked.length, diskMb: picked.reduce((sum, row) => sum + row.disk_mb, 0) }
}

/** One sentence: the totals, or the first reason the action is disabled. */
export function footerCopy(t: Totals, freeGb: number | null, allowInstall: boolean, online = true): string {
  if (t.count === 0) return 'Select an engine first.'
  if (!online) return 'This host is offline.'
  if (!allowInstall) return NO_INSTALL
  const engines = `${t.count} engine${t.count === 1 ? '' : 's'}`
  const free = freeGb === null ? 'free disk unknown' : `${Math.round(freeGb)} GB free`
  return `${engines} · ${(t.diskMb / 1024).toFixed(1)} GB to install · ${free}`
}

/** The plan's argv as the reader sees it: one command per line, never a shell string to send back. */
export const argvText = (step: { argv: string[][] }) => step.argv.map((argv) => argv.join(' ')).join('\n')

/** The confirm body: catalogue ids, versions and runtime enums only. */
export function engineChoices(rows: EngineRowLike[], selected: Set<string>, runtimes: Record<string, string>) {
  return rows.filter((row) => selected.has(row.id))
    .map((row) => ({ id: row.id, version: row.version, runtime: runtimes[row.id] ?? row.runtimes[0] }))
}
export const installRequest = (host: string, rows: EngineRowLike[], selected: Set<string>,
  runtimes: Record<string, string>, planId: string) => ({
  host, engines: engineChoices(rows, selected, runtimes), plan_id: planId, confirm: true,
})

/** Ticking is only ever offered for a selectable row, so this never sees a blocked id. */
export function toggle(sel: Selection, id: string): Selection {
  const selected = new Set(sel.selected)
  if (!selected.delete(id)) selected.add(id)
  return { ...sel, selected, notice: null }
}

/** A different host has a different inventory, so the old ticks cannot carry over. */
export function changeHost(sel: Selection, host: string): Selection {
  if (sel.host === host) return sel
  return { host, selected: new Set(), notice: sel.selected.size ? HOST_CHANGED : null }
}

// ---- T-1009: the engine job, its log and its cancel ------------------------------------------
export type JobStatus = 'queued' | 'running' | 'cancelling' | 'done' | 'failed' | 'cancelled'
export type JobLike = {
  status: JobStatus; progress?: number; phase?: string; log?: string[]; error?: string
  host?: string; action?: 'install' | 'uninstall' | 'pull'
}
export const LOG_CAP = 200                 // the sheet renders the last 200 lines, no more
export const TAIL_LINES = 5                // the card renders the last five

/** A finished, failed or cancelled job: the 2 s poll stops and the engines table refetches. */
export const isTerminal = (job: Pick<JobLike, 'status'>) =>
  job.status === 'done' || job.status === 'failed' || job.status === 'cancelled'

/** `installing vllm` -> `Installing vllm`; a job with no phase yet still names its action. */
export const phaseLabel = (job: Pick<JobLike, 'phase' | 'action'>) => job.phase
  ? job.phase.charAt(0).toUpperCase() + job.phase.slice(1)
  : job.action === 'uninstall' ? 'Removing' : job.action === 'pull' ? 'Pulling' : 'Installing'

/** The card's one sentence per status; a failure carries the safe reason the worker reported. */
export function jobCopy(job: JobLike): string {
  const host = job.host || 'this host'
  const removing = job.action === 'uninstall'
  const pull = job.action === 'pull'
  switch (job.status) {
    case 'queued': return `${removing ? 'Removal' : pull ? 'Pull' : 'Install'} queued on ${host}.`
    case 'running': return `${phaseLabel(job)}.`
    case 'cancelling': return 'Cancelling…'
    case 'cancelled': return 'Cancelled'
    case 'done': return removing ? `Removed from ${host}.`
      : pull ? `Model pulled on ${host}.` : `Installed on ${host}.`
    case 'failed': return `${removing ? 'Uninstall' : pull ? 'Pull' : 'Install'} failed: ${job.error || 'the worker did not report a reason.'}`
  }
}

/** The confirm sentence, asked before anything is stopped; the sheet names the host it will touch. */
export const cancelCopy = (host: string, action: JobLike['action'] = 'install') =>
  action === 'pull'
    ? `Stop this pull on ${host}? The partial model is removed.`
    : `Stop this install on ${host}? The half-built environment is removed.`

/** Newest last, capped at 200: the worker appends, so the tail is what a reader wants. */
export const visibleLog = (job: Pick<JobLike, 'log'>) => (job.log ?? []).slice(-LOG_CAP)
export const tailLines = (job: Pick<JobLike, 'log'>, count = TAIL_LINES) => visibleLog(job).slice(-count)
export const logText = (job: Pick<JobLike, 'log'>) => visibleLog(job).join('\n')

