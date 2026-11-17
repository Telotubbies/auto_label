DONE

# T-475 — Every internal link through one path helper

Branch `t/475`, worktree `B:\02_Projects\ld-worktrees\t-475`, base `feat/labeldesk-v2` `a213d8e`.
No merge, no push, no rebase, no branch deletion; only this worktree was written.

## Options considered (smallest first)

| # | Design | Prod LOC (est.) | Files | Trade-off |
| --- | --- | --- | --- | --- |
| A | Convert only the card's 10 listed files; test scans the whole tree | ~30 | 1 helper + 10 | **Rejected:** card acceptance says the literal `` `/${ws}/${ `` is gone from all of `src/features` and `src/components`; 30 sites in 17 other files would still fail the card's own test |
| B | Add `backPath` next to `projectPath`, then sweep every matching literal to the helper (chosen) | ~45 changed + 5 helper | 1 helper module + 27 components + 3 test files | Touches 17 files the card's inventory forgot; each edit is a link string only, no behaviour or gate change |
| C | New `lib/projectLinks.ts` wrapper module + same sweep | ~70 | +1 module | Extra indirection for no gain; `routes.ts` already is "one place that builds a project URL" |

**Picked B** — it is the only design that satisfies the card's acceptance test ("the literal no longer appears") and its title ("every internal link"), at the smallest diff. C adds a second path module for nothing. A passes review optics but leaves the card's own test red.

No UI surface, layout, copy or style was added, so `REDESIGN.md`/`VISUAL-OVERRIDE.md` glass rules had nothing to bind: this card only changes the strings inside existing links. No flag, no route, no API, no OpenAPI change.

## What I did (plain words)

1. Added `backPath(ws, project, { review })` to `apps/frontend/src/lib/routes.ts`, beside `projectPath`: review mode → `/w/p/:project/annotate`, otherwise → `/w/p/:project/dataset`. `lib/routes.ts` is the card's "one builder" file from T-474 and the only module a Node test can import without React.
2. Home: a project card now links to `/w/p/:project` (one hop), and "create project" lands on `/w/p/:project/upload`.
3. Dashboard: the queue row and the recent-activity project link go through `projectPath`; `dashboardRules.onboardingSteps()` builds its `to` values with `projectPath`, so the checklist now returns `/acme/p/ppe/upload`, `/acme/p/ppe/annotate`, `/acme/p/ppe/train`.
4. Project shell: `ProjectPanel`'s nav links and `ProjectLayout`'s compact strip, "awaiting review" and "Train Model" buttons all call `projectPath(ws, slug, to)`; nav items stay relative (`to: 'upload'`), so one child list still serves both mounted branches.
5. Editor: back arrow (and the "can't open this image" fallback) use `backPath`; next/previous and the thumbnail strip use `editorPath`, keeping the editor's query.
6. The four stage files the card names (`AnnotateBoard`, `Dataset`, `Upload`, `Versions`) no longer use `../browse` / `../upload` / `../annotate` / `../train`; they call the helper with absolute stage paths (`dataset`, `annotate`, `upload`, `train?version=`).
7. Sweep: the remaining literal-`/${ws}/${` links in `src/features` and `src/components` (dashboards, governance, insights, QA, suspects, health, project settings, streams, workspace pages, top bar, `NotEnabled`) now build through `projectPath`/`editorPath` too. Otherwise the card's acceptance bullet cannot be true. Every destination already exists in the T-474 `/p/` route tree, and every permission gate sits on the route, not on the link, so no gate changed.

Tests: new `tests/link-paths.test.mjs` with the card's four tests; `tests/dashboard.test.mjs` expectations moved to the `/p/` shape; `tests/parity-guard-area1.test.mjs` (1-F2.1) now pins the create navigation as `projectPath(ws, p.slug, 'upload')` instead of the old literal.

## RED (before implementation)

```
# tests/link-paths.test.mjs
# import { backPath } from '../src/lib/routes.ts'
#          ^^^^^^^^
# SyntaxError: The requested module '../src/lib/routes.ts' does not provide an export named 'backPath'
not ok 1 - tests\link-paths.test.mjs      (1 test, 0 pass, 1 fail)

# dashboard.test.mjs
not ok 3 - image and label steps point at the first project once one exists
    + '/acme/ppe/upload'
    - '/acme/p/ppe/upload'
not ok 5 - a labeler gets no upload or train shortcut the project gate would bounce
    + '/acme/ppe/annotate'
    - '/acme/p/ppe/annotate'
```

## GREEN (after implementation)

```
$ node --test tests/link-paths.test.mjs tests/dashboard.test.mjs tests/nav.test.mjs tests/project-routes.test.mjs tests/parity-guard-area1.test.mjs
1..63
# tests 63
# pass 63
# fail 0

$ npm test
1..277
# tests 277
# pass 277
# fail 0
```

`npm test` includes the new `link-paths` file and the updated `dashboard`/`parity-guard-area1` guards.

## Build

```
$ npm run build          # gen-api-types --check && tsc -b && vite build
✓ built in 7.49s
BUILD EXIT: 0
```

(`gen-api-types --check` passed: no contract change, so no `export_openapi.py` / `gen:api-types` run was needed.)

## Files changed

