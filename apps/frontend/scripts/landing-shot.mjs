// Screenshot + axe helper for the landing page. Usage:
//   node scripts/landing-shot.mjs <url> <out.png> [width] [light|dark]
//   node scripts/landing-shot.mjs axe <url> [width] [light|dark]
import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

const args = process.argv.slice(2)
const axe = args[0] === 'axe'
const url = axe ? args[1] : args[0]
const out = axe ? null : args[1]
const width = Number(args[2] ?? 1440)
const scheme = args[axe ? 3 : 3] === 'dark' ? 'dark' : 'light'

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width, height: 1000 },
  colorScheme: scheme,
  reducedMotion: 'reduce',
  deviceScaleFactor: 1,
})
const page = await context.newPage()
await page.addInitScript((mode) => {
  localStorage.setItem('ld:theme', JSON.stringify({ mode }))
}, scheme)
await page.goto(url, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(900)
await page.evaluate(() => document.fonts.ready)

if (axe) {
  const report = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  const incomplete = report.incomplete.filter((r) => r.id === 'color-contrast')
  console.log(JSON.stringify({
    url, width, scheme,
    violations: report.violations.map((v) => ({
      id: v.id, impact: v.impact, help: v.help,
      nodes: v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary })),
    })),
    incomplete: incomplete.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({ target: n.target, summary: n.failureSummary, html: n.html.slice(0, 300) })),
    })),
  }, null, 2))
} else {
  mkdirSync(dirname(out), { recursive: true })
  await page.screenshot({ path: out, fullPage: true })
  console.log(`saved ${out} (${width}px, ${scheme})`)
}
await browser.close()
