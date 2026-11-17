// One id per logical API call, reused across the 401→refresh retry, and shown under the error toast.
//   node --test tests/request-id.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'

const store = new Map()
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
}
globalThis.window = { dispatchEvent() {} }
globalThis.URL.createObjectURL = () => 'blob:x'
globalThis.URL.revokeObjectURL = () => {}
globalThis.document = { createElement: () => ({ click() {}, remove() {} }), body: { appendChild() {} } }

const { req, download, upload, requestRef, ApiError } = await import('../src/lib/api/client.ts')

const sent = []
/** A stubbed fetch that records the request id of every attempt and answers from `plan`. */
function stubFetch(plan, echoId) {
  globalThis.fetch = async (url, init = {}) => {
    const headers = init.headers ?? {}
    const id = headers['X-Request-Id']
    sent.push({ url: String(url), id })
    const [status, body] = plan(String(url))
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: 'stub',
      headers: { get: (n) => (n === 'X-Request-Id' ? echoId ?? id ?? null : null) },
      json: async () => body,
      blob: async () => new Blob(),
    }
  }
}

/** A fake XHR for the upload path: it records the id header and answers from `plan`. */
function stubXhr(plan) {
  const attempts = []
  globalThis.XMLHttpRequest = class {
    upload = {}
    status = 0
    responseText = ''
    open() {}
    setRequestHeader(name, value) { if (name === 'X-Request-Id') this.id = value }
    send() {
      attempts.push({ id: this.id })
      const [status, body] = plan()
      this.status = status
      this.responseText = JSON.stringify(body)
      this.onload()
    }
  }
  return attempts
}

const ID16 = /^[A-Za-z0-9_-]{16}$/

test('test_each_call_sends_a_request_id', async () => {
  store.clear()
  store.set('ld_token', 'tok')
  sent.length = 0
  stubFetch(() => [200, { ok: true }])

  await req('/health')
  await req('/health')
  assert.equal(sent.length, 2)
  assert.ok(sent.every((c) => ID16.test(c.id)), 'every call carries a 16-char id')
  assert.notEqual(sent[0].id, sent[1].id, 'one id per logical call')

  sent.length = 0
  await download('/ws/w/projects/p/versions/v1/export.zip', 'export.zip')
  assert.ok(ID16.test(sent[0].id), 'download carries an id too')

  const attempts = stubXhr(() => [200, { id: 'img-1' }])
  await upload('/ws/w/projects/p/upload', new FormData(), () => {})
  assert.ok(ID16.test(attempts[0].id), 'upload carries an id too')
})

test('test_a_retry_reuses_the_same_id', async () => {
  store.clear()
  store.set('ld_token', 'stale')
  store.set('ld_refresh', 'refresh-1')
  sent.length = 0
  let healthCalls = 0
  stubFetch((url) => {
    if (url.endsWith('/api/auth/refresh')) return [200, { token: 'fresh', refresh_token: 'r2', session: 's' }]
    healthCalls += 1
    return healthCalls === 1 ? [401, { detail: 'token expired' }] : [200, { ok: true }]
  })

  await req('/health')
  const attempts = sent.filter((c) => c.url.endsWith('/api/health'))
  assert.equal(attempts.length, 2, 'the 401 is retried once')
  assert.ok(ID16.test(attempts[0].id), 'the first attempt carried an id')
  assert.equal(attempts[1].id, attempts[0].id, 'the retry reuses the id of the call the user made')
})

test('test_an_error_toast_shows_the_id', async () => {
  // The formatter the toast renders under the message: quote it and the API line is one grep away.
  assert.equal(requestRef(new ApiError(500, 'Save failed', 'abc12345')), 'Ref abc12345')
  assert.equal(requestRef(new Error('Save failed')), '', 'a plain error has no id line')
  assert.equal(requestRef('a plain string toast'), '')

  store.clear()
  store.set('ld_token', 'tok')
  stubFetch(() => [500, { detail: 'Save failed' }], 'abc12345')
  await assert.rejects(() => req('/save'), (e) => e instanceof ApiError && e.message === 'Save failed'
    && requestRef(e) === 'Ref abc12345', 'the response header reaches the toast line')
})
