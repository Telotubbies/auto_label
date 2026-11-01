// Task 23 QA page evidence: seeds consensus jobs, a honeypot and label events, then captures
// light/dark/375 screenshots plus axe reports. Usage:
//   node scripts/qa-shot.mjs [baseUrl] [outDir]
// Requires the API on :8010 (LD_SAM_ENABLED=0) and the Vite dev server on the base URL.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { chromium, request } from 'playwright'
import AxeBuilder from '@axe-core/playwright'

const base = process.argv[2] ?? 'http://localhost:5173'
const out = process.argv[3] ?? '.qa-shots'
const WS = 'labeldesk-demo'
const PR = 'ppe-detection'
const USERS = { admin: 'demo@labeldesk.dev', labeler: 'labeler@labeldesk.dev', reviewer: 'reviewer@labeldesk.dev' }
const PW = process.env.LD_DEMO_PW ?? 'demo1234'

mkdirSync(out, { recursive: true })
const api = await request.newContext({ baseURL: base })
const tokens = {}
const userIds = {}
for (const [role, email] of Object.entries(USERS)) {
  const r = await api.post('/api/auth/login', { data: { email, password: PW } })
  if (!r.ok()) throw new Error(`login failed for ${role}: ${await r.text()}`)
  tokens[role] = (await r.json()).token
}
const auth = (role) => ({ Authorization: `Bearer ${tokens[role]}` })
const get = async (role, path) => {
  const r = await api.get(path, { headers: auth(role) })
  if (!r.ok()) throw new Error(`GET ${path} -> ${r.status()} ${await r.text()}`)
  return r.json()
}
const send = async (role, method, path, data) => {
  const r = await api.fetch(path, { method, headers: auth(role), data })
  if (!r.ok()) throw new Error(`${method} ${path} -> ${r.status()} ${await r.text()}`)
  return r.json()
}
for (const role of Object.keys(USERS)) userIds[role] = (await get(role, '/api/me')).id
const roleOf = Object.fromEntries(Object.entries(userIds).map(([role, id]) => [id, role]))

const basePath = `/api/ws/${WS}/projects/${PR}`
const classes = await get('admin', `${basePath}/classes`)
const cls = classes[0]?.id
if (!cls) throw new Error('demo project has no classes')
const images = (await get('admin', `${basePath}/images?limit=100`)).items
const annotated = images.filter((i) => i.annotationCount > 0)
if (annotated.length < 6) throw new Error(`need 6 annotated demo images, have ${annotated.length}`)

const draft = (id, shift = 0) => ({
  id: `qa-${id}`, classId: cls, source: 'human',
  shape: { kind: 'bbox', x: 0.2 + shift, y: 0.2, w: 0.3, h: 0.3 },
})
const save = async (role, imageId, anns) => {
  const r = await api.fetch(`/api/images/${imageId}/annotations`, {
    method: 'PUT', headers: auth(role), data: { annotations: anns },
  })
  if (!r.ok()) throw new Error(`save ${role} -> ${r.status()} ${await r.text()}`)
  return r.json()
}

const jobs = await get('admin', `${basePath}/labeling/consensus`)
if (!jobs.jobs.length) {
  // Consensus jobs only accept unlabeled images; upload four fresh copies of seeded photos with a
  // unique trailing byte so the content hash differs and the upload is not skipped as a duplicate.
  const files = []
  for (let i = 0; i < 4; i++) {
    const src = await api.get(annotated[i].url)
    const buf = Buffer.concat([await src.body(), Buffer.from(`qa-${i}`)])
    files.push({ name: `qa-consensus-${i}.jpg`, mimeType: 'image/jpeg', buffer: buf })
  }
  const up = await api.post(`${basePath}/upload`, {
    headers: auth('admin'), multipart: { batch_name: 'QA consensus', split: 'train', files },
  })
  if (!up.ok()) throw new Error(`upload failed: ${await up.text()}`)
  const fresh = (await up.json()).images.map((i) => i.id)
  if (fresh.length < 4) throw new Error(`need 4 unlabeled images, got ${fresh.length}`)

  // Job A: two disagreeing labelers, merged -> populates the review queue with a disagreement score.
  const a = await send('admin', 'POST', `${basePath}/labeling/consensus`,
    { image_ids: fresh.slice(0, 2), k: 3, iou_threshold: 0.5 })
  await save('admin', fresh[0], [draft('a-admin')])
  await save('labeler', fresh[0], [draft('a-labeler')])
  await save('reviewer', fresh[0], [draft('a-reviewer', 0.5)])
  await save('admin', fresh[1], [draft('b-admin')])
  await save('labeler', fresh[1], [draft('b-labeler')])
  await save('reviewer', fresh[1], [draft('b-reviewer')])
  for (const role of Object.keys(USERS)) {
    for (const id of fresh.slice(0, 2)) {
      await send(role, 'POST', `${basePath}/labeling/consensus/${a.id}/images/${id}/submit`, {})
    }
  }
  await send('admin', 'POST', `${basePath}/labeling/consensus/${a.id}/merge`, {})
  // Job B: agree completely, left ready so the Consensus tab shows the merge action.
  // Members are round-robin: which roles are assigned depends on member order, so read the detail.
  const b = await send('admin', 'POST', `${basePath}/labeling/consensus`,
    { image_ids: fresh.slice(2, 4), k: 2, iou_threshold: 0.5 })
  const detail = await get('admin', `${basePath}/labeling/consensus/${b.id}`)
  for (const im of detail.images) {
    for (const a of im.assignees) {
      await save(roleOf[a.user_id], im.image_id, [draft(`c-${im.image_id}`)])
      await send(roleOf[a.user_id], 'POST',
        `${basePath}/labeling/consensus/${b.id}/images/${im.image_id}/submit`, {})
    }
  }
  console.log(`seeded jobs ${a.id} (merged) and ${b.id} (ready)`)
}

