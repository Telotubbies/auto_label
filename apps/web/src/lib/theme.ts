// Material dynamic colour (HCT) -> OKLCH CSS variables, plus the class/heatmap palettes and theme preferences.
import { useSyncExternalStore } from 'react'
import {
  Hct, MaterialDynamicColors as M, SchemeExpressive, SchemeTonalSpot, SchemeVibrant, TonalPalette, argbFromHex,
  type DynamicScheme,
} from '@material/material-color-utilities'

export type Mode = 'light' | 'dark'
export type ModePref = Mode | 'system'
export type Scheme = 'tonal-spot' | 'vibrant' | 'expressive'
export type Contrast = 0 | 0.5 | 1

// ---------- colour maths -----------------------------------------------------
const lin = (c: number) => { const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }

/** ARGB int -> `oklch(L C H)` string (Björn Ottosson's OKLab). */
export function oklch(argb: number): string {
  const r = lin((argb >> 16) & 255), g = lin((argb >> 8) & 255), b = lin(argb & 255)
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s
  const bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s
  const C = Math.hypot(a, bb)
  const h = C < 0.0004 ? 0 : ((Math.atan2(bb, a) * 180) / Math.PI + 360) % 360
  return `oklch(${(L * 100).toFixed(2)}% ${C.toFixed(4)} ${h.toFixed(1)})`
}

const SCHEMES = { 'tonal-spot': SchemeTonalSpot, vibrant: SchemeVibrant, expressive: SchemeExpressive }

// Status hues are fixed (semantic), independent of the brand seed.
const status = (hue: number, tone: number) => oklch(TonalPalette.fromHueAndChroma(hue, 64).tone(tone))

/** Build the scheme from a seed colour and write every role onto :root under the existing variable names. */
export function applyTheme(seed: string, mode: Mode, contrast: Contrast = 0, scheme: Scheme = 'vibrant'): void {
  if (!/^#[0-9a-f]{6}$/i.test(seed)) seed = DEFAULT_SEED
  const dark = mode === 'dark'
  const s: DynamicScheme = new SCHEMES[scheme](Hct.fromInt(argbFromHex(seed)), dark, contrast)
  const c = (role: { getArgb(s: DynamicScheme): number }) => oklch(role.getArgb(s))
  const v: Record<string, string> = {
    '--background': c(M.surface),
    '--foreground': c(M.onSurface),
    '--card': dark ? c(M.surfaceContainer) : c(M.surfaceContainerLowest),
    '--card-foreground': c(M.onSurface),
    '--popover': c(M.surfaceContainerHigh),
    '--popover-foreground': c(M.onSurface),
    '--primary': c(M.primary),
    '--primary-foreground': c(M.onPrimary),
    '--secondary': c(M.secondaryContainer),
    '--secondary-foreground': c(M.onSecondaryContainer),
    '--muted': c(M.surfaceContainerLow),
    '--muted-foreground': c(M.onSurfaceVariant),
    '--accent': c(M.primaryContainer),
    '--accent-foreground': c(M.onPrimaryContainer),
    '--destructive': c(M.error),
    '--destructive-foreground': c(M.onError),
    '--border': c(M.outlineVariant),
    '--input': c(M.outline),             // controls need 3:1 non-text contrast
    '--ring': c(M.primary),
    '--sidebar': c(M.surfaceContainer),
    '--sidebar-foreground': c(M.onSurface),
    '--sidebar-primary': c(M.primary),
    '--sidebar-primary-foreground': c(M.onPrimary),
    '--sidebar-accent': c(M.secondaryContainer),
    '--sidebar-accent-foreground': c(M.onSecondaryContainer),
    '--sidebar-border': c(M.outlineVariant),
    '--sidebar-ring': c(M.primary),
    '--success': status(145, dark ? 80 : 35),
    '--info': status(255, dark ? 80 : 40),
    '--warning': status(75, dark ? 80 : 40),
    '--upgrade': status(85, dark ? 80 : 80),
    '--tertiary': c(M.tertiary),
    '--tertiary-container': c(M.tertiaryContainer),
    '--scrim': c(M.scrim),
  }
  const root = document.documentElement
  for (const [k, val] of Object.entries(v)) root.style.setProperty(k, val)
  root.style.colorScheme = mode
  root.classList.toggle('dark', dark)
  root.dataset.theme = mode
}

// ---------- preferences ------------------------------------------------------
export const DEFAULT_SEED = '#3b6cf6' // Google-blue family, HCT hue ~265: reads as "Google" without the exact logo blue
export interface ThemePrefs {
  seed: string; mode: ModePref; contrast: Contrast; scheme: Scheme; reduceTransparency: boolean; buddhistEra: boolean
}
const KEY = 'ld:theme'
const defaults: ThemePrefs = { seed: DEFAULT_SEED, mode: 'system', contrast: 0, scheme: 'vibrant', reduceTransparency: false, buddhistEra: false }

function load(): ThemePrefs {
  try { return { ...defaults, ...JSON.parse(localStorage.getItem(KEY) ?? '{}') } } catch { return defaults }
}
let prefs = load()
const subs = new Set<() => void>()
const mq = (q: string) => typeof matchMedia === 'function' && matchMedia(q).matches

export function resolveMode(p: ThemePrefs = prefs): Mode {
  return p.mode === 'system' ? (mq('(prefers-color-scheme: dark)') ? 'dark' : 'light') : p.mode
}

function paint() {
  const root = document.documentElement
  // OS "increase contrast" lifts the scheme to the high-contrast level unless the user already chose one.
  const contrast: Contrast = prefs.contrast || (mq('(prefers-contrast: more)') ? 1 : 0)
  applyTheme(prefs.seed, resolveMode(), contrast, prefs.scheme)
  // Safari ignores prefers-reduced-transparency, so the Settings toggle sets this attribute.
  if (prefs.reduceTransparency) root.setAttribute('data-reduce-transparency', '')
  else root.removeAttribute('data-reduce-transparency')
}

export function setThemePrefs(patch: Partial<ThemePrefs>): void {
  prefs = { ...prefs, ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(prefs)) } catch { /* private mode */ }
  paint(); subs.forEach((f) => f())
}

