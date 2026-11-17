# Part 3 — Area 3 Models and deployment

Gap rows: 15 (10 PARTIAL, 5 MISSING) · Cards: 11 · Hours: 27

## Mapping

| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| `ML3-T3.1` | PARTIAL | T-932 | M | M | 2.5 |
| `ML3-T3.2` | PARTIAL | T-933 | M | M | 3 |
| `ML3-T3.3` | PARTIAL | T-320, T-321 (area 6) | M | L | — |
| `ML3-T3.4` | PARTIAL | T-934 | M | M | 2 |
| `ML3-T3.5` | MISSING | T-935 | M | M | 2.5 |
| `ML3-T3.6` | PARTIAL | T-933 | M | M | — |
| `ML3-T3.7` | MISSING | T-938 | M | M | 3 |
| `ML3-T3.8` | PARTIAL | T-937 | M | S | 2 |
| `ML3-T3.9` | PARTIAL | T-354, T-355 (area 6) | M | M | — |
| `ML3-T3.10` | MISSING | T-939 | M | S | 2.5 |
| `ML3-T3.11` | PARTIAL | T-940 | M | S | 2.5 |
| `ML3-T3.12` | MISSING | T-941 | M | L | 3 |
| `ML3-T3.13` | MISSING | T-936 | M | S | 2 |
| `ML3-T3.14` | PARTIAL | T-942 | M | S | 2 |
| `ML3-T3.15` | PARTIAL | T-920 (area 2) | M | S | — |

Card hours are counted once, against the first row that names them. `ML3-T3.6` shares T-933 with
`ML3-T3.2`; `ML3-T3.3`, `ML3-T3.9` and `ML3-T3.15` are delivered inside another area's cards, so their
Hours cell is `—` and the header total is the sum of this part's eleven cards.

## Shared-file users (suggested merge order)

| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/services/flags.py` | T-933, T-934, T-939, T-942 (one `FLAGS` line each) |
| `apps/backend/app/routers/__init__.py` | T-933, T-937, T-939, T-942 (one import and one `ROUTERS` entry each) |
| `apps/backend/app/models/__init__.py` | T-941 only (module import, name re-export, `DOMAIN_MODULES`) |
| `apps/backend/app/schema/training.py` | T-935, T-940, T-941 (one `ADD COLUMN` or `CREATE TABLE` block each, appended in that order) |
| `apps/backend/app/models/training.py` | T-935, T-940, T-941 (one column or one class each) |
| `apps/backend/app/services/deployments.py` | T-940 (three keys on `alias_out`), then T-934 (none) |
| `apps/frontend/src/lib/api/models.ts` | T-933, T-936, T-937, T-939, T-941, T-942 |
| `apps/frontend/src/lib/types.ts` | T-933, T-935, T-936 |
| `apps/frontend/src/features/project/Models.tsx` | T-932, T-933, T-935, T-936, T-938, T-942 |
| `apps/frontend/src/features/project/Deploy.tsx` | T-937, T-941 |
| `apps/backend/openapi.json`, `apps/frontend/src/lib/api-types.gen.ts` | T-933, T-934, T-935, T-937, T-938, T-939, T-940, T-941, T-942 (generated once, last) |

## Cards

| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-932 | A family says what it can do | M | 2.5 | R3 | no | `apps/backend/app/adapters/base.py`, `apps/backend/app/services/capabilities.py`, `apps/backend/tests/test_adapter_capabilities.py` |
| T-933 | The artefact explains itself | M | 3 | R3 | yes | `apps/backend/app/services/artefacts.py`, `apps/backend/app/routers/models_artefact.py`, `apps/backend/tests/test_artefacts.py`, `apps/frontend/src/features/project/ArtefactPanel.tsx` |
| T-934 | A refused request costs nothing | M | 2 | R3 | no | `apps/backend/app/services/contract_guard.py`, `apps/backend/tests/test_contract_guard.py` |
| T-935 | The environment travels with the weights | M | 2.5 | R3 | no | `apps/backend/app/services/model_env.py`, `apps/backend/tests/test_model_env.py` |
| T-936 | How big is this model, really | M | 2 | R4+R3 | no | `apps/backend/app/services/model_size.py`, `apps/backend/tests/test_model_size.py`, `apps/frontend/src/features/project/SizePanel.tsx`, `apps/frontend/tests/model_size.test.mjs` |
| T-937 | A deployed model you can probe | M | 2 | R3 | yes | `apps/backend/app/routers/model_health.py`, `apps/backend/tests/test_model_health.py` |
| T-938 | Container files for one model | M | 3 | R3 | yes | `apps/backend/app/services/container.py`, `apps/backend/tests/test_container.py` |
| T-939 | Drop in a new model family | M | 2.5 | R3 | yes | `apps/backend/app/adapters/plugins.py`, `apps/backend/tests/test_adapter_plugins.py`, `apps/frontend/src/features/workspace/Families.tsx`, `apps/frontend/tests/families.test.mjs` |
| T-940 | A deployment records whether it answers | M | 2.5 | R3 | no | `apps/backend/app/services/deploy_health.py`, `apps/backend/tests/test_deploy_health.py` |
| T-941 | Register a target you run yourself | M | 3 | R3 | yes | `apps/backend/app/models/targets.py`, `apps/backend/app/routers/targets.py`, `apps/backend/app/services/targets.py`, `apps/backend/tests/test_targets.py`, `apps/frontend/src/features/project/ExternalTargets.tsx`, `apps/frontend/tests/external_targets.test.mjs` |
| T-942 | Ask a vision model your own question | M | 2 | R3 | yes | `apps/backend/app/routers/predict_vlm.py`, `apps/backend/tests/test_predict_vlm.py` |

## Judgment calls

- `ML3-T3.3` → T-320, T-321 (area 6) — a custom model is expressed as a workflow chain; executing
  customer Python is refused on purpose, which matches MLflow 3.18's
  `MLFLOW_ALLOW_MODEL_CODE_EXECUTION=false`.
- `ML3-T3.4` → T-934 only — the *declaration* is already planned by T-926 (`ML2-T2.7`, area 2) and it
  deliberately ships no validator. This part adds the enforcement and reads its `param_specs()`; it
  must not create a second range table or a second contract route.
- `ML3-T3.9` → T-354, T-355 (area 6) — the batch screen, source and result set are already planned
  there; the input-format detail sits inside that card, so a second card would put two agents in
  `routers/batch_inference.py`.
- `ML3-T3.15` → T-920 (area 2) — T-920 tombstones a deleted model and writes one `deleted` event per
  alias before clearing it, which is both the audit trail and the serving consequence this row asks
  for. Refusing the delete instead would fight that card over `delete_model`, and MLflow itself does
  not refuse a delete behind an alias, so refusing is not parity.
- No card takes `apps/frontend/src/lib/api/deploy.ts`: that file belongs to T-310 in wave A, so every
  frontend call here goes through the existing `lib/api/models.ts`. No card takes
  `apps/backend/app/services/model_contract.py` either — T-926 owns it.
- One card adds `mlflow-skinny`, as an optional extra: T-933, for reading a model directory that
  arrived from outside. It is Apache-2.0, it is small next to re-implementing flavour dispatch and
  `_load_pyfunc`, and without it the import route answers 503 with "Importing an external model needs
  the mlflow extra" — the same degrade-with-a-reason shape as `transformers` and `asyncua` in
  `apps/backend/requirements.txt:23-32`. Its `THIRD_PARTY_LICENSES.md` block follows the Ultralytics
  block's Project / Source / Licence / Version lines at `THIRD_PARTY_LICENSES.md:8-11`.
