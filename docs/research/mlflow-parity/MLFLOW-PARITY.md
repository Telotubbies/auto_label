# LabelDesk v2 ↔ MLflow parity matrix

Baseline: `feat/labeldesk-v2` at `f6feb09`, read 2026-11-17. MLflow documentation read the same day at
site version **3.18.0** (released 2026-11-04), plus the release notes of 2025-11-17 → 2026-11-17
(v3.7.0 … v3.18.0, `ts/v0.2.0`).

Owner directive this matrix implements: "copy Roboflow and MLflow entirely", LabelDesk branding. Roboflow
is closed by [`../roboflow-parity/PARITY.md`](../roboflow-parity/PARITY.md); this is the second half.

**What it contains.** 92 rows: 5 HAVE, 48 PARTIAL,
39 MISSING (one of those, `ML2-T2.15`, by design). 87 gap rows,
**82 cards** in `../roboflow-parity/backlog/T-900.md` … `T-987.md`, **211.5 agent-hours**, every card
1–3 hours and flagged. 22 rows are **Must**, 45 **Should**, 23 **Could**.

Every row is owned by one of five area files, which carry the click-by-click flow, the empty / loading /
error states, the code evidence and the docs URL for each claim:

| Area | File | Rows | HAVE | PARTIAL | MISSING | Cards | Hours |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 Tracking | [`01-tracking.md`](01-tracking.md) | 18 | 1 | 10 | 7 | 17 | 44 |
| 2 Model Registry | [`02-model-registry.md`](02-model-registry.md) | 15 | 1 | 7 | 7 | 14 | 37.5 |
| 3 Models & deployment | [`03-models-deploy.md`](03-models-deploy.md) | 15 | 0 | 10 | 5 | 11 | 27 |
| 4 Evaluation & GenAI | [`04-evaluation-genai.md`](04-evaluation-genai.md) | 20 | 1 | 7 | 12 | 20 | 53 |
| 5 Platform | [`05-platform.md`](05-platform.md) | 24 | 2 | 14 | 8 | 20 | 50 |
| **Total** | | **92** | **5** | **48** | **39** | **82** | **211.5** |

Status and size use the same rules as the Roboflow matrix: **HAVE** = the flow exists end to end;
**PARTIAL** = a real implementation with a documented part missing; **MISSING** = no implementation, or a
field with no flow. **Size** S ≤ 1 day, M 2–5 days, L > 1 week, one engineer. **Priority** is for a
commercial CV SaaS: Must = a buyer evaluates on it, Should = gap noticed in a trial, Could = long-tail.

Row ids are `ML<area>-T<area>.<n>`. Row `ML1-T1.2` is §1.2 of `01-tracking.md`.

---

## 1. Decision per feature: integrate, wire, or build

The owner's instruction is to prefer the MLflow library where it is smaller than the rebuild. Each row
carries one of five labels, and the area file says why in one line:

| Decision | Rows | What it means here |
| --- | --- | --- |
| **Build** | 81 | Our table, our route, our screen. Chosen wherever the feature is tenancy, identity, storage or UI — which is most of MLflow's surface, because its own server has no workspace isolation and a second auth boundary is a security decision, not a preference. |
| **Wire** | 4 | We implement the subset of MLflow's REST wire format (`/api/2.0/mlflow/…`) behind our own RBAC, so an external MLflow client logs into LabelDesk. Their client, our tenancy. |
| **Integrate** | 2 | `mlflow-skinny` as an optional extra, degrading with a clear reason when absent — the pattern this repo already uses for `transformers` and `asyncua`. Used only to read foreign model artefacts and to point the MLflow Python client at us. |
| **Integrate + build** | 3 | The library earns its place for one half (metric bundle, judge prompt, model document) and our code owns the other (the store, the screen, the tenancy). |
| **none** | 2 | Deliberately not built; the row says what we keep instead. |

Wire-compatible rows: 4

- `ML1-T1.14` Metric history read API — T-915 (counted under 1.18).
- `ML1-T1.18` Logging from a notebook or another client (the wire API) — T-914, T-915, T-916.
- `ML4-T4.17` OpenTelemetry in and out — T-958.
- `ML5-T5.16` Speaking enough of their wire format that their client works — T-983, T-984.

