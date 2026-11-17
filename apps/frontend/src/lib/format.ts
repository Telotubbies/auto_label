// One rounding rule per kind of number. Pure display helpers: no React, no locale state, no imports.
// Two percentage shapes are deliberate and must not be unified: a rate keeps one decimal, because
// 50.0% and 50.4% are different, while a share of a whole is a whole percent, because a legend with
// one decimal is noise. A duration names its unit in the function name.

const DASH = '—'

/** A count, rounded to a whole number with separators; a non-finite count is unknown. */
export const fmtInt = (n: number) => (Number.isFinite(n) ? Math.round(n).toLocaleString() : DASH)

/** Bytes as B / KB / MB, the rule the streams screens already shipped. */
export const fmtBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 ** 2 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 ** 2).toFixed(1)} MB`

/** A rate in 0…1 at one decimal; a missing rate is unknown. */
export const pct1 = (v?: number | null) => (v == null ? DASH : `${(v * 100).toFixed(1)}%`)

/** A share of a whole as a whole percent; a zero whole is unknown. */
export const pctOf = (part: number, whole: number) => (whole > 0 ? `${Math.round((part / whole) * 100)}%` : DASH)

/** A duration in seconds as minutes:seconds. */
export const fmtClock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

/** A duration in milliseconds as minutes:seconds. */
export const fmtMillis = (ms: number) => fmtClock(ms / 1000)
