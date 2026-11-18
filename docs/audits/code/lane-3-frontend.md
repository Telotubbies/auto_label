# Lane 3 — frontend code audit (`apps/frontend/src`)

Branch `feat/labeldesk-v2`. Read-only audit; nothing was edited. Scope: `apps/frontend/src/` minus
`lib/api-types.gen.ts` and `*.gen.ts`. Baseline from the orchestrator: `npx tsc --noEmit` in
`apps/frontend` → exit 0, no errors, so every item below is dead weight or duplication, not a type
error.

Method: no tool in the toolchain exists for this (see `## Tool output`), so the counts come from
three throwaway Node scans over `src` (unused exports, props passed nowhere, function/JSX depth)
plus `grep`. Every finding cites a line I read.

---

## Finding 1 — Two complete chart toolkits, ~440 lines of parallel implementation

`features/insights/charts.tsx` (375 lines) and `features/project/insights/Chart.tsx` (224 lines) both
implement the same seven things, for two halves of the UI that look identical to a user.

`Evidence:`

| Concern | Copy A (`features/insights/charts.tsx`) | Copy B (`features/project/insights/Chart.tsx`) |
| --- | --- | --- |
| colour normaliser | `toRgb` :32 (canvas paint + `colorCache`) | `cssColor` :20 (hand-rolled oklch→linear-sRGB matrix) |
| theme reader | `useChartTheme` :57 (32 lines, `MutationObserver`) | `useChartTheme` :61 (21 lines, `matchMedia` only) |
| chart card | `ChartCard` :262 (toggle + PNG/CSV/JSON dropdown, 70 lines) | `ChartCard` :164 (toggle + CSV button, 77 lines) |
| table | `DataTable` :334 | `DataTable` :142 (local, not exported) |
| skeleton | `ChartSkeleton` :360, `PageSkeleton` :370 | `ChartSkeleton` :116, `PageSkeleton` `features/project/Insights.tsx`:33 |
| error | `ErrorState` :384 | `PanelError` :107 |
| CSV | `toCsv` :236 + `saveFile` :225 | `csvCell` :126 + `downloadCsv` :131 (own BOM + filename slug) |

Both call `echarts.use([...])` with different component sets (A: `DataZoom`, `MarkLine`, `VisualMap`;
B: `Aria`, `AxisPointer`, `Brush`, `Toolbox`), so the two halves of Insights load different ECharts
plugins — a direct bundle-size cost.

`Why safe:` merging leaf helpers does not touch series options; only the exported helper bodies move.

`Risk:` helper-by-helper low; the whole merge high (export menus differ: A offers JSON + PNG, B only
CSV; table cell styling differs; CSV filename slug differs).

`LOC removed:` 40 for the leaf half (colour, skeleton, table, error), ~200 for the full merge.

`Test coverage:` none — `features/insights/charts.tsx` and `Chart.tsx` appear in no test
(`grep` over `apps/frontend/tests`). Card adds a node test for the merged helper first.

`Card candidate:` yes, staged.
1. Unify the colour normaliser: keep `toRgb` (canvas path, already handles space-separated `rgb()`
   and oklch), delete `cssColor` (`Chart.tsx`:20-44, 25 lines) and re-import. Low.
2. One `ChartSkeleton` and one `PageSkeleton` in `features/insights/charts.tsx`, delete
   `Chart.tsx`:116-124 and `Insights.tsx`:33-49 (21 lines). Low.
3. One `DataTable`: delete `Chart.tsx`:142-162, map `ChartTable` → `DataTable` props at the
   `Chart.tsx`:224 call. Low.
4. One error component: delete `PanelError` (`Chart.tsx`:107-113) and `ErrorNote`
   (`features/project/qa/shared.tsx`:11-17), use `ErrorState`. Low.

---

## Finding 2 — ProjectSettings re-implements `useProjectPermissions`

`apps/frontend/src/features/project/ProjectSettings.tsx:36-40`

`Evidence:` the hook exists at `lib/perms.ts:9-26` with the same query key and query fn:

```ts
// ProjectSettings.tsx:36-40
const perms = useQuery({
  queryKey: ['permissions', ws, project.slug], queryFn: () => api.permissions(ws, project.slug),
  enabled: !admin, retry: false, staleTime: 60_000,
})
const manager = admin || perms.data?.project_role === 'manager'
```

25 other files use `useProjectPermissions(ws, project)` instead.

