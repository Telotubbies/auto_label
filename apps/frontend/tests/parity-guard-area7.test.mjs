// Parity guard, area 7: members, plan & usage, API keys and first run.
// Pins the HAVE rows 7-F7.7, 7-F7.15, 7-F7.26 and 7-F7.57 in the source that renders them, so an
// RBAC, billing or key-lifecycle card cannot drop the owner badge, a meter, the one-time reveal or
// the first-run card.
// Runs with the built-in Node test runner: node --test tests/parity-guard-area7.test.mjs  (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const settings = readFileSync(new URL('../src/features/settings/Settings.tsx', import.meta.url), 'utf8')

/** The body of one top-level component, so a string found elsewhere cannot satisfy the guard. */
function component(name, next) {
  const start = settings.indexOf(`function ${name}`)
  const end = settings.indexOf(next, start)
  assert.ok(start >= 0 && end > start, `expected the ${name} component`)
  return settings.slice(start, end)
}

test('test_members_keeps_the_owner_badge_remove_and_leave', () => {
  const members = component('Members()', 'function ApiKeys()')

  assert.match(members, /\{m\.owner && <Badge>Owner<\/Badge>\}/,
    '7-F7.7: the roster marks the owner row with an Owner badge')
  assert.match(members, /\{!m\.owner &&/,
    '7-F7.7: the owner row has no role control and no removal control')
  assert.match(members, /'Leave this workspace\?'/,
    '7-F7.7: your own row asks the leave question')
  assert.match(members, /`Remove \$\{m\.name\}\?`/,
    '7-F7.7: another row asks the removal question with the name')
  assert.match(members, /m\.id === me\?\.id \? 'Leave' : 'Remove'/,
    '7-F7.7: the control reads Leave on your row and Remove on everyone else')
})

test('test_usage_keeps_credits_and_the_four_meters', () => {
  const usage = component('Usage()', 'function Trash()')

  assert.match(usage, />Credits</, '7-F7.15: the plan card prints the credit allowance')
  assert.match(usage, /u\.limits\.credits/, '7-F7.15: the credit figure comes from the plan ladder')
  assert.match(usage, /METER_ORDER\.flatMap/, '7-F7.15: the meters render in the fixed order')

  const order = settings.match(/const METER_ORDER: UsageMeterKey\[\] = \[([^\]]+)\]/)
  assert.ok(order, '7-F7.15: METER_ORDER declares the four meters')
  assert.deepEqual(order[1].split(',').map((key) => key.trim().replace(/^'|'$/g, '')),
    ['gpu_seconds', 'stream_hours', 'ai_calls', 'storage_bytes'],
    '7-F7.15: the meters keep GPU time, stream hours, AI calls and storage')
})

test('test_api_keys_keeps_the_one_time_reveal_and_the_masked_row', () => {
  const keys = component('ApiKeys()', 'const METER_ORDER')

  assert.ok(keys.includes("Copy your new key now — it won't be shown again."),
    '7-F7.26: creating a key says it will not be shown again')
  assert.match(keys, /\{k\.prefix\}…/, '7-F7.26: the row is masked to the prefix')
  assert.match(keys, /k\.last_used/, '7-F7.26: the row keeps its last-used column')
  assert.match(keys, /`Revoke "\$\{k\.name\}"\?/, '7-F7.26: the delete control names the key it revokes')
})

test('test_first_run_offers_a_create_workspace_screen', () => {
  const firstRun = component('FirstRun()', 'export default function Settings')
  const shell = settings.slice(settings.indexOf('export default function Settings'))

  assert.match(firstRun, /<h1[^>]*>Create a workspace<\/h1>/,
    '7-F7.57: the first-run screen keeps its Create a workspace heading')
  assert.match(firstRun, /post<\{ slug: string \}>\('\/workspaces'/, 
    '7-F7.57: the screen creates the second workspace through the shipped route')
  assert.match(shell, /if \(firstRun\) return <FirstRun \/>/,
    '7-F7.57: Settings still routes an account with no workspace to that screen')
})
