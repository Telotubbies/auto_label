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
