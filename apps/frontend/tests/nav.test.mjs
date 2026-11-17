// Nav v2 shell: workspace groups (BUILD / GOVERN) and the five project groups.
// Runs with the built-in Node test runner: node --test tests/nav.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import {
  GROUPS, isWorkspaceNavActive, LEGACY_PROJECT_PATHS, projectNav, RESERVED_WORKSPACE_SEGMENTS, STAGES,
  v2WorkspaceNav, visibleProjectNav, visibleWorkspaceNav, WORKSPACE_PAGE_LABELS, workspaceIndexPath,
  workspaceNav,
} from '../src/lib/nav.ts'
import { STAGE_TABS, tabsFor } from '../src/lib/nav/project/stages.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
/** Concatenated sources of a split module, so a check follows the code into its feature files. */
const sourceTree = (dir) => readdirSync(new URL(`${dir}/`, import.meta.url), { recursive: true })
  .filter((f) => /\.(ts|tsx)$/.test(f))
  .map((f) => source(`${dir}/${f.replaceAll('\\', '/')}`))
  .join('\n')
const appSrc = source('../src/App.tsx') + sourceTree('../src/routes')
const shellSrc = sourceTree('../src/components/shell')
const settingsSrc = source('../src/features/settings/Settings.tsx')
const insightsSrc = source('../src/features/project/Insights.tsx')
const projectLayoutSrc = source('../src/features/project/ProjectLayout.tsx')

const groupLabels = (groups) => groups.map((g) => [g.label ?? null, g.items.map((i) => i.label)])
const itemLabels = (groups, id) => groups.find((g) => g.id === id)?.items.map((i) => i.label) ?? []
const wsLabels = (role, superadmin = false, projectRole = null) => groupLabels(visibleWorkspaceNav(role, superadmin, projectRole))
const perms = (...granted) => {
  const set = new Set(granted)
  return (p) => set.has(p)
}
const MANAGER = perms('project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.train', 'project.models', 'project.infer', 'project.settings', 'project.streams')
const REVIEWER = perms('project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.models', 'project.infer', 'project.streams')
const LABELER = perms('project.read', 'project.annotate', 'project.classes', 'project.infer')
const VIEWER = perms('project.read')

test('a member sees BUILD and only the personal footer items', () => {
  assert.deepEqual(wsLabels('member'), [
    [null, ['Projects']],
    ['BUILD', ['Models', 'Playground', 'Deployments']],
    // Members & Roles and Usage & Billing are workspace-admin / billing surfaces (rbac.py), not member ones.
    [null, ['Activity', 'Settings']],
  ])
})

test('billing sees Plan & Usage, never the build or member surfaces', () => {
  // rbac.py grants workspace.billing to owner and billing only; a rank check would let admin through.
  assert.deepEqual(wsLabels('billing'), [
    ['GOVERN', ['Plan & Usage']],
    [null, ['Settings']],
  ])
})

test('an admin sees every governance item, audit and integrations included', () => {
  assert.deepEqual(wsLabels('admin'), [
    [null, ['Projects']],
    ['BUILD', ['Models', 'Playground', 'Deployments']],
    ['GOVERN', ['Members', 'Audit log', 'Plan & Usage', 'API Keys']],
    [null, ['Activity', 'Settings']],
  ])
})

test('an owner sees the same nav as an admin', () => {
  assert.deepEqual(visibleWorkspaceNav('owner'), visibleWorkspaceNav('admin'))
})

test('legacy reviewer / annotator roles keep the member core but lose BUILD', () => {
  // The IA gives labelers and reviewers project work only; the workspace ML surfaces are not theirs.
  const expected = [[null, ['Projects']], [null, ['Activity', 'Settings']]]
  assert.deepEqual(wsLabels('reviewer'), expected)
  assert.deepEqual(wsLabels('annotator'), expected)
})

test('a labeler project role hides BUILD while they stay inside that project', () => {
  const memberInProject = wsLabels('member', false, 'labeler')
  assert.deepEqual(memberInProject, [[null, ['Projects']], [null, ['Activity', 'Settings']]])
  // The same member outside a project (or as a manager) keeps the workspace BUILD surfaces.
  assert.deepEqual(wsLabels('member'), [
    [null, ['Projects']],
    ['BUILD', ['Models', 'Playground', 'Deployments']],
    [null, ['Activity', 'Settings']],
  ])
  assert.equal(itemLabels(visibleWorkspaceNav('member', false, 'manager'), 'build').length, 3)
})

