// Uploads outlive the 15-minute access token: a 401 must refresh once and resend the same body.
//   node --test tests/api-upload-refresh.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
}
globalThis.window = { dispatchEvent() {} }

const { upload, ApiError } = await import('../src/lib/api/client.ts')

/** A fake XHR that records the bearer token of every attempt and answers from `plan`. */
function fakeXhr(plan) {
  const attempts = []
  globalThis.XMLHttpRequest = class {
    constructor() {
      this.upload = {}
      this.status = 0
      this.responseText = ''
    }
    open() {}
    setRequestHeader(name, value) { if (name === 'Authorization') this.auth = value }
    send(body) {
      attempts.push({ auth: this.auth, body })
      const [status, payload] = plan(attempts.length)
      this.status = status
      this.responseText = typeof payload === 'string' ? payload : JSON.stringify(payload)
      this.onload()
    }
  }
  return attempts
}

test('a 401 upload refreshes the token once and resends the same form', async () => {
  store.clear()
  store.set('ld_token', 'stale')
  store.set('ld_refresh', 'refresh-1')
  const refreshes = []
  globalThis.fetch = async (url, init) => {
    refreshes.push({ url: String(url), body: init.body })
    return { ok: true, json: async () => ({ token: 'fresh', refresh_token: 'refresh-2', session: 'sess' }) }
  }
  const attempts = fakeXhr((n) => (n === 1 ? [401, { detail: 'token expired' }] : [201, { id: 'img-1' }]))

  const form = new FormData()
  form.set('image', 'x')
  const out = await upload('/ws/w/projects/p/images', form, () => {})

  assert.equal(refreshes.length, 1, 'the upload must refresh the access token exactly once')
  assert.equal(attempts.length, 2, 'a 401 must be retried once, not surfaced to the user')
  assert.equal(attempts[1].auth, 'Bearer fresh', 'the retry must carry the refreshed token')
  assert.equal(attempts[1].body, form, 'the same FormData must be resent')
  assert.deepEqual(out, { id: 'img-1' })
})

test('a successful upload sends once and keeps the current token', async () => {
  store.clear()
  store.set('ld_token', 'good')
  globalThis.fetch = async () => { throw new Error('no refresh expected') }
  const attempts = fakeXhr(() => [200, { id: 'img-2' }])
  await upload('/ws/w/projects/p/images', new FormData(), () => {})
  assert.equal(attempts.length, 1)
  assert.equal(attempts[0].auth, 'Bearer good')
})

test('a failed upload shows the server detail, including validation arrays', async () => {
  store.clear()
  store.set('ld_token', 'good')
  fakeXhr(() => [422, { detail: [{ msg: 'image: field required' }] }])
  await assert.rejects(
    () => upload('/ws/w/projects/p/images', new FormData(), () => {}),
    (e) => e instanceof ApiError && e.message === 'image: field required',
  )
})
