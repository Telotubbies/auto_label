// Dev-only helper: seed a Thai OCR document and capture light/dark/375px editor screenshots.
//   node scripts/ocr-shots.mjs [webUrl] [outDir]
import { chromium, request } from 'playwright'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173'
const outDir = process.argv[3] ?? 'ocr-shots'
const WS = 'labeldesk-demo'
const PR = 'ocr-task32'
mkdirSync(outDir, { recursive: true })

const api = await request.newContext({ baseURL: base })
const login = await api.post('/api/auth/login', { data: { email: 'demo@labeldesk.dev', password: 'demo1234' } })
if (login.status() !== 200) throw new Error(`login failed: ${await login.text()}`)
const token = (await login.json()).token
const auth = { Authorization: `Bearer ${token}` }

// Fresh project (a previous run's demo data dir is discarded before the server starts).
const existing = await (await api.get(`/api/ws/${WS}/projects`, { headers: auth })).json()
for (const p of existing.filter((row) => row.name === PR)) {
  await api.delete(`/api/ws/${WS}/projects/${p.slug}`, { headers: auth })
}
const project = await api.post(`/api/ws/${WS}/projects`, { headers: auth, data: { name: PR, type: 'object-detection' } })
if (project.status() !== 200) throw new Error(`project create failed: ${await project.text()}`)

// Feature flag both ways: the OCR surface is gated on task_32, off by default.
const flag = async (enabled) => {
  const r = await api.put(`/api/ws/${WS}/flags/task_32`, { headers: auth, data: { enabled } })
  if (r.status() !== 200) throw new Error(`flag failed: ${await r.text()}`)
}
await flag(true)

const baseP = `/api/ws/${WS}/projects/${(await project.json()).slug}`
const tpl = await api.put(`${baseP}/ocr/template`, { headers: auth, data: { template: 'delivery_note' } })
if (tpl.status() !== 200) throw new Error(`template failed: ${await tpl.text()}`)

const browser = await chromium.launch()
const doc = await browser.newPage({ viewport: { width: 900, height: 620 }, deviceScaleFactor: 1 })
await doc.setContent(`<!doctype html><meta charset="utf-8"><style>
  body{margin:0;background:#e7e2d8;font-family:"Leelawadee UI","Tahoma",sans-serif;color:#20242b}
  .paper{position:absolute;inset:0;background:#fbf8f0;padding:0}
  .title{position:absolute;left:60px;top:28px;font-size:30px;font-weight:700;letter-spacing:.2px}
  .muted{position:absolute;left:60px;top:72px;font-size:15px;color:#6b665c}
  .line{position:absolute;left:60px;font-size:21px;line-height:1.2}
  table{position:absolute;left:60px;top:300px;border-collapse:collapse;width:520px;font-size:17px}
  td{border:1px solid #8f8a7e;padding:9px 10px}
  th{border:1px solid #8f8a7e;padding:9px 10px;background:#efe9dc;text-align:left}
</style>
<div class="paper">
  <div class="title">ใบส่งของ / DELIVERY NOTE</div>
  <div class="muted">บริษัท สยามขนส่ง จำกัด · สาขาบางนา</div>
  <div class="line" style="top:105px">เลขที่ INV-2569-001</div>
  <div class="line" style="top:150px;font-size:19px">โทร 081-234-5678 · เลขบัตร 1-2345-67890-12-3</div>
  <div class="line" style="top:195px">ผู้ส่ง: บริษัท สยามขนส่ง จำกัด</div>
  <div class="line" style="top:240px">ผู้รับ: คุณสมชาย ใจดี</div>
  <table><tr><th>รายการ</th><th>จำนวน</th><th>น้ำหนัก</th></tr><tr><td>กล่องเอกสาร</td><td>12</td><td>8.5 กก.</td></tr></table>
</div>`)
const png = await doc.screenshot()
await doc.close()

const up = await api.post(`${baseP}/upload`, {
  headers: auth,
  multipart: { files: { name: 'delivery-note.png', mimeType: 'image/png', buffer: png } },
})
if (up.status() !== 200) throw new Error(`upload failed: ${await up.text()}`)
const imageId = (await up.json()).images[0].id

