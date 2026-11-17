# Part 0 — Regression guards (T-001–T-007)

Gap rows: 0 (0 PARTIAL, 0 MISSING) · HAVE rows protected: 72 · Cards: 7 · Hours: 19

Guards are per area (`_BRIEF.md` §6b): `T-001` = area 1 … `T-007` = area 7. A guard pins the flows
PARITY marks HAVE so the 250+ gap cards cannot silently regress them. No guard asks for application
code; every card is test-only.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 1-F1.5 | HAVE | T-001 | — | S | — |
| 1-F2.1 | HAVE | T-001 | — | — | — |
| 1-F3.2 | HAVE | T-001 | — | S | — |
| 1-F3.3 | HAVE | T-001 | — | M | — |
| 1-F3.4 | HAVE | T-001 | — | S | — |
| 1-F6.1 | HAVE | T-001 | — | — | — |
| 1-F6.2 | HAVE | T-001 | — | S | — |
| 2-F2.1 | HAVE | T-002 | — | — | — |
| 2-F2.9 | HAVE | T-002 | — | S | — |
| 2-F2.22 | HAVE | T-002, T-089 | — | S | — |
| 2-F2.23 | HAVE | T-002, T-093 | — | M | — |
| 2-F2.37 | HAVE | T-002, T-102, T-103 | — | M | — |
| 2-F2.38 | HAVE | T-002 | — | S | — |
| 2-F2.39 | HAVE | T-002 | — | S | — |
| 2-F2.40 | HAVE | T-002 | — | — | — |
| 2-F2.42 | HAVE | T-002 | — | — | — |
| 2-F2.43 | HAVE | T-002, T-097 | — | S | — |
| 2-F2.44 | HAVE | T-002 | — | — | — |
| 3-F3.1 | HAVE | T-003 | — | — | — |
| 3-F3.9 | HAVE | T-003 | — | — | — |
| 3-F3.12 | HAVE | T-003 | — | S | — |
| 3-F3.13 | HAVE | T-003 | — | — | — |
| 3-F3.25 | HAVE | T-003 | — | — | — |
| 3-F3.28 | HAVE | T-003 | — | — | — |
| 3-F3.33 | HAVE | T-003 | — | S | — |
| 3-F3.35 | HAVE | T-003 | — | — | — |
| 3-F3.37 | HAVE | T-003 | — | — | — |
| 3-F3.39 | HAVE | T-003 | — | — | — |
| 3-F3.41 | HAVE | T-003 | — | — | — |
| 3-F3.42 | HAVE | T-003 | — | — | — |
| 3-F3.44 | HAVE | T-003 | — | M | — |
| 3-F3.50 | HAVE | T-003 | — | S | — |
| 3-F3.51 | HAVE | T-003 | — | — | — |
| 4-F4.1 | HAVE | T-004 | — | — | — |
| 4-F4.2 | HAVE | T-004 | — | — | — |
| 4-F4.8 | HAVE | T-004 | — | — | — |
| 4-F4.9 | HAVE | T-004 | — | — | — |
| 4-F4.10 | HAVE | T-004 | — | — | — |
| 4-F4.11 | HAVE | T-004 | — | — | — |
| 4-F4.17 | HAVE | T-004 | — | — | — |
| 4-F4.19 | HAVE | T-004 | — | — | — |
| 4-F4.28 | HAVE | T-004 | — | — | — |
| 4-F4.36 | HAVE | T-004 | — | — | — |
| 4-F4.40 | HAVE | T-004 | — | — | — |
| 4-F4.41 | HAVE | T-004 | — | — | — |
| 4-F4.44 | HAVE | T-004 | — | — | — |
| 4-F4.45 | HAVE | T-004 | — | — | — |
| 5-F5.1 | HAVE | T-005 | — | S | — |
| 5-F5.2 | HAVE | T-005 | — | S | — |
| 5-F5.12 | HAVE | T-005 | — | S | — |
| 5-F5.16 | HAVE | T-005 | — | — | — |
| 5-F5.18 | HAVE | T-005 | — | S | — |
| 5-F5.20 | HAVE | T-005 | — | S | — |
| 5-F5.23 | HAVE | T-005 | — | — | — |
| 5-F5.35 | HAVE | T-005 | — | — | — |
| 5-F5.38 | HAVE | T-005 | — | S | — |
| 5-F5.39 | HAVE | T-005 | — | — | — |
| 5-F5.43 | HAVE | T-005 | — | — | — |
| 5-F5.44 | HAVE | T-005 | — | — | — |
| 5-F5.47 | HAVE | T-005 | — | S | — |
| 5-F5.50 | HAVE | T-005 | — | — | — |
| 5-F5.52 | HAVE | T-005 | — | M | — |
| 6-F6.9 | HAVE | T-006 | — | — | — |
| 6-F6.11 | HAVE | T-006 | — | — | — |
| 6-F6.22 | HAVE | T-006 | — | S | — |
| 6-F6.35 | HAVE | T-006 | — | — | — |
| 6-F6.43 | HAVE | T-006 | — | — | — |
| 7-F7.7 | HAVE | T-007 | — | — | — |
| 7-F7.15 | HAVE | T-007 | — | — | — |
| 7-F7.26 | HAVE | T-007 | — | — | — |
| 7-F7.34 | HAVE | T-007 | — | — | — |
| 7-F7.57 | HAVE | T-007 | — | — | — |

