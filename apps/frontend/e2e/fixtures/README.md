# e2e fixtures

Everything a journey spec needs that is not the app itself. Paths stay inside `e2e/`: no font, image
or data file is read from anywhere else.

| File | What it is |
| --- | --- |
| `harness.ts` | The one import a spec starts with: `signIn`, `setFlags`, `record`, `axe`, `stubApi`, `seeded`. |
| `one.jpg` | The upload fixture `core-loop.spec.ts` uses (a real 640×480 JPEG). |
| `frame.jpg` | A 320×180 **PNG saved with a `.jpg` name**, committed as bytes. A stream spec fulfils its MJPEG route from these bytes, so the live view renders without a decoder, a camera or a GPU. It is a UI contract, not capture. |

## Running

From `apps/frontend`:

```
npm run e2e           # smoke set: every spec not tagged @nightly
npm run e2e:nightly   # every spec, including @nightly
```

Both start the same two servers: `apps/backend` through `e2e/app.py` (the real API with the fake
worker) and the Vite dev server. `playwright.config.ts` picks free ports and a fresh data directory
under `%TMP%`, seeds the demo workspace and never touches `apps/backend/data`.

## When the API is missing

The API runs under `LD_E2E=1` and writes its output to `%TMP%/labeldesk-e2e-api.log`. A sign-in that
cannot reach it fails with that path in the message instead of waiting for a timeout, and the API
refuses to start at all without `LD_E2E=1` or with `LD_ENV=production`.

## Adding a spec

```ts
import { test, expect } from '@playwright/test'
import { signIn, setFlags, record, seeded } from './fixtures/harness'

test('J9 the gate camera counts a person', async ({ page, request }) => {
  await setFlags(request, ['task_10b'])          // before the first navigation
  await signIn(page)
  record.step()
  ...
  expect(record.done({ steps: 8, timeMs: 120_000 })).toMatchObject({ ok: true })
})
```

`stubApi(page, url, { status, body, delayMs, times })` forces the empty, loading and error states:
`body: []` for empty, `delayMs` for loading, `status: 503` (or `times: 1`) for a failure and its retry.
`record.reset()` restarts the counter between two tests in one file.
