DONE

Task T-483 — Project overview: the pipeline board a project never had. Branch `t/483`, worktree
`B:/02_Projects/ld-worktrees/t-483`, base `feat/labeldesk-v2` at `a213d8e`. Nothing merged, rebased,
pushed, deleted, or killed; `main` untouched.

## Options first

| # | Design | Files touched | Est. LOC | Trade-offs |
| --- | --- | --- | --- | --- |
| A (chosen) | A pure `overviewModel.ts` (order, state table, copy, one primary) + `StageCard.tsx` (one card) + `Overview.tsx` (queries, header, board, skeletons). | 3 production + 2 test files | ~320 | One file beyond the card's list. Required: Node cannot execute `.tsx`, and the card's own tests import `board()` / `card()`; the repo already does this with `datasetCopy.ts` and T-479's `stages.ts`. State and copy stay unit-testable. |
| B | Everything inside `Overview.tsx` / `StageCard.tsx`; tests assert the `.tsx` source text only. | 2 production + 2 test files | ~260 | Smaller, but the five card tests would verify regexes, not behaviour — it does not satisfy "for each fixture, the card returns {…}". Rejected. |
| C | Import T-477's `stageFacts()` and add no local model. | 2 production + 2 test + T-477's module | ~180 | Smallest, but T-477 is not on `feat` and has no branch: the build fails today. Rejected; A's `overviewFacts()` is the seam where T-477 replaces ~40 lines after it lands. |

Among designs that fully satisfy the card, A is the smallest that compiles and tests real
behaviour. Total diff: **+486 −2**.

## What I did, in plain words

- `/:ws/p/:project` now renders the overview while `task_470` (`ui_v3`) is on. Flag off renders the
  same `<Navigate to="browse" replace />` as before, so the old behaviour is one commit away.
- The page header keeps the shipped gradient band (`PageHeader`): project name, type and
  `24 approved`, and exactly one primary button that follows the earliest open step — "Review 16
  labels" on the demo seed, "Label 40 images", "Create a version", "Train on v1", "Test the model"
  for the other states.
- Below it, five numbered cards in pipeline order (Upload, Annotate, Dataset, Train, Deploy) as an
  `<ol>`: state chip, dot, count, one sentence and one action each. The action is a link (or Retry),
  never a second primary.
- Counts use the API's one vocabulary: uploaded = `images`, approved = `statusCounts.done`,
  to label = `unassigned + annotating`, in review = `review`. A failed call passes `null`, and the
  card shows `—` with a `Retry` that refetches, never a fake `0`.
- State precedence is blocked → needs you → done: a failed run reads `blocked` even when a ready
  model exists; its sentence names the epoch parsed from the error ("failed at epoch 4").
- A labeler keeps all five cards; Train and Deploy are dimmed with a lock and "Request access"
  (→ `settings?tab=access`), instead of being hidden.
- Empty project: Upload is the only enabled card; the other four read `not started` with
  "After upload". Loading paints five skeletons of one height; a foreign slug never renders a card
  because `ProjectLayout` answers "Project not found" first.
- Board is full width; below 768 px it stacks into five rows. A 360 px column seam is left *under*
  the board for T-484 (side-by-side only at xl and up) — beside the board it squeezed the cards to
  96 px, which the frame does not do.
- The rail's project name is now a link to the overview.

## Files changed

| File | +/- |
| --- | --- |
| `apps/frontend/src/features/project/overviewModel.ts` (new) | +189 |
| `apps/frontend/src/features/project/StageCard.tsx` (new) | +64 |
| `apps/frontend/src/features/project/Overview.tsx` (new) | +67 |
| `apps/frontend/src/routes/project/index.tsx` (shared: index element + flag wrapper) | +12 −1 |
| `apps/frontend/src/components/shell/ProjectPanel.tsx` (shared: project-name link) | +2 −1 |
| `apps/frontend/tests/overview.test.mjs` (new) | +142 |
| `apps/frontend/tests/nav.test.mjs` (shared: one appended test) | +10 |

Commits on `t/483`:
- `2cbdd53` test(overview): pin the five-card board, state copy and one primary (T-483 RED)
- `af28016` feat(overview): the project pipeline board, five cards with one action each (T-483)
- `7256802` fix(overview): the board spans the page; the 360 px column sits under it (T-483)
- `f1562c9` refactor(overview): read the primary choice top to bottom (T-483)

## RED

`node --test tests/overview.test.mjs` before the model existed:

```
# Error [ERR_MODULE_NOT_FOUND]: Cannot find module
# '.../apps/frontend/src/features/project/overviewModel.ts'
not ok 1 - tests\overview.test.mjs
# tests 1
# pass 0
# fail 1
```

`node --test tests/nav.test.mjs` before the route changed:

```
# Subtest: the project index renders the overview, not the dataset grid
not ok 40 - the project index renders the overview, not the dataset grid
error: 'the index must read the ui_v3 flag'
# tests 49
# pass 48
# fail 1
```

