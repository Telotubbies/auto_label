# Part E — LabelDesk-native redesign (wave E)

Gap rows: 2 owned (1 PARTIAL, 0 MISSING) + 2 HAVE rows with a real gap cell · Cards: 29 · Hours: 76.5
Band: `T-470–T-498` used of `T-470–T-519` (per `_BRIEF.md` §6b). 17 cards are **E-frame** and must land before
the wave A/B cards that assume `/p/` routes and stage navigation: 45.5 h. 12 are **E-finish**: 31 h.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 1-F1.4 | PARTIAL | T-486 | E | S | 2 |
| 3-F3.1 | HAVE (gap cell) | T-497, T-498 | E | M | 6 |
| 1-F3.2 | HAVE (gap cell) | T-477, T-478 | E | S | 5.5 |
| 1-F6.2 | HAVE (gap cell) | T-485 | E | S | 3 |
| E#37 states / skeleton / error / mobile (plan entry) | plan | T-487, T-488, T-489, T-491 | E | M | — (counted once in Cards) |
| E#38 route + stage frame (plan entry) | plan | T-474, T-475, T-476, T-479 | E | M | — (counted once in Cards) |
| E#39 own tokens, icons and copy (plan entry) | plan | T-470, T-471, T-472, T-473, T-493, T-494, T-495 | E | M | — (counted once in Cards) |
| E#40 mobile 375 (plan entry) | plan | T-491, T-492 | E | M | — (counted once in Cards) |