Commit `9e73040` test(link-paths) — 3 files, +54 / −5
- `apps/frontend/tests/link-paths.test.mjs` (new, 49 lines)
- `apps/frontend/tests/dashboard.test.mjs` (+4 / −4)
- `apps/frontend/tests/parity-guard-area1.test.mjs` (+1 / −1)

Commit `f14f4ef` feat(links) — 29 files, +89 / −56
- `src/lib/routes.ts` +5 (`backPath`)
- `src/features/workspace/dashboardRules.ts` +2 / −1
- `src/features/workspace/Home.tsx` +3 / −2
- `src/features/workspace/Dashboard.tsx` +3 / −2
- `src/features/workspace/WorkspacePages.tsx` +4 / −3
- `src/components/shell/ProjectPanel.tsx` +2 / −1
- `src/components/shell/TopBar.tsx` +2 / −1
- `src/components/NotEnabled.tsx` +2 / −1
- `src/features/project/ProjectLayout.tsx` +4 / −3
- `src/features/editor/Editor.tsx` +5 / −4
- `src/features/project/AnnotateBoard.tsx` +4 / −3
- `src/features/project/Dataset.tsx` +3 / −2
- `src/features/project/Upload.tsx` +3 / −2
- `src/features/project/Versions.tsx` +2 / −1
- `src/features/project/ProjectSettings.tsx` +3 / −2
- `src/features/project/Suspects.tsx` +3 / −2
- `src/features/project/VideoTimeline.tsx` +2 / −1
- `src/features/project/DatasetHealth.tsx` +2 / −1
- `src/features/project/HealthCheck.tsx` +7 / −6
- `src/features/project/insights/Embeddings.tsx` +2 / −1
- `src/features/project/insights/Leakage.tsx` +2 / −1
- `src/features/project/insights/VersionsOps.tsx` +2 / −1
- `src/features/project/qa/ReviewQueue.tsx` +2 / −1
- `src/features/project/qa/Workforce.tsx` +3 / −2
- `src/features/streams/StreamDetail.tsx` +4 / −3
- `src/features/streams/Streams.tsx` +4 / −3
- `src/features/dashboards/DashboardEditor.tsx` +4 / −3
- `src/features/dashboards/Dashboards.tsx` +3 / −2
- `src/features/governance/Privacy.tsx` +2 / −1

## Deviations from the card, and why

1. **`lib/routes.ts` gained `backPath`.** The card names the four tests but not a home for the pure back-link rule; `routes.ts` is the module T-474 created as the single URL builder, and it is the only place a Node test can import without React. +5 lines, no new module.
2. **The sweep touched 17 files the card's file list does not mention** (`dashboards/*`, `governance/Privacy`, `project/insights/*`, `project/qa/*`, `DatasetHealth`, `HealthCheck`, `ProjectSettings`, `Suspects`, `VideoTimeline`, `streams/*`, `workspace/WorkspacePages`, `shell/TopBar`, `NotEnabled`). The card's own acceptance test scans all of `src/features` and `src/components` for `` `/${ws}/${ `` and fails the file it finds; with only the listed files converted, 30 sites in those 17 files would keep it red. Each edit is a link string pointing at a route that already exists under `/p/`. No behaviour, copy or permission gate changed.
3. **`tests/parity-guard-area1.test.mjs` was updated.** Its 1-F2.1 assertion pinned the exact old literal `/ws/project/upload` in Home; it now pins `projectPath(ws, p.slug, 'upload')`. The guard's intent (create lands on upload) is unchanged. The card did not list this file.
4. **The card's "browser script"** for the one-navigation acceptance has no counterpart in this repo except `e2e/core-loop.spec.ts`, which is T-008's live-stack smoke and not in this card's test list. The redirect trigger is exactly the old `/:ws/:project/...` shape, and the node test proves no such project link remains in the UI source. I did not invent a Playwright spec that needs a running API.
5. **Editor back link keeps the old `status` clause at the call site** (`review: reviewMode || !!sp.get('status')`), so a labeler coming from a filtered queue still returns to the board "as today". `backPath` itself has the two outcomes the card's test specifies.
6. **`Models.tsx` / `Train.tsx` relative `../train`, `../models`, `../deploy`, `../model-insights`, `../versions` were left alone.** They are not in the card's file list, do not match the failing literal, and resolve correctly under `/p/`; converting them is a behaviour-owned file change (T-263/T-268/T-255) with no acceptance criterion asking for it. Flagged for the captain rather than done.
7. **No route, nav registry, flag, API or OpenAPI change**, as the card requires. `npm run build`'s `gen-api-types --check` proves the contract still matches.

## Open risks

- The sweep is broad for an "M" card; the merge captain should merge T-475 before T-478/T-480/T-485/T-486/T-495/T-497/T-498 as the card orders, since those rewrite the same files.
- Until T-483 mounts the Project Overview at `/p/:project`, Home's one-hop card link lands on the index route, which T-474 redirects to `browse`. One client-side `Navigate` remains only in that window; the card's target URL is already the final one.
- `node_modules` in the worktree is a junction to `E:\02_Projects\auto_label\apps\frontend\node_modules` (untracked, gitignored) so `npm run build` could run; remove it with the worktree.