Integrate and integrate + build rows: 5

- `ML1-T1.17` Automatic capture per model family (the autolog equivalent) — T-914, T-915, T-916 (counted under 1.18) + T-285, T-286 (area 5).
- `ML3-T3.2` One interface that loads any model — T-933.
- `ML3-T3.6` Save, load, and the metadata document — T-933.
- `ML4-T4.9` Built-in judges for free-text answers — T-960.
- `ML5-T5.17` The Python client, and what "skinny" means for us — T-985.

**Licensing.** MLflow is Apache-2.0: its code may be reused or called with attribution, and every card
that adds `mlflow-skinny` names the `THIRD_PARTY_LICENSES.md` block it appends (project, URL, version).
Its name and logo are trademarks: no row or card uses them as UI copy, navigation, empty-state text or an
icon. Source labels appear once per card as `(MLF: <url>)`.

**Deduplication.** A row that an existing Roboflow card already closes gets no card. 19 rows point at a
wave-B/C/D/E card; 13 of those need no new card at all — mostly the run comparison (`T-283`, `T-284`), the
trash window (`T-267`, `T-405`–`T-407`), the workspace registry (`T-257`, `T-258`), the model identity and
serving pointer (`T-268`, guard `T-006`), the workflow canvas (`T-320`–`T-332`) and per-object ACLs
(`T-384`–`T-387`). The RF cards column shows them per row.

---

## 2. The matrix

### Area 1 — Tracking

