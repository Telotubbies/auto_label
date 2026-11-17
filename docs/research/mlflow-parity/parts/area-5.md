# Part 5 — Area 5 Platform

Gap rows: 22 (14 PARTIAL, 8 MISSING) · Cards: 20 · Hours: 50

Rows 5.9 (auth) and 5.22 (workspaces) are HAVE and carry no card; they are listed in Mapping with `—`.

## Mapping

| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| ML5-T5.1 | MISSING | T-968 | M | M | 3 |
| ML5-T5.2 | MISSING | T-969 | M | S | 2.5 |
| ML5-T5.3 | MISSING | T-971 | M | S | 2.5 |
| ML5-T5.4 | PARTIAL | T-970 | M | S | 2 |
| ML5-T5.5 | PARTIAL | T-972 | M | M | 3 |
| ML5-T5.6 | PARTIAL | T-441 (area 7) | M | S | 0 |
| ML5-T5.7 | PARTIAL | T-973, T-974 | M | M | 5.5 |
| ML5-T5.8 | MISSING | T-975 | M | S | 2.5 |
| ML5-T5.9 | HAVE | — (no guard exists yet) | M | — | 0 |
| ML5-T5.10 | MISSING | T-384, T-385, T-386, T-387 (area 7) | M | L | 0 |
| ML5-T5.11 | PARTIAL | T-976 | M | S | 2.5 |
| ML5-T5.12 | PARTIAL | T-977 | M | S | 2 |
| ML5-T5.13 | PARTIAL | T-423, T-424, T-425, T-426 (area 7) | M | L | 0 |
| ML5-T5.14 | PARTIAL | T-981 | M | S | 2 |
| ML5-T5.15 | PARTIAL | T-982 | M | S | 3 |
| ML5-T5.16 | MISSING | T-983, T-984 | M | M | 5 |
| ML5-T5.17 | PARTIAL | T-985 | M | S | 2 |
| ML5-T5.18 | MISSING | T-987 | M | S | 2 |
| ML5-T5.19 | PARTIAL | T-986 | M | S | 2.5 |
| ML5-T5.20 | PARTIAL | T-980 | M | S | 2.5 |
| ML5-T5.21 | MISSING | T-978, T-979 | M | M | 5.5 |
| ML5-T5.22 | HAVE | — (no guard exists yet) | M | — | 0 |
| ML5-T5.23 | PARTIAL | T-986 (shared with 5.19) | M | S | 0 |
| ML5-T5.24 | PARTIAL | T-481 (wave E) | M | S | 0 |

Hours: 3 + 2.5 + 2.5 + 2 + 3 + 0 + 5.5 + 2.5 + 0 + 0 + 2.5 + 2 + 0 + 2 + 3 + 6 + 2 + 2 + 2.5 + 2.5 + 5.5 + 0 + 0 + 0 = **51**.

Rows covered by another area's cards (no card here): 5.6 → T-441, 5.10 → T-384–T-387, 5.13 →
T-423–T-426, 5.24 → T-481. Wave **M** on every row because this lane's cards are all wave M by the
brief's deviation; T-481's own card stays in wave E and is cited, not re-planned.

## Shared-file users (suggested merge order)

| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-968, T-969, T-970, T-971, T-972, T-973, T-974, T-975, T-976, T-977, T-978, T-979, T-980, T-981, T-982, T-983, T-984, T-985, T-986, T-987 |
| `apps/backend/requirements.txt` | T-968 |
| `apps/backend/app/models/project.py` | T-978 |
| `apps/backend/app/models/training.py` | T-972 |
| `apps/backend/app/models/__init__.py` | T-972, T-978 |
| `apps/backend/app/schema/dataset.py` | T-968, T-974 |
| `apps/backend/app/schema/training.py` | T-971 |
| `apps/backend/app/schema/__init__.py` | T-974 |
| `apps/backend/app/config.py` | T-977, T-981 |
| `apps/backend/app/main.py` | T-977 |
| `apps/backend/app/errors.py` | T-982 |
| `apps/backend/app/routers/__init__.py` | T-978, T-981 |
| `apps/backend/app/routers/projects.py` | T-968 |
| `apps/backend/app/routers/training.py` | T-969, T-970, T-971, T-972 |
| `apps/backend/app/routers/workspaces.py` | T-972, T-977, T-986 |
| `apps/backend/app/routers/rbac.py` | T-976 |
| `apps/backend/app/routers/remote.py` | T-971, T-972 |
| `apps/backend/app/routers/workflows.py` | T-973, T-974 |
| `apps/backend/app/routers/devapi.py` | T-975, T-982 |
| `apps/backend/app/services/runtime_state.py` | T-977, T-986 |
| `apps/backend/app/services/workflows.py` | none (read-only reuse of `validate_blocks`) |
| `THIRD_PARTY_LICENSES.md` | T-985 |
| `.github/workflows/ci.yml` | T-985 |
| `packages/sdk/labeldesk/cli.py` | T-969, T-975, T-986 |
| `packages/sdk/labeldesk/client.py` | T-975, T-982 |
| `apps/frontend/src/lib/nav/project/models.ts`, `lib/nav/registry.ts` | T-980 |
| `apps/frontend/src/lib/nav/workspace/govern.ts` | T-972 |
| `apps/frontend/src/routes/project/index.tsx` | T-980 |
| `apps/frontend/src/features/project/Train.tsx` | T-968, T-969, T-970 |
| `apps/frontend/src/features/project/Models.tsx` | T-971 |
| `apps/frontend/src/features/project/Workflows.tsx` | T-973, T-974 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-972, T-977, T-983, T-986, T-987 |
| `apps/frontend/src/lib/api/models.ts` | T-968, T-969, T-970, T-971, T-972, T-978, T-979, T-983 |
| `apps/frontend/src/lib/api/governance.ts` | T-976, T-977, T-986 |
| `apps/frontend/src/lib/api/workflows.ts` | T-973, T-974 |
| `apps/backend/openapi.json` + `apps/frontend/src/lib/api-types.gen.ts` | regenerate last, after T-982 (the last schema change) |

## Cards

| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-968 | A run spec committed next to the code | M | 3 | R3 | yes | `apps/backend/app/services/run_spec.py`, `apps/backend/tests/test_run_spec.py`, `apps/frontend/src/features/project/SpecPanel.tsx`, `apps/frontend/tests/run-spec-preview.test.mjs` |
| T-969 | Typed parameters and the resolved plan | M | 2.5 | R4+R3 | no | `apps/backend/tests/test_run_params.py`, `apps/frontend/src/features/project/ParamFields.tsx`, `apps/frontend/tests/param-fields.test.mjs` |
| T-970 | Check before you spend | M | 2 | R3 | no | `apps/backend/app/services/train_preflight.py`, `apps/backend/tests/test_train_preflight.py`, `apps/frontend/src/features/project/Preflight.tsx`, `apps/frontend/tests/preflight-view.test.mjs` |
| T-971 | Record the environment a run happened in | M | 2.5 | R3 | no | `apps/backend/app/services/env_fingerprint.py`, `apps/backend/tests/test_env_fingerprint.py`, `apps/frontend/src/features/project/EnvPanel.tsx`, `apps/frontend/tests/env-panel.test.mjs` |
| T-972 | Choose where a run executes | M | 3 | R4+R3 | yes | `apps/backend/app/services/workers.py`, `apps/backend/tests/test_workers.py`, `apps/frontend/src/features/project/WhereSelect.tsx`, `apps/frontend/src/features/settings/Workers.tsx`, `apps/frontend/tests/worker-select.test.mjs` |
| T-973 | A pipeline file becomes a workflow | M | 3 | R3 | yes | `apps/backend/app/services/pipeline_file.py`, `apps/backend/tests/test_pipeline_file.py`, `apps/frontend/src/features/project/PipelineImport.tsx`, `apps/frontend/tests/pipeline-import.test.mjs` |
| T-974 | Profiles: one pipeline, three settings | M | 2.5 | R4+R3 | no | `apps/backend/tests/test_pipeline_profiles.py`, `apps/frontend/src/features/project/ProfilePicker.tsx`, `apps/frontend/tests/profile-picker.test.mjs` |
| T-975 | Run a pipeline from the terminal | M | 2.5 | R3 | no | `apps/backend/tests/test_pipeline_cli.py` |
| T-976 | "Why can this person do this?" | M | 2.5 | R4+R3 | yes | `apps/backend/tests/test_rbac_explain.py`, `apps/frontend/src/features/governance/AccessDrawer.tsx`, `apps/frontend/tests/access-drawer.test.mjs` |
| T-977 | Refuse a request under the wrong host name | M | 2 | R3 | yes | `apps/backend/app/services/runtime_state.py`, `apps/backend/tests/test_trusted_host.py`, `apps/frontend/src/features/settings/NetworkFacts.tsx`, `apps/frontend/tests/network-facts.test.mjs` |
| T-978 | Experiments exist as a container for runs | M | 3 | R3 | no | `apps/backend/app/services/experiments.py`, `apps/backend/app/routers/experiments.py`, `apps/backend/tests/test_experiments.py` |
| T-979 | Tag, note and restore an experiment | M | 2.5 | R3 | no | `apps/backend/tests/test_experiment_meta.py`, `apps/frontend/src/features/project/ExperimentMeta.tsx`, `apps/frontend/tests/experiment-meta.test.mjs` |
| T-980 | Experiments in the sidebar | M | 2.5 | R4 | no | `apps/frontend/src/routes/project/experiments.routes.tsx`, `apps/frontend/src/features/project/Experiments.tsx`, `apps/frontend/src/features/project/ExperimentDetail.tsx`, `apps/frontend/tests/experiments-nav.test.mjs` |
| T-981 | One endpoint that says what this server speaks | M | 2 | R3 | no | `apps/backend/app/routers/version.py`, `apps/backend/tests/test_version_endpoint.py`, `docs/api/versioning.md` |
| T-982 | Cursors and one error shape on the public API | M | 3 | R3 | no | `apps/backend/app/services/page.py`, `apps/backend/tests/test_public_paging.py` |
| T-983 | Experiments wire endpoints, on area 1's router | M | 3 | R3 | yes | `apps/backend/app/services/mlflow_shapes.py`, `apps/backend/tests/test_wire_experiments.py`, `apps/frontend/src/features/settings/WireSnippet.tsx`, `apps/frontend/tests/wire-snippet.test.mjs` |
| T-984 | Single-verb aliases and artifact listing on the wire | M | 2 | R3 | yes | `apps/backend/tests/test_wire_single_verbs.py` |
| T-985 | Prove a third-party client can log here | M | 2 | R3 | no | `apps/backend/tests/test_wire_client_smoke.py`, `apps/backend/requirements-wire.txt` |
| T-986 | `labeldesk doctor` | M | 2.5 | R3 | yes | `packages/sdk/labeldesk/doctor.py`, `apps/backend/tests/test_diagnostics.py`, `apps/frontend/src/features/settings/Diagnostics.tsx`, `apps/frontend/tests/doctor-render.test.mjs` |
| T-987 | A JavaScript client from the same OpenAPI file | M | 2 | R5 | yes | `packages/sdk-js/package.json`, `packages/sdk-js/src/client.ts`, `packages/sdk-js/src/generated.ts`, `packages/sdk-js/README.md`, `tools/export_client_js.py`, `apps/backend/tests/test_export_client_js.py`, `apps/frontend/src/features/settings/JsSnippet.tsx`, `apps/frontend/tests/js-snippet.test.mjs` |

## Judgment calls

- **All 20 cards are wave M** — the brief's deviation for this lane fixes Wave M, so no row is
  re-litigated against the Roboflow A–E map. T-481 (wave E) and the area-7 cards (C/D) keep their waves
  and are cited only.
- **T-983/T-984 depend on area 1's run table** — they are placed after T-978 (experiments) and write
  through `services/runs.py`; if area 1 shipped a different module name, only the import changes. This
  is the one cross-lane ordering the merge captain must check.
- **T-975 serves two rows** (5.7's CLI bullet and 5.8) — its 2.5 h are counted once, under 5.8, so the
  header sums. Same for T-986 under 5.19, with 5.23 citing it as shared.
- **5.17 (notebook) is PARTIAL, not MISSING** — our SDK exists and is thin; what is missing is the wire
  surface (T-983/T-984) and the proof (T-985). Status follows the flow, not the shipping state of a
  library we do not yet have.
- **5.10 and 5.13 map into area 7** — per-object ACLs and SSO are already costed there (T-384–T-387,
  T-423–T-426). Writing a second plan for one IdP integration is the duplication the brief forbids.
- **5.23 store choice has no card of its own** — a pluggable artifact store and a schema-revision table
  were considered and declined (a new S3 client for a need nobody stated; `schema.apply` is already
  idempotent). The row's card is T-986, which reports the store instead of replacing it.
- **T-980 owns the nav slot** — area 1 builds the run screens and mounts them inside
  `ExperimentDetail`'s named slot; this lane owns only the experiment branch, so the two cannot collide
  in `lib/nav/project/models.ts`.
