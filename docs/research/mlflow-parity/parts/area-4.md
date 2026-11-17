# Part 4 — Area 4 Evaluation & GenAI

Gap rows: 19 (7 PARTIAL, 12 MISSING) · Cards: 20 · Hours: 53

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| ML4-T4.1 | PARTIAL | T-283 (area 5), T-947 | M | M | — |
| ML4-T4.2 | PARTIAL | T-950, T-285, T-286 (area 5) | M | M | 3 |
| ML4-T4.3 | MISSING | T-951 | M | M | 3 |
| ML4-T4.4 | PARTIAL | T-946, T-947 | M | M | 5.5 |
| ML4-T4.5 | PARTIAL | T-952 | M | M | 2.5 |
| ML4-T4.6 | MISSING | T-948, T-949 | M | M | 5.5 |
| ML4-T4.7 | HAVE | — (guard T-005 area 5; sampled/unavailable states owned by T-287) | M | — | — |
| ML4-T4.8 | PARTIAL | T-953, T-283, T-284 (area 5) | M | M | 3 |
| ML4-T4.9 | MISSING | T-960 | M | M | 3 |
| ML4-T4.10 | MISSING | T-961 | M | S | 2 |
| ML4-T4.11 | MISSING | T-962 | M | S | 2.5 |
| ML4-T4.12 | MISSING | T-963 | M | S | 2 |
| ML4-T4.13 | MISSING | T-954 | M | M | 3 |
| ML4-T4.14 | MISSING | T-955 | M | M | 3 |
| ML4-T4.15 | MISSING | T-956 | M | M | 3 |
| ML4-T4.16 | MISSING | T-957 | M | S | 2 |
| ML4-T4.17 | MISSING | T-958 | M | M | 2.5 |
| ML4-T4.18 | MISSING | T-964 | M | M | 3 |
| ML4-T4.19 | PARTIAL | T-965 | M | S | 2 |
| ML4-T4.20 | PARTIAL | T-959 | M | S | 2.5 |

