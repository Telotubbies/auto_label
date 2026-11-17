# Feature: upload an image

From an open project to a labelled dataset row. Proven by `apps/frontend/e2e/core-loop.spec.ts`,
**step 3, Upload**. This file is the feature reference for [VERIFY.md](../VERIFY.md).

## Starting state

- Signed in, with `PPE Detection` open on `/labeldesk-demo/p/ppe-detection/browse` (see
  [project-open.md](project-open.md)).
- The run uses Playwright's throwaway data directory, so the upload never writes to
  `apps/backend/data` and never changes a real workspace.
- The fixture exists: `apps/frontend/e2e/fixtures/one.jpg` (a real 640×480 JPEG).

## Route

| Step | URL |
| --- | --- |
| Start | `http://127.0.0.1:<webPort>/labeldesk-demo/p/ppe-detection/browse` |
| After the Upload link | `http://127.0.0.1:<webPort>/labeldesk-demo/p/ppe-detection/upload` |
| After View Dataset | `http://127.0.0.1:<webPort>/labeldesk-demo/p/ppe-detection/browse` |

## Selectors

| Element | Selector used by the spec |
| --- | --- |
| Upload link | `getByRole('link', { name: 'Upload' })` |
| Page heading | `getByRole('heading', { name: 'Upload Data' })` |
| File input | `locator('input[type=file]').first()` |
| Submit | `getByRole('button', { name: 'Save and Continue' })` |
| Result summary | `getByText(/Uploaded 1 .* failed 0/)` |
| Return to dataset | `getByRole('button', { name: 'View Dataset' })` |
| Review filter | `getByRole('combobox').first()` with option `all` |
| Filename search | `getByPlaceholder('Search filename')` |
| Dataset row | `getByRole('button', { name: 'Open one.jpg in the editor' })` |

## Actions and expected result

1. On the dataset, click **Upload**.
   - Expected: the URL ends `/upload` and the `Upload Data` heading is visible.
2. Set the first file input to `e2e/fixtures/one.jpg`; click **Save and Continue**.
   - Expected: within 30 seconds the summary matches `Uploaded 1 … failed 0`.
   - Expected: the run has no rejected upload; a duplicate or a refusal is a failure of this step.
3. Click **View Dataset**.
   - Expected: the URL ends `/browse` and the `Dataset` heading is visible.
4. Set the first combobox to `all` (a fresh upload has no labels, and the reviewer default shows
   approved images only); type `one.jpg` in **Search filename**.
   - Expected: the row button `Open one.jpg in the editor` is visible.

## Failure conditions

| Symptom | Meaning |
| --- | --- |
| No `Upload Data` heading | the upload route or its permission gate regressed (`project.upload`) |
| Summary says failed `1`, or never appears | the fixture, the storage path or the decoder failed; read the API log and the upload response by `request_id` |
| Summary says uploaded `0` | the file input did not receive the fixture; a harness change, not a product pass |
| `View Dataset` stays on the upload page | navigation or the result payload regressed |
| `one.jpg` is absent with filter `all` and the filename search | the row was not persisted, or the grid filter no longer matches; a finding for the owning card |
| A console error appears | a frontend regression; the spec fails on it at the end of the core loop |

## Evidence

- The summary is asserted in step 3; the HTML report, trace and screenshot show the upload page and
  the dataset row.
- The upload request and the dataset search request in `$evidence/e2e-api.log`, joined by
  `request_id`, when the failure is server-side.