| ID | Capability | Status | Primary evidence | Pri | Size | Decision | RF cards | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ML1-T1.1` | Training run record and the project run list | HAVE | `apps/backend/app/models/training.py:34-53` | Must | S | Build | T-005, T-263 | — (asserted by T-900) |
| `ML1-T1.2` | Parameters of a run | PARTIAL | `apps/backend/app/routers/training.py:281-282` | Must | S | Build | T-255, T-256 | T-901 |
| `ML1-T1.3` | Metric logging and the per-epoch history | PARTIAL | `apps/backend/app/handlers/training.py:90-96` | Must | S | Build | T-005, T-272 | T-902 |
| `ML1-T1.4` | Watching a run while it trains | PARTIAL | `apps/frontend/src/features/project/Models.tsx:265-268` | Should | S | Build | T-005, T-266 | T-903 |
| `ML1-T1.5` | Chart types for comparing runs | PARTIAL | `TrainingTab.tsx:52-96` | Should | S | Build | T-284 | T-904 |
| `ML1-T1.6` | Nested runs (parent and child) | MISSING | `routers/training.py:262-268` | Should | S | Build | T-005, T-259 | T-905 |
| `ML1-T1.7` | Run tags and the run note | MISSING | `models/training.py:34-53` | Should | S | Build | — | T-906 |
| `ML1-T1.8` | Searching, filtering and ordering runs | MISSING | `apps/backend/app/routers/training.py:146-165` | Should | M | Build | — | T-907, T-908 |
| `ML1-T1.9` | Saved table views | MISSING | `apps/frontend/src/features/project/Models.tsx` | Could | S | Build | — | T-909 |
| `ML1-T1.10` | System metrics during a run | MISSING | `handlers/training.py:90-96` | Should | M | Build | — | T-910 |
| `ML1-T1.11` | Run artifacts: browse and download | PARTIAL | `TrainedModel.weights` | Must | M | Build | T-224, T-229 | T-911, T-912 |
| `ML1-T1.12` | Logged models and per-run checkpoints | PARTIAL | `TrainedModel` | Should | S | Build | T-268 | T-911, T-912 (same two cards, see 1.11) |
| `ML1-T1.13` | Dataset inputs of a run | PARTIAL | `version_id` | Should | S | Build | T-004 | T-913 |
| `ML1-T1.14` | Metric history read API | MISSING | `GET /insights/training?runs=a,b` | Could | S | Wire | — | T-915 (counted under 1.18) |
| `ML1-T1.15` | Run deletion and restore | PARTIAL | `apps/backend/app/routers/training.py:314-324` | Should | M (already planned elsewhere) | Build | T-267, T-405, T-406, T-407 | — covered by T-267 (RF `5-F5.37`) and T-405, T-406, T-407 (RF `7-F7.43`) |
| `ML1-T1.16` | Comparing runs side by side | PARTIAL | `routers/insights_models.py:52-60` | Must | M (already planned elsewhere) | Build | T-283, T-284 | — covered by T-283, T-284 (RF `5-F5.27`) |
| `ML1-T1.17` | Automatic capture per model family (the autolog equivalent) | PARTIAL | `adapters/ultralytics_ad.py:197-210` | Should | S | Integrate + build | T-285, T-286 | T-914, T-915, T-916 (counted under 1.18) + T-285, T-286 (area 5) |
| `ML1-T1.18` | Logging from a notebook or another client (the wire API) | MISSING | `apps/backend/app/routers/devapi.py` | Should | L | Wire | — | T-914, T-915, T-916 |

### Area 2 — Model Registry

| ID | Capability | Status | Primary evidence | Pri | Size | Decision | RF cards | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ML2-T2.1` | A registered model is a named container, not a training run | MISSING | `TrainedModel` | Must | M | Build | T-257 | T-918, T-919 |
| `ML2-T2.2` | A model version is immutable and numbered per model | MISSING | `version_id` | Must | M | Build | T-268 | T-918, T-920 |
| `ML2-T2.3` | Aliases: several mutable pointers, resolved at call time | PARTIAL | `DeploymentAlias(alias, model_id, previous_model_id)` | Should | S | Build | T-005, T-268 | T-921 |
| `ML2-T2.4` | Tags on models and versions | MISSING | `TrainedModel` | Should | S | Build | T-005 | T-922, T-923 |
| `ML2-T2.5` | Deprecation, and why there are no stages | PARTIAL | `queued|training|ready|failed` | Should | S | Build | T-005 | T-924 |
| `ML2-T2.6` | Lineage: which run, dataset and parameters produced this version | PARTIAL | `version_id` | Should | S | Build | T-004, T-268 | T-925 |
| `ML2-T2.7` | A signature: input, output and inference-parameter contract | MISSING | `apps/backend/app/models/training.py:34-53` | Should | M | Build | — | T-926 |
| `ML2-T2.8` | A written description on the model and on each version | MISSING | `apps/backend/app/models/training.py:34-53` | Should | S | Build | — | T-927 |
| `ML2-T2.9` | A stored input example per version | MISSING | `apps/backend/app/routers/training.py:131-143` | Could | S | Build | — | T-928 |
| `ML2-T2.10` | Deleting a version, and what stops serving | PARTIAL | `delete_model` | Should | S | Build | T-267 | T-267 (area 5) |
| `ML2-T2.11` | Permission on one model, not only on the project | PARTIAL | `project.models` | Could | M | Build | T-005 | T-929 |
| `ML2-T2.12` | Registry events on the webhook channel | PARTIAL | `job.done` | Could | S | Build | T-435, T-438 | T-930, T-931 |
| `ML2-T2.13` | Shared and cross-workspace registries | PARTIAL | `apps/backend/app/routers/registry.py:13-15` | Could | S | Build | T-257, T-258 | T-257, T-258 (area 5) |
| `ML2-T2.14` | Comparing versions | HAVE | `CompareTab` | — | — | none | T-004 | — (guard T-004) |
| `ML2-T2.15` | Deployment-job state on a version | MISSING (by design) | `DeploymentAlias` | — | — | none | T-006 | — |

### Area 3 — Models and deployment

