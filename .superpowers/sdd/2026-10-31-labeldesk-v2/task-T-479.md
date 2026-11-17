DONE

Task T-479 — Stage tabs: Images · Versions · Health inside one stage. Branch `t/479`, worktree
`B:/02_Projects/ld-worktrees/t-479`, base `feat/labeldesk-v2` at `a213d8e`.

## Options first

| # | Design | Files touched | Est. LOC | Trade-offs |
| --- | --- | --- | --- | --- |
| A (chosen) | One pure registry (`stages.ts`) + one accessible `StageTabs` that owns `?tab=`, and two thin hosts that pick the existing child. Route files swap the two elements and wrap three legacy paths in a flag-aware redirect. | 4 new + 3 route files + 2 test files | ~190 | Smallest complete change. Children untouched. One extra file (`stages.ts`) because T-477 has not landed yet; T-477 will absorb it. |
| B | A generic `StageHost` driven by a route-config table (`{stage, panes: {id, element}}`) rendered by one route. | 3 new + 3 route files | ~230 | Less repetition, but a second registry on top of the manifest T-477 is about to create; no second consumer exists. Rejected as speculative. |
| C | Extend the shipped `Tabs` in `components/ui.tsx` with roles, arrow keys and the `tab` param, then reuse it. | 1 shared file + 2 hosts | ~150 | Touches a component `Deploy.tsx`, `Models.tsx` and `Settings` already call; their behaviour would change and the file is outside this card. Rejected. |

A keeps the diff at composition level: no child page, no API and no backend file changed.

## What I did, in plain words

- `Dataset` now opens a tabbed stage: `Images · Versions · Health`. The tab lives in `?tab=` and a tab
  click replaces the history entry, so refresh and paste land on the same sub-surface. `?tab=report`
  falls back to Images and says nothing.
- `Deploy` now opens `Test · Streams`; Streams stays behind `task_10b`, Test keeps `project.models`.
- `…/versions` redirects to `…/dataset?tab=versions`; `…/streams` to `…/deploy?tab=streams`;
  `…/model-insights` to `…/models`. Train and Models mount directly, so Train has no tab row.
- Each pane keeps the exact gate its old sibling route had (`PermGate` for `project.export`,
  `project.review`, `project.models`, `project.streams`; `FlagGate` for `task_10b`), so a foreign
  project still 404s before any tab renders, and a role without the permission sees no such tab while
  its URL still hits the gate.
- The row is a real tablist: `role="tablist"` / `role="tab"`, `aria-selected`, roving `tabIndex`,
  `aria-controls` to one `role="tabpanel"`, ArrowLeft/ArrowRight wrap and move focus with the tab.
  Enter/Space activate natively. If a URL names a tab the role cannot open, the first visible tab is
  still focusable.
- While permissions load the row paints unfiltered (children keep their gates); a lazy child suspends
  under a local `Suspense`, so the row never disappears behind the child's chunk.
- The row is solid content on `Card`: active `bg-accent text-accent-foreground` with a 2 px
  `border-primary` underline, inactive `text-muted-foreground`. No glass on content, no new token.
- Flag `task_470` off: `dataset` renders `Dataset`, `deploy` renders the gated `Deploy`, and
  `versions` / `streams` / `model-insights` render their old pages because `LegacyTabRedirect` passes
  the children through.

## Files changed

New (production):
- `apps/frontend/src/components/shell/StageTabs.tsx` +77
- `apps/frontend/src/features/project/DatasetStage.tsx` +25
- `apps/frontend/src/features/project/DeployStage.tsx` +23
- `apps/frontend/src/lib/nav/project/stages.ts` +55

Changed (shared registries):
- `apps/frontend/src/routes/project/index.tsx` +2 −2
- `apps/frontend/src/routes/project/data.routes.tsx` +3 −2
- `apps/frontend/src/routes/project/deploy.routes.tsx` +4 −3