const classes = await (await api.get(`${baseP}/classes`, { headers: auth })).json()
const cls = Object.fromEntries(classes.map((c) => [c.name, c.id]))
const box = (x, y, w, h) => ({ kind: 'bbox', x, y, w, h })
const annotations = [
  { id: 'ocr-t1', classId: cls['text-line'], shape: box(0.0667, 0.169, 0.36, 0.05), ocr: { kind: 'text', text: 'เลขที่ INV-2569-001' }, source: 'human' },
  { id: 'ocr-t2', classId: cls['text-line'], shape: box(0.0667, 0.242, 0.66, 0.045), ocr: { kind: 'text', text: 'โทร 081-234-5678 · เลขบัตร 1-2345-67890-12-3' }, source: 'human' },
  { id: 'ocr-kv', classId: cls['key-value'], shape: box(0.0667, 0.315, 0.45, 0.045), ocr: { kind: 'keyvalue', key: 'ผู้รับ', value: 'คุณสมชาย ใจดี' }, source: 'human' },
  { id: 'ocr-tb', classId: cls.table, shape: box(0.0667, 0.484, 0.578, 0.242), ocr: { kind: 'table', rows: 2, cols: 3, cells: [['รายการ', 'จำนวน', 'น้ำหนัก'], ['กล่องเอกสาร', '12', '8.5 กก.']] }, source: 'human' },
]
const saved = await api.put(`/api/images/${imageId}/annotations`, { headers: auth, data: { annotations } })
if (saved.status() !== 200) throw new Error(`annotations failed: ${await saved.text()}`)

const path = `/${WS}/${baseP.split('/').pop()}/images/${imageId}`
const shot = async (name, width, height, scheme) => {
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme, deviceScaleFactor: 1 })
  await context.addInitScript(({ t, mode }) => {
    localStorage.setItem('ld_token', t)
    localStorage.setItem('ld:theme', JSON.stringify({ mode }))
  }, { t: token, mode: scheme })
  const page = await context.newPage()
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  await page.goto(base + path, { waitUntil: 'networkidle' })
  if (width < 768) await page.getByRole('button', { name: 'Toggle annotation panels' }).click()
  await page.getByRole('button', { name: 'OCR', exact: true }).click()
  const textRow = page.getByRole('button', { name: /เลขที่ INV-2569-001/ })
  await textRow.waitFor({ timeout: 10_000 })
  await textRow.click()
  if (scheme === 'light' && width > 768) {
    // One edit must undo as one step: type, blur to commit, then a single Ctrl+Z restores it.
    const text = page.getByLabel('Text', { exact: true }).first()
    const before = await text.inputValue()
    await text.press('End')
    await text.pressSequentially(' แก้ไข', { delay: 20 })
    await text.blur()
    await page.waitForTimeout(400)
    await page.keyboard.press('Control+z')
    const after = await text.inputValue()
    if (after !== before) throw new Error(`undo restored ${JSON.stringify(after)}, expected ${JSON.stringify(before)}`)
    console.log(JSON.stringify({ undo: 'one step', before, after }))
  }
  // Screenshot the table annotation: it shows the grid, the other two kinds' fields and the exports.
  await page.getByRole('button', { name: /2×3 table/ }).click()
  await page.getByRole('group', { name: 'Table cells' }).waitFor({ timeout: 10_000 })
  await page.waitForTimeout(400)
  if (scheme === 'light' && width > 768) {
    const report = await new AxeBuilder({ page }).include('aside')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
    console.log(JSON.stringify({ axe: report.violations.map((v) => ({
      id: v.id, impact: v.impact, nodes: v.nodes.map((n) => ({ target: n.target, html: n.html })),
    })) }))
  }
  await page.screenshot({ path: `${outDir}/ocr-editor-${name}.png`, fullPage: false })
  console.log(`saved ${outDir}/ocr-editor-${name}.png`, errors.length ? `console errors: ${errors.join(' | ')}` : '')
  await context.close()
}

// Feature flag both ways: the OCR rail is absent while off, present while on.
const railVisible = async (enabled) => {
  await flag(enabled)
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addInitScript(({ t }) => localStorage.setItem('ld_token', t), { t: token })
  const page = await context.newPage()
  await page.goto(base + path, { waitUntil: 'networkidle' })
  const visible = await page.getByRole('button', { name: 'OCR', exact: true }).count()
  await context.close()
  return visible > 0
}
if (await railVisible(false)) throw new Error('OCR rail is visible while the task_32 flag is off')
if (!(await railVisible(true))) throw new Error('OCR rail is missing while the task_32 flag is on')
console.log(JSON.stringify({ flag: 'off hides the rail, on shows it' }))

try {
  await shot('light', 1440, 900, 'light')
  await shot('dark', 1440, 900, 'dark')
  await shot('375', 375, 812, 'light')
} finally {
  await browser.close()
  await api.dispose()
}
console.log(JSON.stringify({ imageId, path, ok: true }))