const honeypots = await get('admin', `${basePath}/labeling/honeypots`)
if (!honeypots.items.length) {
  const target = annotated[4]
  await send('admin', 'POST', `${basePath}/images/bulk`, { ids: [target.id], action: 'assign', value: userIds.labeler })
  const hp = await send('admin', 'POST', `${basePath}/labeling/honeypots`, { image_id: target.id })
  const truth = await get('admin', `/api/images/${target.id}`)
  const gt = truth.annotations[0]
  await save('labeler', target.id, [{ ...gt, id: 'hp-good', source: 'human' }])
  console.log(`seeded honeypot ${hp.id} on ${target.name}`)
}

const context = async (scheme, width) => {
  const c = await chromium.launch()
  const ctx = await c.newContext({ viewport: { width, height: 1000 }, colorScheme: scheme, reducedMotion: 'reduce' })
  await ctx.addInitScript(({ mode, token }) => {
    localStorage.setItem('ld:theme', JSON.stringify({ mode }))
    localStorage.setItem('ld_token', token)
  }, { mode: scheme, token: tokens.admin })
  const page = await ctx.newPage()
  return { browser: c, page }
}

const qaPath = `/${WS}/${PR}/qa`
for (const [scheme, width, name] of [['light', 1440, 'light'], ['dark', 1440, 'dark'], ['light', 375, '375-light']]) {
  const { browser, page } = await context(scheme, width)
  await page.goto(base + qaPath, { waitUntil: 'networkidle' })
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: join(out, `qa-workforce-${name}.png`), fullPage: true })
  const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
  writeFileSync(join(out, `axe-workforce-${name}.json`), JSON.stringify({
    violations: report.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target) })),
    incomplete: report.incomplete.find((r) => r.id === 'color-contrast')?.nodes.map((n) => n.target) ?? [],
  }, null, 2))
  if (scheme === 'light' && width === 1440) {
    for (const [tab, file] of [['Review queue', 'review'], ['Consensus', 'consensus'], ['Honeypots', 'honeypots']]) {
      await page.getByRole('button', { name: tab }).click()
      await page.waitForTimeout(700)
      await page.screenshot({ path: join(out, `qa-${file}-light.png`), fullPage: true })
    }
  }
  if (width === 375) {
    // The app shell's fixed sidebars overflow at 375 px (pre-existing, tracked for the final UI review).
    // Hide them to also capture and audit the page's own responsive layout.
    await page.addStyleTag({ content: 'aside{display:none !important} .glass-sidebar{display:none !important}' })
    await page.waitForTimeout(300)
    await page.screenshot({ path: join(out, `qa-workforce-${name}-content.png`), fullPage: true })
    const inner = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
    writeFileSync(join(out, `axe-workforce-${name}-content.json`), JSON.stringify({
      violations: inner.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target) })),
      incomplete: inner.incomplete.find((r) => r.id === 'color-contrast')?.nodes.map((n) => n.target) ?? [],
    }, null, 2))
  }
  console.log(`captured ${name} (${width}px) + axe`)
  await browser.close()
}

// Editor evidence: a labeler's private consensus draft with the explicit Submit button.
const jobList = (await get('admin', `${basePath}/labeling/consensus`)).jobs
const openJob = jobList.find((j) => j.status === 'ready') ?? jobList.find((j) => j.status === 'collecting')
if (openJob) {
  const det = await get('admin', `${basePath}/labeling/consensus/${openJob.id}`)
  const mine = det.images.find((im) => im.assignees.some((a) => a.user_id === userIds.labeler))
  if (mine) {
    const c = await chromium.launch()
    const ctx = await c.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light', reducedMotion: 'reduce' })
    await ctx.addInitScript(({ t, m }) => {
      localStorage.setItem('ld_token', t)
      localStorage.setItem('ld:theme', JSON.stringify({ mode: m }))
    }, { t: tokens.labeler, m: 'light' })
    const page = await ctx.newPage()
    await page.goto(`${base}/${WS}/${PR}/images/${mine.image_id}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(900)
    await page.screenshot({ path: join(out, 'editor-consensus-light.png'), fullPage: true })
    console.log('captured editor-consensus-light.png')
    await c.close()
  }
}
await api.dispose()
