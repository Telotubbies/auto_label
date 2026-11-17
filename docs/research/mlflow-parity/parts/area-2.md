# Part 2 — Area 2 Model Registry

Gap rows: 14 (7 PARTIAL, 7 MISSING — one by design) · Cards: 14 · Hours: 37.5

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| ML2-T2.1 | MISSING | T-918, T-919 | M | M | 4.5 |
| ML2-T2.2 | MISSING | T-918, T-920 | M | M | 3.5 |
| ML2-T2.3 | PARTIAL | T-921 | M | S | 3 |
| ML2-T2.4 | MISSING | T-922, T-923 | M | S | 5 |
| ML2-T2.5 | PARTIAL | T-924 | M | S | 2.5 |
| ML2-T2.6 | PARTIAL | T-925 | M | S | 2.5 |
| ML2-T2.7 | MISSING | T-926 | M | M | 3 |
| ML2-T2.8 | MISSING | T-927 | M | S | 2 |
| ML2-T2.9 | MISSING | T-928 | M | S | 2.5 |
| ML2-T2.10 | PARTIAL | T-267 (area 5) | B | S | 0 |
| ML2-T2.11 | PARTIAL | T-929 | M | M | 3 |
| ML2-T2.12 | PARTIAL | T-930, T-931 | M | S | 6 |
| ML2-T2.13 | PARTIAL | T-257, T-258 (area 5) | C | S | 0 |
| ML2-T2.14 | HAVE | — (guard T-004) | — | — | 0 |
| ML2-T2.15 | MISSING | — | — | — | 0 |

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `apps/backend/app/schema/training.py` | T-918, T-920, T-922, T-924, T-927, T-929 |
| `apps/backend/app/models/training.py` | T-918, T-920, T-922, T-924, T-927, T-929 |
| `apps/backend/app/routers/training.py` | T-918, T-919, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929, T-930 |
| `apps/backend/app/services/model_registry.py` | T-918, T-920 |
| `apps/backend/app/services/deployments.py` | T-921, T-930 |
| `apps/backend/app/services/flags.py` | T-918, T-919, T-920, T-921, T-922, T-923, T-924, T-925, T-926, T-927, T-928, T-929, T-930, T-931 |
| `apps/backend/app/models/common.py` | T-930 |
| `apps/backend/app/bootstrap.py` | T-918 |
| `apps/frontend/src/features/project/Models.tsx` | T-919, T-921, T-923, T-924, T-925, T-926, T-927, T-928, T-929 |
| `apps/frontend/src/features/project/Deploy.tsx` | T-924, T-927, T-928 |
| `apps/frontend/src/features/settings/Settings.tsx` | T-931 |
| `apps/frontend/src/lib/api.ts` | T-931 |
| `apps/frontend/src/lib/api/models.ts` | T-919, T-921, T-922, T-923, T-924, T-925, T-926, T-927, T-928, T-929 |
| `apps/frontend/src/lib/types.ts` | T-918, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929, T-931 |
| `apps/backend/openapi.json`, `apps/frontend/src/lib/api-types.gen.ts` | T-918, T-919, T-920, T-921, T-922, T-924, T-925, T-926, T-927, T-928, T-929 — generated last |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-918 | Give every model row a registered name and a version number | M | 3 | R3 | no | `apps/backend/app/services/model_registry.py` (new), `apps/frontend/src/lib/modelName.ts` (new), `apps/backend/tests/test_registered_models.py` (new), `apps/frontend/tests/model-name.test.mjs` (new) |
| T-919 | Group the Models rail by registered name, with search | M | 3 | R4+R3 | no | `apps/frontend/src/features/project/models/RegistryRail.tsx` (new), `.../models/registry.ts` (new), `apps/frontend/tests/registry-groups.test.mjs` (new), `apps/backend/tests/test_registry_search.py` (new) |
| T-920 | Keep deleted versions as tombstones so numbers are never reused | M | 2 | R3 | yes | `apps/backend/tests/test_model_tombstones.py` (new) |
| T-921 | Free-form aliases on a version, with production reserved | M | 3 | R4+R3 | no | `.../models/AliasChips.tsx` (new), `.../models/aliases.ts` (new), `apps/backend/tests/test_model_aliases.py` (new), `apps/frontend/tests/model-aliases.test.mjs` (new) |
| T-922 | Key-value tags on a model version, filterable | M | 2 | R3 | no | `apps/backend/app/services/model_tags.py` (new), `apps/backend/tests/test_model_tags.py` (new) |
| T-923 | Tag chips, an editor and a tag filter on the model page | M | 3 | R4 | no | `.../models/TagEditor.tsx` (new), `.../models/tags.ts` (new), `apps/frontend/tests/model-tags-ui.test.mjs` (new) |
| T-924 | Deprecate a version with a reason, without deleting it | M | 2.5 | R4+R3 | no | `apps/backend/app/services/model_lifecycle.py` (new), `.../models/DeprecateDialog.tsx` (new), `.../models/lifecycle.ts` (new), `apps/backend/tests/test_model_lifecycle.py` (new), `apps/frontend/tests/model-lifecycle.test.mjs` (new) |
| T-925 | A "produced by" panel on the model page | M | 2.5 | R4+R3 | no | `apps/backend/app/services/model_provenance.py` (new), `.../models/ProvenancePanel.tsx` (new), `.../models/provenance.ts` (new), `apps/backend/tests/test_model_provenance.py` (new), `apps/frontend/tests/model-provenance.test.mjs` (new) |
| T-926 | A declared contract on every version: input, output, parameters | M | 3 | R4+R3 | no | `apps/backend/app/services/model_contract.py` (new), `.../models/ContractPanel.tsx` (new), `.../models/contract.ts` (new), `apps/backend/tests/test_model_contract.py` (new), `apps/frontend/tests/model-contract.test.mjs` (new) |
| T-927 | A written description on the model and on each version | M | 2 | R4+R3 | no | `apps/backend/app/services/model_text.py` (new), `.../models/DescriptionBlock.tsx` (new), `.../models/description.ts` (new), `apps/backend/tests/test_model_text.py` (new), `apps/frontend/tests/model-description.test.mjs` (new) |
| T-928 | Show a real example input on the model page | M | 2.5 | R4+R3 | no | `apps/backend/app/services/model_example.py` (new), `.../models/ExampleInput.tsx` (new), `.../models/example.ts` (new), `apps/backend/tests/test_model_example.py` (new), `apps/frontend/tests/model-example.test.mjs` (new) |
| T-929 | Restrict one model to managers or admins | M | 3 | R4+R3 | yes | `apps/backend/app/services/model_access.py` (new), `.../models/AccessPanel.tsx` (new), `.../models/access.ts` (new), `apps/backend/tests/test_model_access.py` (new), `apps/frontend/tests/model-access.test.mjs` (new) |
| T-930 | Emit model-registry events on the existing webhook channel | M | 3 | R3 | yes | `apps/backend/app/services/registry_events.py` (new), `apps/backend/tests/test_registry_events.py` (new) |
| T-931 | A Webhooks screen under workspace settings | M | 3 | R4 | yes | `apps/frontend/src/features/settings/Webhooks.tsx` (new), `.../settings/webhooks.ts` (new), `apps/frontend/src/lib/api/webhooks.ts` (new), `apps/frontend/tests/webhooks-ui.test.mjs` (new) |