Coverage: 72/72 HAVE rows mapped. Wave is `—` for every row because a guard runs continuously; Size and
Hours are `—` because the guard's cost is counted once on its card, not per protected row.

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/tests/test_api_keys_scopes.py` | T-001 (append one test), then area 7's key-lifecycle card |
| `apps/backend/tests/test_autolabel_v2.py` | T-003 (append one test), then area 3's assist cards |
| `apps/frontend/tests/editor-g4.test.mjs` | T-003 (append one test), then area 3's shortcut cards |
| `apps/backend/tests/test_rbac.py` | T-007 (append one test), then area 7's RBAC cards |

No application, schema, flag or generated file is shared: the guards add tests only.

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-001 | Guard area 1: workspace, projects, first run | A–E | 2.5 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area1.py`, `apps/frontend/tests/parity-guard-area1.test.mjs` |
| T-002 | Guard area 2: upload, dataset grid, splits, deletion, health | A–E | 3 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area2.py`, `apps/frontend/tests/parity-guard-area2.test.mjs` |
| T-003 | Guard area 3: editor shell, tools, proposals, board, keyboard | A–E | 3 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area3.py`, `apps/frontend/tests/parity-guard-area3.test.mjs` |
| T-004 | Guard area 4: version snapshot, wizard, preprocessing, export | A–E | 3 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area4.py`, `apps/frontend/tests/parity-guard-area4.test.mjs` |
| T-005 | Guard area 5: model table, train entry, evaluation, alias | A–E | 3 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area5.py`, `apps/frontend/tests/parity-guard-area5.test.mjs` |
| T-006 | Guard area 6: deploy threshold, workflow blocks, zones | A–E | 2.5 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area6.py`, `apps/frontend/tests/parity-guard-area6.test.mjs` |
| T-007 | Guard area 7: membership removal, usage limits, keys, first run | A–E | 2 | R3+R4 | no | `apps/backend/tests/test_parity_guard_area7.py`, `apps/frontend/tests/parity-guard-area7.test.mjs` |

## Judgment calls
- **Guard ids are per area, not per theme.** `.parts/area-2.md` (Judgment calls) and
  `.parts/area-3.md` (last line) number their guards by subject — `T-001` ingest, `T-002` grid,
  `T-004` board, `T-006` objects drawer, and area 3's `T-007` for statistics. `_BRIEF.md` §6b overrides
  all of it: every area-2 HAVE row is **T-002**, every area-3 HAVE row is **T-003**. The PM should
  re-point those names when merging; no area card plans a HAVE behaviour, so nothing is lost.
- `.parts/area-4.md` maps its HAVE rows "by subject" and leaves T-007 unclaimed. Under §6b all
  fourteen area-4 HAVE rows are **T-004**.
- **`2-F2.37` → T-002 _and_ T-102, T-103.** Status is HAVE but the row's own gap (annotation heat map,
  object-count histogram) is real work the area-2 part plans (`.parts/area-2.md` cards table). The
  guard pins the report, charts and staleness that ship today; T-102/T-103 build the missing charts.
- **`2-F2.22` → T-002 and T-089.** Its gap ("no export selection, no assign-to") is the selection
  export owned by `2-F2.26` → T-089. The guard pins the bulk bar that exists.
- **`2-F2.23` → T-002 and T-093.** Its gap (batch merge/delete absent from the board) is
  `2-F2.33`'s batch lifecycle → T-093; the guard pins the four columns and the move.
- **`2-F2.43` → T-002 and T-097.** Its gap ("no undo, no label revival") is the re-upload-restores-labels
  rule owned by `2-F2.35` → T-097. The guard asserts today's soft delete and row hiding.
- **`2-F2.38`, `2-F2.39` — guard only.** Both are HAVE with a small real gap (the `generated` timestamp
  is not explained; an unmatched folder name falls to the random split with no warning). The area-2 part
  assigns no card to either, so they stay guard-only and are the obvious first pick if area 2 gains a
  spare S.
- **`1-F3.2`, `3-F3.1` — guard plus the wave-E band (T-470–T-519, no part written yet).** 1-F3.2's gap
  is the STUDIO position in the rail (IA pass, wave E); 3-F3.1's gap is the panel/menu shell (editor
  shell pass, wave E). T-001/T-003 pin what ships today; the E cards change it and must update the
  guard in the same PR.
- **`1-F1.5` — guard plus area 7's key lifecycle (band T-380–T-469, not written yet).** Area 1's part
  already says this (`1-F1.5` Judgment call): the shipped one-click key is guarded; rename/protect/
  disable/roll/per-key usage arrive with `7-F7.25–29`.
- **`6-F6.35` — guard plus area 6 (band T-310–T-379, not written yet).** It is HAVE because detect →
  count runs end to end, but its own gap cell says the draw/visualisation blocks are absent: the
  catalogue is `model/filter/crop/ocr/rule/sink` (`app/services/workflows.py:18-20`). T-006 pins
  `rule`/`sink`; the area-6 card must add a viz kind, not rewrite the tuple.
- **`5-F5.12`, `5-F5.18`, `5-F5.52` — guard only for now.** Their gap cells name real work (land on the
  run after submit, checkpoint expiry copy, anomaly threshold calibration) and the area-5 band
  (T-250–T-309) is not written yet. The guard pins the backend behaviour that exists today.
- **R7: none of the seven guards touches fixtures with real secrets.** T-001 and T-007 mint throwaway
  API keys through the shipped route and revoke them in teardown; the value never leaves the test
  process. No guard uses safefetch, an external URL or a captured credential.
- **Hours** are 2.5 + 3 + 3 + 3 + 3 + 2.5 + 2 = 19. Each card is test-only and fits one agent session;
  the two-card split per area would hide half a day of fixture work, which is why none exceeds 3.
- Count line check: 7 + 11 + 15 + 14 + 15 + 5 + 5 = 72, matching `PARITY.md:437`.