`Why safe:` same key, same fn, same derived boolean (`isManager`). The only difference is
`enabled: !admin`, i.e. admins skip the request. Swapping to the hook adds one cached request per
admin visit to project settings (the key is already populated by `ProjectLayout`:22 on every project
route, so in practice it is a cache hit).

`Risk:` low.

`LOC removed:` 4 of 5 lines (`manager = admin || isManager`).

`Test coverage:` `project-screen-permissions.test.mjs` does not cover `ProjectSettings.tsx`; no
regression risk from the tests, and the added request is the reason to add one node test asserting
`enabled` behaviour if the hook gains an option.

`Card candidate:` yes — 1-line swap plus a `enabled` option on the hook.

---

## Finding 3 — `upload()` is a third, weaker transport: no token refresh, mangled validation errors

`apps/frontend/src/lib/api/client.ts:77-92` vs `:47-65` (`req`) and `:109-129` (`download`).

`Evidence:`
- `req` (:55) and `download` (:114) both retry once through `tryRefresh()` on 401. `upload` (:84-88)
  does not — an expired access token (`security.py:15`, `ACCESS_TTL = 15 * 60`) makes the three big
  uploads fail with "Unauthorized" instead of refreshing: `features/project/Upload.tsx:111`,
  `features/project/VideoTimeline.tsx:161`, `features/project/Deploy.tsx:32`.
- `req` (:61) flattens FastAPI validation errors (`d.detail.map(x => x.msg).join(', ')`).
  `upload` (:87) does `new ApiError(x.status, d.detail || x.statusText)` → for a 422 with
  `detail: [{...}]` the toast prints `[object Object]`.
- A fourth shape, `store.ts:26-33` `authRequest`, throws a plain `Error` with its own
  detail-fallback chain (`detail?.[0]?.msg ?? 'Something went wrong'`), so callers cannot tell a
  network failure from a 401 by type.

`Why safe:` making `upload` reuse the same 401 and detail handling only changes paths that
currently fail.

`Risk:` low for the detail flattening; medium for the 401 retry (an XHR retry must re-send the same
`FormData`, which is still valid, but it doubles traffic on a genuinely dead refresh token).

`LOC removed:` ~6 (one shared `errorMessage(r)` + `authHeaders()` helper used by all three).

`Test coverage:` none. Card adds a node test over a pure `errorMessage(detail, statusText)` helper
(the retry itself needs the Playwright spec `e2e/core-loop.spec.ts`).

`Card candidate:` yes — extract `errorMessage()` and use it in `req`, `upload`, `download`,
`store.authRequest`; then add the 401 path to `upload`.

---

## Finding 4 — BUG: a failed `GET /api/me` logs the user out of the UI

`apps/frontend/src/routes/guards.tsx:31-37`

`Evidence:`

```ts
const me = useQuery({ queryKey: ['me'], queryFn: api.me })
if (me.isLoading) return <Loading />
if (!me.data) return <Navigate to="/login" replace />
```

`me.data` is undefined for both "401" and "the API is down / 500 / offline". Any backend hiccup on
the first load of a workspace route sends an authenticated user (valid refresh token still in
`localStorage`) to `/login`, and `store.authed` stays `true` because nothing cleared it. The same
pattern is at `:46-49` (`Home0`) and `:88` (`AccountGate`).

`Why safe:` (for the fix) distinguish `me.isError` from "no session" and render a retry instead of a
redirect.

`Risk:` medium — guards decide routing for every page.

`LOC removed:` 0 (net +3).

`Test coverage:` `feature-flags.test.mjs` reads `src/routes/**` but only asserts `<FlagGate flag=…>`;
no test covers this branch.

`Card candidate:` yes — bug card, fix + assert `isError → not a redirect` in the guard.

---

## Finding 5 — BUG: `Dataset` renders nothing when the image request fails

`apps/frontend/src/features/project/Dataset.tsx:153-156`

`Evidence:` the body only has

```tsx
{(imgs.isLoading || !selectionResolved) && <div className="py-20 text-center"><Spinner /></div>}
{imgs.isSuccess && !items.length && <EmptyState title="No images match these filters." … />}
```

No `imgs.isError` / `imgs.error` branch anywhere in the file (4 `useQuery`, 0 `isError`). A 500 on
`GET /ws/{ws}/projects/{p}/images` leaves an empty scroll area with no message — and the filter bar
still looks live. Compare `VideoTimeline.tsx:284-289`, which does render `videos.isError` with a
Retry.

`Why safe:` adding an error branch changes only the failed path.

`Risk:` low.

