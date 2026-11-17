// A failed GET /me must not sign the user out: only a 401 means the session is gone.
//   node --test tests/me-gate-policy.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
}

const { meNeedsLogin } = await import('../src/routes/mePolicy.ts')
const { ApiError } = await import('../src/lib/api/client.ts')

test('a 401 ends the session', () => {
  assert.equal(meNeedsLogin(new ApiError(401, 'unauthorized')), true)
})

test('a server failure keeps the session and offers retry', () => {
  assert.equal(meNeedsLogin(new ApiError(500, 'internal error')), false)
})

test('a network failure keeps the session and offers retry', () => {
  assert.equal(meNeedsLogin(new ApiError(0, 'network error')), false)
  assert.equal(meNeedsLogin(new TypeError('Failed to fetch')), false)
  assert.equal(meNeedsLogin(undefined), false)
})
