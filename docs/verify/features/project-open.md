# Feature: open a project

From the workspace home into the project's dataset. Proven by `apps/frontend/e2e/core-loop.spec.ts`,
**step 2, Open project**. This file is the feature reference for [VERIFY.md](../VERIFY.md).

## Starting state

- Signed in as `demo@labeldesk.dev` (see [auth.md](auth.md)).
- The workspace `/labeldesk-demo` is open, with the seeded project `PPE Detection` (`ppe-detection`)
  visible under the `Projects` heading.
- The demo seed populated the project's dataset; a missing project is a BLOCKED seed, not an empty
  workspace.

## Route

| Step | URL |
| --- | --- |
| Start | `http://127.0.0.1:<webPort>/labeldesk-demo` |
| After the project card | `http://127.0.0.1:<webPort>/labeldesk-demo/p/ppe-detection/browse` |

## Selectors

| Element | Selector used by the spec |
| --- | --- |
| Project list region | `[data-tour="home-projects"]` |
| Project card link | `getByRole('link', { name: /PPE Detection/ }).first()` inside the region |
| Dataset heading | `getByRole('heading', { name: 'Dataset' })` |
| Breadcrumb | `getByRole('navigation', { name: 'Breadcrumb' })` |
| Breadcrumb project link | `getByRole('link', { name: 'PPE Detection' })` inside the breadcrumb |

## Actions and expected result

1. On `/labeldesk-demo`, find the `PPE Detection` card inside the projects region and click its link.
   - Expected: the URL is `/labeldesk-demo/p/ppe-detection/browse`.
   - Expected: the `Dataset` heading is visible.
   - Expected: the breadcrumb contains the `PPE Detection` link.
2. Confirm the dataset route is the landing page for the project, not an editor or a legacy
   `:project/*` route.
   - Expected: every later project step (upload, annotate, version) starts from this route.

## Failure conditions

| Symptom | Meaning |
| --- | --- |
| No `PPE Detection` card | the demo seed or the project slug changed; BLOCKED, fix the seed before testing the feature |
| Card click stays on `/labeldesk-demo` | the project link is missing or the router guard rejected the workspace |
| URL is a legacy path such as `/labeldesk-demo/ppe-detection` | the v3 route map regressed; the card under test is wrong |
| `Dataset` heading absent, or the page shows an error state | the dataset request failed; join it by `request_id` in the API log |
| Breadcrumb lacks the project link | the stage header regressed; a UI finding for the owning card |

## Evidence

- The step result and the final screenshot from `$evidence/playwright-report/`.
- The `/api/ws/labeldesk-demo/projects` (or the project payload) request line in the API log, joined
  by `request_id`, when the failure is data-shaped rather than visual.