`LOC removed:` 0 (net +4, reusing the existing `ErrorState`).

`Test coverage:` `parity-guard-area2.test.mjs` and `project-screen-permissions.test.mjs` read this
file but assert permissions only. Card adds a small node check that the file renders `ErrorState`.

`Card candidate:` yes.

---

## Finding 6 — Nine copies of `fmtInt`, three `fmtBytes`, three `pct`

`Evidence:`

- `const fmt = (n: number) => n.toLocaleString()` — byte-identical in
  `features/lineage/Lineage.tsx:35`, `features/workspace/Dashboard.tsx:19`,
  `features/project/DatasetHealth.tsx:26`, `features/project/HealthCheck.tsx:37`,
  `features/project/insights/VersionsOps.tsx:9`, `features/project/insights/Overview.tsx:6`,
  `features/project/insights/Leakage.tsx:10`, `features/project/insights/Embeddings.tsx:11`,
  `features/project/insights/DataQuality.tsx:10`. Variants: `fmtInt` (`features/streams/Streams.tsx:37`,
  `StreamDetail.tsx:17`, `StreamAnalytics.tsx:25` — the latter two guard `Number.isFinite`).
- bytes: `features/streams/Streams.tsx:36` (1024-based, B/KB/MB, 0-decimal KB) vs
  `features/project/EdgeExport.tsx:8` (1000-based, B/KB/MB/GB, 2-decimal GB) vs
  `features/settings/Settings.tsx:862` `fmtStorage` (1024-based, MB/GB only). The same model
  artifact is printed as `1.0 GB` on one page and `1.07 GB` on another.
- percentages: `pct(v)` with `toFixed(1)` in `features/project/Models.tsx:16` **and**
  `features/insights/EvaluationTab.tsx:16` (byte-identical, 2 copies), `pct(v)` with `Math.round` in
  `features/project/qa/shared.tsx:4`; `pct(part, whole)` in `DatasetHealth.tsx:27`,
  `HealthCheck.tsx:38`, `VersionsOps.tsx:10`, `Overview.tsx:7`; `pct` in `AdminConsole.tsx:14`;
  `fmtPct` `features/project/Suspects.tsx:31`; `pct` `StreamAnalytics.tsx:49` returns `'—'` where the
  others return `0`.

`Why safe:` pure functions, same input domain, same output strings if the canonical version keeps the
existing rounding per call site (group by behaviour, not by name).

`Risk:` low (but must not silently change `'—'` vs `0` where the UI relies on it).

`LOC removed:` ~24 (11 one-liners + imports).

`Test coverage:` none for these helpers. Card adds node tests for `fmtInt`/`fmtBytes`/`pct1`/`pct0`
first — `apps/frontend/tests/*.test.mjs` already imports `.ts` modules directly, so this is cheap.

`Card candidate:` yes — new `lib/format.ts` with `fmtInt`, `fmtPct1`, `fmtPct0`, `pctOf(part, whole)`,
`fmtBytes`.

---

## Finding 7 — Three "pair (seconds, milliseconds)" danger zones: `fmtTime` means two things

`Evidence:`

- `features/streams/StreamDetail.tsx:20` — `fmtTime(t)` = `new Date(t * 1000)` (**seconds**), prints
  date + time.
- `features/editor/Panels.tsx:38` — `fmtTime(t)` = `new Date(t)` (**milliseconds**), prints time only.
  Its data arrives as ms on purpose (`apps/backend/app/routers/images.py:625` returns
  `r.created * 1000`).
- `features/governance/AuditLog.tsx:11` — `fmtClock(t)` = `new Date(t * 1000)` (**seconds**), time only.
- `components/ui.tsx:211` — `fmtDate(t)` = `new Date(t * 1000)` (**seconds**).
- Raw `new Date(x * 1000).toLocaleString()` inlined again in
  `features/streams/StreamAnalytics.tsx:187`, `features/project/EventSearch.tsx:255`,
  `features/dashboards/DashboardEditor.tsx:220`.

Two different functions with the same name and different units is one copy-paste away from a 1970
timestamp; nothing in the codebase documents which unit a timestamp field carries.

`Why safe:` moving the three functions into one module with unit-suffixed names (`fmtDateSec`,
`fmtClockSec`, `fmtClockMs`) and keeping their bodies identical changes no output. Callers change
only by import.

`Risk:` low (mechanical), medium if a call site is guessed wrong — hence the unit suffix.

`LOC removed:` ~8.

`Test coverage:` none. Card adds a node test pinning each formatter against a fixed epoch.

