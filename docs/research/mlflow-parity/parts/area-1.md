# Part 1 — Area 1 Tracking

Gap rows: 17 (10 PARTIAL, 7 MISSING) · Cards: 17 · Hours: 44

All cards are Wave M (this lane's deviation from the A–E wave map). Hours are counted once per card; a row that
shares a card with another row shows `—` in the Hours column and the total stays 44.

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| ML1-T1.1 | HAVE | — (asserted by T-900) | — | S | 2.5 |
| ML1-T1.2 | PARTIAL | T-901 | M | S | 2 |
| ML1-T1.3 | PARTIAL | T-902 | M | S | 2.5 |
| ML1-T1.4 | PARTIAL | T-903 | M | S | 2 |
| ML1-T1.5 | PARTIAL | T-904 | M | S | 2.5 |
| ML1-T1.6 | MISSING | T-905 | M | S | 2 |
| ML1-T1.7 | MISSING | T-906 | M | S | 2.5 |
| ML1-T1.8 | MISSING | T-907, T-908 | M | M | 5.5 |
| ML1-T1.9 | MISSING | T-909 | M | S | 2.5 |
| ML1-T1.10 | MISSING | T-910 | M | M | 3 |
| ML1-T1.11 | PARTIAL | T-911, T-912 | M | M | 5.5 |
| ML1-T1.12 | PARTIAL | T-911, T-912 (same two cards, see 1.11) | M | S | — |
| ML1-T1.13 | PARTIAL | T-913 | M | S | 2.5 |
| ML1-T1.14 | MISSING | T-915 (counted under 1.18) | M | S | — |
| ML1-T1.15 | PARTIAL | — covered by T-267 (RF `5-F5.37`) and T-405, T-406, T-407 (RF `7-F7.43`) | — | M | — |
| ML1-T1.16 | PARTIAL | — covered by T-283, T-284 (RF `5-F5.27`) | — | M | — |
| ML1-T1.17 | PARTIAL | T-914, T-915, T-916 (counted under 1.18) + T-285, T-286 (area 5) | M | S | — |
| ML1-T1.18 | MISSING | T-914, T-915, T-916 | M | L | 9 |

HAVE guard: no guard existed for the tracking record before this lane. `ML1-T1.1` is therefore asserted by the new
in-band guard `T-900`; it lands before the first area-1 card merges, and it protects `ML1-T1.1` plus the parts of
`ML1-T1.3` that already ship.

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| apps/backend/app/services/flags.py | T-901 (`task_mlruns`), T-914 (`task_mlruns_wire`) |
| apps/backend/app/routers/training.py | T-901, T-905, T-906, T-907, T-910, T-911, T-913 |
| apps/backend/app/services/run_view.py | T-901 (creates), T-905, T-913 |
| apps/backend/app/handlers/training.py | T-902, T-910 |
| apps/backend/app/services/insights.py | T-902, T-910 |
| apps/backend/app/models/training.py | T-906 |
| apps/backend/app/schema/training.py | T-906 |
| apps/backend/app/routers/mlrun_api.py | T-914 (creates), T-915 |
| apps/backend/app/services/mlrun_wire.py | T-914 (creates), T-915 |
| apps/backend/app/models/__init__.py | T-914 |
| apps/backend/app/routers/__init__.py | T-914 (last entry, so it cannot shadow an existing route) |
| apps/backend/requirements.txt | T-910 |
| THIRD_PARTY_LICENSES.md | T-916 |
| apps/frontend/src/features/insights/TrainingTab.tsx | T-902 (owns), T-904, T-910 |
| apps/frontend/src/features/project/Models.tsx | T-901, T-905, T-906, T-908, T-909, T-912, T-913 (owner T-263) |
| apps/frontend/src/lib/api/models.ts | T-906, T-908, T-911, T-913 |
| apps/frontend/src/lib/types.ts | T-901, T-905, T-906, T-911, T-913 |
| apps/backend/openapi.json + apps/frontend/src/lib/api-types.gen.ts | T-901, T-905, T-906, T-907, T-911, T-913, T-914, T-915 — generated last, once |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-900 | Guard area 1: the training run record stays honest | M | 2.5 | R3+R4 | no | `apps/backend/tests/test_mlruns_guard.py`, `apps/frontend/tests/mlruns-guard.test.mjs` |
| T-901 | Run settings block: the parameters a run used | M | 2 | R4+R3 | yes | `apps/backend/app/services/run_view.py`, `apps/frontend/src/features/project/models/RunParams.tsx`, `apps/backend/tests/test_run_params.py`, `apps/frontend/tests/run-params.test.mjs` |
| T-902 | Every metric point gets a time, not just an epoch | M | 2.5 | R4+R3 | no | `apps/backend/tests/test_run_metric_times.py`, `apps/frontend/src/features/insights/metricTooltip.ts`, `apps/frontend/src/features/insights/TrainingTab.tsx`, `apps/frontend/tests/metric-tooltip.test.mjs` |
| T-903 | Curves keep drawing while a run is still training | M | 2 | R4 | no | `apps/frontend/src/features/insights/runLive.ts`, `apps/frontend/src/features/insights/useInsights.ts`, `apps/frontend/tests/run-live.test.mjs` |
| T-904 | Parallel coordinates: 1–6 runs across every metric | M | 2.5 | R4 | no | `apps/frontend/src/features/insights/parallelRuns.ts`, `apps/frontend/src/features/insights/ParallelRunsChart.tsx`, `apps/frontend/tests/parallel-runs.test.mjs` |
| T-905 | Continued runs: a parent link, not two unrelated rows | M | 2 | R4+R3 | no | `apps/frontend/src/features/project/models/runLineage.ts`, `apps/frontend/src/features/project/models/RunLineage.tsx`, `apps/backend/tests/test_run_lineage.py`, `apps/frontend/tests/run-lineage.test.mjs` |
| T-906 | Run tags and a run note | M | 2.5 | R4+R3 | yes | `apps/frontend/src/features/project/models/RunTags.tsx`, `apps/backend/tests/test_run_tags.py`, `apps/frontend/tests/run-tags.test.mjs` |
| T-907 | A filter grammar for the run list | M | 3 | R3 | yes | `apps/backend/app/services/run_filter.py`, `apps/backend/tests/test_run_filter.py` |
| T-908 | The filter bar on the run list | M | 2.5 | R4 | no | `apps/frontend/src/features/project/models/runQuery.ts`, `apps/frontend/src/features/project/models/RunFilterBar.tsx`, `apps/frontend/tests/run-query.test.mjs` |
| T-909 | Saved run views you can hand to a teammate | M | 2.5 | R4 | no | `apps/frontend/src/features/project/models/runViews.ts`, `apps/frontend/src/features/project/models/SavedViews.tsx`, `apps/frontend/tests/run-views.test.mjs` |
| T-910 | Host metrics sampled during a run | M | 3 | R3 | no | `apps/backend/app/services/system_metrics.py`, `apps/backend/tests/test_system_metrics.py` |
| T-911 | Artifacts and checkpoints of a run, listed | M | 3 | R3 | yes | `apps/backend/app/services/run_artifacts.py`, `apps/backend/tests/test_run_artifacts.py` |
| T-912 | The artifacts panel on the run page | M | 2.5 | R4 | no | `apps/frontend/src/features/project/models/RunArtifacts.tsx`, `apps/frontend/tests/run-artifacts.test.mjs` |
| T-913 | Which dataset a run actually consumed | M | 2.5 | R4+R3 | no | `apps/frontend/src/features/project/models/RunDataset.tsx`, `apps/backend/tests/test_run_dataset.py`, `apps/frontend/tests/run-dataset.test.mjs` |
| T-914 | A notebook can create and log into a run | M | 3 | R3 | yes | `apps/backend/app/models/mlruns.py`, `apps/backend/app/routers/mlrun_api.py`, `apps/backend/app/services/mlrun_wire.py`, `apps/backend/tests/test_mlrun_wire_runs.py` |
| T-915 | Search, metric history, restore and artifacts on the wire | M | 3 | R3 | yes | `apps/backend/tests/test_mlrun_wire_search.py` |
| T-916 | Prove the wire API with the real client, and document it | M | 3 | R5+R3 | no | `apps/backend/requirements-mlflow.txt`, `apps/backend/tests/test_mlflow_client_compat.py`, `docs/mlflow-client.md` |

## Judgment calls
- `ML1-T1.1` → HAVE, no card of its own — the run list and the per-epoch history exist end to end; only the *general*
  run (any code execution) is missing, and that is `ML1-T1.18`.
- `ML1-T1.8` → two cards (T-907, T-908) — a parser a reviewer can reject without rejecting the UI, and a UI that ships
  nothing until the endpoint exists. Split on the seam the brief asks for.
- `ML1-T1.11` / `ML1-T1.12` → the same two cards (T-911, T-912) — artifacts and checkpoints are the same listing, from
  the same directory, drawn by the same panel; splitting them would ship two nearly identical endpoints.
- `ML1-T1.14` → no hours of its own; the metric-history endpoint is a route on the surface T-914/T-915 already builds,
  so it would be a second card editing the same two files.
- `ML1-T1.15` / `ML1-T1.16` → no cards — `T-267` already plans delete with the serving consequence and `T-405…T-407`
  already add `deleted_at`/`deleted_by` to `TrainedModel` plus the trash screen; `T-283`/`T-284` already plan the
  compare metric and the staleness warning. Re-planning them here would put two cards on one file.
- `ML1-T1.17` → no separate card for the adapter half — the three adapters already capture per epoch; what is missing is
  a user's own script, which is T-914/T-915/T-916, plus `T-285`/`T-286` for the metric set.
- `ML1-T1.18` → Wave M but three cards — the wire surface is new auth-facing code; each card is ≤ 3 h and stops at a
  seam (writes · reads/restore · proof and docs).
- `T-902` owns `TrainingTab.tsx` for this part; `T-904` and `T-910` add one line each and are listed under Shared. No
  two cards claim the same exclusive file.
- `T-907` deliberately excludes `param:` and `epochs:` from the grammar — the training options live in `Job.params`
  JSON, and a dialect-specific JSON scan for a v1 filter fails the ponytail test; `variant:`, `version:`, `task:`,
  `metric:` answer the same questions.
- `T-909` keeps saved views in the browser — a new table for a column preference is not worth a migration; the URL
  carries the view, which is also how a link is shared.
- `T-914` adds a new table instead of extending `TrainedModel` — `version_id` is a non-null FK and a notebook run has
  no dataset version, no weights and no task; a nullable column is impossible here (no Alembic) and would leak
  weight-less rows into deploy, compare and the registry.
