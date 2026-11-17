// Settings split guard (T-058): the account and security pages live in SettingsAccount.tsx, every
// settings tab still resolves to a page, and the route table keeps its ids and its order.
// A page cannot be lost, duplicated or reordered by the move.
// Runs with the built-in Node test runner: node --test tests/settings-tabs.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

const settings = read('../src/features/settings/Settings.tsx')
const account = read('../src/features/settings/SettingsAccount.tsx')

/** The tab ids the settings nav renders, in source order. */
const TAB_IDS = ['account', 'security', 'appearance', 'workspace', 'members', 'roles', 'privacy', 'alerts', 'api', 'usage', 'trash']

/** The route ids the settings router mounts, in source order. */
const ROUTE_IDS = ['account', 'security', 'appearance', 'workspace', 'members', 'roles', 'privacy', 'alerts', 'api', 'usage', 'trash']

/** Every page a tab can show, and the file that declares it. */
const PAGES = {
  Account: 'SettingsAccount.tsx',
  Security: 'SettingsAccount.tsx',
  Appearance: 'Settings.tsx',
  Workspace: 'Settings.tsx',
  FeatureFlags: 'Settings.tsx',
  Members: 'Settings.tsx',
  ApiKeys: 'Settings.tsx',
  Usage: 'Settings.tsx',
  Trash: 'Settings.tsx',
  FirstRun: 'Settings.tsx',
}

/** Count `function <name>(` declarations in a source file. */
const declares = (src, name) => src.split(new RegExp(`function ${name}\\(`)).length - 1

test('test_every_tab_id_still_resolves', () => {
  // The nav ids, in order: the eleven settings tabs.
  const tabs = [...settings.matchAll(/\{ to: '(\w[\w-]*)', label: /g)].map((m) => m[1])
  assert.deepEqual(tabs, TAB_IDS, 'the settings nav keeps its eleven tabs, in order')

  // The route ids, in order, and the index redirect that lands on Account.
  const routes = [...settings.matchAll(/<Route path="([\w-]+)" element=/g)].map((m) => m[1])
  assert.deepEqual(routes, ROUTE_IDS, 'the settings router keeps its eleven routes, in order')
  assert.match(settings, /<Route index element=\{<Navigate to="account" replace \/>\} \/>/,
    'the settings index still redirects to the account page')
  assert.equal(routes.length, tabs.length, 'every tab has a route')

  // Each tab is a link to its own page, built from the tab id.
  assert.match(settings, /\{tabs\.map\(\(t\) => <NavLink key=\{t\.to\} to=\{`\$\{base\}\/\$\{t\.to\}`\}/,
    'every tab renders a NavLink to its own settings page')

  // Every page a tab can show is declared exactly once, in the file that owns it.
  for (const [page, file] of Object.entries(PAGES)) {
    const src = file === 'Settings.tsx' ? settings : account
    assert.equal(declares(src, page), 1, `${page} is declared once, in ${file}`)
    assert.equal(declares(file === 'Settings.tsx' ? account : settings, page), 0,
      `${page} is not declared twice across the two files`)
  }

  // The first-run surface still resolves: the shell hands a workspace-less account to it.
  assert.match(settings, /if \(firstRun\) return <FirstRun \/>/,
    'the first-run route still renders the create-a-workspace screen')

  // The account and security routes render the pages this move created.
  assert.match(settings, /<Route path="account" element=\{<Account \/>\} \/>/,
    'the account route still renders the account page')
  assert.match(settings, /<Route path="security" element=\{<Security \/>\} \/>/,
    'the security route still renders the security page')
})

test('test_settings_imports_the_account_pages', () => {
  assert.match(settings, /import \{ Account, Security \} from '\.\/SettingsAccount'/,
    'Settings.tsx imports Account and Security from ./SettingsAccount')

  for (const name of ['Account', 'Security', 'EmailCard', 'TwoFactorCard', 'SessionsCard', 'LoginHistoryCard', 'TableLoading', 'TableError']) {
    assert.equal(declares(settings, name), 0, `Settings.tsx no longer declares ${name}`)
    assert.equal(declares(account, name), 1, `SettingsAccount.tsx declares ${name}`)
  }
  assert.match(account, /export function Account\(\)/, 'SettingsAccount.tsx exports Account')
  assert.match(account, /export function Security\(\)/, 'SettingsAccount.tsx exports Security')

  // The shared device helper moved with its only callers.
  assert.match(account, /function describeDevice\(/, 'SettingsAccount.tsx owns describeDevice')
  assert.doesNotMatch(settings, /function describeDevice\(/, 'Settings.tsx no longer owns describeDevice')

  // Moved, not rewritten: the account and security pages keep their copy and their states.
  assert.match(account, />Change password</, 'the account page keeps its password card')
  assert.match(account, />Email address</, 'the security page keeps the email card')
  assert.match(account, />Two-factor authentication</, 'the security page keeps the two-factor card')
  assert.match(account, />Sessions</, 'the security page keeps the sessions card')
  assert.match(account, />Login history</, 'the security page keeps the login-history card')
  assert.match(account, /<TableLoading label="Loading sessions…" \/>/, 'the sessions table keeps its loading state')
  assert.match(account, /'Could not load sessions\.'/, 'the sessions table keeps its error state')
  assert.match(account, /title="No active sessions\."/, 'the sessions table keeps its empty state')
  assert.match(account, /<TableLoading label="Loading login history…" \/>/, 'the login history keeps its loading state')
  assert.match(account, /'Could not load login history\.'/, 'the login history keeps its error state')
  assert.match(account, /title="No sign-ins recorded yet\."/, 'the login history keeps its empty state')
})
