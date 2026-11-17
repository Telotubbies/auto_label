
---

## 7. File ownership matrix

**The rule that prevents merge failures:** a card owns a file **exclusively** only when no other card
lists it. Everything else is shared, and shared means: smallest possible edit, one line or one block,
merge in the order below, rebase before your review continues.

The matrix below was computed from all 381 cards (not from their labels). Where a card called a file
exclusive that another card also edits, the label was corrected in the card and the file appears here as
shared. **If a file is in this table, it is shared, whatever a card says.**

- **Generated artefacts** (`openapi.json`, `api-types.gen.ts`): never hand-edited; regenerate after the
  merge that changed the contract. A conflict here is resolved by re-running
  `python tools/export_openapi.py` and `npm run gen:api-types`.
- **Registries over 30 cards** (`services/flags.py`, `lib/types.ts`, …): append one line per card, merge
  ascending id. A conflict is resolved by keeping both lines, never by reordering.
- The exhaustive list — all shared files with all their cards — is in
  [`_FILE-OWNERSHIP.md`](_FILE-OWNERSHIP.md). The table here is the top of that list, where conflicts
  actually happen.

<!-- FILE MATRIX -->

### 7.1 Exclusive-file collisions found and resolved

Eight files were declared exclusive by two cards each. The resolution is recorded in the cards:

| File | Cards | Resolution |
| --- | --- | --- |
| `apps/sdk/labeldesk/client.py` | T-022, T-075 (+T-344) | Shared; T-342 creates the methods, T-022/T-075 append, T-344 appends `batch/jobs/workflows` |
| `apps/sdk/labeldesk/cli.py` | T-022, T-075, T-344 | T-344 owns the parser and exit codes; the other two register subcommands |
| `apps/backend/tests/test_sdk_cli.py` | T-022, T-075, T-344 | Append-only sections, in that order |
| `apps/backend/tests/test_folders.py` | T-024, T-094 | T-024 creates, T-094 appends |
| `apps/frontend/src/features/workspace/FolderTree.tsx` | T-025, T-096 | T-025 creates and owns, T-096 adds drag-move and the access dialog |
| `apps/frontend/tests/folder-tree.test.mjs` | T-025, T-096 | T-025 creates, T-096 appends |
| `apps/backend/app/services/folder_access.py` | T-095, T-384 | T-095 creates the enforcement; T-384 adds the grant table |
| `apps/sdk/labeldesk/config.py` | T-348, T-441 | T-348 creates the credential file module; T-441 stores the default workspace |

### 7.2 Cross-area rows (one piece of work, one owner)

The rows below are one piece of work that two areas both list. The owning card declares the foreign row,
so the mapping is complete from either direction:

| Row | Owning card | Area that maps it |
| --- | --- | --- |
| `3-F3.40` | T-020 (shared class vocabulary) | 3 |
| `4-F4.12` | T-100 (rebalance strategies) | 4 |
| `6-F6.13` | T-391 (key disable/rotate) | 6 |
| `7-F7.2`, `7-F7.3` | T-039 (members panel) | 7 |
| `7-F7.4` | T-038 (join links) | 7 |
| `7-F7.5` | T-040 (same-domain join) | 7 |
| `7-F7.46` | T-076 (credential store) | 7 |
| `7-F7.47` | T-080 (connectors screen) | 7 |
| `7-F7.48` | T-079 (sync guards) | 7 |
| `1-F4.3` | T-060 (query language) | 1 |
| `1-F5.6`, `2-F2.45` | area 7 trash cards | 1, 2 |
| `2-F2.25` | T-026–T-029 (asset library) | 2 |
| `2-F2.20`, `7-F7.55` | T-032, T-037 (fork) | 2, 7 |
| `7-F7.54` | T-035, T-036 (public project page) | 7 |
| `7-F7.18`, `7-F7.56` | T-252/T-254, T-257/T-258 | 7 |
| `7-F7.53` | T-033/T-034 (publish licence) | 7 |

### 7.3 Labels corrected during assembly

- **Guards are per area.** `.parts/area-2.md`, `area-3.md`, `area-4.md` and `area-5.md` numbered guards
  by theme before §6b of the brief fixed the convention. `INDEX` uses `T-001` = area 1 … `T-007` = area
  7 for every HAVE row; no card body depends on the old numbering.
- **HAVE rows with real gap cells got top-up cards.** `2-F2.38`, `2-F2.39`, `2-F2.44`, `4-F4.44`
  (T-104), `3-F3.12` (T-172), `3-F3.28`, `3-F3.33` (T-173), `3-F3.51` (T-174), `4-F4.2`, `4-F4.10`
  (T-232), `5-F5.52` (T-296). They stay mapped to their guard as well.
- **Area 1's part-index header miscounts statuses** (says 14 PARTIAL / 6 MISSING; `PARITY.md` and the
  rows themselves give 12 / 8). All 27 rows are mapped; the header line is the only error.

---

## 7.4 Wave E arbitration — where REDESIGN and the running app disagree

The redesign lane resolved these in its cards; the owner or the merge captain can overrule any of them.
They are listed so nobody "fixes" a card back to the old behaviour by accident.