test('no role yet renders the member view, never a privileged item', () => {
  assert.deepEqual(wsLabels(null), wsLabels('member'))
})

test('the platform admin console entry appears only for superadmins', () => {
  const plain = visibleWorkspaceNav('admin', false)
  const superadmin = visibleWorkspaceNav('admin', true)
  assert.equal(plain.some((g) => g.items.some((i) => i.label === 'Admin')), false)
  assert.equal(superadmin.some((g) => g.items.some((i) => i.label === 'Admin')), true)
})

test('project nav has the six v2 groups in lifecycle order', () => {
  assert.deepEqual(projectNav.map((g) => g.label), ['DATA', 'LABEL', 'MODELS', 'STUDIO', 'DEPLOY', 'SETTINGS'])
})

test('a manager sees every project group', () => {
  assert.deepEqual(groupLabels(visibleProjectNav(MANAGER, 'manager')), [
    ['DATA', ['Upload', 'Dataset', 'Search', 'Event search', 'Video', 'Versions', 'Classes & Tags', 'Insights',
              'Suspect labels']],
    ['LABEL', ['Annotate', 'Review & Quality']],
    ['MODELS', ['Train', 'Anomaly', 'Model insights', 'Models', 'Workflows']],
    ['STUDIO', ['Lineage', 'Dashboards', 'Stream analytics']],
    ['DEPLOY', ['Deploy & Test', 'Streams']],
    ['SETTINGS', ['Project Settings']],
  ])
})

test('a reviewer loses Train and the settings group', () => {
  const groups = visibleProjectNav(REVIEWER, 'reviewer')
  assert.deepEqual(groups.map((g) => g.id), ['data', 'label', 'models', 'studio', 'deploy'])
  assert.deepEqual(itemLabels(groups, 'data'),
    ['Upload', 'Dataset', 'Search', 'Event search', 'Video', 'Versions', 'Classes & Tags', 'Insights',
     'Suspect labels'])
  assert.deepEqual(itemLabels(groups, 'label'), ['Annotate', 'Review & Quality'])
  assert.deepEqual(itemLabels(groups, 'models'), ['Anomaly', 'Model insights', 'Models', 'Workflows'])
  assert.deepEqual(itemLabels(groups, 'studio'), ['Lineage', 'Dashboards', 'Stream analytics'])
  assert.deepEqual(itemLabels(groups, 'deploy'), ['Deploy & Test', 'Streams'])
  assert.deepEqual(itemLabels(groups, 'settings'), [])
})

test('a labeler sees dataset, video and annotate only — the IA labeler view', () => {
  assert.deepEqual(groupLabels(visibleProjectNav(LABELER, 'labeler')), [
    ['DATA', ['Dataset', 'Search', 'Video']],
    ['LABEL', ['Annotate']],
    // Streams carry camera footage and predictions: project.streams (manager/reviewer) only, and
    // event search reads the same footage, so a labeler gets neither.
  ])
  assert.deepEqual(visibleProjectNav(LABELER, 'labeler').flatMap((g) => g.items).map((i) => i.label),
    ['Dataset', 'Search', 'Video', 'Annotate'])
})

test('a viewer keeps the dataset and no stream list', () => {
  assert.deepEqual(groupLabels(visibleProjectNav(VIEWER, 'viewer')), [
    ['DATA', ['Dataset', 'Search']],
  ])
})

test('no permission means no project nav at all', () => {
  assert.deepEqual(visibleProjectNav(() => false, 'manager'), [])
})

test('an unresolved project role falls back to the permission check', () => {
  assert.deepEqual(itemLabels(visibleProjectNav(LABELER, null), 'data'), ['Dataset', 'Search', 'Video', 'Classes & Tags'])
})

test('search and event search stay hidden until their own flag is on', () => {
  const labels = (flags) => visibleProjectNav(MANAGER, 'manager', flags).flatMap((g) => g.items).map((i) => i.label)
  assert.equal(labels(new Set()).includes('Search'), false)
  assert.equal(labels(new Set()).includes('Event search'), false)
  assert.equal(labels(new Set(['task_27'])).includes('Search'), true)
  assert.equal(labels(new Set(['task_27'])).includes('Event search'), false)
  assert.equal(labels(new Set(['task_38'])).includes('Event search'), true)
  assert.equal(labels(new Set(['task_23'])).includes('Review & Quality'), true)
})

