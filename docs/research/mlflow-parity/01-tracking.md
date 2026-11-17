# MLflow parity — Area 1: Tracking

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read at 2026-11-17. Release notes window
2025-11-17 → 2026-11-17 checked at https://github.com/mlflow/mlflow/releases (per-tag pages
`/releases/tag/v3.7.0` … `/releases/tag/v3.18.0`).

**Doc pages covered (full navigation walk).** The docs moved: `tracking.html` now 302s to
`/docs/latest/ml/tracking/`, and the ML sidebar is Build → Tracking (5 pages), Search (3 pages), Model,
Datasets, plus Team Collaboration → Architecture (3 pages). Every page below was fetched in this session.

Tracking section
- https://mlflow.org/docs/latest/ml/tracking/
- https://mlflow.org/docs/latest/ml/tracking/quickstart/
- https://mlflow.org/docs/latest/ml/tracking/tracking-api/
- https://mlflow.org/docs/latest/ml/tracking/autolog/
- https://mlflow.org/docs/latest/ml/tracking/system-metrics/

Search section
- https://mlflow.org/docs/latest/ml/search/search-runs/
- https://mlflow.org/docs/latest/ml/search/search-models/
- https://mlflow.org/docs/latest/ml/search/search-experiments/

Build section, adjacent pages read for tracking semantics
- https://mlflow.org/docs/latest/ml/dataset/
- https://mlflow.org/docs/latest/ml/mlflow-3/

Team Collaboration → Architecture (backend/artifact store, tracking server)
- https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/
- https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/
- https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store/

Pages that produced no row of their own, and why
- `search-experiments/` — the filter identifiers here are experiment name/tags only; LabelDesk has no
  experiment entity (the project is the container), so the syntax detail lands in row 1.8 instead.