| ID | Capability | Status | Primary evidence | Pri | Size | Decision | RF cards | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ML3-T3.1` | Every model family states what it can do | PARTIAL | `apps/backend/app/adapters/base.py:26` | Must | M | Build | T-310, T-311 | T-932 |
| `ML3-T3.2` | One interface that loads any model | PARTIAL | `apps/backend/app/adapters/base.py:85` | Must | M | Integrate | T-288, T-342 | T-933 |
| `ML3-T3.3` | A model you write yourself | PARTIAL | `apps/backend/app/services/workflow_runner.py:185` | Could | L | Build | T-320, T-332 | T-320, T-321 (area 6) |
| `ML3-T3.4` | A declared input and output contract, enforced | PARTIAL | `apps/backend/app/adapters/base.py:107` | Must | M | Build | T-315, T-316, T-926 | T-934 |
| `ML3-T3.5` | The environment travels with the model | MISSING | `apps/backend/requirements.txt:23-32` | Should | M | Build | — | T-935 |
| `ML3-T3.6` | Save, load, and the metadata document | PARTIAL | `apps/backend/app/services/exporters.py:67` | Must | M | Integrate + build | T-288, T-291, T-342 | T-933 |
| `ML3-T3.7` | Build a container that serves this model | MISSING | `apps/backend/app/services/edge.py:114` | Should | M | Build | T-312 | T-938 |
| `ML3-T3.8` | A local server with a contract you can probe | PARTIAL | `apps/backend/app/routers/training.py:662` | Must | S | Build | T-313, T-314, T-317, T-318 | T-937 |
| `ML3-T3.9` | Batch inference as a repeatable job | PARTIAL | `apps/backend/app/routers/batch_inference.py:46` | Should | M | Build | T-354, T-355 | T-354, T-355 (area 6) |
| `ML3-T3.10` | A documented way to add a family | MISSING | `apps/backend/app/adapters/__init__.py:2` | Could | S | Build | — | T-939 |
| `ML3-T3.11` | A deployment is a resource with a state | PARTIAL | `apps/backend/app/services/deployments.py:43` | Should | S | Build | T-006 | T-940 |
| `ML3-T3.12` | Ship to someone else's machine | MISSING | `apps/backend/app/adapters/catalog.py` | Could | L | Build | T-312 | T-941 |
| `ML3-T3.13` | Size, storage and what you actually ship | MISSING | `TrainedModel.weights` | Should | S | Build | T-288, T-289 | T-936 |
| `ML3-T3.14` | Vision-language models served like any other | PARTIAL | `apps/backend/app/adapters/base.py:35` | Could | S | Build | — | T-942 |
| `ML3-T3.15` | Serving an immutable version, and what may change under it | PARTIAL | `apps/backend/app/models/training.py:83` | Must | S | Build | T-006, T-267, T-268, T-920 | T-920 (area 2) |

### Area 4 — Evaluation and GenAI

| ID | Capability | Status | Primary evidence | Pri | Size | Decision | RF cards | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ML4-T4.1` | One call scores a model on data it did not train on | PARTIAL | `apps/backend/app/handlers/training.py:166` | Must | M | Build | T-005, T-283, T-290, T-947 | T-283 (area 5), T-947 |
| `ML4-T4.2` | Task presets and the metric set each one implies | PARTIAL | `apps/backend/app/services/evaluate.py:23` | Must | M | Build | T-283, T-285, T-286 | T-950, T-285, T-286 (area 5) |
| `ML4-T4.3` | Your own metric, without forking the evaluator | MISSING | `apps/backend/app/services/evaluate.py` | Should | M | Build | T-278, T-279, T-280 | T-951 |
| `ML4-T4.4` | An evaluation set you can name, pin and reuse | PARTIAL | `Version` | Should | M | Build | T-004, T-292, T-293 | T-946, T-947 |
| `ML4-T4.5` | Score predictions you already have | PARTIAL | `apps/frontend/src/features/evaluation/EvalPanel.tsx:42-92` | Should | M | Build | T-290 | T-952 |
| `ML4-T4.6` | A metric threshold decides pass or fail | MISSING | `apps/backend/app/services/deployments.py:27` | Must | M | Build | T-277, T-295 | T-948, T-949 |
| `ML4-T4.7` | A result you can open: metrics, plots, export and the rows behind them | HAVE | `apps/backend/app/services/evaluate.py:87-101` | Must | — | Build | T-005, T-278, T-287 | — (guard T-005 area 5; sampled/unavailable states owned by T-287) |
| `ML4-T4.8` | Comparing two runs: is the difference real? | PARTIAL | `apps/frontend/src/features/insights/CompareTab.tsx:181,295, 317,351` | Should | M | Build | T-283, T-284 | T-953, T-283, T-284 (area 5) |
| `ML4-T4.9` | Built-in judges for free-text answers | MISSING | `apps/backend/app/adapters/vlm_ad.py` | Could | M | Integrate + build | T-279 | T-960 |
| `ML4-T4.10` | Your own judge, written as criteria | MISSING | `apps/backend/app/routers/playground.py:76,99` | Could | M | Build | — | T-961 |
| `ML4-T4.11` | A judge you can trust: agreement with your reviewers | MISSING | `SuspectFeedback` | Could | S | Build | — | T-962 |
| `ML4-T4.12` | Expected answers, stored as records | MISSING | `apps/backend/app/models/project.py` | Could | S | Build | T-292 | T-963 |
| `ML4-T4.13` | A trace is a record of one request, made of spans | MISSING | `apps/backend/app/models/__init__.py:13` | Should | M | Build | T-263 | T-954 |
| `ML4-T4.14` | Finding a trace: the list, the filters and the detail view | MISSING | `apps/frontend/src/routes/project/models.routes.tsx` | Should | M | Build | — | T-955 |
| `ML4-T4.15` | Instrumentation without hand-decorating every function | MISSING | `apps/backend/app/adapters/ultralytics_ad.py` | Could | M | Build | — | T-956 |
| `ML4-T4.16` | Instrumenting a function by hand | MISSING | `apps/backend/app/services/workflow_runner.py` | Could | S | Build | — | T-957 |
| `ML4-T4.17` | OpenTelemetry in and out | MISSING | `apps/backend/app/routers/__init__.py` | Could | M | Wire | — | T-958 |
| `ML4-T4.18` | A prompt you can name, version and point an alias at | MISSING | `apps/backend/app/routers/playground.py:76` | Could | M | Build | — | T-964 |
| `ML4-T4.19` | Try a prompt against models, on real images, and keep the result | PARTIAL | `apps/frontend/src/features/playground/Playground.tsx:155` | Could | M | Build | — | T-965 |
| `ML4-T4.20` | What each call cost, in time and tokens | PARTIAL | `apps/backend/app/services/evaluate.py:98` | Should | S | Build | T-263 | T-959 |