test('the old access and analytics routes redirect into their new homes', () => {
  assert.deepEqual(LEGACY_PROJECT_PATHS, {
    access: 'settings?tab=access',
    analytics: 'insights?tab=health',
  })
})

test('dataset health is a tab of Insights, not a sixth DATA entry', () => {
  assert.equal(projectNav.flatMap((g) => g.items).some((i) => i.label === 'Dataset health'), false)
  assert.match(insightsSrc, /id: 'health', label: 'Dataset health'/, 'Insights needs the health tab')
  assert.match(insightsSrc, /\.get\('tab'\)/, 'the legacy redirect must be able to open the health tab')
})

test('the Task 22 video section keeps its nav entry and route', () => {
  const video = projectNav.flatMap((g) => g.items).find((i) => i.label === 'Video')
  assert.ok(video, 'the video authoring page lost its nav entry')
  assert.equal(video.to, 'videos')
  assert.equal(video.perm, 'project.annotate')
  assert.match(appSrc, /import VideoTimeline from '@\/features\/project\/VideoTimeline'/)
})

test('Task 23 QA and Task 10b Streams keep their nav entries and routes', () => {
  const qa = projectNav.flatMap((g) => g.items).find((i) => i.to === 'qa')
  assert.ok(qa, 'the QA page lost its nav entry')
  assert.equal(qa.perm, 'project.review')
  assert.deepEqual(qa.roles, ['manager', 'reviewer'])
  const streams = projectNav.flatMap((g) => g.items).find((i) => i.to === 'streams')
  assert.ok(streams, 'the Streams page lost its nav entry')
  assert.equal(streams.perm, 'project.streams')
  assert.match(appSrc, /path="qa"/, 'the QA route must render the QA page')
  assert.match(appSrc, /path="streams"/, 'the Streams route must render the Streams page')
  assert.match(appSrc, /path="streams\/:sid"/, 'a stream keeps its detail URL')
  assert.match(appSrc, /<PermGate perm="project\.streams">/, 'the Streams route must use project.streams')
})

test('the Task 29 anomaly station is scoped to anomaly projects', () => {
  const anomaly = projectNav.flatMap((g) => g.items).find((i) => i.to === 'anomaly')
  assert.ok(anomaly, 'the anomaly station lost its nav entry')
  assert.equal(anomaly.perm, 'project.read')
  assert.equal(anomaly.type, 'anomaly-detection')
  assert.equal(anomaly.flag, 'task_29')
  const targets = (type) => visibleProjectNav(MANAGER, 'manager', undefined, type)
    .flatMap((g) => g.items.map((i) => i.to))
  assert.ok(!targets('object-detection').includes('anomaly'))
  assert.ok(targets('anomaly-detection').includes('anomaly'), 'an anomaly project keeps its station')
  assert.match(appSrc, /path="anomaly"/)
})

test('roles without a Projects entry land on their first visible surface', () => {
  assert.equal(workspaceIndexPath('billing'), 'settings/usage')
  for (const role of ['owner', 'admin', 'member', 'reviewer', 'annotator', null]) {
    assert.equal(workspaceIndexPath(role), '', `${role} should keep the Projects grid`)
  }
})