## GREEN

```
node --test tests/overview.test.mjs tests/nav.test.mjs     exit 0
# tests 49
# pass 49
# fail 0

npm test                                                   exit 0
# tests 283
# pass 283
# fail 0

npm run build                                              exit 0
✓ built in 6.43s
```

`npm run build` also runs `gen-api-types --check` and `tsc -b`; the API contract did not change, so
no `export_openapi.py` / `gen:api-types` regeneration was needed.

## Runtime check (real demo seed, Playwright, temporary — deleted)

A throwaway spec started the repo's e2e stack (seeded demo: 40 images, 24 approved, 16 in review,
v1), enabled `task_470`, and checked the rendered page:

- 1440: five `<h2>`s, cards 173 px wide; 1280: 141 px; 768: 118 px, five across; 375: one 311 px
  column, no horizontal scroll.
- Card text: `["1 done Upload 40 images uploaded 40 Open images", "2 needs you Annotate 16 labels
  are waiting for approval 16 Review 16", "3 done Dataset 1 version · 24 approved 1 Open versions",
  "4 needs you Train Version v1 is ready to train 0 Train on v1", "5 not started Deploy No endpoint
  yet 0 After training"]`.
- Tab to the first card action + Enter navigated to `/labeldesk-demo/p/ppe-detection/dataset`.
- Failed `/versions` → Dataset card rendered `3 unknown Dataset · Could not load versions · — ·
  Retry` (screenshot `overview-error.png`).
- `/p/no-such-project` → "Project not found", zero pipeline lists.
- Flag off → `/p/ppe-detection` redirected to `/p/ppe-detection/browse` (today's grid).
- Console errors: `[]`. Screenshots: `B:/02_Projects/ld-tmp/pytest/t483-shots/`
  (`overview-1440/1280/768/375.png`, `overview-error.png`).

The `task_470` line used for this run was a temporary local edit to `services/flags.py`, reverted;
the working tree is clean. The two throwaway specs were deleted.

## Deviations from the card, and why

1. **One file beyond the card's list: `overviewModel.ts`.** Node cannot import a `.tsx` module, and
   the card's tests call `board()` / `card()`; putting the pure model in a `.ts` module follows
   `datasetCopy.ts` / `datasetGrid.ts` and T-479's `stages.ts`. No new dependency, no new token.
2. **T-477 and T-478 are not on `feat` (T-477 has no branch; `t/478` is untouched).** The overview
   derives the same five facts from the four calls in T-477's exact vocabulary, in one exported
   `overviewFacts()`; when T-477 lands, that function's body is replaced by `stageFacts()` and the
   view does not change. The rail's stage ② parity (acceptance 1) cannot be verified until T-478
   merges — flagged, not claimed.
3. **`task_470` is declared by T-476, not by this card.** I did not append a second `"task_470"` key
   (duplicate dict key, T-476 owns the registry line). T-476 must merge first (ascending id), which
   its branch already does. For the runtime check above the key was added temporarily and reverted.
4. **Jobs call:** the existing typed client has no workspace `/ws/{ws}/jobs` method, so the page uses
   `api.jobs(ws, slug)` (`GET /projects/{project}/jobs`). Same rows, strictly narrower scope — no API
   client change, and it keeps workspace isolation.
5. **360 px column.** First implementation put it beside the board (as the note's wording allows);
   at 1440 that left 96 px per card. The frame wins on layout, so the board is full width and the
   360 px seam sits under it for T-484.
6. **"Request access"** links to the real `settings?tab=access`; the request-access sheet is T-478's,
   so this card does not invent a second one.
7. Empty-project Train/Deploy say "After upload" as the card says; with images but no version/training
   they read "After dataset" / "After training" (state table extension).

## Acceptance checklist

- [x] Index renders the overview behind `task_470`; grid redirect unchanged when off. (Rail ② parity
      blocked on T-478.)
- [x] Every card has a chip, count, one sentence, one action.
- [x] Locked stages dimmed with a lock and reason; all five always rendered.
- [x] Ordered list, one `h1` (PageHeader) then five `h2`, action reachable Tab → Enter (browser).
- [x] Empty, loading and error states: empty fixture, five skeletons, `—` + Retry (browser).
- [x] Foreign slug → "Project not found", no card (browser); reads only project-scoped calls.
- [x] Flag off → dataset grid (browser).

## Risks

- The stage vocabulary is duplicated from T-477 until that card merges; the fields are identical, so
  a rebase swap is mechanical, but the merge captain should check T-477's final wording.
- Chips use the shipped `bg-*/15 text-*` idiom; their AA pass belongs to T-490/T-495, not this card.
- A missing `statusCounts` on a loaded project renders Annotate/Dataset as `unknown` + Retry
  (unit-level only; the demo payload always carries counts).
- Full backend suite not run: the card has no backend surface and none was touched.
