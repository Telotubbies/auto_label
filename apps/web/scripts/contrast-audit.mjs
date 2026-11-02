// Pixel-sampled text contrast audit: finds text whose rendered background (gradients included) is too close
// in luminance to its own colour. Not a replacement for axe — this covers axe's color-contrast *incomplete*.
//   node scripts/contrast-audit.mjs <url> [width] [light|dark]
import { chromium } from 'playwright'

const [url, widthArg, schemeArg] = process.argv.slice(2)
const width = Number(widthArg ?? 1440)
const scheme = schemeArg === 'dark' ? 'dark' : 'light'

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: scheme, reducedMotion: 'reduce' })
const page = await context.newPage()
await page.addInitScript((mode) => localStorage.setItem('ld:theme', JSON.stringify({ mode })), scheme)
if (process.env.LD_TOKEN) await page.addInitScript((t) => localStorage.setItem('ld_token', t), process.env.LD_TOKEN)
await page.goto(url, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1200)
await page.evaluate(() => document.fonts.ready)

const nodes = await page.evaluate(() => {
  const out = []
  const seen = new Set()
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  let n
  while ((n = walker.nextNode())) {
    const text = (n.textContent ?? '').trim()
    if (!text) continue
    const el = n.parentElement
    if (!el || seen.has(el)) continue
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) < 0.2) continue
    const r = el.getBoundingClientRect()
    if (r.width < 6 || r.height < 6) continue
    seen.add(el)
    out.push({
      text: text.slice(0, 50),
      rect: { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height },
      color: cs.color,
      size: parseFloat(cs.fontSize),
      weight: Number(cs.fontWeight),
      decorative: !!el.closest('[aria-hidden="true"]'),
      tag: el.tagName.toLowerCase(),
      cls: (el.className || '').toString().slice(0, 90),
    })
  }
  return out
})

const shot = (await page.screenshot({ fullPage: true })).toString('base64')

const results = await page.evaluate(async ({ b64, nodes }) => {
  const img = new Image()
  img.src = `data:image/png;base64,${b64}`
  await img.decode()
  const canvas = document.createElement('canvas')
  canvas.width = img.width
  canvas.height = img.height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(img, 0, 0)
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data

  const probe = document.createElement('canvas')
  probe.width = probe.height = 1
  const pctx = probe.getContext('2d', { willReadFrequently: true })
  const toRgb = (css) => {
    pctx.clearRect(0, 0, 1, 1)
    pctx.fillStyle = css
    pctx.fillRect(0, 0, 1, 1)
    const d = pctx.getImageData(0, 0, 1, 1).data
    return [d[0], d[1], d[2], d[3] / 255]
  }
  const lum = ([r, g, b]) => {
    const f = (c) => { const s = c / 255; return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const ratio = (a, b) => {
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
    return (hi + 0.05) / (lo + 0.05)
  }
  const hex = ([r, g, b]) => `#${[r, g, b].map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')}`

  const flagged = []
  for (const node of nodes) {
    const { x, y, w, h } = node.rect
    const x0 = Math.max(0, Math.floor(x) + 1), y0 = Math.max(0, Math.floor(y) + 1)
    const x1 = Math.min(canvas.width, Math.ceil(x + w) - 1), y1 = Math.min(canvas.height, Math.ceil(y + h) - 1)
    if (x1 - x0 < 3 || y1 - y0 < 3) continue
    // Most frequent quantised colour inside the text box = the rendered background.
    const counts = new Map()
    for (let py = y0; py < y1; py += 2) {
      for (let px = x0; px < x1; px += 2) {
        const i = (py * canvas.width + px) * 4
        const key = `${data[i] >> 4},${data[i + 1] >> 4},${data[i + 2] >> 4}`
        const entry = counts.get(key)
        if (entry) { entry.n++; entry.r += data[i]; entry.g += data[i + 1]; entry.b += data[i + 2] }
        else counts.set(key, { n: 1, r: data[i], g: data[i + 1], b: data[i + 2] })
      }
    }
    let bg = null
    for (const e of counts.values()) if (!bg || e.n > bg.n) bg = e
    const bgRgb = [bg.r / bg.n, bg.g / bg.n, bg.b / bg.n]

    const [tr, tg, tb, ta] = toRgb(node.color)
    // Composite the (possibly translucent) text colour over the sampled background.
    const fg = [tr * ta + bgRgb[0] * (1 - ta), tg * ta + bgRgb[1] * (1 - ta), tb * ta + bgRgb[2] * (1 - ta)]
    const cr = ratio(fg, bgRgb)
    const large = node.size >= 24 || (node.size >= 18.66 && node.weight >= 700)
    const min = large ? 3 : 4.5
    if (cr < min) {
      flagged.push({
        ratio: Math.round(cr * 100) / 100, min, text: node.text, tag: node.tag, cls: node.cls,
        fg: hex(fg), bg: hex(bgRgb), size: node.size, weight: node.weight, decorative: node.decorative,
      })
    }
  }
  return flagged
}, { b64: shot, nodes })

console.log(JSON.stringify({ url, width, scheme, checked: nodes.length, flagged: results }, null, 2))
await browser.close()