Extra ownership: `1-F3.2` — its gap cell names the mixed DATA→LABEL→MODELS→STUDIO→DEPLOY order, which the
numbered stage rail replaces. Extra ownership: `1-F6.2` — its gap cell names the checklist competing with the
empty state on the first screen, which T-485 resolves. Both rows are HAVE and keep their area-1 guard (T-001)
for the routes themselves.

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/frontend/src/index.css` | T-470 (token block, owner), T-472 (glass block), T-473 (clamp utilities), T-489 (`hit-44`, scroll padding), T-491 (mobile tabbar var) |
| `apps/frontend/src/lib/theme.ts` | T-470 (owner), T-495 (two palette helpers) |
| `apps/frontend/src/components/ui.tsx` | T-487 (owner), T-488 (skeletons), T-489 (icon-button hit area) |
| `apps/frontend/src/components/shell/AppSidebar.tsx` | T-471 (label classes), T-480 (switcher removed), T-489 (hit areas) |
| `apps/frontend/src/components/shell/TopBar.tsx` | T-471 (one class), T-480 (owner, rewritten), T-481 (job button), T-482 (palette trigger), T-489, area 7's T-419 (`SpendBanner` mount) |
| `apps/frontend/src/components/shell/ProjectPanel.tsx` | T-471 (one class), T-478 (owner, rewritten), T-483 (project header link), T-488 (count skeleton), T-489 |
| `apps/frontend/src/components/shell/JobTray.tsx` | T-471 (one class), T-481 (owner, rewritten) |
| `apps/frontend/src/components/shell/AppLayout.tsx` | T-480 (owner), T-482 (palette mount), T-491 (bottom tabs + padding) |
| `apps/frontend/src/components/shell/index.tsx` | T-478, T-480 (one export each) |
| `apps/frontend/src/features/project/ProjectLayout.tsx` | T-475 (link strings), T-478 (portal removed, compact strip), T-480 (portal deleted) |
| `apps/frontend/src/features/workspace/Home.tsx` | T-475 (links), T-485 (owner, order), T-486 (guide entry), T-488 (loading branch), T-494 (copy), area 7's T-385 (folder empty-state sentence) |
| `apps/frontend/src/features/workspace/Dashboard.tsx` | T-475, T-485 (KPI block moves), T-488, T-494 |
| `apps/frontend/src/features/workspace/dashboardRules.ts` | T-475 (step URLs), T-486 (step titles) |
| `apps/frontend/src/features/project/Overview.tsx` | T-483 (owner), T-484 (header action), T-488 (loading), T-491 (`<md` branch), T-494 (copy) |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-475 (links), T-495 (one class), T-496 (owner, lanes) |
| `apps/frontend/src/features/project/Dataset.tsx` | T-475 (links), T-495 (split colours) — T-062 owns the file |
| `apps/frontend/src/features/project/Upload.tsx` | T-475 (link strings only) — T-068 owns the file |
| `apps/frontend/src/features/project/Versions.tsx` | T-475 (link strings only) — area 4 owns the file |
| `apps/frontend/src/features/project/Train.tsx` | none from this part — T-255 owns the container |
| `apps/frontend/src/features/project/Models.tsx` | none from this part — T-263 owns the container |
| `apps/frontend/src/features/project/Deploy.tsx` | none from this part — T-314 owns the rebuild, T-311 adds a content tab |
| `apps/frontend/src/features/editor/Editor.tsx` | T-475 (links), T-492 (phone branch), T-497 (rail), T-498 (header + toolbar); area 3 owns the behaviour |
| `apps/frontend/src/features/editor/Panels.tsx` | none planned (imported by T-497) |
| `apps/frontend/src/features/editor/shortcuts.ts` | T-498 (only if `→` is missing) — T-120 owns the file |
| `apps/frontend/src/lib/nav/registry.ts` | T-474 (`p` reserved), T-476 (`workspaceNav` array), T-477, T-387 and T-414 (area 7: reserved segments + labels), T-493 (via `types.ts`) |
| `apps/frontend/src/lib/nav/visibility.ts` | T-476 (one branch removed), T-477 (stage filter) |
| `apps/frontend/src/lib/nav/types.ts` | T-493 (new `NavIcon` members) — area 1's T-043 also edits it |
| `apps/frontend/src/lib/nav/project/stages.ts` | T-477 (owner), T-479 (`tabs` field) |
| `apps/frontend/src/routes/project/index.tsx` | T-474 (owner), T-479 (three elements + three redirects), T-483 (index element) |
| `apps/frontend/src/routes/workspace.routes.tsx` | none from this part — T-400 moves `/audit` |
| `apps/frontend/src/features/settings/Settings.tsx` | none from this part — T-380/T-387/T-400/T-414 own the tabs |
| `apps/frontend/src/lib/api/core.ts` | T-481 (one client function) |
| `apps/frontend/tests/nav.test.mjs` | T-474, T-476, T-478, T-479, T-480, T-481, T-482, T-483 |
| `apps/frontend/tests/dashboard.test.mjs` | T-475, T-485, T-486 |
| `apps/frontend/tests/editor-g4.test.mjs`, `editor-g5.test.mjs` | T-497 (selectors only, if the DOM moves) |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-470 | Tokens v3: surfaces, outline, glass and type scale | E | 3 | R4 | no | `index.css`, `lib/theme.ts`, `tests/tokens.test.mjs` |
| T-471 | Enforce a 13 px text floor and freeze stray values | E | 2.5 | R4 | no | `components/shell/AppSidebar.tsx`, `tests/type-floor.test.mjs` |
| T-472 | Glass parity: 24 px blur, 62/66 fill, 96% fallback | E | 2 | R4 | no | `tests/glass.test.mjs` |
| T-473 | Thai-safe truncation: two lines, then an explicit more | E | 2.5 | R4 | no | `lib/text.ts`, `tests/thai-text.test.mjs` |
| T-474 | `/p/` project routes, with legacy URLs redirected | E | 3 | R4 | no | `routes/project/index.tsx`, `routes/project/LegacyProject.tsx`, `lib/routes.ts`, `tests/project-routes.test.mjs` |
| T-475 | Every internal link through one path helper | E | 2.5 | R4 | no | `tests/link-paths.test.mjs` |
| T-476 | Workspace rail: six destinations, governance in Settings | E | 3 | R4 | no | `lib/nav/workspace/core.ts`, `build.ts`, `govern.ts`, `footer.ts` |
| T-477 | Stage manifest: five steps, their state and their count | E | 2.5 | R4 | no | `lib/nav/project/stages.ts`, `tests/stage-manifest.test.mjs` |
| T-478 | Project rail: numbered StageItem with dot, count and lock | E | 3 | R4 | no | `components/shell/StageItem.tsx`, `components/shell/ProjectPanel.tsx`, `tests/stage-rail.test.mjs` |
| T-479 | Stage tabs: Images · Versions · Health inside one stage | E | 2.5 | R4 | no | `components/shell/StageTabs.tsx`, `features/project/{Dataset,Train,Deploy}Stage.tsx`, `tests/stage-tabs.test.mjs` |
| T-480 | One 56 px top bar; the global Train button is gone | E | 3 | R4 | no | `components/shell/TopBar.tsx`, `WorkspaceSwitcher.tsx`, `AppLayout.tsx`, `tests/topbar.test.mjs` |
| T-481 | The job tray becomes a workspace panel behind its icon | E | 2.5 | R4 | no | `components/shell/JobTray.tsx`, `JobButton.tsx`, `lib/jobs.ts`, `tests/job-tray.test.mjs` |
| T-482 | A real command palette on ⌘K | E | 3 | R4 | no | `components/shell/CommandPalette.tsx`, `lib/palette.ts`, `tests/palette.test.mjs` |
| T-483 | Project overview: the pipeline board a project never had | E | 3 | R4 | no | `features/project/Overview.tsx`, `StageCard.tsx`, `tests/overview.test.mjs` |
| T-484 | Overview header: one dynamic primary and a truthful aside | E | 2.5 | R4 | no | `OverviewAside.tsx`, `overviewFacts.ts`, `tests/overview-facts.test.mjs` |
| T-485 | Home: the queue first, then five-count project cards | E | 3 | R4 | no | `TaskRow.tsx`, `ProjectCard.tsx`, `homeQueue.ts`, `tests/home-queue.test.mjs` |
| T-486 | First-run hint in the first project card, replayable | E | 2 | R4 | no | `features/workspace/Tour.tsx` |
| T-487 | Page header, chip, empty state and error sheet primitives | E | 2.5 | R4 | no | `lib/chips.ts`, `tests/ui-primitives.test.mjs` |
| T-488 | Skeletons that match the geometry they replace | E | 2 | R4 | no | `tests/skeleton.test.mjs` |
| T-489 | Focus order, 44 px hit areas and labelled stage dots | E | 2.5 | R4 | no | `tests/a11y-contract.test.mjs` |
| T-490 | axe and keyboard proof, with the contrast table as a test | E | 3 | R4 | no | `scripts/a11y-scan.mjs`, `scripts/keyboard-path.mjs`, `lib/contrast.ts`, `tests/contrast-math.test.mjs`, `docs/a11y/keyboard-path.md` |
| T-491 | 375 px: bottom tabs, a stacked overview, no sideways scroll | E | 3 | R4 | no | `components/shell/BottomTabs.tsx`, `tests/mobile-tabs.test.mjs` |
| T-492 | Phone editor: a read-only preview with a desktop handoff | E | 2.5 | R4 | no | `features/editor/MobileNotice.tsx`, `lib/desktopLink.ts`, `tests/editor-mobile.test.mjs` |
| T-493 | One icon registration for every rail, stage and screen | E | 2 | R4 | no | `components/shell/icons.ts`, `tests/icons.test.mjs` |
| T-494 | LabelDesk copy deck for the ten screens, in real Thai | E | 2.5 | R4 | no | `lib/copy.ts`, `tests/copy.test.mjs` |
| T-495 | One colour source for status, split and class chips | E | 2 | R4 | no | `tests/colour-source.test.mjs` |
| T-496 | Annotate board: three lanes of batch rows, one way in | E | 3 | R4 | no | `BatchRow.tsx`, `boardLanes.ts`, `tests/annotate-lanes.test.mjs` |
| T-497 | Editor rail: two tabs, and an inspector for the rest | E | 3 | R4 | no | `features/editor/InspectorSheet.tsx`, `railTabs.ts`, `tests/editor-shell.test.mjs` |
| T-498 | Editor header: next image, review state, assists at the pointer | E | 3 | R4 | no | `features/editor/EditorToolbar.tsx`, `nextImage.ts`, `tests/editor-header.test.mjs` |

## Skipped / owned elsewhere
| Screen or surface | Owning card | Why this part does not duplicate it |
| --- | --- | --- |
| S1 Home, first-run landing as the assistant | `T-015`, `T-016` (area 1) | The assistant is the *first* screen only; every later visit is T-485's Projects home, and this part adds no second home. |
| S3 Upload (drop zone, pre-flight, result sheet) | `T-068` (area 2) | Its card rewrites `Upload.tsx` around four blocks and the result sheet; wave E only adds the `/p/` link string (T-475). |
| S4 bulk review confirm, reject reason | `T-129`, `T-164` (area 3) | T-496 deletes the board's green `Approve all` and points at their sheet; the confirmation itself is not re-planned. |
| S5 editor behaviour (zoom, save guard, repeat, assist, history) | `T-120`–`T-171` (area 3) | T-497/T-498 move chrome; every behaviour keeps its owning card. |
| S5 image menu (cover, download, find similar) | `T-087`, `T-088` (area 2) | `3-F3.1`'s second gap half; the editor shell card must not grow one. |
| S6 Dataset filter bar, saved views, uploaded/approved header | `T-062` (area 2) | It owns `Dataset.tsx` and `FilterBar.tsx`; T-479 nests the page under a stage tab without editing it. |
| S6 health charts, heat map, histogram | `T-102`, `T-103` (area 2) | The Health tab mounts the existing `DatasetHealth`; the new charts are area 2's. |
| S7 Versions (list, detail, diff, recipe, export menu) | `T-194`, `T-217`, `T-219`, `T-220`, `T-222`, `T-224` (area 4) | Area 4 splits and rewrites the version screens; T-479 only makes Versions a tab of stage 3. |
| S8 Train: three blocks, presets, ETA/credits summary | `T-255` (area 5, owner of `Train.tsx`) + `T-253`, `T-254`, `T-256`, `T-259`, `T-261` | The screen rewrite is area 5's; T-479 mounts its component under a stage tab and T-484 reads its counts. |
| S9 Models: run list, metric tiles, interactive matrix, recommendations | `T-263` (area 5, owner of `Models.tsx`) + `T-268`, `T-272`, `T-276` | Same reason; the overview's latest-run line (T-484) reads the API without touching the screen. |
| S10 Deploy: two-pane test-first layout, wrapped endpoint, sample image | `T-314` (owner of `Deploy.tsx`) + `T-311` (delivery-options content tab), `T-318` | Area 6's screen rewrite; T-479 mounts it under a stage tab, and T-495 hands its colour mapping to T-314 instead of editing the file. |
| Playground folded into Deploy's Test tab | `T-314` (area 6) | `/playground` stays alive; the fold-in belongs to the Deploy rebuild. |
| Settings tabs (Members, Keys, Audit, Billing, auth groups) | `T-380`, `T-387`, `T-400`, `T-414` (area 7) | T-476 removes the duplicate rail entries only; it adds no tab and does not touch `Settings.tsx`. |
| Classes & tags, project settings | `T-169` (area 3), `T-018`/`T-023`/`T-034`/`T-041` (area 1) | Reachable from the rail's secondary group; their surfaces are unchanged. |
| Login screen (audit finding 1) | unowned | No parity row and no request in this lane's brief; the PM should decide whether an E card in `T-499–T-519` takes it. |

## Judgment calls
- **`1-F3.2` and `1-F6.2` are HAVE rows that carry cards.** §6b allows it when the row's own gap cell names real
  work; both gap cells name a visual/hierarchy defect, so T-477/T-478 (order) and T-485 (competing first screen)
  close them while the guard (T-001) keeps asserting the routes.
- **`3-F3.1` is a HAVE row with a gap cell** ("panels are a drawer, no image menu"). T-497/T-498 close the shell
  half; the image menu stays with `T-087` (area 2), so the row is mapped but not claimed whole.
- **`3-F3.3` (next-image, sticky settings) stays with `T-120`.** T-498 renders the affordance the row's UX asks
  for, but the sticky-settings behaviour is T-120's and is not re-planned.
- **`1-F1.4` → T-486.** `Dashboard.tsx:100` already ships a `Replay tour` button, so the card moves the entry point
  and deletes the floating card instead of adding a second tour.
- **One flag for the frame.** `task_470` (`ui_v3`) is declared once, read by the shell/Home/overview cards, and
  switched off returns the v2 rail, bar, order and links. Tokens, glass, typography, colour and a11y cards carry
  no flag because a token or a contrast fix that can be switched off is not a fix; their acceptance line says so.
- **Routes are additive, not flagged.** T-474 keeps `/:ws/:project/*` as a `<Navigate replace>` branch, so the
  old URLs survive and the change is one commit to revert; a flag on top of that would only add a second failure
  mode.
- **Three stage tab rows, not five.** Dataset is `Images · Versions · Health`; Train is `Train · Models` because
  area 5's `T-255` and `T-263` build those two containers; Deploy is `Test · Streams` because `T-314` puts the
  endpoint inside the test pane and `T-311` adds its own `Delivery options` content tab. An `API` tab or a
  `Compare` tab would invent a third entry point the area cards do not have.
- **`/p/` and a project slugged `p`.** The segment is reserved in the frontend shell only; a legacy project named
  `p` resolves at `/w/p/p`. No backend slug change: adding one would be a migration for a name nobody has.
- **`audit` is not mine.** `T-400` (area 7) already plans the `Settings → Audit log` tab and the `/audit`
  redirect; T-476 only drops the rail entry. Its Nav-entry fields for `T-380`/`T-389` ("the rail already points
  at this tab") become stale but their tabs do not break — the PM should correct that sentence, not re-plan.
- **`registry.ts` is a hot file, not an exclusive one.** T-476 changes one array line; area 7's `T-387`/`T-414`
  append labels and reserved segments. Merge order in the table above.
- **Band.** `_BRIEF.md` §6b says `T-470–T-519`; the area-1 and area-3 part indexes wrote `T-470–T-529` and
  `T-470–T-509`. This part uses §6b's band and leaves `T-499–T-519` (21 ids) for the screens still unowned
  (Login) and for polish that depends on area 5–7 cards not yet merged.
- **Dependencies on area 5–7 are named by card id** (`T-255`, `T-263`, `T-311`, `T-314`, `T-380`, `T-385`,
  `T-387`, `T-400`, `T-414`, `T-419`), read from their cards as they stood while this part was written; those
  parts had no `.parts/` index yet, so the PM should re-check the ids at merge time.