## Judgment calls
- ML2-T2.1 → T-918/T-919, grouped per project — MLflow's registry is server-wide, but LabelDesk's model list is project-scoped and the workspace list is `T-257`; a workspace-level group would duplicate that card.
- ML2-T2.2 → T-918 + T-920, split at the seam "assign a number" / "never recycle it" — the second half is the one that touches erasure and needs its own review.
- ML2-T2.5 → T-924, deprecation only, no stages — upstream deprecates stages and the deployment alias already answers "what serves production".
- ML2-T2.7 → T-926, a derived contract rather than a schema language — one input type and three parameters; `mlflow-skinny` buys nothing and would add a dependency plus an attribution line.
- ML2-T2.10 → `T-267` (area 5) — the typed confirm and the serving consequence are already planned there; this area only records the missing alias cleanup, which `T-920` writes.
- ML2-T2.12 → T-930 (events) + T-931 (screen) — the API existed with no UI at all, so events without a subscription surface would ship unobservable.
- ML2-T2.13 → `T-257`, `T-258` (area 5) — star/share and the shared checkpoint catalogue already cover the whole row.
- ML2-T2.14 → `—` guard `T-004` — comparison already exceeds the documented surface; the guard asserts it.
- ML2-T2.15 → no card — the deployment-job state appears only in release notes, and the brief forbids a card on an unverified claim.