`Card candidate:` yes — `lib/time.ts`.

---

## Finding 8 — Three job-status sets and twelve inline poll predicates

`Evidence:`

- `const ACTIVE = new Set(['queued','running','cancelling'])` — byte-identical in
  `components/shell/JobTray.tsx:16` and `features/workspace/Dashboard.tsx:18`;
  `const ACTIVE = new Set(['queued','running'])` in `features/project/Insights.tsx:30` and
  `features/project/Suspects.tsx:32`; `const ACTIVE = new Set(['queued','extracting'])`
  `features/project/VideoTimeline.tsx:13`; `const TERMINAL = new Set([...])`
  `features/project/EventSearch.tsx:12`.
  The drift is already visible: `cancelling` counts as active on the shell tray and the workspace
  dashboard, but not on Insights/Suspects, so a cancelling job stops being polled there.
- The predicate `(q) => q.state.data?.some(j => ['queued','running'].includes(j.status)) ? N : false`
  is written out at `Models.tsx:151,169`, `EdgeExport.tsx:24`, `AnnotateBoard.tsx:31`,
  `VideoTimeline.tsx:80`, `Versions.tsx:198`, `Anomaly.tsx:110`, `Suspects.tsx:71`,
  `Dashboard.tsx:34`, `Insights.tsx:31`, `EventSearch.tsx:53`, `DatasetHealth.tsx:121` — with
  intervals 1200/1500/2000/2500/3000/4000 ms chosen per file.

`Why safe:` replacing literals with one shared `ACTIVE_JOB_STATUSES` set keeps every `has()` answer
only if the set is the union (`queued, running, cancelling`) — that *changes* Insights/Suspects
behaviour for `cancelling` (they would keep polling 2.5 s longer). Ship the shared set + `whileActive`
helper without changing membership, then widen deliberately in a separate change.

`Risk:` low if membership is preserved verbatim per file; medium if unified blindly.

`LOC removed:` ~12.

`Test coverage:` none. Card adds a node test for `whileActive(jobs)` returning the interval/`false`.

`Card candidate:` yes.

---

## Finding 9 — `qs()` exists but two modules hand-roll query strings

`Evidence:` `lib/api/client.ts:98-103` defines `qs()`. `lib/api/search.ts:9,12` and
`lib/api/governance.ts:11,26,27,37,41,43` use it. `lib/api/streams.ts:22-27` writes its own
`URLSearchParams` loop and `lib/api/dataset.ts:14` interpolates `new URLSearchParams(q as …)`
(which also emits a trailing `?` when the filter object is empty).

`Why safe:` `qs` skips exactly `undefined`, `null` and `''` — the same values the streams loop skips;
dataset passes an already-filtered object, so output is identical apart from the dropped trailing `?`.

`Risk:` low.

`LOC removed:` 8.

`Test coverage:` none. No card node test needed (string output is trivially reviewable), but
`search-state.test.mjs` covers the sibling helper style.

`Card candidate:` yes.

---

## Finding 10 — 12 hand-rolled loading/error panes next to three shared ones

`Evidence:` two shared components exist: `features/insights/charts.tsx:370 PageSkeleton` +
`:384 ErrorState`, and `features/project/qa/shared.tsx:7 Loading` + `:11 ErrorNote`. Yet:

- `<div className="flex h-full items-center justify-center"><Spinner /></div>` —
  `features/project/ProjectLayout.tsx:28`, `features/project/Workflows.tsx:135`;
- `<div className="flex justify-center py-16"><Spinner /></div>` — `features/project/Anomaly.tsx:145`;
- `<div className="p-10 text-center"><Spinner /></div>` — `features/project/Suspects.tsx:109`;
- `<div className="flex justify-center p-4"><Spinner /></div>` — `features/project/WorkflowVersions.tsx:36`;
- `<div className="flex h-full items-center justify-center"><Spinner /></div>` — `features/streams/StreamDetail.tsx:781`;
- `<Card …><Spinner /> Loading edge presets…</Card>` — `features/project/EdgeExport.tsx:57`, and the
  same `<Card role="status"><Spinner /> Loading …</Card>` shape at `features/governance/Privacy.tsx:300`,
  `features/settings/Alerts.tsx:238`;
- skeletons: `ChartSkeleton`/`PageSkeleton` (two each, Finding 1), `Settings.tsx:82 TableLoading`,
  `Settings.tsx:907 UsageSkeleton`, `WorkspacePages.tsx:41 DeploymentsSkeleton`,
  `governance/AuditLog.tsx:37 SkeletonRows`, and inline `.skeleton` stacks at
  `VideoTimeline.tsx:291,354`, `project/Insights.tsx:33`.