- `mlflow-3/` — migration guide; used as evidence for rows 1.11 and 1.12 (model artifacts moved out of the
  run's Artifacts tab into Logged Models in v3), not a feature row.
- `quickstart/` — the 6-step tutorial restates rows 1.1/1.2/1.3/1.11; used as a source, no new row.
- `api_reference/rest-api.html` — fetched, but the page renders its endpoint list client-side (one string in
  the HTML). Endpoint paths for rows 1.14/1.18 were therefore read from the service definition the page is
  generated from, `mlflow/protos/service.proto` (`/mlflow/runs/*`, `/mlflow/metrics/*`,
  `/mlflow/artifacts/*`), and every path below is quoted from that file.

Release notes that carried tracking features with no docs page: v3.15.0 (shareable Runs-table views),
v3.15.0 (presigned artifact transfer, presigned-only mode), v3.17.0 (`restore_run` / `restore_experiment`
fluent API, run-level sub-resource permission tiers), v3.16.0 (`basic-auth` fail-closed by default),
v3.13.0 (a local file-system store now raises unless `MLFLOW_ALLOW_FILE_STORE=true`), v3.10.0
(multi-workspace "Organization" support), v3.7.0 (SQLite became the default backend). Rows 1.9 and 1.15
exist only because of these.

## Area count

18 rows: 1 HAVE · 10 PARTIAL · 7 MISSING.

## 1.1 Training run record and the project run list
**What it does.** A *run* is one execution of training code; it carries metadata (start/end time, status,
user, source), the parameters and metrics it logged, and the artifacts it wrote. The UI lists an
experiment's runs and opens one on its own page. `(MLF: /docs/latest/ml/tracking/ §Runs, §Tracking UI)`
**UX flow, click by click.**
1. **Models** (`/:ws/:project/models`) — the run list, newest first, each row a model with name, task,
   variant, version number and status. [empty: `No models yet.` + *Train your first model*] [loading: row
   skeletons keep the table height] [error: a retry card naming the failure]
2. **Row → detail** — the right-hand panel shows the run: progress or `Epoch N of M`, metrics block,
   evaluation tab, leaderboard tab. [empty: `No evaluated models yet`] [error: `Training failed: …`]
3. **Insights → Training** (`/:ws/:project/model-insights`) — all runs with a history, newest first, as
   overlay chips. [empty: `No training history yet`]
**LabelDesk:** HAVE — `apps/backend/app/models/training.py:34-53` (`TrainedModel`: `status`, `metrics`,
`history`, `classes`, `weights`, `created`), `apps/backend/app/routers/training.py:146-165` (`GET /models`),
`apps/frontend/src/features/project/Models.tsx:214` (empty state) and `:256-268` (tabs, progress, `Epoch N of M`).
The record is a training run, not an arbitrary code execution: there is no "start a run without training".
That narrower entity is row 1.18, and it is the only reason this row is not also MLflow-shaped.
**Priority:** Must · **Size:** S
**Decision:** Build (our store/UI) — the run table is tenancy-scoped data; MLflow's store has no workspace
column (`/docs/latest/self-hosting/workspaces/` is a header-scoped bolt-on, not row-level isolation).
**Roboflow overlap:** `5-F5.1` → T-263 (run list host), guard `5-F5.16` → T-005
**Sources:** https://mlflow.org/docs/latest/ml/tracking/, https://mlflow.org/docs/latest/ml/search/search-runs/

## 1.2 Parameters of a run
**What it does.** `log_param`/`log_params` record the configuration a run was started with; params are
stored as strings, searchable with string comparators, and shown as the run's parameter table. Values are
immutable per run in practice — logging the same key twice raises on the SQL store.
`(MLF: /docs/latest/ml/tracking/tracking-api/ §Data Logging)`
**UX flow, click by click.**
1. **Models → a finished run** — open the *Run settings* block: dataset version, model family + variant,
   epochs, image size, batch, max minutes, continued-from. [empty: an old run with no job row renders
   `Parameters were not recorded for this run.`] [loading: three skeleton rows] [error: the block renders
   the raw status and a retry link, never a blank card]
2. **Insights → Training → a run chip** — the same values in the chart caption's source line, so a curve can
   be attributed without leaving the tab. [empty: the caption drops the parameter clause]
3. **Copy parameters** — one button copies the block as JSON for a bug report or a repeat run.
**LabelDesk:** PARTIAL — parameters are persisted only as the job payload: `apps/backend/app/routers/training.py:281-282`
(`Job.params = {"model_id", "version_id", "options": {family, variant, epochs, imgsz, batch, max_minutes, resume_from}}`),
read back in `apps/frontend/src/features/project/Models.tsx:265` (`m.job?.params.options?.epochs`). They are not
on `TrainedModel` (`models/training.py:34-53`), not returned by `model_out` (`routers/training.py:90-103`), not
searchable, and disappear for any run whose job row was pruned. Resolved defaults (patience=50, device) are in
the adapter, not the record (`adapters/ultralytics_ad.py:222-226`).
**Priority:** Must · **Size:** S
**Decision:** Build (our store/UI) — one read-only projection over data we already store; no library involved.
**Roboflow overlap:** `5-F5.7`, `5-F5.9` → T-255, T-256 (they own the *editor* for the options; this row shows
the options a finished run used, which those cards do not add)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/tracking-api/, https://mlflow.org/docs/latest/ml/search/search-runs/

## 1.3 Metric logging and the per-epoch history
**What it does.** `log_metric(key, value, step, timestamp)` records a value at a step (a 64-bit integer, may
be negative, may skip) and a millisecond timestamp; the same key logged repeatedly becomes a *metric history*
series that the UI plots as a line chart. Step and timestamp are independent: a run may backfill a step with a
custom timestamp. `(MLF: /docs/latest/ml/tracking/tracking-api/ §Precise Metric Tracking)`
**UX flow, click by click.**
1. **A training run** — the adapter appends one row per epoch; the worker writes the whole array every epoch
   so the curve survives a crash. [empty: `No metrics logged` inside the Training tab for a run that recorded
   epochs but no numeric keys] [error: a run that failed before epoch 1 has no history and is excluded]
2. **Insights → Training** — pick 1–6 runs, choose quality/loss/other groups, EMA smoothing 0–0.90, log-scale
   toggle. [loading: two chart skeletons] [error: `Training curves could not be loaded` + retry]
3. **Hover a point** — the tooltip names run + metric and the value to 3 decimals; a reader comparing two
   runs on the wall needs the epoch, and today that is the only axis available.
**LabelDesk:** PARTIAL — `apps/backend/app/handlers/training.py:90-96` appends `{"epoch": ep, **metrics}` and
rewrites `TrainedModel.history`; `apps/backend/app/services/insights.py:672-685` buckets the keys into
quality/loss/other; `apps/frontend/src/features/insights/TrainingTab.tsx:33-43` plots them. Missing: no
timestamp per point (only `epoch`), so a 30-epoch run cannot say *when* epoch 12 happened, and nothing can
distinguish a real step from an epoch. `insights.py:673` filters only `k != "epoch"`, so any non-metric key
added to the row becomes a chart series.
**Priority:** Must · **Size:** S
**Decision:** Build (our store/UI) — three columns of JSON in a row we already own; a library would not know
our history shape.
**Roboflow overlap:** `5-F5.16` → T-005 (guard), T-272 (search-side charts only)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/tracking-api/, https://mlflow.org/docs/latest/ml/tracking/system-metrics/

## 1.4 Watching a run while it trains
**What it does.** A run is visible with status `RUNNING` and its metrics update as they are logged; the UI
polls and redraws, so a long job is debuggable before it ends.
`(MLF: /docs/latest/ml/tracking/ §Runs, §Tracking UI)`
**UX flow, click by click.**
1. **Models → a queued run** — `Waiting for a worker…`, then a progress bar with `Epoch 4 of 30`.
   [empty: n/a — the row exists from the moment it is queued] [loading: indeterminate bar while queued]
   [error: a stalled job flips to `failed` with the watchdog message]
2. **Insights → Training** — select the running run and watch the curves advance without a reload.
   [empty: a run that has not logged epoch 1 yet renders `No metrics logged`] [error: the tab keeps the last
   good curves and shows a retry banner rather than an empty grid]
**LabelDesk:** PARTIAL — the run list already updates: `apps/frontend/src/features/project/Models.tsx:265-268`
renders `Epoch ${m.history.length} of …` and the job's percentage, and `handlers/training.py:94-96` writes
history + progress per epoch. But the analytics are explicitly not polled:
`apps/frontend/src/features/insights/useInsights.ts:1-2` ("No polling: … a tab focus refetch is enough"),
so a user watching a 30-epoch run sees a frozen curve until they refocus the tab.
**Priority:** Should · **Size:** S
**Decision:** Build (our UI) — the data is already on the wire once per epoch; only the refetch policy is wrong.
**Roboflow overlap:** `5-F5.19` → T-266 (spend meter + log tail), `5-F5.16` → T-005 guard
**Sources:** https://mlflow.org/docs/latest/ml/tracking/

## 1.5 Chart types for comparing runs
**What it does.** The runs view plots any metric or param as a line over steps, as a bar or scatter across
runs, and as a parallel-coordinates chart where each run is one line crossing N metric axes — the fastest way
to see which run dominates on several metrics at once. Charts are cards that can be added, moved and sized.
`(MLF: /docs/latest/ml/tracking/ §Tracking UI; https://github.com/mlflow/mlflow/releases/tag/v3.17.0 —
"Fix Parallel Coordinates metric label contrast on Compare Runs", #26275)`
**UX flow, click by click.**
1. **Insights → Training** — three stacked groups of line charts (quality, loss, other), one card per group,
   each with CSV + JSON export and a table view for screen readers.
   [empty: `No metrics logged`] [error: `Training curves could not be loaded`]
2. **Insights → Compare** — precision–recall lines overlaid, per-class AP as grouped bars, latency vs mAP50 as
   a scatter with the Pareto front outlined. [empty: `Select at least two models`]
3. **Compare 4+ runs on 5 metrics** — there is no single view for it today; the user reads four separate
   charts and remembers the numbers.
**LabelDesk:** PARTIAL — line (`TrainingTab.tsx:52-96`), bar (`CompareTab.tsx:52-71`), scatter
(`CompareTab.tsx:73-107`) all exist with CSV/JSON/table affordances (`CompareTab.tsx:294-326`). No parallel
coordinates, no user-added chart card, no area/stacked form. The chart primitives are shared and reusable:
`apps/frontend/src/features/insights/charts.tsx` (`ChartCard`, `EChart`, `DataTable`, imported at
`TrainingTab.tsx:6-9`).
**Priority:** Should · **Size:** S
**Decision:** Build (our UI) — ECharts renders parallel coordinates natively; no new dependency.
**Roboflow overlap:** `5-F5.27` → T-284 (it adds the metric selector to the same tab and owns `CompareTab.tsx`)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/, https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 1.6 Nested runs (parent and child)
**What it does.** `start_run(nested=True)` creates a child run under the open parent; children carry
`tags.mlflow.parentRunId` and are found by searching that tag. The documented uses are a cross-validation
fold per child and one child per point of a hyper-parameter sweep.
`(MLF: /docs/latest/ml/tracking/tracking-api/ §Hierarchical Runs with Parent-Child Relationships)`
**UX flow, click by click.**
1. **Train → Continue from model** — the picker already offers a ready model of the same variant
   (`Train.tsx:115-120`); starting the run creates a new row.
2. **Models → the child run** — a `Continued from <parent name>` link, one click to the parent, and the
   parent's row shows `N continuations`. [empty: a run started from pretrained weights shows no lineage]
3. **Insights → Training** — a "show continuations" chip adds the parent's curve behind the child's, so a
   resumed run reads as one line of work instead of two unrelated chips.
**LabelDesk:** MISSING — the relationship is *recorded but never exposed*: `routers/training.py:262-268`
validates `resume_from` and `:278` stores it inside `Job.params.options.resume_from`; nothing on
`TrainedModel` (`models/training.py:34-53`) or in `model_out` (`routers/training.py:90-103`) names the parent,
and `services/insights.py:621-669` has no parent concept.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — the edge already exists in a JSON blob; promoting it to a row key plus a
link is smaller than any library call.
**Roboflow overlap:** `5-F5.18` → T-005 (guard: resume itself is HAVE), `5-F5.8` → T-259 (the weights *picker*)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/tracking-api/

## 1.7 Run tags and the run note
**What it does.** `set_tag`/`set_tags` attach arbitrary key/value strings to a run; system tags
(`mlflow.user`, `mlflow.source.name`, `mlflow.parentRunId`) are set automatically; `mlflow.note.content` is
the one user-editable tag and renders in the run's Notes section. Tags are searchable with `tags.` and
`IS NULL / IS NOT NULL`. `(MLF: /docs/latest/ml/tracking/tracking-api/ §Smart Tagging, §System Tags Reference)`
**UX flow, click by click.**
1. **Models → a run → Tags** — key/value chips (`team: vision`, `nightly`, `line-3`), an editable note with
   Save/Cancel, and the system tags in a dimmed second row (`Trained by <user>`, `Started 12 Nov 14:02`,
   `Continued from …`). [empty: `No tags yet.` + *Add tag*] [loading: the chip row keeps its height]
   [error: a save failure keeps the typed text and offers retry]
2. **Models → filter** — `tag:nightly` narrows the list; `tag:nightly` with no match shows
   `No runs match this filter.` and a *Clear filters* action.
3. **Delete a tag** — the chip's × removes it after a confirm; the run's audit entry records it.
**LabelDesk:** MISSING — no tag field on the run (`models/training.py:34-53`), none in `model_out`
(`routers/training.py:90-103`); `GET /models` (`:146-165`) has no filter argument at all. The only free-form
text is the run's `name` and the job's `error`.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a JSON column plus one PATCH route; the alternative (borrowing MLflow's
tag store) would put customer metadata in a second database.
**Roboflow overlap:** none
**Sources:** https://mlflow.org/docs/latest/ml/tracking/tracking-api/, https://mlflow.org/docs/latest/ml/search/search-runs/

## 1.8 Searching, filtering and ordering runs
**What it does.** A SQL-like filter string selects runs: `metrics.`, `params.`, `tags.`, `datasets.` and
`attributes.` prefixes; comparators `= != > >= < <= LIKE ILIKE IN IS NULL IS NOT NULL`; `AND` only (`OR` is
not supported); fields with special characters go in backticks; `order_by` takes `ASC|DESC` (default `ASC`,
and `start_time DESC, run_id ASC` when omitted); `max_results` caps the page; `run_view_type`
(`ACTIVE_ONLY|DELETED_ONLY|ALL`) includes or excludes deleted runs; `search_all_experiments` widens the scope.
`(MLF: /docs/latest/ml/search/search-runs/)`
**UX flow, click by click.**
1. **Models → filter bar** — a text field with a one-line cheat sheet (`metric:map50>=0.5`, `param:epochs=30`,
   `tag:nightly`, `status:ready`, `task:detect`, `version:12`) and chips for each active clause.
   [empty: `No runs match this filter.` + *Clear filters* — distinct from the page's `No models yet.`]
   [loading: the row list dims, the filter bar keeps focus] [error: an unparseable clause underlines the token
   and says `Unknown field: metricx — try metric:, param:, tag:, status:, task:, version:`]
2. **Column header → sort** — click sorts by created/name/AP; the arrow shows direction; the URL carries it so
   a refresh keeps the view.
3. **Recent filters** — the last 3 filters as chips under the field; *Clear all* resets to the unfiltered list.
**LabelDesk:** MISSING — `apps/backend/app/routers/training.py:146-165` returns every model of the project
ordered by `created desc` with no parameters; `:168-191` sorts the leaderboard in Python by AP only. The front
end filters by nothing (`apps/frontend/src/lib/api/models.ts:10`). The database-side equivalent the query would
compile to does not exist.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a filter compiles to SQLAlchemy over tables we own; wire-format search
(`/api/2.0/mlflow/runs/search`) is the same filter language parsed into our rows, and is planned separately in
rows 1.14/1.18 so the two share one parser.
**Roboflow overlap:** none — the image query language (`2-F2.27`, `1-F4.3`) is a different corpus and it is
owner-area 2's card
**Sources:** https://mlflow.org/docs/latest/ml/search/search-runs/, https://mlflow.org/docs/latest/ml/search/search-experiments/

## 1.9 Saved table views
**What it does.** A named view of the runs table stores the visible columns, their order and width, the filter,
and the sort, and is shared by URL so a teammate opens the same lens.
`(MLF: https://github.com/mlflow/mlflow/releases/tag/v3.15.0 — "Sharable table views", no docs page yet)`
**UX flow, click by click.**
1. **Models → Views** — a select listing saved views (this project's, then the user's own), *Save current view…*
   and *Copy link*. [empty: `No saved views. Save the current columns and filters as a view.`]
   [error: a view naming a column that no longer exists opens with that column dropped and a one-line notice]
2. **Save current view** — name it, tick *Share with the project*, confirm; the active view is highlighted and
   the URL carries `?view=<token>`.
3. **Open a shared link** — the page restores columns, order, filter and sort; a foreign workspace's view token
   answers 404 like any other foreign id.
**LabelDesk:** MISSING — the models page keeps no view state: `Models.tsx` holds tabs and a selection in
component state only, the URL carries `?model=` (`Models.tsx:208`) and nothing else, and there is no table
column chooser. No storage for views anywhere in `app/models/`.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — v1 is URL state plus a per-user list; a server table would be a new
entity for a preference, so the first slice stores nothing the server must own.
**Roboflow overlap:** none
**Sources:** https://github.com/mlflow/mlflow/releases/tag/v3.15.0

## 1.10 System metrics during a run
**What it does.** With the sampler on, a run logs CPU, memory, disk, network and (when a GPU is present) GPU
utilisation, GPU memory, power and temperature every 10 s by default, all named with a `system/` prefix so they
group together; the sampling interval and the number of samples aggregated per log line are configurable, and
system metrics appear in the run's metrics section like any other metric.
`(MLF: /docs/latest/ml/tracking/system-metrics/)`
**UX flow, click by click.**
1. **Models → a finished run → Resources** — a compact table (GPU util avg/max, GPU memory peak, CPU avg,
   disk free at end) with the sample count. [empty: `No resource samples — this run trained on a worker without
   the sampler.`] [error: a run whose worker lacked a GPU shows CPU/disk rows and `GPU not reported`]
2. **Insights → Training → System group** — a fourth chart group (utilisation, memory, disk) sharing the same
   run selection, so "why was epoch 20 slow" is answerable next to the loss curve.
3. **Export** — the CSV includes the `system/*` keys, as any other metric.
**LabelDesk:** MISSING — nothing samples the worker: `handlers/training.py:90-96` writes only whatever the
adapter's epoch callback reports, and `adapters/ultralytics_ad.py:201` forwards `trainer.metrics` (model
metrics, not host metrics). No `psutil`, no `nvidia-smi` call anywhere in `apps/backend`.
**Priority:** Should · **Size:** M
**Decision:** Build (our worker) — the sampler is ~40 lines of stdlib plus one `nvidia-smi` call; sampling is a
property of *our* GPU worker, which no library can observe.
**Roboflow overlap:** none
**Sources:** https://mlflow.org/docs/latest/ml/tracking/system-metrics/

## 1.11 Run artifacts: browse and download
**What it does.** A run's artifacts are its output files — weights, plots, reports, data — listed in a tree in
the UI and downloadable per file or as a folder. Since MLflow 3, model artifacts live on the Logged Model page
instead of the run's Artifacts tab; the artifact store can be local, S3, Azure, GCS, B2, SFTP/NFS/HDFS, and the
server can stream them or hand out presigned URLs.
`(MLF: /docs/latest/self-hosting/architecture/artifact-store/; /docs/latest/ml/mlflow-3/ §Model Artifacts Storage Location)`
**UX flow, click by click.**
1. **Models → a run → Artifacts** — rows for `weights/best.pt`, `weights/last.pt`, `results.csv`, the plots the
   trainer wrote, the evaluation report JSON and any edge build, each with size and a download button.
   [empty: `This run produced no downloadable files.`] [loading: five skeleton rows]
   [error: a file deleted on disk renders the row with `No longer on disk` and a disabled button, never a 500]
2. **Download** — a signed, short-lived URL (existing `sign_path`), so the browser goes straight to the file.
3. **Open the eval report** — the stored evaluation JSON opens in a viewer with a copy-to-clipboard action.
**LabelDesk:** PARTIAL — `TrainedModel.weights` is a single path served through `sign_path`
(`routers/training.py:92`, `security.py:117`), and edge builds are already enumerated with sizes
(`routers/training.py:94-98`). The trainer's run directory exists and is deterministic —
`adapters/ultralytics_ad.py:186` writes `DATA_DIR/runs/<model_id>/` with `weights/best.pt`,
`weights/last.pt`, plots and `results.csv` (`:222-231`) — but nothing lists it: there is no artifact route,
no artifact component, and `job.result` only carries stage timestamps (`handlers/training.py:51-56`).
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — we already own the bytes and the signing; an object-store abstraction is
premature while every artifact is on the worker's local disk.
**Roboflow overlap:** `4-F4.34`/`4-F4.35` → T-224…T-229 are *dataset export*, a different artifact; none
**Sources:** https://mlflow.org/docs/latest/self-hosting/architecture/artifact-store/, https://mlflow.org/docs/latest/ml/mlflow-3/

## 1.12 Logged models and per-run checkpoints
**What it does.** A logged model is an entity in its own right: it can be created without a run, has its own
id, params, metrics, tags and artifacts, can be `PENDING`/`READY`/`FAILED`, and several checkpoints of one run
can each be logged with their own step and metrics. Model URIs became `models:/<model_id>`.
`(MLF: /docs/latest/ml/tracking/tracking-api/ §Model Management (New in MLflow 3); /docs/latest/ml/mlflow-3/)`
**UX flow, click by click.**
1. **Models → a finished run → Checkpoints** — `best.pt (epoch 27 · mAP50 0.71)` and `last.pt (epoch 30 ·
   mAP50 0.69)`, each with size, download, and a `deployed` badge when it is the file behind the alias.
   [empty: a run started by a family whose adapter keeps only the best file renders one row and a note]
   [error: a missing directory renders `Checkpoints were not kept for this run.`]
2. **Pick the artifact to deploy** — *Deploy this checkpoint* is disabled (only the registered model can be
   aliased, by design) and explains why in a tooltip.
3. **Registry handover** — the checkpoint's epoch and metric link to the same run in the model registry list.
**LabelDesk:** PARTIAL — one model row per run: `TrainedModel` fuses run and model (`models/training.py:34-53`)
and `weights` points at exactly one copied file (`routers/training.py:92`); the trainer's `best.pt`/`last.pt`
are both on disk (`adapters/ultralytics_ad.py:229-234`) and the best is chosen by the adapter, never recorded as
a choice. `try: resume_from` accepts only a ready `TrainedModel` (`routers/training.py:262-268`), so a
checkpoint is not addressable. No PENDING/FAILED lifecycle for the model entity itself (status mirrors the job).
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — the checkpoints are files we already have; naming them is a read-time
listing, and a second entity would duplicate the registry's job.
**Roboflow overlap:** `5-F5.33`/`5-F5.34` → T-268 (stable identity + per-version alias, area 5)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/tracking-api/, https://mlflow.org/docs/latest/ml/mlflow-3/

## 1.13 Dataset inputs of a run
**What it does.** `log_input(dataset, context)` attaches the dataset a run consumed — name, automatically
computed digest, source (file/URL/S3/DB), schema and profile — with a context such as `training` or
`evaluation`; runs are then searchable by `datasets.name`, `datasets.digest` and `datasets.context`, and a
metric can be tied to the dataset that produced it.
`(MLF: /docs/latest/ml/dataset/ §Core Components, §Dataset Tracking in MLflow UI)`
**UX flow, click by click.**
1. **Models → a run → Dataset** — version number and name, `1 240 images · 992 train / 198 valid / 50 test`,
   class list with counts, the manifest digest (first 8 chars + copy), and the evaluation split.
   [empty: a run whose version row was deleted renders `The dataset version behind this run was deleted.`]
   [error: a version with no stats renders counts from the manifest and `profile unavailable`]
2. **Click the digest** — copies it; pasting it into the run filter (row 1.8) finds every run on that exact
   snapshot, which is what makes two runs comparable.
3. **Compare guard** — a run on a different version says `Trained on a different dataset version` and is not
   offered for comparison, matching `services/insights.py:714-715`.
**LabelDesk:** PARTIAL — the run stores `version_id` (`models/training.py:39`) and the version stores
`stats` + `settings` (`models/project.py:194-205`), and the eval report records its split
(`services/insights.py:605`). Missing: no digest, so "same dataset" is an id equality only; no source/profile
contract; no explicit inputs list with per-input context; the UI shows the version on the model card
(`TrainingTab.tsx:180`) but no dataset block, no class list and no digest anywhere.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — the version snapshot *is* the dataset entity; a digest over its manifest
plus a read-only block is the whole feature.
**Roboflow overlap:** `4-F4.44` → T-004 (guard), `4-F4.45` → T-004; the version snapshot itself is area 4's
**Sources:** https://mlflow.org/docs/latest/ml/dataset/, https://mlflow.org/docs/latest/ml/search/search-runs/

## 1.14 Metric history read API
**What it does.** `GET /api/2.0/mlflow/metrics/get-history?run_id&metric_key` returns every `(step, timestamp,
value)` of one metric; the UI's charts are built from it, and a client can pull a series without the run body.
`(MLF: /docs/latest/ml/tracking/system-metrics/ — `get_metric_history` shown; path from mlflow/protos/service.proto)`
**UX flow, click by click.**
1. **A script or notebook** — `client.get_metric_history(run_id, "system/gpu_util")` against LabelDesk returns
   the series, because the run lives behind our auth. [empty: a metric key that was never logged returns an
   empty list, not a 404] [error: an unknown run id returns 404 with our error body]
2. **A chart on another screen** — any surface can fetch one series by URL without the full run payload.
3. **A CSV export of one series** — served from the same endpoint, so the export and the chart cannot drift.
**LabelDesk:** MISSING — the only series read is the whole-project payload
`GET /insights/training?runs=a,b` (`routers/insights_models.py:25-31`), which returns every run's full history
(`services/insights.py:655-669`); there is no per-key endpoint, and no wire route at all.
**Priority:** Could · **Size:** S
**Decision:** Wire-compatible (MLflow REST subset) — the endpoint name and payload are fixed by the client we
want to accept; it is a projection over `TrainedModel.history`, not new storage, and it sits behind our API-key
auth with the key's workspace deciding visibility.
**Roboflow overlap:** none
**Sources:** https://mlflow.org/docs/latest/ml/tracking/system-metrics/, https://mlflow.org/docs/latest/api_reference/rest-api.html

## 1.15 Run deletion and restore
**What it does.** Deleting a run marks it deleted rather than erasing it, so it can be restored; metadata and
artifacts stay in the stores until an explicit garbage collection pass removes the deleted runs. `restore_run`
is the fluent counterpart, and `run_view_type` decides whether deleted runs are listed.
`(MLF: /docs/latest/self-hosting/architecture/backend-store/ §Deletion Behavior;
https://github.com/mlflow/mlflow/releases/tag/v3.17.0 — "Add mlflow.restore_experiment() and mlflow.restore_run()", #25852)`
**UX flow, click by click.**
1. **Models → a run → Delete** — confirm, and the run leaves the list. [empty: the list's own empty state]
   [error: a run behind a deployment alias refuses with `This run serves “production”. Move the alias first.`]
2. **Trash → Runs** — who deleted it, when, and days left; *Restore* puts it back with its history and metrics.
3. **Permanent delete** — only from the trash, typed confirmation, and it removes the weights file too.
**LabelDesk:** PARTIAL — deletion is hard and immediate: `apps/backend/app/routers/training.py:314-324`
(`DELETE /models/{mid}`, no soft stamp, weights file left on disk), driven from
`apps/frontend/src/features/project/Models.tsx:248` (a `confirm()` then a delete). There is no restore path and
no trash for runs.
**Priority:** Should · **Size:** M (already planned elsewhere)
**Decision:** Build (our store/UI) — soft delete is tenancy data; the deletion policy is ours.
**Roboflow overlap:** `5-F5.37` → T-267 (delete with the serving consequence, typed name);
`7-F7.43` → T-405, T-406, T-407 (`TrainedModel` gains `deleted_at`/`deleted_by`, purge, trash screen).
Covered — no card here.
**Sources:** https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/, https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 1.16 Comparing runs side by side
**What it does.** The compare view puts several runs of one experiment next to each other: overlaid metric
charts, a parameter/metric diff table, and chart forms (bar, scatter, parallel coordinates) that make a winner
visible. `(MLF: /docs/latest/ml/tracking/ §Tracking UI — "Experiment-based run listing and comparison";
https://github.com/mlflow/mlflow/releases/tag/v3.17.0 — Parallel Coordinates on Compare Runs)`
**UX flow, click by click.**
1. **Insights → Compare** — pick 2–4 evaluated models from the same version and task; ineligible ones are
   dimmed with the reason. [empty: `Select at least two models`] [error: `Comparison failed` + retry; a mixed
   selection answers 400 with the reason]
2. **Read the four blocks** — PR overlay, per-class AP bars, latency/Pareto scatter, disagreement gallery.
3. **Decide** — the summary line names the dataset version, split, threshold and disagreement count.
**LabelDesk:** PARTIAL — end to end and CV-specific: `routers/insights_models.py:52-60`, guards in
`services/insights.py:694-719` (same task, same version, same split, no classify), UI in
`features/insights/CompareTab.tsx:241-326`, selection logic in `modelSelection.ts` with tests at
`apps/frontend/tests/compare-selection.test.mjs:9-35`. Gaps named by the Roboflow cards: comparison is fixed to
the COCO metrics (no task-appropriate metric for segmentation/keypoints), and a stale evaluation is compared
silently.
**Priority:** Must · **Size:** M (already planned elsewhere)
**Decision:** Build (our store/UI) — a screen over our eval payload; MLflow's compare UI cannot read our
detections.
**Roboflow overlap:** `5-F5.27` → T-283 (task metric + staleness), T-284 (metric selector). Covered — no card.
**Sources:** https://mlflow.org/docs/latest/ml/tracking/, https://github.com/mlflow/mlflow/releases/tag/v3.17.0

## 1.17 Automatic capture per model family (the autolog equivalent)
**What it does.** `mlflow.autolog()` records metrics, parameters, the model signature, artifacts and the input
dataset with no log statements, per library: Keras/TensorFlow (fit params, EarlyStopping), LightGBM, Paddle,
PySpark ML, PyTorch Lightning, scikit-learn (including one child run per CV fold for search estimators), Spark
datasources, statsmodels, XGBoost — with the exact captured fields documented per library.
`(MLF: /docs/latest/ml/tracking/autolog/ §Supported Libraries)`
**UX flow, click by click.**
1. **Train → pick a family** — the card states what will be captured automatically (`mAP50, mAP50-95,
   precision, recall, per-epoch losses`). [empty: an adapter that is not installed renders its reason instead]
2. **Models → a run → Captured automatically** — the keys the adapter wrote, grouped and labelled, with the
   family named; the same list is what the Training tab groups.
3. **A user's own script** — nothing to click yet; today only our adapters can produce a run (see row 1.18).
**LabelDesk:** PARTIAL — the three adapters capture without user code: `adapters/ultralytics_ad.py:197-210`
(per-epoch `trainer.metrics` + summed `train/loss`), `adapters/rfdetr_ad.py:247-276`,
`adapters/hf_ad.py:170-197`; headline metrics are picked at `services/ml.py:14-26`. Missing: the captured set
is undocumented per family in the product (no "captured automatically" surface), nothing records the model
signature or an input example, and a user's own training script cannot log at all.
**Priority:** Should · **Size:** S
**Decision:** Integrate + Build — the *in-product* capture stays ours (our adapters); the *user-script* half is
the MLflow client contract, and borrowing `mlflow-skinny`'s client is only worth it after the wire endpoints of
row 1.18 exist.
**Roboflow overlap:** `5-F5.28` → T-285, T-286 (task-appropriate metrics — they define *what is computed*;
this row declares *what is captured* and shows it)
**Sources:** https://mlflow.org/docs/latest/ml/tracking/autolog/, https://mlflow.org/docs/latest/ml/tracking/tracking-api/

## 1.18 Logging from a notebook or another client (the wire API)
**What it does.** Any client speaking the REST API can create a run, log params/metrics/tags in batches,
attach an input, fetch and search runs, and read a metric's history: `POST /api/2.0/mlflow/runs/create`,
`/runs/log-batch`, `/runs/log-parameter`, `/runs/log-metric`, `/runs/set-tag`, `/runs/log-inputs`,
`/runs/update`, `POST /api/2.0/mlflow/runs/search`, `GET /api/2.0/mlflow/runs/get`,
`GET /api/2.0/mlflow/metrics/get-history`, `/artifacts/list`, and the restore/delete pair. A local notebook
points `set_tracking_uri()` at the server and logs while it trains.
`(MLF: /docs/latest/ml/tracking/quickstart/ §Step 5; /docs/latest/self-hosting/architecture/tracking-server/ §Logging to a Tracking Server; paths from mlflow/protos/service.proto)`
**UX flow, click by click.**
1. **Settings → API keys** — an admin mints a key with the `train` scope; the notebook sets
   `MLFLOW_TRACKING_URI` and the bearer token.
2. **Notebook** — `with run(): log_param(...); log_metric("val_loss", v, step=e)`; each call lands in the
   workspace that owns the key. [error: an unknown field or a bad body answers 400 with the offending key;
   a run id from another workspace answers 404]
3. **Models** — the notebook run appears in the same list as a worker run, with its params, its curve and its
   absence of a checkpoint, so a data scientist's experiment is comparable to a trained model.
**LabelDesk:** MISSING — no run/experiment/param store beyond `TrainedModel`+`Job`, and no `/api/2.0/mlflow/*`
route at all (`apps/backend/app/routers/__init__.py:15-21` lists every router mounted). The public API is
v1 developer routes only (`routers/devapi.py:104` `start_training`, `:111` `get_job`, `:123` `list_models`) and
the SDK exposes `train()`/`job()` but no `log_*` (`packages/sdk/labeldesk/client.py:114-127`).
**Priority:** Should · **Size:** L
**Decision:** Wire-compatible (MLflow REST subset) — their client, our tenancy: the subset is implemented as
routes in front of our tables, authenticated by our API keys (`app/apikeys.py:79 resolve_key`, `KeyCtx.need`
`:53`), with the key's workspace deciding what exists. No MLflow server, no second database, no second auth
boundary.
**Roboflow overlap:** none
**Sources:** https://mlflow.org/docs/latest/ml/tracking/quickstart/, https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/, https://mlflow.org/docs/latest/api_reference/rest-api.html

## Judgment calls

- **"Run" is our training record, not a general execution.** MLflow's run wraps any `python train.py`. LabelDesk's
  buyer trains a detector, so 1.1 is HAVE with `TrainedModel` as the run, and the general-case capability is
  isolated in 1.18 rather than pretending 1.1 is missing.
- **1.2 params PARTIAL, not MISSING.** The values exist and a user can see epochs/variant on the run
  (`Models.tsx:265`); what is absent is a first-class, searchable, always-present parameter block. Calling it
  MISSING would overstate the gap and duplicate T-255/T-256.
- **1.16 compare stays PARTIAL with no card.** The flow is complete for COCO detection/segmentation; the named
  gaps (task metric, stale evaluation) are owned by T-283/T-284. Writing a third card would split one file
  three ways.
- **1.15 delete/restore gets no card.** T-267 owns the delete UX and T-405–T-407 already add `deleted_at`/
  `deleted_by` to `TrainedModel` plus the trash screen. The only MLflow-only nuance (restore) is inside T-406.
- **1.9 saved views is Could and stores nothing server-side.** Release-notes-only feature; v1 is URL state plus
  a per-user list, because a new table for a column preference fails the ponytail test. If the PM wants
  server-shared views, that is a follow-up, not this card.
- **1.18 wire API is Should, not Must.** A CV buyer never types `set_tracking_uri`; a data-science team
  evaluating us does. It gates no other row, so it sits last in the dependency chain.
- **Parallel coordinates (1.5) mounts in the Training tab, not Compare.** T-284 owns `CompareTab.tsx`
  exclusively; the Training tab already has the run selection and the metric catalogue, so the new chart is one
  new file plus one mount line.
- **System metrics write into `history`, not a new table (1.10).** `services/insights.py:672-685` already groups
  unknown keys, so `system/*` keys chart for free; the trade-off is that they show in every history export.
  Accepted, and noted in the card.
- **No `OR` and no arbitrary JSON.** The run filter (1.8) mirrors MLflow's `AND`-only syntax on purpose: one
  grammar, one parser, and the wire search endpoint can reuse it later.