| # | Conflict | Resolution in the cards |
| --- | --- | --- |
| 1 | REDESIGN §6.1 lists literal hex tokens; the app derives every role from HCT at runtime (seed `#3b6cf6`) | T-470 keeps HCT as the source and moves the seed to `#5B4BE0`; the hex table becomes the reference/fallback, not a parallel palette |
| 2 | REDESIGN §3.2 draws seven rail labels and calls them "six items" | T-476 ships five destinations plus Admin, with governance as Settings tabs; the count is asserted in `nav.test.mjs` |
| 3 | Glass numbers differ (redesign 24 px / 62–66 % / 96 % fallback vs app 16–20 px / 58–62 % / 92 %) | T-472 adopts the redesign values and the fallback in the same card; T-490 asserts contrast on the glass text pairs |
| 4 | The global "Train Model" button is injected through a `#topbar-actions` portal in `ProjectLayout` | T-480 deletes the portal rather than hiding it; the stage owns its primary |
| 5 | Area 7 cards say "the rail already points at this tab" | Their tabs survive; T-476 drops the rail entry. The sentence is corrected at merge, not re-planned |
| 6 | 179 sub-12 px text occurrences in 30 files | T-471 fixes the shared scale and freezes the remaining count; each owning card clears its own file, so no lane edits another lane's screen |
| 7 | Dataset Health lives inside the Insights studio, but §3.3 puts Health in the Dataset stage | T-479 mounts the existing component under the stage tab; T-103 owns the chart work and the eventual single home |

### 7.5 Ordering exceptions (merge order ≠ id order)

Four train-screen cards build child components that a lower id imports. Merge them in this order, not
ascending id:

```
T-262 (PreflightList) → T-261 (DataBlock) → T-256 (RecipePanel) → T-255 (Train container) → T-251 (FamilyGrid access)
```

Every other family merges ascending within its wave. Two path notes for the captain: `features/project/train/`
and `features/project/versions/steps/` are new directories created by their first card, and `apps/sdk` files
are shared by id order T-022 → T-075 → T-344 → T-348 → T-441.

---

## 8. Risks the merge captain should watch

| # | Risk | Why it bites | Mitigation in this plan |
| --- | --- | --- | --- |
| 1 | `Editor.tsx` is touched by 37 cards | It is the product's core file; a bad merge is a lost week | Wave B's editor lane is serialised; behaviour cards land before E-finish's shell cards; the matrix orders them |
| 2 | `openapi.json` + `api-types.gen.ts` conflicts | 204 cards change the contract | Regenerate, never hand-merge; run the contract test after every merge |
| 3 | Migration ordering | This repo has no Alembic; `schema.apply` is ordinal | One migration-bearing branch at a time; existing-database test per merge |
| 4 | Flags nobody turns on | 100+ new keys can hide unfinished work forever | Every card's flag-off acceptance and one flag per surface; `task_470` (`ui_v3`) is the only cross-screen switch |
| 5 | Wave D encodes a guess | Provider, prices and licence are undecided | Mock provider, `None` prices, "Pricing not set", flag off |
| 6 | Numbers disagree across screens (uploaded / annotated / approved) | REDESIGN §9 risk R3 | `T-104` and `T-479` pull counts from one API vocabulary; the guard asserts today's counts |
| 7 | 13 px type floor and glass fallback regress | Token fixes are easy to undo in a later card | `T-471`, `T-472`, `T-490` assert them mechanically |
| 8 | Wave B's 419 h | It is half the programme | Four parallel families with disjoint exclusive files; E-frame already landed |

---

## 9. Completeness verification

Computed mechanically from `PARITY.md` and the 381 card headers at assembly time:

- PARITY rows parsed: **334** — 72 HAVE, 163 PARTIAL, 99 MISSING (matches `PARITY.md:437`).
- Gap rows with at least one card: **262 / 262**.
- HAVE rows with a guard: **72 / 72**.
- Card ids: **381**, unique, `T-001`–`T-498` with no duplicate; every card declares ≥ 1 parity row or is
  a wave-E redesign card (23 such cards, listed with `—` in the wave-E table).
- Unknown parity ids referenced by cards: **0**.
- Cards exceeding 3 agent-hours: **0**.
- Files claimed exclusively by two cards: **0** (after §7.1).

Re-run the check any time with the assembly script logic: read every `T-*.md`, extract the
`| Parity rows |` cell, and diff the set against `PARITY.md`'s id column.

---

## 10. Definition of done

The programme is done when:

- [ ] `pytest` is green serially, `npm run build` is green, node tests are green, ruff is clean at the
      CI-pinned version, and the OpenAPI contract test passes.
- [ ] The 262 gap rows each have a card whose acceptance criteria are demonstrably met, and the card's
      flag-off state is tested.
- [ ] The seven guards pass on the final tip, so no HAVE flow regressed on the way.
- [ ] Every shared file was merged in the matrix order, and no branch carried a hand-edited generated
      artefact into a merge.
- [ ] Wave D remains inert without the three owner decisions: no charge, no vendor name, no price.
- [ ] A demo pass of waves A–C needs no explanation of a missing state: empty, loading, error and
      permission states all render as the cards describe.

Programme ledger for the owner: [`parity-backlog-report.md`](../../../../.superpowers/sdd/2026-10-31-labeldesk-v2/parity-backlog-report.md).