Row hours sum to 53. `ML4-T4.1` carries no hours: it is delivered by area 5's T-283 plus T-947, whose hours
are counted once under `ML4-T4.4`. `ML4-T4.7` is HAVE and carries none.

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| apps/backend/app/models/evaluation.py | T-946, T-948, T-951, T-952, T-954, T-955, T-956, T-959, T-960, T-961, T-963, T-965 |
| apps/backend/app/models/__init__.py | T-946, T-948, T-951, T-952, T-954, T-955, T-956, T-959, T-960, T-961, T-963, T-964, T-965 |
| apps/backend/app/routers/__init__.py | T-946, T-948, T-952, T-954, T-958, T-960, T-964 |
| apps/backend/app/services/flags.py | T-946 … T-965 (one `task_mlruns` line; the first card in merge order adds it) |
| apps/backend/app/services/tracing.py | T-954, T-956, T-957 |
| apps/backend/app/services/evaluate.py | T-947, T-950 |
| apps/backend/app/routers/training.py | T-947, T-948, T-954, T-959 |
| apps/backend/app/routers/playground.py | T-954, T-965 |
| apps/backend/app/adapters/catalog.py | T-956 |
| apps/frontend/src/lib/api/evaluation.ts | T-946, T-951, T-952, T-963 |
| apps/frontend/src/lib/api/traces.ts | T-954, T-955, T-956, T-958 |
| apps/frontend/src/lib/api/judges.ts | T-960, T-961, T-962 |
| apps/frontend/src/lib/api/models.ts | T-947, T-953, T-959 |
| apps/frontend/src/routes/project/models.routes.tsx | T-946, T-955 |
| apps/frontend/src/lib/nav/project/models.ts | T-946, T-955 |
| apps/frontend/src/lib/nav/workspace/build.ts | T-964 |
| apps/backend/openapi.json, apps/frontend/src/lib/api-types.gen.ts | T-946 … T-965 (regenerated last on the branch) |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-946 | Pin an evaluation set: table, digest and create route | M | 3 | R3 | no | `apps/backend/app/models/evaluation.py`, `apps/backend/app/routers/evaluation_sets.py`, `apps/backend/app/services/evaluation_sets.py`, `apps/frontend/src/features/evaluation/EvaluationSets.tsx` |
| T-947 | Score any model on a pinned set, from its panel | M | 2.5 | R4+R3 | no | `apps/frontend/src/features/evaluation/EvaluateMenu.tsx`, `apps/frontend/src/features/evaluation/EvalPanel.tsx` |
| T-948 | Release rules: store a metric threshold and judge a model | M | 3 | R3 | no | `apps/backend/app/routers/release_rules.py`, `apps/backend/app/services/release_rules.py`, `apps/frontend/src/features/project/settings/ReleaseRules.tsx` |
| T-949 | The gate answers in the deploy dialog | M | 2.5 | R4+R3 | yes | `apps/frontend/src/features/project/deploy/GateGate.tsx`, `apps/frontend/src/features/project/Deploy.tsx` |
| T-950 | Classification gets its own evaluation preset | M | 3 | R3 | no | `apps/frontend/src/features/insights/EvaluationTab.tsx` |
| T-951 | A customer's own metric, declared not coded | M | 3 | R3 | yes | `apps/backend/app/routers/custom_metrics.py`, `apps/backend/app/services/custom_metrics.py`, `apps/frontend/src/features/project/settings/CustomMetrics.tsx` |
| T-952 | Score a prediction file someone handed you | M | 2.5 | R3 | yes | `apps/backend/app/services/external_results.py`, `apps/backend/app/routers/external_results.py`, `apps/frontend/src/features/evaluation/ExternalPredictions.tsx` |
| T-953 | Is the difference real? Paired deltas with an interval | M | 3 | R3 | no | `apps/backend/app/services/compare_stats.py`, `apps/frontend/src/features/insights/DeltaTable.tsx`, `apps/frontend/src/features/insights/CompareTab.tsx` |
| T-954 | One trace per request: table, emit call, read route | M | 3 | R3 | yes | `apps/backend/app/services/tracing.py`, `apps/backend/app/routers/traces.py`, `apps/frontend/src/lib/api/traces.ts` |
| T-955 | The trace list, its filters and the span waterfall | M | 3 | R4+R3 | no | `apps/backend/app/services/trace_query.py`, `apps/frontend/src/features/traces/Traces.tsx`, `apps/frontend/src/features/traces/TraceDetail.tsx` |
| T-956 | Every adapter call traced without editing the adapter | M | 3 | R3 | no | `apps/frontend/src/features/project/settings/Tracing.tsx`, `apps/frontend/src/features/traces/component.ts` |
| T-957 | Mark any function as a step, by hand | M | 2 | R3 | no | `apps/backend/tests/test_manual_tracing.py` |
| T-958 | Accept OpenTelemetry traces from a customer's own service | M | 2.5 | R3 | yes | `apps/backend/app/routers/otel.py`, `apps/backend/app/services/otel.py`, `apps/frontend/src/features/project/settings/Otel.tsx` |
| T-959 | What each call cost in time and tokens | M | 2.5 | R4+R3 | no | `apps/backend/app/services/model_cost.py`, `apps/frontend/src/features/insights/CostTab.tsx`, `apps/frontend/src/features/insights/cost.ts` |
| T-960 | Score a VLM answer on the axes that matter | M | 3 | R3 | yes | `apps/backend/app/services/judges.py`, `apps/frontend/src/features/evaluation/JudgeDrawer.tsx`, `apps/frontend/src/lib/api/judges.ts` |
| T-961 | A judge written as criteria, versioned like a prompt | M | 2 | R3 | yes | `apps/frontend/src/features/project/settings/CustomJudges.tsx`, `apps/frontend/src/features/evaluation/criteria.ts` |
| T-962 | Does the judge agree with your reviewers? | M | 2.5 | R3 | no | `apps/backend/app/services/judge_agreement.py`, `apps/frontend/src/features/evaluation/Agreement.tsx` |
| T-963 | Store the answer a human would accept | M | 2 | R3 | no | `apps/frontend/src/features/evaluation/Expectations.tsx` |
| T-964 | Prompts with immutable versions and an alias | M | 3 | R3 | yes | `apps/backend/app/models/prompts.py`, `apps/backend/app/routers/prompts.py`, `apps/backend/app/services/prompts.py`, `apps/frontend/src/features/prompts/Prompts.tsx` |
| T-965 | The Playground keeps what you tried | M | 2 | R4+R3 | no | `apps/frontend/src/features/playground/runs.ts`, `apps/frontend/src/lib/api/playground.ts` |

## Judgment calls
- `ML4-T4.1` → T-283 + T-947, no card of its own — the entry point is one call and both halves already have
  an owner; a third card would declare the same route twice.
- `ML4-T4.7` → HAVE, guard T-005 — the detail sample's 120-image cap is a stated, visible limit and its states
  belong to T-287, so the row is cited rather than re-planned.
- `ML4-T4.3` → T-951 as a declared aggregation, not a Python callback — executing customer code in a
  multi-tenant request path is not acceptable, so the card keeps the behaviour and drops the mechanism.
- `ML4-T4.19` is PARTIAL because the Playground already runs three models on one image
  (`features/playground/Playground.tsx:155`); only persistence and a prompt reference are missing, hence S.
- The GenAI half is Could wherever it needs a GenAI surface: 4.9–4.12 and 4.15–4.19 are Could and 2–3 h each.
  4.13/4.20 are Should because they improve CV inference (per-request latency, cost) with no LLM in the loop.
- `ML4-T4.17` → T-958 covers OTLP **ingest only**; exporting our traces to a third-party collector is a later
  card, named in the card's notes rather than hidden.
- Release-notes-only features that are deliberately not rowed: automatic issue detection, custom trace views,
  skill registry, and online code-based evaluation (3.16–3.18). Each needs a trace corpus that 4.13 does not
  yet provide; `04-evaluation-genai.md` lists them and says so.