### Area 5 — Platform

| ID | Capability | Status | Primary evidence | Pri | Size | Decision | RF cards | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ML5-T5.1` | A runnable spec committed next to the code | MISSING | `apps/backend/app/routers/training.py` | Should | M | Build | T-968 | T-968 |
| `ML5-T5.2` | Entry points and typed parameters | MISSING | `packages/sdk/labeldesk/cli.py:95-103` | Should | S | Build | T-969 | T-969 |
| `ML5-T5.3` | The environment a run happened in | MISSING | `apps/backend/app/models/training.py:34-54` | Should | S | Build | T-971 | T-971 |
| `ML5-T5.4` | Running locally, and a dry run that costs nothing | PARTIAL | `apps/backend/app/routers/training.py` | Must | S | Build | T-252, T-254, T-970 | T-970 |
| `ML5-T5.5` | Choosing where a run executes | PARTIAL | `apps/backend/app/routers/remote.py:1` | Should | M | Build | T-972 | T-972 |
| `ML5-T5.6` | Pointing a client at a server, once | PARTIAL | `packages/sdk/labeldesk/client.py:51-56` | Should | S | Build | T-441 | T-441 (area 7) |
| `ML5-T5.7` | Pipelines as a file: steps, graph, caching, profiles | PARTIAL | `apps/backend/app/services/workflows.py:17-22` | Should | M | Build | T-320, T-324, T-325, T-330, T-973, T-974, T-975 | T-973, T-974 |
| `ML5-T5.8` | Recipe CLI | MISSING | `packages/sdk/labeldesk/cli.py:71-110` | Could | S | Build | T-975 | T-975 |
| `ML5-T5.9` | Accounts, default access and the role model | HAVE | `apps/backend/app/routers/auth.py:144-482` | Must | — (shipped) | Build | T-005, T-381, T-382, T-383 | — (no guard exists yet) |
| `ML5-T5.10` | A permission on one object | MISSING | `rbac.py:28-42` | Could | L | Build | T-384, T-385, T-386, T-387 | T-384, T-385, T-386, T-387 (area 7) |
| `ML5-T5.11` | An admin screen that explains access | PARTIAL | `apps/backend/app/routers/rbac.py:163-175` | Should | S | Build | T-382, T-383, T-976 | T-976 |
| `ML5-T5.12` | What sits in front of the server | PARTIAL | `apps/backend/app/main.py:66-77` | Should | S | Build | T-977 | T-977 |
| `ML5-T5.13` | Single sign-on | PARTIAL | `apps/backend/app/oidc.py:1-91` | Should | L | Build | T-423, T-426, T-430, T-432 | T-423, T-424, T-425, T-426 (area 7) |
| `ML5-T5.14` | API families and version negotiation | PARTIAL | `/api/v1` | Could | S | Build | T-441, T-981 | T-981 |
| `ML5-T5.15` | Paging and the error contract | PARTIAL | `routers/devapi.py:56-62` | Should | S | Build | T-399, T-982 | T-982 |
| `ML5-T5.16` | Speaking enough of their wire format that their client works | MISSING | `/api/2.0/mlflow/*` | Must | M | Wire | T-983, T-984 | T-983, T-984 |
| `ML5-T5.17` | The Python client, and what "skinny" means for us | PARTIAL | `packages/sdk/labeldesk/client.py` | Should | S | Integrate | T-441, T-985 | T-985 |
| `ML5-T5.18` | Other language SDKs | MISSING | `packages/sdk/labeldesk/{client.py,cli.py,_generated.py}` | Could | S | Build | T-007, T-987 | T-987 |
| `ML5-T5.19` | The command line | PARTIAL | `packages/sdk/labeldesk/cli.py:71-110` | Should | S | Build | T-441, T-986 | T-986 |
| `ML5-T5.20` | Where the model surfaces live in the sidebar | PARTIAL | `apps/frontend/src/lib/nav/registry.ts:21-25` | Should | S | Build | T-005, T-980 | T-980 |
| `ML5-T5.21` | An experiment as a thing you can name, tag and delete | MISSING | no experiment entity (grep) | Must | M | Build | T-405, T-407, T-978, T-979 | T-978, T-979 |
| `ML5-T5.22` | Workspaces: many teams, one deployment | HAVE | `apps/frontend/src/components/shell/AppSidebar.tsx:68,120` | Must | — (shipped) | Build | T-007, T-380, T-447, T-449 | — (no guard exists yet) |
| `ML5-T5.23` | One server, one store, and a way to see both | PARTIAL | `apps/backend/app/config.py:36-39` | Should | S | Build | T-986 | T-986 (shared with 5.19) |
| `ML5-T5.24` | Job status, ownership and cancellation | PARTIAL | `apps/backend/app/models/training.py:9-31` | Should | S | Build | T-016, T-481 | T-481 (wave E) |

---

## 3. Ranked build plan

The 22 Must rows come first. They are the ones a buyer meets in the first hour: a run that records what it
did, artifacts, a registered model with immutable versions, a contract, a gate, a result they can reopen,
and the wire endpoint that makes "we log from our notebook" true.

- `ML1-T1.1` Training run record and the project run list — asserted by T-900.
- `ML1-T1.2` Parameters of a run — T-901.
- `ML1-T1.3` Metric logging and the per-epoch history — T-902.
- `ML1-T1.11` Run artifacts: browse and download — T-911, T-912.
- `ML1-T1.16` Comparing runs side by side — covered by T-283, T-284 (RF `5-F5.27`).
- `ML2-T2.1` A registered model is a named container, not a training run — T-918, T-919.
- `ML2-T2.2` A model version is immutable and numbered per model — T-918, T-920.
- `ML3-T3.1` Every model family states what it can do — T-932.
- `ML3-T3.2` One interface that loads any model — T-933.
- `ML3-T3.4` A declared input and output contract, enforced — T-934.
- `ML3-T3.6` Save, load, and the metadata document — T-933.
- `ML3-T3.8` A local server with a contract you can probe — T-937.
- `ML3-T3.15` Serving an immutable version, and what may change under it — T-920 (area 2).
- `ML4-T4.1` One call scores a model on data it did not train on — T-283 (area 5), T-947.
- `ML4-T4.2` Task presets and the metric set each one implies — T-950, T-285, T-286 (area 5).
- `ML4-T4.6` A metric threshold decides pass or fail — T-948, T-949.
- `ML4-T4.7` A result you can open: metrics, plots, export and the rows behind them — guard T-005 (area 5); T-287 owns the sampled and unavailable states.
- `ML5-T5.4` Running locally, and a dry run that costs nothing — T-970.
- `ML5-T5.9` Accounts, default access and the role model — no guard card exists yet.
- `ML5-T5.16` Speaking enough of their wire format that their client works — T-983, T-984.
- `ML5-T5.21` An experiment as a thing you can name, tag and delete — T-978, T-979.
- `ML5-T5.22` Workspaces: many teams, one deployment — no guard card exists yet.

**Ordering.** Wave M is not one queue; it is four lanes that meet only in the registries:

1. **Runs and tracking** (`T-900`–`T-916`) — the store, the read API, the screens. Lands after wave B's
   train lane (`T-250`–`T-296`) because it extends `TrainedModel`/`Job` and the model detail screen that
   lane rewrites.
2. **Registry and contract** (`T-918`–`T-931`) — registered models, versions, aliases, tags, signature,
   description. Lands in parallel with lane 1; it touches the models surface, not the run tables.
3. **Models and deployment** (`T-932`–`T-942`) — flavour capability, portable artefact, signature
   enforcement, container, serve probe, batch, deployment state. After lane 2, because the contract it
   enforces is lane 2's `ML2-T2.7`.
4. **Evaluation, traces and prompts** (`T-946`–`T-965`) — classic evaluation first (Must: presets, the
   pass/fail gate), traces and prompts after. Depends on wave B's `T-283`/`T-284` and on lane 1's run
   table.
5. **Platform and wire** (`T-968`–`T-987`) — the runnable spec, experiments, the REST subset. Last: the
   wire routes read the tables lanes 1–2 create.

**Hard dependency:** `T-983`/`T-984` (the `/api/2.0/mlflow` subset) start only after lane 1 merges. They
are the only cards in this wave that open a new request surface onto customer run data, and both carry R7
review for that reason.

---

## 4. What was deliberately not built

- **A managed deployment orchestrator** (`ML2-T2.15`). The deployment-job state appears only in a release
  note; the docs page does not document it, and our serving state is the alias plus the deploy target.
  A card on an unverified claim would be invented work.
- **Stages** (`ML2-T2.5`). Upstream calls them deprecated; a second lifecycle vocabulary next to the
  deployment alias would cost a screen and teach nothing.
- **A general signature type system** (`ML2-T2.7`). LabelDesk has one input type and three inference
  parameters; the contract is derived from the task instead of importing a schema language.
- **A Python-callback custom metric** (`ML4-T4.3`). Running customer code in a multi-tenant request path
  is not a metric feature; the row keeps the behaviour (their own number) and drops the mechanism.
- **An embedded MLflow server, its auth, and its UI.** No row: the tenancy model is the product.
- **R and Java SDKs** (`ML5-T5.18` covers generation from the OpenAPI document instead). Could, and not
  worth a client per language for a CV SaaS.

---

## 5. Limits of this research

- MLflow's docs moved during the window: `tracking.html`, `models.html`, `model-registry.html`,
  `auth/` and `projects.html` are redirects to `/docs/latest/ml/…`; `recipes.html` no longer exists. The
  area files list the redirect and the page actually read, so a later reader can follow the same path.
- The release-notes trail is 60 tags (v3.7.0 … v3.18.0). Three Tracking rows and one Registry row exist
  only because of those notes, and the Registry one is unverified by docs and therefore cardless.
- Every code path in every row was verified in this baseline. Line numbers drift; the file and function
  names are the citation.
- Cards are sized 1–3 agent-hours. House practice adds review, fix rounds and rebase: budget **250–265
  agent-hours** end to end for this wave.