test('the mobile drawer contract survives the nav rewrite', () => {
  assert.match(shellSrc, /export function AppSidebar\(\{ mobileOpen[^)]*onClose/, 'AppSidebar must accept the mobile drawer props')
  assert.match(shellSrc, /<AppSidebar mobileOpen=\{navOpen\} onClose=/, 'AppLayout must wire the drawer')
  assert.match(shellSrc, /<TopBar onMenu=/, 'the mobile menu button must open the drawer')
})

// T-481 moved the middle-dot rule into `lib/jobs.ts`: the row label is `resultLine(job)`, written
// with U+00B7 as an escape so no shell file carries a re-encoded separator.
test('the job row builds its middle dot in jobs.ts, not in the shell', () => {
  const jobsSrc = source('../src/lib/jobs.ts')
  assert.ok(jobsSrc.includes('\\u00B7'), 'jobs.ts must own the U+00B7 separator')
  assert.ok(!shellSrc.includes('\u00B7'), 'no shell file may carry the separator itself')
})

test('the mobile drawer moves, traps and restores keyboard focus', () => {
  assert.match(shellSrc, /aria-expanded=\{menuOpen\}/, 'the menu button must expose its expanded state')
  assert.match(shellSrc, /aria-controls="app-sidebar"/, 'the menu button must point at the drawer')
  assert.match(shellSrc, /id="app-sidebar"/, 'the drawer needs the id the button points at')
  assert.match(shellSrc, /closeRef\.current\?\.focus\(\)/, 'opening the drawer must focus its close button')
  assert.match(shellSrc, /e\.key !== 'Tab'/, 'the drawer must trap Tab')
  assert.match(shellSrc, /menuRef\.current\?\.focus\(\)/, 'closing the drawer must restore focus to the menu button')
})

test('governed nav labels match the Settings tabs they open', () => {
  // The governance entries live on the v2 rail (flag off); the v3 rail keeps only Settings.
  const governed = v2WorkspaceNav.find((g) => g.id === 'govern').items.filter((i) => i.to.startsWith('settings/'))
  assert.ok(governed.length >= 3)
  for (const item of governed) {
    assert.ok(settingsSrc.includes(`label: '${item.label}'`),
      `the Settings tab for ${item.to} must be named "${item.label}", like the nav and breadcrumb`)
  }
})

test('every workspace nav destination has a route', () => {
  for (const item of workspaceNav.flatMap((g) => g.items)) {
    if (!item.to) {
      assert.match(appSrc, /<Route index/, 'the core Projects entry needs the index route')
      continue
    }
    const [first, second] = item.to.split('/')
    // Settings subpages live in the nested Settings router; everything else is in App.
    const src = second ? settingsSrc : appSrc
    const name = second ?? first
    assert.ok(src.includes(`path="${name}`), `${item.label} points at ${item.to}, which has no route`)
  }
})

// Fix round 4 (I2): the shell decides "workspace page vs project" from this set. A destination
// missing from it is wrapped in project chrome — no top padding, no page scroll — which painted
// the Playground title under the floating top bar and clipped the page below the fold.
test('every workspace nav destination renders as a workspace page', () => {
  for (const item of workspaceNav.flatMap((g) => g.items)) {
    if (!item.to) continue
    const segment = item.to.split('/')[0]
    assert.ok(RESERVED_WORKSPACE_SEGMENTS.has(segment),
      `${item.label} (${item.to}) would be treated as a project slug`)
    assert.ok(WORKSPACE_PAGE_LABELS[segment], `${item.label} has no breadcrumb label`)
  }
  assert.equal(WORKSPACE_PAGE_LABELS.playground, 'Playground')
})

test('every reserved workspace segment has a breadcrumb label', () => {
  for (const segment of RESERVED_WORKSPACE_SEGMENTS) {
    assert.ok(WORKSPACE_PAGE_LABELS[segment], `${segment} has no breadcrumb label`)
  }
})

// T-474: `/w/p/ppe` reads `p` as the project prefix, never as a project slug.
test('the /p/ project prefix is a reserved workspace segment', () => {
  assert.ok(RESERVED_WORKSPACE_SEGMENTS.has('p'))
})

test('every project nav destination has a route', () => {
  for (const item of projectNav.flatMap((g) => g.items)) {
    assert.ok(appSrc.includes(`path="${item.to}"`), `${item.label} points at ${item.to}, which has no route`)
  }
  // Legacy paths are rendered from LEGACY_PROJECT_PATHS.map(...), so assert the wiring, not literals.
  assert.match(appSrc, /Object\.entries\(LEGACY_PROJECT_PATHS\)\.map\(/)
  for (const target of Object.values(LEGACY_PROJECT_PATHS)) {
    assert.ok(appSrc.includes(`path="${target.split('?')[0]}"`), `legacy redirect target ${target} has no route`)
  }
})

// A new page adds its own `*.routes.tsx`; the registry must import it or the route never renders.
test('every route module is composed by a registry', () => {
  const dir = new URL('../src/routes/', import.meta.url)
  const files = readdirSync(dir, { recursive: true }).map((f) => f.replaceAll('\\', '/'))
  const registry = files
    .filter((f) => f.endsWith('index.tsx') || f.endsWith('.routes.tsx'))
    .map((f) => readFileSync(new URL(f, dir), 'utf8'))
    .join('\n')
  for (const file of files.filter((f) => f.endsWith('.routes.tsx'))) {
    const name = file.split('/').pop().replace(/\.tsx$/, '')
    assert.ok(registry.includes(`./${name}`), `${file} is not composed by any route registry`)
  }
})

const wsItem = (label) => workspaceNav.flatMap((g) => g.items).find((i) => i.label === label)
const active = (label, pathname) => isWorkspaceNavActive(wsItem(label), pathname, '/acme')
// The governance rows only exist on the v2 rail, so their matcher tests read that rail.
const v2Item = (label) => v2WorkspaceNav.flatMap((g) => g.items).find((i) => i.label === label)
const v2Items = v2WorkspaceNav.flatMap((g) => g.items)
const activeV2 = (label, pathname) => isWorkspaceNavActive(v2Item(label), pathname, '/acme', v2Items)

test('a settings subpage lights the specific governance item, not Settings', () => {
  assert.equal(activeV2('Plan & Usage', '/acme/settings/usage'), true)
  assert.equal(activeV2('Settings', '/acme/settings/usage'), false)
  assert.equal(activeV2('Members', '/acme/settings/members'), true)
  assert.equal(activeV2('Settings', '/acme/settings/members'), false)
})

test('a plain settings tab keeps Settings active', () => {
  assert.equal(active('Settings', '/acme/settings/account'), true)
  assert.equal(activeV2('Members', '/acme/settings/account'), false)
})

// Fix round 5 (I1): the longer-match loop only walked the full nav, so a role-hidden item
// suppressed the shorter item the sidebar renders. A member/annotator opening Settings →
// Members had no current nav item at all; Settings must stay lit there.
test('a hidden longer item does not un-light the item the sidebar renders', () => {
  const memberItems = visibleWorkspaceNav('member').flatMap((g) => g.items)
  const memberSettings = memberItems.find((i) => i.label === 'Settings')
  assert.ok(memberSettings, 'a member must still see Settings')
  assert.equal(isWorkspaceNavActive(memberSettings, '/acme/settings/members', '/acme', memberItems), true)
  assert.equal(isWorkspaceNavActive(memberSettings, '/acme/settings/usage', '/acme', memberItems), true)
  // An owner does render Members / Plan & Usage, so Settings yields to those specific items.
  const ownerItems = visibleWorkspaceNav('owner').flatMap((g) => g.items)
  const ownerSettings = ownerItems.find((i) => i.label === 'Settings')
  assert.equal(isWorkspaceNavActive(ownerSettings, '/acme/settings/members', '/acme', ownerItems), false)
  assert.equal(isWorkspaceNavActive(ownerSettings, '/acme/settings/usage', '/acme', ownerItems), false)
})

test('the workspace root is active only at the root, with or without a trailing slash', () => {
  assert.equal(active('Projects', '/acme'), true)
  // React Router keeps the slash the sidebar link renders (`/acme/`), so clicking Projects must
  // still mark it current; before fix round 4 it matched only the slashless pathname.
  assert.equal(active('Projects', '/acme/'), true)
  assert.equal(active('Projects', '/acme/models'), false)
  assert.equal(active('Models', '/acme/models/'), true)
})

// Fix round 4 (I1): a click-level guard. The sidebar renders `${base}/${item.to}`, so every item
// must be active at exactly that href — the rendered link and the matcher cannot drift apart.
test('every workspace nav link is active at the href the sidebar renders', () => {
  for (const item of workspaceNav.flatMap((g) => g.items)) {
    const href = `/acme/${item.to}`
    assert.equal(isWorkspaceNavActive(item, href, '/acme'), true,
      `${item.label} renders ${href} but is not the current item there`)
  }
})

// Fix round 2 (I1): the compact strip used to filter on permission alone, so a project labeler saw
// Classes & Tags at 375 px while the desktop panel hid it. Both renderers must use one role-aware list.
test('the compact project strip and the project panel derive from one role-filtered list', () => {
  assert.ok(shellSrc.includes('export function projectNavGroups('),
    'shell.tsx must expose the shared, role-aware project nav builder')
  assert.ok(shellSrc.includes('projectNavGroups(visible, projectRole'),
    'the desktop panel must render the shared builder')
  assert.ok(projectLayoutSrc.includes('projectNavGroups(canProject, projectRole'),
    'the compact strip must render the same builder, with the resolved project role')
  assert.ok(!projectLayoutSrc.includes('filter((i) => canProject(i.perm))'),
    'the strip must not filter on permission alone: project.classes is granted to labelers')
  assert.ok(projectLayoutSrc.includes('const items = projectNavGroups(canProject, projectRole'),
    'the strip must reuse its single items list instead of recomputing it')
})

// --- T-476: five destinations plus Admin, governance inside Settings ---------------------------
// `task_470` (`ui_v3`) switches the rail: off is the frozen v2 rail, on is the v3 one below.
// REDESIGN §3.2 draws seven labels and calls them six; the card resolves it as five + Admin.
const V3 = true
const v3Groups = (role, superadmin = false, projectRole = null) =>
  groupLabels(visibleWorkspaceNav(role, superadmin, projectRole, V3))
const v3Items = (role, superadmin = false, projectRole = null) =>
  visibleWorkspaceNav(role, superadmin, projectRole, V3).flatMap((g) => g.items)
const railLabels = (groups) => groups.flatMap(([, labels]) => labels)

test('test_workspace_rail_has_six_items', () => {
  assert.deepEqual(workspaceNav.map((g) => [g.id, g.label ?? null]), [['core', null], ['footer', null]])
  assert.deepEqual(railLabels(v3Groups('owner')), ['Projects', 'Models', 'Deployments', 'Activity', 'Settings'])
  assert.deepEqual(railLabels(v3Groups('owner', true)),
    ['Projects', 'Models', 'Deployments', 'Activity', 'Settings', 'Admin'])
  // No ALL-CAPS group caption survives: an unlabelled group renders no caption at all.
  for (const [label] of v3Groups('owner', true)) assert.equal(label, null, 'the rail carries no group label')
})

test('test_governance_left_the_rail', () => {
  const gone = ['Members', 'Plan & Usage', 'API Keys', 'Playground', 'Audit log']
  const labels = workspaceNav.flatMap((g) => g.items).map((i) => i.label)
  for (const label of gone) assert.equal(labels.includes(label), false, `${label} is a Settings tab, not a rail row`)
  // No audience re-admits one of them: not for a superadmin, not for billing, not inside a project.
  for (const role of ['owner', 'admin', 'member', 'reviewer', 'annotator', 'billing', null]) {
    for (const superadmin of [false, true]) {
      for (const projectRole of [null, 'labeler', 'manager']) {
        assert.deepEqual(railLabels(v3Groups(role, superadmin, projectRole)).filter((l) => gone.includes(l)), [],
          `${role} / superadmin ${superadmin} / ${projectRole} still sees a governance row`)
      }
    }
  }
})

test('test_every_removed_destination_is_a_settings_tab', () => {
  // The governance surfaces kept the names they had in the rail, so tab and breadcrumb agree.
  const tabs = { Members: 'members', 'Plan & Usage': 'usage', 'API Keys': 'api' }
  for (const [label, segment] of Object.entries(tabs)) {
    assert.ok(settingsSrc.includes(`to: '${segment}', label: '${label}'`),
      `Settings needs a "${label}" tab at ${segment}`)
  }
})

// Pending, not passing: T-400 owns the Settings → Audit log tab and the /audit redirect.
test('Audit log is a Settings tab once T-400 lands', { todo: 'T-400 owns the Audit log tab and the /audit redirect' }, () => {
  assert.ok(settingsSrc.includes("to: 'audit', label: 'Audit log'"), 'Settings needs the Audit log tab')
})

test('test_roles_keep_a_landing_page', () => {
  assert.equal(workspaceIndexPath('billing'), 'settings/usage')
  for (const role of ['owner', 'admin', 'member', 'reviewer', 'annotator', null]) {
    assert.equal(workspaceIndexPath(role), '', `${role} keeps the Projects grid`)
  }
  // A role change narrows the rail instead of emptying it: every role keeps somewhere to land.
  assert.deepEqual(railLabels(v3Groups('annotator')), ['Projects', 'Activity', 'Settings'])
  assert.deepEqual(railLabels(v3Groups('billing')), ['Settings'])
  assert.deepEqual(railLabels(v3Groups('member', false, 'labeler')), ['Projects', 'Activity', 'Settings'])
})

test('test_no_rail_item_points_into_a_project', () => {
  for (const item of workspaceNav.flatMap((g) => g.items)) {
    // The shell reads this set to tell a workspace page from a project slug, so membership is the test.
    assert.ok(item.to === '' || RESERVED_WORKSPACE_SEGMENTS.has(item.to.split('/')[0]),
      `${item.label} (${item.to}) is not a workspace URL`)
    assert.equal(item.to.startsWith('p/'), false, `${item.label} must not point into a project`)
  }
})

test('test_flag_off_restores_the_v2_rail', () => {
  const V2 = [
    [null, ['Projects']],
    ['BUILD', ['Models', 'Playground', 'Deployments']],
    ['GOVERN', ['Members', 'Audit log', 'Plan & Usage', 'API Keys']],
    [null, ['Activity', 'Settings', 'Admin']],
  ]
  // T-1000 appends a flag-gated Inference row to the v2 BUILD group. The filtered role views
  // below pass no flag set, so they stay exactly the pre-inference rail.
  const V2_RAW = V2.map(([label, items]) => [label, label === 'BUILD' ? [...items, 'Inference'] : items])
  assert.deepEqual(groupLabels(v2WorkspaceNav), V2_RAW)
  // The default (no flag argument) is off, so nothing changes for a workspace that never opts in.
  assert.deepEqual(wsLabels('admin'), [...V2.slice(0, 3), [null, ['Activity', 'Settings']]])
  assert.deepEqual(wsLabels('owner', true), V2)
  // …and the sidebar really reads the flags and hands the enabled set to the rail builder.
  assert.match(shellSrc, /useFlag\('task_470'\)/, 'AppSidebar must read the ui_v3 flag')
  assert.match(shellSrc, /useWorkspaceFlags\(\)/, 'AppSidebar must read the workspace flag set')
  assert.match(shellSrc, /visibleWorkspaceNav\(role, superadmin, [^)]*uiV3, enabled\)/,
    'the enabled flags must reach visibleWorkspaceNav')
})

test('the playground keeps its URL without a rail entry', () => {
  assert.ok(RESERVED_WORKSPACE_SEGMENTS.has('playground'), 'the shell must read /w/playground as a workspace page')
  assert.equal(WORKSPACE_PAGE_LABELS.playground, 'Playground')
  assert.match(appSrc, /path="playground"/, '/w/playground must still resolve')
  assert.equal(workspaceNav.flatMap((g) => g.items).some((i) => i.to === 'playground'), false)
})

test('every settings tab keeps Settings lit once governance left the rail', () => {
  const items = v3Items('owner')
  const settings = items.find((i) => i.label === 'Settings')
  for (const path of ['/acme/settings', '/acme/settings/members', '/acme/settings/usage', '/acme/settings/api']) {
    assert.equal(isWorkspaceNavActive(settings, path, '/acme', items), true, `Settings must be current at ${path}`)
  }
})

// --- T-477: the stage manifest is the v3 rail's source; the v2 groups stay untouched -----------
test('the stage manifest is the rail source and the v2 groups are untouched', () => {
  assert.deepEqual(STAGES.map((s) => s.id), ['upload', 'annotate', 'dataset', 'train', 'deploy'])
  assert.deepEqual(GROUPS.map((g) => g.label), ['Data', 'Models', 'Deploy'])
  // Flag off renders `projectNav` exactly as before: six groups, no numbered row.
  assert.deepEqual(projectNav.map((g) => g.label), ['DATA', 'LABEL', 'MODELS', 'STUDIO', 'DEPLOY', 'SETTINGS'])
  assert.equal(projectNav.flatMap((g) => g.items).some((i) => 'number' in i), false)
})

// Acceptance: the active row is the shared treatment — accent fill, 1 px primary outline — and the
// row keeps the shipped glass sidebar surface. One row, one style, flag off untouched.
test('the active rail row carries the shared accent fill and primary outline', () => {
  assert.match(shellSrc, /border border-primary bg-accent font-medium text-accent-foreground/,
    'the active row needs the accent fill and the 1 px primary outline')
  assert.match(shellSrc, /glass-sidebar/, 'the rail keeps the shipped Glass sidebar surface')
  assert.match(shellSrc, /sidebar-accent font-medium text-sidebar-accent-foreground/,
    'flag off keeps the v2 row')
})

// T-479: Versions, Health and Streams live inside their stage as tabs, so the rail lists each
// destination once. A tab id may never also be a stage id.
test('every stage tab is a child of its stage', () => {
  const stages = Object.keys(STAGE_TABS)
  for (const stage of stages) {
    assert.ok(STAGE_TABS[stage].length > 1, `${stage} hosts tabs only when there is more than one`)
    for (const tab of STAGE_TABS[stage]) {
      assert.ok(!stages.includes(tab.id), `${tab.id} is a tab, not a stage of its own`)
      assert.ok(tab.perm, `${stage}/${tab.id} must keep the permission its child route gates on`)
    }
  }
  assert.deepEqual(tabsFor('train'), [], 'Train is a destination, not a tab host')
  assert.deepEqual(stages.sort(), ['dataset', 'deploy'])
})

// T-483: the project index is the overview while `task_470` (ui_v3) is on, and the old grid
// redirect is what renders when the frame is off. One source assertion for both states.
test('the project index renders the overview, not the dataset grid', () => {
  const indexSrc = source('../src/routes/project/index.tsx')
  assert.ok(indexSrc.includes("useFlag('task_470')"), 'the index must read the ui_v3 flag')
  assert.ok(indexSrc.includes('<Overview />'), 'the index must render the overview')
  assert.ok(indexSrc.includes('<Navigate to="browse" replace />'),
    'flag off keeps the dataset-grid redirect exactly as today')
})

// --- T-478: the project rail is the stage manifest, at both widths ------------------------------
test('the project rail renders the stage manifest from one model', () => {
  assert.match(shellSrc, /useFlag\('task_470'\)/, 'the rail reads the ui_v3 flag')
  assert.match(shellSrc, /visibleStageGroups\(/, 'flag on renders the five numbered stages')
  assert.match(shellSrc, /useProjectRail/, 'one rail model serves both widths')
  assert.match(projectLayoutSrc, /useProjectRail\(project\)/, 'the compact strip renders the same groups')
  // Flag off: the frozen v2 groups stay the rail's source, unchanged.
  assert.match(shellSrc, /projectNavGroups\(visible, projectRole/, 'flag off keeps the grouped panel')
  assert.match(projectLayoutSrc, /RailGroup|rail\.groups/, 'the strip reads the rail model')
})

// --- T-1000: the Inference hub is a flag-gated workspace destination ----------------------------
test('test_inference_is_a_reserved_workspace_page', () => {
  // The shell reads this set to tell a workspace page from a project slug, and the breadcrumb
  // needs the label. Both are the hub's, not a project's.
  assert.ok(RESERVED_WORKSPACE_SEGMENTS.has('inference'))
  assert.equal(WORKSPACE_PAGE_LABELS.inference, 'Inference')
})

test('test_inference_route_is_lazy_and_member_gated', () => {
  assert.match(appSrc, /lazy\(\(\) => import\('@\/features\/inference\/InferenceHub'\)\)/)
  // T-1110 (row 14): PLAN §12.5 opens the read-only Calculator to a member; the hub itself serves
  // that member the Calculator alone and keeps the other three surfaces for admins. The audience is
  // named exactly, because the rank rule would also have admitted a reviewer and an annotator.
  assert.match(appSrc, /<Route path="inference" element=\{<Gate roles=\{\['owner', 'admin', 'member'\]\}><InferenceHub \/><\/Gate>\} \/>/)
})

test('test_inference_is_a_flag_gated_item_in_both_rails', () => {
  for (const rail of [v2WorkspaceNav, workspaceNav]) {
    const item = rail.flatMap((g) => g.items).find((i) => i.to === 'inference')
    assert.equal(item?.label, 'Inference')
    assert.equal(item?.flag, 'task_inference')
    assert.deepEqual(item?.roles, ['owner', 'admin', 'member'])
  }
})
