// T-470: the token contract. The v3 frames decide layout, flow and copy; the running app's Liquid Glass decides
// colour (design/labeldesk-v3/VISUAL-OVERRIDE.md §1, §5). So every surface, text, glass and radius role a frame
// names is mapped onto a variable that already ships in index.css, instead of a second name for the same colour.
// Source-checked like the other parity guards, because the suite has no DOM renderer.
//   node --test tests/tokens.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = (rel) => readFileSync(new URL(`../src/${rel}`, import.meta.url), 'utf8')
const css = src('index.css')
const theme = src('lib/theme.ts')

/** The eleven frame roles, and the shipped variable each one stands for. */
const MAPPING = {
  surface: '--card',
  'raised surface': '--popover',
  'subtle surface': '--muted',
  outline: '--border',
  text: '--foreground',
  'muted text': '--muted-foreground',
  primary: '--primary',
  'glass fill': '--glass-tint',
  'glass solid': '--glass-solid',
  'glass edge': '--glass-edge',
  'glass highlight': '--glass-hi',
}

const mappingBlock = css.match(/\/\* ===== v3 frame vocabulary[\s\S]*?\*\//)?.[0] ?? ''
/** Body of the first rule with this exact selector, up to the first closing brace (these rules do not nest). */
const rule = (selector) => {
  const start = css.indexOf(`${selector} {`)
  assert.notEqual(start, -1, `${selector} rule exists in index.css`)
  const open = css.indexOf('{', start)
  return css.slice(open, css.indexOf('}', open))
}

test('test_every_frame_role_maps_to_a_shipped_variable', () => {
  for (const [role, variable] of Object.entries(MAPPING)) {
    assert.match(mappingBlock, new RegExp(`${role}\\s+->\\s+${variable}\\b`),
      `the mapping names "${role}" -> ${variable}`)
    assert.match(css, new RegExp(`${variable}:`), `${variable} is declared in index.css`)
  }
})

test('test_no_parallel_token_family', () => {
  for (const name of ['--surface-[\\w-]+', '--glass-fill', '--glass-blur', '--text-small', '--text-micro',
    '--radius-(8|12|16|24)']) {
    assert.doesNotMatch(css, new RegExp(`${name}\\s*:`), `index.css must not declare ${name}`)
  }
})

test('test_glass_values_are_the_shipped_ones', () => {
  const light = rule('.glass')
  assert.match(light, /--glass-solid: color-mix\(in oklab, var\(--popover\) 92%, var\(--foreground\)\)/,
    'the no-blur fallback is popover at 92%')
  assert.match(light, /--glass-tint: color-mix\(in oklab, var\(--popover\) 58%, transparent\)/,
    'chrome blurs at 58% in light mode')
  assert.match(rule('.dark .glass'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 62%, transparent\)/,
    'chrome blurs at 62% in dark mode')
  assert.match(rule('.glass-overlay'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 80%, transparent\)/,
    'overlays are denser: 80% in light mode')
  assert.match(rule('.dark .glass-overlay'), /--glass-tint: color-mix\(in oklab, var\(--popover\) 84%, transparent\)/,
    'overlays are denser: 84% in dark mode')

  const supports = css.slice(css.indexOf('@supports ((-webkit-backdrop-filter'),
    css.indexOf('@media (prefers-reduced-transparency: reduce)'))
  assert.match(supports, /\.glass \{[^}]*blur\(16px\)/, 'chrome blurs at 16px')
  assert.match(supports, /\.glass-overlay \{[^}]*blur\(20px\)/, 'overlays blur at 20px')
})

test('test_radius_scale_is_the_shipped_one', () => {
  assert.match(rule(':root'), /--radius: 0\.625rem;/, 'the base radius is the shipped 10px')
  for (const [name, value] of Object.entries({
    '--radius-sm': 'calc\\(var\\(--radius\\) - 4px\\)',
    '--radius-md': 'calc\\(var\\(--radius\\) - 2px\\)',
    '--radius-lg': 'var\\(--radius\\)',
    '--radius-xl': 'calc\\(var\\(--radius\\) \\+ 4px\\)',
  })) {
    assert.match(css, new RegExp(`${name}: ${value};`), `${name} is derived from --radius`)
  }
})

test('test_default_seed_is_unchanged', () => {
  assert.match(theme, /export const DEFAULT_SEED = '#3b6cf6'/, 'the seed is still #3b6cf6')
  const applyTheme = theme.slice(theme.indexOf('export function applyTheme'),
    theme.indexOf('const root = document.documentElement'))
  assert.match(applyTheme, /\^#\[0-9a-f\]\{6\}\$\/i\.test\(seed\)/, 'a malformed seed is still tested')
  assert.match(applyTheme, /seed = DEFAULT_SEED/, 'and still falls back to the default seed')
})

test('test_mapping_comment_exists', () => {
  assert.notEqual(mappingBlock, '', 'index.css carries the one mapping block, above :root')
  assert.ok(css.indexOf(mappingBlock) < css.indexOf(':root {'), 'the block sits above :root')
  for (const role of Object.keys(MAPPING)) {
    assert.match(mappingBlock, new RegExp(`\\b${role}\\b`), `the block names the "${role}" role`)
  }
  assert.match(mappingBlock, /refused/, 'and says why a second variable was refused')
})
