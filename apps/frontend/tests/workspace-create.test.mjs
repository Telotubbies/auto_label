// T-010: the signup and first-run screens show the workspace address before submit.
// The preview must use the API's own rule (`apps/backend/app/routers/auth.py:slugify_workspace`)
// so the line the person reads is the slug the server creates.
//   node --test tests/workspace-create.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import { workspaceLinkCopy, workspaceSlug } from '../src/lib/slug.ts'

const CASES = [
  ['Acme Labs', 'acme-labs'],
  ['Café Labs', 'caf-labs'],
  ['  Lots   of   SPACE  ', 'lots-of-space'],
  ['a'.repeat(80), 'a'.repeat(40)],
  ['Settings', 'settings-ws'],
  ['Playground', 'playground-ws'],
]

test('test_slugify_matches_the_server_rules', () => {
  for (const [name, expected] of CASES) {
    assert.equal(workspaceSlug(name), expected, `workspaceSlug(${JSON.stringify(name)})`)
  }
  assert.equal(workspaceSlug(''), 'workspace')
})

test('test_availability_copy_covers_empty_loading_taken', () => {
  assert.equal(workspaceLinkCopy('empty', 'acme'), 'Your workspace link: /acme')
  assert.equal(workspaceLinkCopy('loading'), 'Checking…')
  assert.equal(workspaceLinkCopy('taken', 'acme', 'acme-2'), 'Taken — try acme-2')
  assert.equal(workspaceLinkCopy('invalid'), 'Use letters, numbers and dashes')
})
