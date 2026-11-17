# Part 1 — Area 1 Workspace, projects, first run

Gap rows: 20 (14 PARTIAL, 6 MISSING) of 27 rows · Cards: 35 · Hours: 102

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| 1-F1.1 | PARTIAL | T-010, T-011 | A, D | S | 5 |
| 1-F1.2 | MISSING | T-012 | B | M | 3 |
| 1-F1.3 | MISSING | T-013, T-014, T-015, T-016 | B | L | 12 |
| 1-F1.4 | PARTIAL | T-4xx (area E, band T-470–T-529) | E | S | — |
| 1-F1.5 | HAVE | — (guard T-001; key lifecycle extends it in area 7) | — | S | — |
| 1-F2.1 | HAVE | — (guard T-001) | — | — | — |
| 1-F2.2 | PARTIAL | T-017 | A | M | 3 |
| 1-F2.3 | PARTIAL | T-018, T-019 | B | M | 5 |
| 1-F2.4 | PARTIAL | T-020, T-021 | C | M | 6 |
| 1-F2.5 | PARTIAL | T-022 | C | S | 3 |
| 1-F3.1 | PARTIAL | T-023 | A | S | 3 |
| 1-F3.2 | HAVE | — (guard T-001) | — | S | — |
| 1-F3.3 | HAVE | — (guard T-001) | — | M | — |
| 1-F3.4 | HAVE | — (guard T-001) | — | S | — |
| 1-F4.1 | PARTIAL | T-024, T-025 | C | S | 6 |
| 1-F4.2 | MISSING | T-026, T-027, T-028, T-029 | C | L | 12 |
| 1-F4.3 | PARTIAL | T-0xx (area 2, band T-060–T-119) | A | M | — |
| 1-F4.4 | MISSING | T-030, T-031, T-044 | C | L | 9 |
| 1-F5.1 | PARTIAL | T-033, T-034 | A | S | 5 |
| 1-F5.2 | MISSING | T-035, T-036 | A | M | 6 |
| 1-F5.3 | MISSING | T-032, T-037 | A | S | 6 |
| 1-F5.4 | PARTIAL | T-038, T-039, T-040 | C | M | 9 |
| 1-F5.5 | MISSING | T-041 | C | S | 3 |
| 1-F5.6 | PARTIAL | T-3xx (area 7, band T-380–T-469) | C | S | — |
| 1-F6.1 | HAVE | — (guard T-001) | — | — | — |
| 1-F6.2 | HAVE | — (guard T-001) | — | S | — |
| 1-F6.3 | PARTIAL | T-042, T-043 | D | M | 6 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-010, T-011, T-012, T-014, T-017, T-024, T-025, T-026, T-030, T-032, T-033, T-035, T-038, T-040, T-041, T-042 |
| `apps/backend/app/routers/__init__.py` | T-014, T-026, T-030, T-032, T-033, T-035, T-038 |
| `apps/backend/app/models/__init__.py` | T-014, T-020, T-038, T-040 |
| `apps/backend/app/schema/identity.py` | T-012, T-038, T-040 |
| `apps/backend/app/schema/dataset.py` | T-020, T-023, T-025, T-032, T-041 |
| `apps/backend/app/schema/__init__.py` | T-025, T-038 |
| `apps/backend/app/bootstrap.py` | T-020 |
| `apps/backend/app/config.py` | T-029, T-032, T-042 |
| `apps/backend/app/handlers/__init__.py` | T-029, T-032 |
| `apps/backend/app/routers/projects.py` | T-014, T-017, T-018, T-020, T-023, T-024, T-041 |
| `apps/backend/app/routers/workspaces.py` | T-012, T-017, T-020, T-025, T-038, T-040, T-042, T-043 |
| `apps/backend/app/routers/auth.py` | T-011, T-038, T-040 |
| `apps/frontend/src/lib/api/core.ts` | T-010, T-011, T-012, T-017, T-021, T-025, T-042 |
| `apps/frontend/src/lib/api.ts` | T-015, T-026, T-030, T-032, T-033, T-035, T-038 |
| `apps/frontend/src/routes/workspace.routes.tsx` | T-012, T-015, T-027 |
| `apps/frontend/src/routes/public.routes.tsx` | T-031, T-036, T-038 |
| `apps/frontend/src/routes/lazy.ts` | T-015, T-027, T-031, T-036, T-038 |
| `apps/frontend/src/routes/guards.tsx` | T-012, T-016, T-040 |
| `apps/frontend/src/lib/nav/registry.ts` | T-015, T-027 |
| `apps/frontend/src/lib/nav/types.ts`, `lib/nav/visibility.ts`, `lib/nav/project/label.ts` | T-043 |
| `apps/frontend/src/features/workspace/Home.tsx` | T-017, T-021, T-023, T-024, T-025, T-034 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-010, T-027, T-039, T-040, T-043 |
| `apps/frontend/src/features/project/ProjectSettings.tsx` | T-018, T-023, T-034, T-041 |
| `apps/frontend/src/features/editor/Editor.tsx` | T-019 |
| `apps/frontend/src/features/project/AnnotateBoard.tsx` | T-043 |
| `apps/frontend/src/lib/types.ts` | T-018, T-021, T-023, T-025, T-034, T-039, T-041 |
| `apps/frontend/tests/nav.test.mjs` | T-015, T-027 |
| `apps/frontend/tests/dashboard.test.mjs` | T-016, T-024 |
| `apps/backend/tests/test_folders.py` | T-024 (creates), T-025 (appends) |
| `apps/backend/tests/test_assets.py` | T-026 (creates), T-028 (appends) |
| `apps/backend/app/routers/assets.py` | T-026 (creates), T-028, T-029 |
| `apps/backend/app/routers/discovery.py` | T-030 (creates), T-044 |
| `apps/frontend/src/lib/api/assets.ts` | T-026 (creates), T-028, T-029 |
| `apps/backend/openapi.json`, `apps/frontend/src/lib/api-types.gen.ts` | regenerated last, after every route card (T-010 … T-044) |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-010 | Name the workspace and show its address before submit | A | 3 | R4+R3 | yes | `apps/backend/app/routers/auth.py` |
| T-011 | Offer the plan on the same screen, mock and off by default | D | 2 | R4+R3 | yes | `apps/frontend/src/features/onboarding/PlanPicker.tsx` |
| T-012 | Ask three setup questions on first run and keep the answers | B | 3 | R4+R3 | yes | `apps/backend/app/services/onboarding.py` |
| T-013 | Deterministic assistant planner: brief in, project plan out | B | 3 | R3 | no | `apps/backend/app/services/assistant_planner.py` |
| T-014 | Assistant thread endpoints and the create-project action | B | 3 | R3 | yes | `apps/backend/app/routers/assistant.py` |
| T-015 | Assistant surface: composer, proposal row, attach menu | B | 3 | R4 | no | `apps/frontend/src/features/assistant/Assistant.tsx` |
| T-016 | Sign up lands on the assistant, with a background-task panel | B | 3 | R4 | no | `apps/frontend/src/features/assistant/TaskPanel.tsx` |
| T-017 | Eight project types with outcome wording, plus "ask for another" | A | 3 | R4+R3 | no | `apps/frontend/src/features/project/projectTypes.ts` |
| T-018 | One type contract: what each type may store, import, train, export | B | 3 | R3 | no | `apps/backend/app/services/project_contract.py` |
| T-019 | The editor shows only the tools the project type can learn from | B | 2 | R4 | no | `apps/frontend/src/features/editor/toolsForType.ts` |
| T-020 | Shared class vocabulary: group table, project link, propagation | C | 3 | R3 | yes | `apps/backend/app/services/vocabulary.py` |
| T-021 | Group picker on the create form and a shared-vocabulary panel | C | 3 | R4 | no | `apps/frontend/src/features/workspace/GroupPicker.tsx` |
| T-022 | Create a project from the SDK and the CLI, same shape as the form | C | 3 | R5 | yes | `packages/sdk/labeldesk/client.py` |
| T-023 | Project description and its public link, written where the author is | A | 3 | R4+R3 | yes | `apps/frontend/src/features/project/DescriptionCard.tsx` |
| T-024 | Move projects and folders by drag, including a multi-selection | C | 3 | R4 | no | `apps/frontend/src/features/workspace/ProjectDnd.tsx` |
| T-025 | Folders inside folders, with a cycle rule and a breadcrumb | C | 3 | R3+R4 | no | `apps/frontend/src/features/workspace/FolderTree.tsx` |
| T-026 | Workspace asset search: one query across every project | C | 3 | R3 | yes | `apps/backend/app/routers/assets.py` |
| T-027 | Asset library page: one filter bar, a grid, a saved sort | C | 3 | R4 | no | `apps/frontend/src/features/assets/AssetLibrary.tsx` |
| T-028 | Cross-project bulk actions on a selection | C | 3 | R4+R3 | yes | `apps/backend/app/services/asset_bulk.py` |
| T-029 | Select all matches and export the workspace as one job | C | 3 | R3 | yes | `apps/backend/app/services/asset_export.py` |
| T-030 | Public dataset listing with type, size and model filters | C | 3 | R3 | yes | `apps/backend/app/routers/discovery.py` |
| T-031 | Discovery gallery page a visitor can browse signed out | C | 3 | R4 | no | `apps/frontend/src/features/discovery/Gallery.tsx` |
| T-032 | Clone or fork a project with enumerated failure codes | A | 3 | R3 | yes | `apps/backend/app/routers/fork.py` |
| T-033 | Publish a project: licence choice and an explicit content check | A | 2 | R3 | yes | `apps/backend/app/routers/publishing.py` |
| T-034 | Make public / make private dialog with the content warning | A | 3 | R4 | yes | `apps/frontend/src/features/project/PublishDialog.tsx` |
| T-035 | Public dataset payload: description, classes, licence, samples | A | 3 | R3 | yes | `apps/backend/app/routers/public.py` |
| T-036 | Public dataset page a visitor can read and copy from | A | 3 | R4 | no | `apps/frontend/src/features/public/DatasetPage.tsx` |
| T-037 | Copy dialog: progress, five precise failures, land on versions | A | 3 | R4 | no | `apps/frontend/src/features/public/ForkDialog.tsx` |
| T-038 | Per-role join links, invite expiry and resend | C | 3 | R3 | yes | `apps/backend/app/routers/join.py` |
| T-039 | Members panel: join links, pending invites with expiry and resend | C | 3 | R4 | no | `apps/frontend/src/features/settings/JoinLinks.tsx` |
| T-040 | Same-domain join requests an admin accepts | C | 3 | R4+R3 | yes | `apps/backend/app/services/domains.py` |
| T-041 | Hand a project to a named colleague | C | 3 | R4+R3 | yes | `apps/frontend/src/features/project/OwnerDialog.tsx` |
| T-042 | Entitlements: one map of what a plan unlocks | D | 3 | R3 | yes | `apps/backend/app/entitlements.py` |
| T-043 | Gate the review column, labeling analytics and non-admin seats | D | 3 | R4+R3 | yes | `apps/frontend/src/features/nav/PlanLock.tsx` |
| T-044 | Drop one photo and reorder public datasets by visual similarity | C | 3 | R3+R4 | yes | `apps/backend/app/services/similarity.py` |

