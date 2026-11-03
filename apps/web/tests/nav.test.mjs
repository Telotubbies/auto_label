// Nav v2 shell: workspace groups (BUILD / GOVERN) and the five project groups.
// Runs with the built-in Node test runner: node --test tests/nav.test.mjs  (from apps/web)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  isWorkspaceNavActive, LEGACY_PROJECT_PATHS, projectNav, RESERVED_WORKSPACE_SEGMENTS,
  visibleProjectNav, visibleWorkspaceNav, WORKSPACE_PAGE_LABELS, workspaceIndexPath, workspaceNav,
} from '../src/lib/nav.ts'

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const appSrc = source('../src/App.tsx')
const shellSrc = source('../src/components/shell.tsx')
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
  'project.classes', 'project.train', 'project.models', 'project.infer', 'project.settings')
const REVIEWER = perms('project.read', 'project.annotate', 'project.review', 'project.upload', 'project.export',
  'project.classes', 'project.models', 'project.infer')
const LABELER = perms('project.read', 'project.annotate', 'project.classes', 'project.infer')
const VIEWER = perms('project.read')

test('workspace nav groups follow the v2 tree order', () => {
  assert.deepEqual(workspaceNav.map((g) => [g.id, g.label ?? null]), [
    ['core', null], ['build', 'BUILD'], ['govern', 'GOVERN'], ['footer', null],
  ])
  assert.deepEqual(itemLabels(workspaceNav, 'build'), ['Models', 'Playground', 'Deployments'])
})

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
    ['DATA', ['Upload', 'Dataset', 'Video', 'Versions', 'Classes & Tags', 'Insights']],
    ['LABEL', ['Annotate', 'Review & Quality']],
    ['MODELS', ['Train', 'Model insights', 'Models']],
    ['STUDIO', ['Lineage', 'Dashboards', 'Stream analytics']],
    ['DEPLOY', ['Deploy & Test', 'Streams']],
    ['SETTINGS', ['Project Settings']],
  ])
})

test('a reviewer loses Train and the settings group', () => {
  const groups = visibleProjectNav(REVIEWER, 'reviewer')
  assert.deepEqual(groups.map((g) => g.id), ['data', 'label', 'models', 'studio', 'deploy'])
  assert.deepEqual(itemLabels(groups, 'data'),
    ['Upload', 'Dataset', 'Video', 'Versions', 'Classes & Tags', 'Insights'])
  assert.deepEqual(itemLabels(groups, 'label'), ['Annotate', 'Review & Quality'])
  assert.deepEqual(itemLabels(groups, 'models'), ['Model insights', 'Models'])
  assert.deepEqual(itemLabels(groups, 'studio'), ['Lineage', 'Dashboards', 'Stream analytics'])
  assert.deepEqual(itemLabels(groups, 'deploy'), ['Deploy & Test', 'Streams'])
  assert.deepEqual(itemLabels(groups, 'settings'), [])
})

test('a labeler sees dataset, video and annotate only — the IA labeler view', () => {
  assert.deepEqual(groupLabels(visibleProjectNav(LABELER, 'labeler')), [
    ['DATA', ['Dataset', 'Video']],
    ['LABEL', ['Annotate']],
    // Streams are viewable by any project member (Task 10b), like the deploy surface they feed.
    ['DEPLOY', ['Streams']],
  ])
  assert.deepEqual(visibleProjectNav(LABELER, 'labeler').flatMap((g) => g.items).map((i) => i.label),
    ['Dataset', 'Video', 'Annotate', 'Streams'])
})

test('a viewer keeps the dataset and the view-only stream list', () => {
  assert.deepEqual(groupLabels(visibleProjectNav(VIEWER, 'viewer')), [
    ['DATA', ['Dataset']],
    ['DEPLOY', ['Streams']],
  ])
})

test('no permission means no project nav at all', () => {
  assert.deepEqual(visibleProjectNav(() => false, 'manager'), [])
})

test('an unresolved project role falls back to the permission check', () => {
  assert.deepEqual(itemLabels(visibleProjectNav(LABELER, null), 'data'), ['Dataset', 'Video', 'Classes & Tags'])
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
  assert.equal(streams.perm, 'project.read')
  assert.match(appSrc, /path="qa"/, 'the QA route must render the QA page')
  assert.match(appSrc, /path="streams"/, 'the Streams route must render the Streams page')
  assert.match(appSrc, /path="streams\/:sid"/, 'a stream keeps its detail URL')
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

// Fix round 3 (I2): the job tray's separator was re-encoded through the wrong code page, so every
// row read "Training ยท Project" instead of using U+00B7.
test('the job tray separates the project name with a middle dot', () => {
  assert.ok(shellSrc.includes('` · ${j.project_name}`'), 'the job row must use U+00B7 as its separator')
  assert.ok(!shellSrc.includes('ยท'), 'the job row must not contain the corrupted Thai bytes')
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
  const governed = workspaceNav.find((g) => g.id === 'govern').items.filter((i) => i.to.startsWith('settings/'))
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

const wsItem = (label) => workspaceNav.flatMap((g) => g.items).find((i) => i.label === label)
const active = (label, pathname) => isWorkspaceNavActive(wsItem(label), pathname, '/acme')

test('a settings subpage lights the specific governance item, not Settings', () => {
  assert.equal(active('Plan & Usage', '/acme/settings/usage'), true)
  assert.equal(active('Settings', '/acme/settings/usage'), false)
  assert.equal(active('Members', '/acme/settings/members'), true)
  assert.equal(active('Settings', '/acme/settings/members'), false)
})

test('a plain settings tab keeps Settings active', () => {
  assert.equal(active('Settings', '/acme/settings/account'), true)
  assert.equal(active('Members', '/acme/settings/account'), false)
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