`Why safe:` each replacement is the same markup with the same roles; pick `qa/shared`'s `Loading`
(promote it to `components/ui.tsx`) and `ErrorState`.

`Risk:` low (cosmetic surfaces), medium for `PageSkeleton` (its `sr-only` text differs: "Loading
insights" vs conversation-free).

`LOC removed:` ~12 plus ~15 for the duplicate skeletons already counted in Finding 1.

`Test coverage:` none. Accessibility strings are the only contract; a node test can pin the `role`
and `aria-live` attributes.

`Card candidate:` yes.

---

## Finding 11 — The same "busy flag + toast + invalidate" action written 33 times

`Evidence:` 30 busy/saving states (`grep 'const \[(busy|saving)'` → `Auth.tsx:171`, `OcrPanel.tsx:181`,
`DashboardEditor.tsx:48`, `Editor.tsx:299`, `Roles.tsx:67,121,215`, `Privacy.tsx:54,95,179,288`,
`Playground.tsx:168`, `Home.tsx:30`, `Alerts.tsx:36,144`, `Settings.tsx:684`, `Anomaly.tsx:104`,
`ZoneEditor.tsx:63`, `Streams.tsx:60,335`, `StreamDetail.tsx:254,329,770`, `Deploy.tsx:25`,
`OtOutputs.tsx:32,126`, `Upload.tsx:59`, `VideoTimeline.tsx:172`, `WorkflowVersions.tsx:12`,
`Workflows.tsx:81`) and 33 inline `catch (e) { toast.err(e as Error) }` handlers, 25 of them followed
by `finally { setX(false) }`.

`Why safe:` an `useAction(fn)` returning `[run, busy]` that wraps `setBusy(true) / try / catch
toast.err / finally setBusy(false)` reproduces the exact sequence; the 8 sites that already use
`.then().catch().finally()` keep their shape.

`Risk:` medium — 25 files, and `StreamDetail.tsx:807` intentionally omits the reset because it
navigates away on success; invalid refactors of that kind of site change a spinner, not data.

`LOC removed:` ~30.

`Test coverage:` none for handlers; the Playwright spec covers upload only. Not worth a card on its
own — bundle with any touch of those files.

`Card candidate:` no (opportunistic cleanup).

---

## Finding 12 — `Settings.tsx` (1168 lines) is 12 page components in one file

`apps/frontend/src/features/settings/Settings.tsx`. It is already a tabbed shell (`:1128-1140` builds
the tab list, `:1150-1163` routes each tab), so each section is an independent island.

`Evidence:`
`Account` :26-51 · `UA_BROWSERS`/`describeDevice` :55-74 · `LOGIN_METHOD` :76-80 ·
`TableLoading`/`TableError` :82-97 · `EmailCard` :99-155 · `TwoFactorCard` :158-403 ·
`SessionsCard` :404-488 · `LoginHistoryCard` :489-547 · `Security` :548-566 · `Appearance` :572-616 ·
`Workspace` :617-679 · `FeatureFlags` :680-737 · `Members` :738-812 · `ApiKeys` :814-873 ·
`MeterCard`/`Usage` :885-1081 · `Trash` :1083-1100 · `FirstRun` :1102-1116 · shell :1118-1168.
`copy` :22-24 is the only helper shared by two sections (security `:276,328` and members/keys
`:752,802,830`).

`Why safe:` each section only reads `useParams`/`useApp`/`useQuery`; the shell keeps the tab array
and the `<Routes>` elements, so routing and the `nav.test.mjs` label assertions are untouched.

`Risk:` low — with one hazard, see below.

`LOC removed:` 541 (account+security, lines 26-566) and 166 (appearance+workspace+flags, 572-737) move
verbatim into `features/settings/AccountSecuritySection.tsx` and `WorkspaceSection.tsx`; `copy` moves
to `lib/clipboard.ts`. `Settings.tsx` ends near 460 lines.

`Test coverage:` `tests/parity-guard-area7.test.mjs:10` reads `Settings.tsx` and slices component
bodies by name (`component('Members()', 'function ApiKeys()')`, `component('Usage()', 'function
Trash()')`, `component('FirstRun()', 'export default function Settings')`). **Keep `Members`,
`ApiKeys`, `Usage`, `Trash` and `FirstRun` in `Settings.tsx`** and the guard keeps passing with no
test edit. `nav.test.mjs:19` asserts tab labels are in `Settings.tsx` — also preserved by keeping the
tab array in the shell.

`Card candidate:` yes — extract lines 26-566 only (biggest win, zero test coupling), then the
workspace block in a follow-up card.

---

## Finding 13 — `Auth.tsx` (1072 lines) is seven page components behind one import

`apps/frontend/src/features/auth/Auth.tsx` exports `Login` :272, `Signup` :369, `Forgot` :469,
`Reset` :543, `VerifyEmail` :626, `AcceptInvite` :707, `MfaGate` :865 on top of a shared shell
(`FACTS` :19, `tidy` :40, `useTitle` :47, `Brand` :55, `Rail` :69, `AuthShell` :95, `AuthCard` :116,
`TextField` :132, `FormError` :148, `Submit` :161, `useSubmit` :170, `useNext` :193, `MfaForm` :207).

`Evidence:` the module is imported as a barrel in three places
(`routes/public.routes.tsx:3`, `routes/account.routes.tsx:2`, `routes/guards.tsx:11`), and every page
is lazy-loaded per route.

`Why safe:` split each page into `features/auth/pages/<Name>.tsx` and keep `Auth.tsx` as the barrel
re-exporting the same seven names — the import surface stays byte-identical.

`Risk:` low.

`LOC removed:` ~800 (pages), leaving ~270 lines of shell; `Auth.tsx` drops to a barrel.

`Test coverage:` no test reads `Auth.tsx` (`grep` over `tests/`), and `e2e/core-loop.spec.ts` walks
login by URL, not by module. Safe to move.

`Card candidate:` yes.

---

## Finding 14 — `Editor.tsx` (1288 lines): a 1060-line component with three clean extractions

`apps/frontend/src/features/editor/Editor.tsx`. `export default function Editor()` runs :229-1288
(28 `useState`, 13 `useEffect`, 6 `useQuery` in one function). Three top-level units before it have
no dependency on Editor state:

- `NumberField` :75-106 (34 lines) + `fmtNum` :59 + `parseNum` :61-64
- `GeometryPanel` :109-214 (106 lines), used once at the geometry panel slot
- `useHtmlImage` :216-228 (13 lines)
- also `insideTransformer` :44-47, `inPoly` :50-57, `wrapAngle` :65 (pure, belong with `culling.ts`
  which already hosts `shapeBounds`/`intersects`)

`Why safe:` all four are pure module-level units; moving them needs only the props already passed.

`Risk:` low.

`LOC removed:` 175 from Editor (1288 → ~1115).

`Test coverage:` `parity-guard-area3.test.mjs:10` and `project-screen-permissions.test.mjs:14` read
`Editor.tsx` and assert on strings inside `Editor()` (`{can('project.review') && <>`,
`Approve</Button>`, `const admin` is in StreamDetail). None of those strings live in the extracted
units, so both tests keep passing.

`Card candidate:` yes — `features/editor/GeometryPanel.tsx`, `NumberField.tsx`, `useHtmlImage.ts`;
pure maths to `culling.ts`.

---

## Finding 15 — `VideoTimeline.tsx`: a 401-line component with a self-contained upload card inside

`apps/frontend/src/features/project/VideoTimeline.tsx:73-448`

`Evidence:` the upload state and handler (:135-169: `fileRef`, `file`, `batch`, `mode`, `num`, `prog`,
`uploading`, `numOk`, `invalidate`, `submit`) never touch the timeline selection, and the JSX block
:235-282 ("Upload a video" `Card`) reads only those. The rest of the component (:171-229 keyframes /
marks / track-forward, :310-448 strip + inspector) is independent.

`Why safe:` the upload card hands one callback (`onUploaded(video)`) back; `setVideoId`,
`setFile`-reset and both `invalidate` calls move with it.

`Risk:` low.

`LOC removed:` 85 from `VideoTimeline()` (→ ~315).

`Test coverage:` no test reads this file. Safe.

`Card candidate:` yes — `features/project/VideoUploadCard.tsx`.

---

## Finding 16 — `StreamDetail.tsx` (866 lines): five panels, one function

`apps/frontend/src/features/streams/StreamDetail.tsx`: `StreamDetail()` is :762-866; everything above
is `ruleName` :34, `ruleDetail` :46, `LivePanel` :66-155, `SummaryPanel` :156-209, `ReadOnlyRules`
:210-250, `TilingSection` :251-312, `RulesSection` :313-525, `EventsTimeline` :526-704,
`EventPreview` :705-761.

`Why safe:` each panel takes `{stream, ws, project}` (or a narrower slice) — no shared mutable state.

`Risk:` low; `project-screen-permissions.test.mjs:76` asserts `canReview =` and `const admin` inside
`StreamDetail()`, and both stay.

`LOC removed:` ~450 from the main component (file → four files under `features/streams/panels/`).

`Test coverage:` `project-screen-permissions.test.mjs:72-78` — preserved as noted.

`Card candidate:` yes.

---

## Finding 17 — Dead exports, dead props and dead branches (small, zero-risk sweep)

`Evidence:`

- `components/ui.tsx:113-115` `Kebab` — 0 references anywhere (its `Dropdown` sibling is used
  directly at 9 call sites).
- `features/dashboards/widgetModel.ts:50` `MAX_WIDGETS = 24` — 0 references; the server enforces the
  same number independently (`apps/backend/app/services/insights_dashboards.py:19,45`), so this is a
  duplicated constant that is already only half-alive.
- `features/insights/charts.tsx:333` `rowHeader = true` — never passed; the two call sites of the
  branch (`:350-352`) are dead.
- `features/insights/charts.tsx:400` `Swatch … dashed` — never passed, so
  `strokeDasharray={dashed ? '4 2' : undefined}` (:404) is always `undefined`.
- `features/landing/primitives.tsx:7-9` `SectionShell … innerClassName` — never passed (4 call sites,
  all `CapabilitiesSection.tsx:141`, `FeaturesBentoSection.tsx:292`, `ShowcaseSection.tsx:302`,
  `CtaFooterSection.tsx:34`).
- `features/project/ProjectSettings.tsx:20,29` `initialTab` — the only call site is
  `routes/project/settings.routes.tsx:7` with no props; `params.get('tab')` is the live path.
- `index.css:95-96` `.truncate-th` — 0 references in `src` (Thai truncation is done inline with
  `[overflow-wrap:anywhere]`).

`Why safe:` unreferenced code and unpassable props; no render path changes.

`Risk:` low (the CSS rule is only a utility).

`LOC removed:` ~15.

`Test coverage:` none; `tsc --noEmit` (already green) is the check, plus the existing suite.

`Card candidate:` yes — one mechanical sweep, no test edit needed.

---

## Finding 18 — `task_36` is a user-visible toggle with no frontend surface

`apps/backend/app/services/flags.py:34` registers `task_36` ("Batch inference…"), and
`features/settings/Settings.tsx:700-730` renders **every** flag the API sends with a `Switch`. The
string `task_36` does not occur anywhere under `apps/frontend/src` (`grep`: 0 hits), and
`lib/nav/project/data.ts` has no batch-inference entry. So an admin can turn it on and see exactly
nothing; the API surface behind it is real (`app/routers/batch_inference.py:18`).

`Why safe:` either hide non-shipped keys from the settings list (server-side allow-list) or label them
— no render logic changes.

`Risk:` low.

`LOC removed:` 0. This is a product/flag-hygiene item, not dead code.

`Test coverage:` `apps/backend/tests/test_flags.py:36` asserts the key exists; no frontend test asserts
that every flag has a consumer.

`Card candidate:` yes (either ship the UI or keep the flag out of the settings list until it has one).

---

## Finding 19 — Complexity: 17-level JSX, 35 functions over 50 lines

`Evidence:` maximum JSX indentation (2-space steps) per file:

| file:line | depth |
| --- | --- |
| `features/editor/Editor.tsx:977` | 17 |
| `features/insights/CompareTab.tsx:358` | 17 |
| `features/lineage/Lineage.tsx:393` | 17 |
| `features/governance/AuditLog.tsx:195` | 15 |
| `features/project/Suspects.tsx:209` | 15 |
| `features/admin/AdminConsole.tsx:138` | 14 |
| `features/project/HealthCheck.tsx:356` | 14 |
| `features/project/VideoTimeline.tsx:384` | 14 |

Functions over 50 lines (brace-matched): `VideoTimeline` 401, `DashboardEditor` 257, `Suspects` 223,
`AdminConsole` 221, `DatasetHealth` 202, `WorkflowDarkSection` 192, `AuditLog` 178, `Upload` 168,
`Dataset` 167, `SearchPage` 166, `EventSearch` 157, `project/Insights` 157, `Classes` 149,
`Workflows` 141, `Train` 125, `widgetModel.buildWidgetOption` 121, `Deploy` 119, `Dashboards` 117,
`Alerts` 116, `PrivacyWorkspace` 111, `AnnotateBoard` 106, `Streams` 101, `Home` 98, `WorkspaceRoles`
93, `Login` 92 (35 total).

`Why safe:` depth alone is not a defect; the actionable part is the three 17-level blocks, each of
which is a table row wrapper that can become a small local component.

`Risk:` low per extraction, medium for `VideoTimeline`/`DashboardEditor` (Finding 15 covers the former).

`LOC removed:` 0 (restructure, not deletion).

`Test coverage:` none for JSX shape. Do not card this alone; attach to Findings 12-16.

`Card candidate:` no (fold into the file-splitting cards).

---

## Finding 20 — Two confirmation idioms

`Evidence:` 23 native `confirm()`/`prompt()` calls (`Home.tsx:115,126,127,143,146`, `Roles.tsx:245`,
`Streams.tsx:359`, `StreamDetail.tsx:800`, `Settings.tsx:414,417,795,839,1094`, `Alerts.tsx:69`,
`CollectionsPanel.tsx:103,162`, `Classes.tsx:119,120,135,136`, `Dataset.tsx:145,148`, `Models.tsx:248`,
`OtOutputs.tsx:143`, `Versions.tsx:151`, `Consensus.tsx:118`, `ProjectSettings.tsx:91`,
`Honeypots.tsx:96`) next to three `<Modal>` confirm dialogs (`Dashboards.tsx:112`,
`DashboardEditor.tsx:276`, `Roles.tsx:196`) that also confirm a delete.

`Why safe:` no change proposed — recorded so exactly one card can pick a side later.

`Risk:` n/a.

`LOC removed:` 0 by itself.

`Test coverage:` `parity-guard-area7.test.mjs:27-31` pins the literal `'Leave this workspace?'` and
`` `Remove ${m.name}?` `` strings in `Members()`, so a modal migration must keep those strings.

`Card candidate:` no (pattern note only).

---

## Tool output

Commands run in `apps/frontend` with the installed toolchain (Node 22.20.0), verbatim results:

1. `npx --no-install knip --reporter compact`
   ```
   npm error npx canceled due to missing packages and no YES option: ["knip@6.45.1"]
   EXIT=1
   ```
   knip is not installed (`apps/frontend/node_modules/.bin/knip.cmd` absent). Not installed, per
   instructions.

2. `npx --no-install ts-prune`
   ```
   npm error npx canceled due to missing packages and no YES option: ["ts-prune@0.10.3"]
   EXIT=1
   ```

3. `npx --no-install depcheck`
   ```
   npm error npx canceled due to missing packages and no YES option: ["depcheck@1.4.7"]
   EXIT2=1
   ```

Fallback (grep-based, as instructed):

| measurement | value |
| --- | --- |
| `src` files scanned (`.ts`/`.tsx`, excluding generated) | 160 |
| `export function/const/type/interface/class` declarations | 632 |
| exports referenced **nowhere outside their own file** | 90 (23 values, 67 types) |
| of those, referenced **nowhere at all** (truly dead) | 2 — `components/ui.tsx:113 Kebab`, `features/dashboards/widgetModel.ts:50 MAX_WIDGETS` |
| type exports used only inside their own file | 60 (shape definitions — not dead, just over-exported) |
| files never imported | 0 (only `main.tsx`, `vite-env.d.ts`, `lib/api-types.gen.ts`, i.e. entry + generated) |
| components scanned for props | 203 |
| components with ≥1 prop that is never passed | 4 (`DataTable.rowHeader`, `Swatch.dashed`, `SectionShell.innerClassName`, `ProjectSettings.initialTab`) |
| `useQuery({` call sites | 136 |
| `isError` references | 67 |
| inline `catch (x) { toast.err(x as Error) }` | 33 |
| `finally { setX(false) }` busy resets | 25 |
| functions > 50 lines | 35 |
| max JSX indent (levels of 2 spaces) | 17 |
| `console.log` / `debugger` / commented-out JSX | 0 / 0 / 0 |
| orphaned CSS classes in `index.css` | 1 (`.truncate-th`) |

`tsc --noEmit` baseline (exit 0) was taken by the orchestrator and not re-run.

## Note

Nothing in `apps/frontend/src` was modified. Scratch scripts live in
`B:/02_Projects/ld-tmp/pytest/` (`unused-exports.mjs`, `unused-props.mjs`, `long-fns.mjs`,
`jsx-depth.mjs`, `prop-counts.mjs`).