export function initTheme(): void {
  paint()
  if (typeof matchMedia === 'function') {
    for (const q of ['(prefers-color-scheme: dark)', '(prefers-contrast: more)'])
      matchMedia(q).addEventListener('change', paint)
  }
}

export function useThemePrefs(): ThemePrefs {
  return useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f) }, () => prefs)
}

// ---------- dates (Gregorian by default; Buddhist Era is a setting) -----------
export function dateLocale(): string {
  const th = typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('th')
  const base = th ? 'th-TH' : 'en-US'
  return `${base}-u-ca-${prefs.buddhistEra ? 'buddhist' : 'gregory'}`
}

// ---------- class palette (separate from brand) -------------------------------
// Okabe-Ito (colour-blind safe) first, then a Glasbey-style extension chosen for max pairwise distance.
const OKABE_ITO = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
const GLASBEY = [
  '#FF0000', '#00FF00', '#0000FF', '#FF00B6', '#005300', '#FFD300', '#009FFF', '#9A4D42', '#00FFBE', '#783FC1',
  '#1F9698', '#FFACFD', '#B1CC71', '#F1085C', '#FE8F42', '#DD00FF', '#201A01', '#720055', '#766C95', '#02AD24',
]
const PALETTE = [...OKABE_ITO, ...GLASBEY]
export function classColor(i: number): string {
  const n = Math.max(0, Math.floor(i))
  if (n < PALETTE.length) return PALETTE[n]
  const h = ((n - PALETTE.length) * 137.508) % 360 // golden-angle fallback keeps neighbours distinct
  return `hsl(${h.toFixed(0)} 70% ${n % 2 ? 45 : 60}%)`
}

const VIRIDIS = ['#440154', '#482878', '#3E4A89', '#31688E', '#26828E', '#1F9E89', '#35B779', '#6DCD59', '#B4DE2C', '#FDE725']
/** Viridis colour for t in [0,1] (heatmaps). */
export function viridis(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (VIRIDIS.length - 1)
  const i = Math.min(VIRIDIS.length - 2, Math.floor(x)), f = x - i
  const a = VIRIDIS[i], b = VIRIDIS[i + 1]
  const ch = (h: string, k: number) => parseInt(h.slice(1 + k * 2, 3 + k * 2), 16)
  const mix = (k: number) => Math.round(ch(a, k) + (ch(b, k) - ch(a, k)) * f)
  return `rgb(${mix(0)} ${mix(1)} ${mix(2)})`
}