Tests:
- `apps/frontend/tests/stage-tabs.test.mjs` +103
- `apps/frontend/tests/nav.test.mjs` +16

Total, both commits: +308 −7.

Commits on `t/479`:
- `5c5ac6c` test(stage-tabs): pin tab resolution, legacy redirects and the tablist (T-479 RED)
- `0d3e800` feat(stage): Dataset and Deploy host their sub-surfaces as tabs (T-479)

## RED

`node --test tests/stage-tabs.test.mjs` before the module existed:

```
# Error [ERR_MODULE_NOT_FOUND]: Cannot find module
# '.../src/lib/nav/project/stages.ts' imported from '.../tests/stage-tabs.test.mjs'
not ok 1 - tests\stage-tabs.test.mjs
# tests 1
# pass 0
# fail 1
```

(The six card tests could not load until `stages.ts` existed; the first implementation then failed
the build once — `DatasetHealth` has a named export — and the test was corrected to the lazy named-
export form before GREEN.)

## GREEN

```
node --test tests/stage-tabs.test.mjs tests/nav.test.mjs
# tests 46
# pass 46
# fail 0
```

## Full test and build (foreground, worktree)

```
npm test
# tests 280
# pass 280
# fail 0
# duration_ms 509.5804

npm run build
dist/assets/index-VSc8jIYm.js   733.73 kB │ gzip: 207.64 kB
✓ built in 6.46s
```

Note: the worktree had no `node_modules`; `npm ci` installed 221 packages before the suite could run.
Chunk check: the untouched base builds `index` at 730.45 kB. A first cut imported `Deploy`/`Versions`
statically and grew the entry chunk to 1,238 kB; the hosts now `lazy()` those children (with the local
`Suspense` above) and the entry chunk is 733.73 kB, i.e. +3.3 kB for the tab row and route wiring.

## Deviations from the card, and why

1. **Three route files, not one.** The card lists only `routes/project/index.tsx` as the shared route
   file, but `versions`/`model-insights` live in `data.routes.tsx` and `deploy`/`streams` in
   `deploy.routes.tsx` on this base. All three route elements had to change to avoid duplicate paths;
   `index.tsx` still swaps the `dataset` element as the card says. No other task owns those two files
   in the ownership matrix.
2. **`stages.ts` created here.** T-477 (which owns the file) has not landed, so the `tabs` field had no
   home. The file is deliberately tiny and pure (no React): `STAGE_TABS`, `LEGACY_TAB_PATHS`,
   `tabsFor`, `resolveTab`, `tabHref`. T-477 rewrites the manifest around it and absorbs the same
   field; merge `t/477` first and rebase, keeping both sides.
3. **`LegacyTabRedirect` lives in `StageTabs.tsx`.** The card's exclusive list has no separate route
   helper file, so the 3-line flag-aware redirect sits with the tab component. It reads
   `useFlag('task_470')`; while the flag is still loading it shows the legacy page, then redirects.
4. **`DatasetHealth` is lazy with a named-export mapping.** It is exported as `DatasetHealth`, not a
   default, and it is ~700 lines incl. `HealthCheck`; lazy keeps the entry chunk at the base size.
5. **Health's permission** is `project.review`, matching the `Insights` health tab and the old
   `model-insights` gate, so a labeler's Dataset row is `Images · Versions` only when export is
   granted, as the card's test states.

## Not checked / risks

- No browser run (R9 territory): the local `Suspense`, focus-after-change and the two redirects are
  proven by source tests and `tsc`, not by a live click-through. `npm run e2e` was not run.
- T-478's rail is not on this base, so the rail still shows the v2 groups; this card only guarantees
  that Versions, Health and Streams no longer need a rail row of their own.
- `tabHref` is exercised by the test and used by `resolveTab` validation; `StageTabs.pick` builds the
  param directly so it preserves the child's other filters (`q`, `split`, `model`, …).
