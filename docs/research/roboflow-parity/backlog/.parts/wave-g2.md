# Part G2 — UI clean-up (T-520–T-525)

Gap rows: 0 (0 PARTIAL, 0 MISSING) · Cards: 6 · Hours: 12

This part closes no PARITY row. It carries the six defects from `docs/audits/ui/UI-AUDIT.md` that no
existing card owns. Everything else the audit found is already planned: the mapping below names the card
that owns it, so the PM can see at a glance that the wave is deliberately short.

## Mapping

| Audit id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| A8 dataset grid at 375 | defect | T-520 | G2 | — | 3 |
| A9 dataset count honesty | defect | T-520 | G2 | — | — |
| A10 flag-off silent redirect | defect | T-521 | G2 | — | 2.5 |
| A11 deploy copy button overlap | defect | T-522 | G2 | — | 1 |
| A6 chart legend contrast | defect | T-523 | G2 | — | 2.5 |
| A7 blank chart | defect | T-523 | G2 | — | — |
| A21 playground vendor repetition | defect | T-524 | G2 | — | 1 |
| A18 tour card placement | defect | T-525 | G2 | — | 2 |
| A19 tour spotlight looks like focus | defect | T-525 | G2 | — | — |
| A1 page header gradient | defect | T-487 (exists) | E | — | — |
| A2 type floor | defect | T-471 (exists) | E | — | — |
| A3 split chip palette | defect | T-495 (exists) | E | — | — |
| A4 approve-all colour | defect | T-495, T-496 (exist) | E | — | — |
| A5 dark-mode pastel surfaces | defect | T-487 (exists) | E | — | — |
| A12 clipped header action at 375 | defect | T-487 (exists) | E | — | — |
| A13 mobile top bar | defect | T-480 (exists) | E | — | — |
| A14 usage page has three names | defect | T-494 (exists) | E | — | — |
| A15 status vocabulary | defect | T-494 (exists) | E | — | — |
| A16 lavender default surface | defect | T-470 (exists) | E | — | — |
| A17 checklist banner clipped | defect | T-485 (exists) | E | — | — |
| A20 stat tile shapes | defect | T-487 (exists) | E | — | — |
| A22 empty lane copy | defect | T-496 (exists) | E | — | — |
| A23 board does not fill the page | defect | T-496 (exists) | E | — | — |
| A24 bare trash in the model actions | defect | T-267 (exists) | B | — | — |
| A25 insights title | defect | T-494 (exists) | E | — | — |
| A26 duplicate navigation | defect | T-476 (exists) | E | — | — |
| A27 tab strip clips at 375 | defect | T-478 (exists) | E | — | — |
| A28 stat strip at 375 | defect | T-491 (exists) | E | — | — |
| A29 editor thumbnail checkmark | defect | T-498 (exists) | E | — | — |
| A30 editor header density | defect | T-498 (exists) | E | — | — |
| A31 login empty illustration | defect | — (login deliberately unplanned, `INDEX.md` §4.2 #13) | — | — | — |
| A32 insights chart axis and height | defect | T-103 (exists) | C | — | — |
| A33 sidebar plan meter | defect | T-471 (exists) | E | — | — |
| A34 monospace below the floor | defect | T-471 (exists) | E | — | — |
| A35 upload empty state | defect | T-071 (exists) | B | — | — |
| A36 versions destructive proximity | defect | T-219 (exists) | B | — | — |
| F1–F18 frames | defect | design lane (not code) | — | — | — |

## Shared-file users (suggested merge order)

| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/frontend/src/features/project/Dataset.tsx` | T-520, then T-062, T-104, T-471, T-495 |
| `apps/frontend/src/routes/guards.tsx` | T-521, then T-010, T-012, T-016, T-040 |
| `apps/frontend/src/features/project/Deploy.tsx` | T-522, then T-313, T-314, T-495 |
| `apps/frontend/src/features/project/Models.tsx` | T-523, then T-263, T-268, T-272, T-276, T-286, T-289 |
| `apps/frontend/src/features/workspace/WorkspacePages.tsx` | T-523, then the billing cards |
| `apps/frontend/src/features/playground/Playground.tsx` | T-524, then T-965 |
| `apps/frontend/src/features/workspace/Tour.tsx` | T-525 |
| `apps/frontend/src/index.css` | T-525 (one `.tour-target` rule), then T-470, T-472 |

## Cards

| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-520 | Dataset grid reflows at 375, and the count tells the truth | G2 | 3 | R4 | no | `features/project/datasetGrid.ts`, `features/project/datasetCopy.ts`, `tests/dataset-grid.test.mjs` |
| T-521 | A surface that is off says so, instead of bouncing to the dataset | G2 | 2.5 | R4 | no | `lib/flagGate.ts`, `components/NotEnabled.tsx`, `tests/flag-gate.test.mjs` |
| T-522 | Deploy snippet: the Copy button stops covering the first line | G2 | 1 | R4 | no | `tests/deploy-snippet.test.mjs` |
| T-523 | A chart with no series says so, and every legend reads at AA | G2 | 2.5 | R4 | no | `components/charts/SeriesEmpty.tsx`, `lib/chartSeries.ts`, `tests/chart-series.test.mjs` |
| T-524 | Playground: the vendor appears once, not ten times | G2 | 1 | R4 | no | `features/playground/modelGroups.ts`, `tests/model-groups.test.mjs` |
| T-525 | The tour stops covering what it points at | G2 | 2 | R4 | no | `features/workspace/tourPlacement.ts`, `tests/tour-placement.test.mjs` |

## Judgment calls

- **Card ids are T-520–T-525, not T-010–T-049 as the lane was briefed.** T-010–T-044 are area 1's cards and
  T-045–T-059 are reserved for it; overwriting them would have destroyed another lane's work. T-500–T-519 sit
  inside wave E's declared band, and T-600+ is wave F's. T-520–T-599 is unallocated, so G2 takes the head of
  it. The PM should record the band in `_BRIEF.md` §6b if it holds.
- **Six cards, not twenty.** The audit found 54 defects; 36 are app defects and 26 of those already have an
  owner among the 635 cards in the folder. Writing a second card for `PageHeader` (T-487), the type floor
  (T-471) or the split palette (T-495) would create two cards for one file and one reviewer, which §2 of
  `_BRIEF.md` forbids. The six here close nine of the remaining ten; the tenth is the login screen, which
  the owner deliberately left unplanned.
- **G2 runs before E-frame, as instructed.** Every card here is a small edit to a file that E-frame later
  rewrites or sweeps, so merging G2 first means E rebases onto a smaller diff, not a larger one. The shared
  table above is the merge order; no G2 card edits a hot registry.
- **No card plans the login screen** (A31). `INDEX.md` §4.2 #13 records the owner's decision that login has
  no parity row and is deliberately unplanned; a cleanup card would reopen it.
- **No card plans a frame fix** (F1–F18). The frames belong to the design lane, and the audit's job was to
  name the defect, not to edit the file. F2, F3 and F4 need a Thai reviewer and an owner decision
  respectively, so a code card cannot close them.
- **A9 is a copy defect, not a data defect.** The route already returns the filtered `total` and the project
  already carries `images`; nothing new is fetched. That is why it fits in T-520's three hours.
- **T-522 and T-523 touch files that wave A and wave B rewrite.** They are 1 and 2.5 hours of edit in files
  the later cards replace anyway, so the cost of merging them early is the rebase, and the benefit is that a
  buyer's first hour does not show a covered code line or a blank chart. The PM may defer either to the
  owning card instead; nothing else depends on them.
- **Hours** are 3 + 2.5 + 1 + 2.5 + 1 + 2 = 12. No card exceeds 3, and each has a node test for the pure
  part plus a source assertion for the markup, because no G2 card adds a backend surface.