## Judgment calls
- `1-F1.4` → area E (band T-470–T-529) — §4 assigns "tour replay + first-run hints" to E; take the exact id from the E part index. Note: `Dashboard.tsx:100` already ships a `Replay tour` button, so the remaining gap is the inline v3 hint, not a missing entry point.
- `1-F4.3` → area 2, band T-060–T-119 — §4 owner for the query language; T-030/T-027 leave the `q` parameter and the read-only query toggle ready for it.
- `1-F5.6` → area 7, band T-380–T-469 — who/when/days-left is the same trash table; no separate project-side card would be separable.
- `1-F1.5` (HAVE) → guard T-001 here, but §4 gives the key lifecycle to area 7 (7-F7.25–29). Both are true: the shipped flow is guarded, roll/rotate/last-used arrive with area 7.
- `1-F1.1` → split A + D — the screen and slug are trial-visible (A); a self-serve plan choice is money and by owner order is mock, flag-off (D).
- `1-F1.2`, `1-F1.3` → wave B, not A — first run is Must but not small; B (workflow mechanics) keeps wave A to the one-hour blockers.
- `1-F1.3` → deterministic planner — no LLM provider is wired (`capabilities.vlm_configured()` is false by default), so the assistant ships templates and actions, not chat. A provider choice is an owner decision.
- `1-F1.3` landing — the assistant is the *first* screen only; every later visit lands on the v3 Projects home with the Needs-you queue, so no second home is invented.
- `1-F2.2` → wave A, `1-F2.3` → wave B — the catalogue is demo-visible at creation; the downstream contract is editor/training mechanics.
- `1-F2.2`/`1-F2.3` boundary — the create-form catalogue and the type contract are here; the per-type editor surfaces belong to area 3 (3-F3.15 action segments, 3-F3.16 multi-label, 3-F3.17 multimodal) and export formats to area 4.
- `1-F3.1` — the about surface lands in Project settings General now; the v3 Overview (area E) reads the same `description`/`publicPath` fields and must not add a second editor. 1-F3.1's row is closed by T-023; the overview page itself is E's T5.
- `1-F4.2` — no workspace-rail item, per REDESIGN §3.2; the page is reached from Settings and (once E ships the palette) from ⌘K.
- `1-F4.4` — wave C (dataset discovery), and HEIC is refused with a remedy sentence: this repo has no HEIC decoder and adding one is a dependency decision, not a ponytail change.
- `1-F5.1` (A) vs `7-F7.60` (C) — the publish flow ships without the workspace kill switch; T-033 reads `allow_public_projects` defensively and names 7-F7.60 as the owner of the column, so the enforcement lands in wave C without re-planning the dialog.
- `1-F5.3` — the 409 needs a durable marker, so T-032 adds `projects.forked_from`; the five codes are validated in the documented order.
- `1-F6.3` → wave D — plan packaging is commercial; the cards carry capability names and limits only, with no price, provider or charge.
- `1-F2.5` — no MCP server exists in this repo, so the agent path is the assistant (T-014), not a new protocol surface.
- Area count line — `PARITY.md:62` says 12 PARTIAL / 8 MISSING, but the 27 rows contain 14 PARTIAL, 6 MISSING, 7 HAVE. This part follows the rows; the count line needs a correction.
- Cards: 35 against a 24–34 target — the extra card is the fourth asset-library slice (T-029), which cannot share a file with T-028 without hiding two separate permissions behind one test.
