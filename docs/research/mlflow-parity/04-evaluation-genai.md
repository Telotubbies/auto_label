# MLflow parity — Area 4: Evaluation & GenAI

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read at 2026-11-17. Release notes window
2025-11-17 → 2026-11-17 checked at <https://github.com/mlflow/mlflow/releases> (newest: 3.18.0,
2026-11-04; also read `releases/tag/v3.17.0`, `releases/tag/v3.16.0`).

**Doc pages covered (full navigation walk).**

Classic ML section, sidebar under `/docs/latest/ml/`:

- <https://mlflow.org/docs/latest/ml/>
- <https://mlflow.org/docs/latest/ml/evaluation/>
- <https://mlflow.org/docs/latest/ml/dataset/>

GenAI section, navigation walked from `/docs/latest/genai/` through `eval-monitor/`, `tracing/`,
`prompt-registry/`, `datasets/`, `concepts/` and `governance/`:

- <https://mlflow.org/docs/latest/genai/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/predefined/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/alignment/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/comparing-evaluation-runs/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/regression-testing/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/automatic-evaluations/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/ai-insights/detect-issues/>
- <https://mlflow.org/docs/latest/genai/eval-monitor/running-evaluation/eval-examples/>
- <https://mlflow.org/docs/latest/genai/datasets/>
- <https://mlflow.org/docs/latest/genai/concepts/evaluation-datasets/>
- <https://mlflow.org/docs/latest/genai/concepts/trace/>
- <https://mlflow.org/docs/latest/genai/assessments/expectations/>
- <https://mlflow.org/docs/latest/genai/tracing/>
- <https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/>
- <https://mlflow.org/docs/latest/genai/tracing/search-traces/>
- <https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/automatic/>
- <https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing/>
- <https://mlflow.org/docs/latest/genai/tracing/integrations/>
- <https://mlflow.org/docs/latest/genai/tracing/opentelemetry/>
- <https://mlflow.org/docs/latest/genai/tracing/prod-tracing/>
- <https://mlflow.org/docs/latest/genai/tracing/track-users-sessions/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/create-and-edit-prompts/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/manage-prompt-lifecycles-with-aliases/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/use-prompts-in-apps/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/evaluate-prompts/>
- <https://mlflow.org/docs/latest/genai/prompt-registry/playground/>
- <https://mlflow.org/docs/latest/genai/governance/ai-gateway/>

Pages read that produced no row, and why:

- `genai/` and `ml/` landing pages — navigation only; every capability they list is rowed below or
  belongs to another area.
- `genai/governance/ai-gateway/` — multi-provider routing, key custody and per-endpoint budget. That is
  a platform/key-custody feature (area 5: API keys, secrets) plus deployment (area 3), and LabelDesk
  already reaches the VLM through `adapters/vlm_ad.py`. Not an evaluation feature.
- `genai/tracing/track-users-sessions/` — feeds T4.14's session filter column; no separate row.
- `genai/tracing/prod-tracing/` — async upload, sampling, production checklist. It configures the store
  in T4.13, it is not a separate user-facing capability.
- `genai/eval-monitor/automatic-evaluations/` — online judges on live traffic. It needs the judge store
  (T4.9/T4.10) and a live LLM app; LabelDesk has no live LLM traffic (see T4.20 evidence). Documented
  in T4.9's flow as the follow-on state, not rowed or carded.
- `genai/eval-monitor/ai-insights/detect-issues/` — recurring-failure clustering over a trace corpus.
  Ships in release 3.18.0 only. It presumes T4.13 and T4.15 exist; rowing it now would be a plan for a
  feature two waves away. Named here so the omission is deliberate.
- `genai/eval-monitor/running-evaluation/eval-examples/` — input shapes for T4.1/T4.5; no separate row.
- `genai/prompt-registry/evaluate-prompts/` — the join of the prompt registry with evaluation; covered by
  T4.18 plus T4.19, no separate row.
- `genai/skill-registry/`, `genai/mcp-registry/`, `genai/serving/agent-server/`, `genai/mcp/`,
  `genai/version-tracking/`, `genai/flavors/` — agent-server, MCP and model packaging; areas 3 and 5.

## Area count

20 rows: 1 HAVE · 7 PARTIAL · 12 MISSING.

## 4.1 One call scores a model on data it did not train on
**What it does.** A single entry point takes a model, a data table, a task type and the name of the
label column, runs inference over that data, and returns metrics, artefacts and the per-row table. The
caller chooses the data, so the same model can be scored against more than the split it was trained
with. `(MLF: https://mlflow.org/docs/latest/ml/evaluation/)`
**UX flow, click by click.**
1. **Models → a model's Evaluation panel** — a primary *Evaluate again*. Its menu offers *the version it
   was trained on* (default) and *choose a set*; the panel states which split produced the numbers on
   screen. [empty: a model with no evaluation shows *Run evaluation* instead, and no charts] [loading: a
   job row appears above the panel — "Evaluating on test · 340 of 820 images" — and the old charts stay
   with a dimmed overlay] [error: "Evaluation failed: <reason>" with *Try again* and the previous result
   still shown].
2. **Pick a target** — a dialog lists the project's pinned evaluation sets and the model's own version,
   each with image count and last-run date.
3. **Confirm** — the run is queued; the panel's badge flips to *Queued*, then *Running*, then the
   numbers replace themselves in place.
4. **Read the result** — the same panel, now labelled with the set name and the run time.

**LabelDesk:** PARTIAL — `apps/backend/app/handlers/training.py:166` calls `w.evaluate(...)` once, inside
the training handler, against `versioning.version_dir(v)` — the version the model trained from.
`apps/backend/app/services/evaluate.py:35` therefore has no data parameter: the dataset is implied.
`apps/backend/app/routers/insights_models.py:44` only reads the stored report. There is no user-initiated
scoring call, and no way to name a different dataset. Re-running is planned by T-283
(`POST {P}/models/evaluate`, `eval_model` job kind), and the "different dataset" half is T4.4.
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — the evaluator already exists; what is missing is the call and the
choice of data, not a metric implementation.
**Roboflow overlap:** `5-F5.20` → T-005 (eval runs after training, guard) and `5-F5.29` → T-290
(uploaded weights get the same evaluation). No new card: T-283 delivers the re-run entry point, T-947
delivers the dataset choice.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>

## 4.2 Task presets and the metric set each one implies
**What it does.** `model_type` selects a preset: a classifier yields accuracy, precision, recall, F1,
ROC-AUC, precision-recall AUC, log loss, Brier score, a confusion matrix and a classification report; a
regressor yields MAE, MSE, RMSE, R², adjusted R², MAPE and residual plots. The preset is also what makes
`pos_label` and `average` meaningful. `(MLF: https://mlflow.org/docs/latest/ml/evaluation/)`
**UX flow, click by click.**
1. **Models → Evaluation** — the KPI strip is chosen by the model's task, and the panel says which preset
   it used: "Detection preset: mAP, per-class AP, F1 at a chosen confidence."
2. **A classification model** — the strip shows *Top-1*, *Top-5*, then *Per-class precision / recall / F1*
   and a confusion matrix by predicted class, with counts per row. [empty: a class with no test images
   reads "no examples" in its row, never 0.000]
3. **A segmentation model** — mask AP and boundary AP join the strip.
4. **A task with no preset** (pose, OBB, OCR) — the panel names the missing preset and what to do, rather
   than drawing an empty chart: "No metric preset for this task yet."

**LabelDesk:** PARTIAL — detection and segmentation presets exist and are rich
(`apps/backend/app/services/evaluate.py:23` COCO keys, `:80-83` per class, `:305` confusion);
`apps/backend/app/services/insights_eval.py:95,122,155,189` add curves, calibration and slices.
Classification has no evaluation at all: `evaluate.py:38-39` returns `_empty("test", "classification
models are not evaluated with COCO metrics")`, and the only classification numbers are the training-time
`accuracy_top1`/`accuracy_top5` from the validation split (`apps/backend/app/services/ml.py:18-20`).
`apps/frontend/src/features/insights/EvaluationTab.tsx:168` renders one panel for every task.
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — extend the existing evaluator with a task branch; the metric
definitions are a page of arithmetic, not a library.
**Roboflow overlap:** `5-F5.28` → T-285 (pixel and boundary AP for masks), T-286 (mask card, task metric
set); T-283 already advertises *accuracy* and *F1* for classification in its selector. Those cover pose,
mask and selection; no existing card computes a classification evaluation.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>

## 4.3 Your own metric, without forking the evaluator
**What it does.** A caller supplies a function that receives predictions, targets and the already-computed
metrics, and returns named aggregate values; it is passed as `extra_metrics` and lands in the result under
`<metric>/<key>`. The GenAI side has the same idea as a code-based scorer: a decorated function over a
trace that returns a feedback value with an explanation. `(MLF:
https://mlflow.org/docs/latest/ml/evaluation/)` `(MLF:
https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/)`
**UX flow, click by click.**
1. **Project settings → Evaluation → Custom metrics** — a table of the project's own metrics: name, what it
   counts, which task it applies to, and who added it. [empty: "No custom metrics yet" plus an example —
   "cost per 1,000 boxes: 1.5 × false positives + 0.2 × misses"]
2. **Add a metric** — a form builds it from the stored per-image table: pick a *condition* (a prediction
   whose class is X, a ground truth with no matching prediction, a box smaller than N px, a class
   confused with Y), an *aggregation* (count, mean confidence, sum of areas) and a *weight*.
3. **A preview** — the form shows the value on the model's last evaluation before saving, and refuses a
   metric that returns nothing on that data ("no rows match this condition").
4. **Saved** — the metric appears in the model's Evaluation strip beside the built-ins, tagged *Custom*,
   and in the CSV export. [error: a metric whose referenced class was renamed reads "class no longer
   exists" instead of a number]

**LabelDesk:** MISSING — every number in `apps/backend/app/services/evaluate.py` is computed inline; there
is no registry, no hook and no per-project metric. `apps/frontend/src/features/evaluation/EvalPanel.tsx`
renders a fixed list (`:13` `COCO_METRICS`). Grepped `custom_metric`, `extra_metrics`, `make_metric`,
`scorer` across `apps/backend/app` — no hits.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a declared aggregation over the stored eval table, not arbitrary
Python: no code execution in the request path, no sandbox to secure. Integrate nothing.
**Roboflow overlap:** none — `5-F5.22` → T-278 counts what exists, `5-F5.24` → T-279/T-280 recommend from
it; neither lets a customer define a metric.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>,
<https://mlflow.org/docs/latest/genai/eval-monitor/scorers/custom/>

## 4.4 An evaluation set you can name, pin and reuse
**What it does.** A declared set of test cases — inputs plus, optionally, the expected output — that lives
on its own, attached to an experiment, and is reused across runs and models. Records carry a source type
so results can be broken down by where the data came from, and the set can grow from production traces.
`(MLF: https://mlflow.org/docs/latest/genai/datasets/)` `(MLF:
https://mlflow.org/docs/latest/genai/concepts/evaluation-datasets/)`
**UX flow, click by click.**
1. **Data → Evaluation sets** — a list: name, images, classes, "pinned 12 Nov", last model scored against
   it. [empty: "No evaluation sets" plus *Pin one from a version*]
2. **Create** — pick a version and a split, name the set, and the dialog shows what will be frozen: 820
   images, 4,910 annotations, digest `a91f…`, and the warning "images added to the project later are not
   part of this set".
3. **Use it** — on any model's Evaluation panel, the *choose a set* menu lists it; the model is scored
   against the frozen set even when the project has moved on. [loading: the set's digest is checked before
   the job starts; a mismatch stops the run with "this set's images changed on disk"]
4. **Grow it** — from the Suspect queue or a dataset filter, *Add to evaluation set* appends the selected
   images as new rows with source *hard case* and a note.
5. **Delete** — blocked while a deployment still references a result computed on it, with the alias named.

**LabelDesk:** PARTIAL — a frozen `Version` already is a pinned dataset: `apps/backend/app/models/project.py`
`Version` (`settings`, `stats`), and every evaluation is bound to one through
`apps/backend/app/models/training.py` `TrainedModel.version_id`. But there is no set *entity*: nothing can
be named, reused across versions, or grown with new rows, and the compare screen insists on one version
(`apps/frontend/src/features/insights/CompareTab.tsx:281` — "from the same dataset version").
`apps/backend/app/services/evaluate.py:41-48` takes the version directory as given.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a set is a row that pins a version digest plus an optional appended
row list; our tenancy and storage rules apply, so no library can hold it.
**Roboflow overlap:** `5-F5.30` → T-292 (suites and check grammar), T-293 (running a suite) presuppose a
pinned dataset but declare suites, not sets; `4-F4.45` → T-004 guards the version snapshot. New card
because the entity is what both reuse.
**Sources:** <https://mlflow.org/docs/latest/genai/datasets/>,
<https://mlflow.org/docs/latest/genai/concepts/evaluation-datasets/>,
<https://mlflow.org/docs/latest/ml/dataset/>

## 4.5 Score predictions you already have
**What it does.** Instead of running the model, the caller hands over a table that already contains
predictions and targets and names the two columns; the evaluator produces the same metric set. It is how a
team scores a model it cannot run, or re-scores an export. `(MLF:
https://mlflow.org/docs/latest/ml/evaluation/)`
**UX flow, click by click.**
1. **Models → Evaluation → Score a prediction file** — a dialog with a file drop (COCO results JSON or a
   CSV of image name, class, confidence, box) and the set to score against.
2. **Column mapping** — for a CSV, one select per required field (image, class, confidence, box), with a
   preview of the first three rows. [error: "row 14 has no image name" naming the row, the file kept]
3. **Result** — the same Evaluation panel, badged *External predictions*, with the file name and digest,
   and a note that no model was run.
4. **Compare** — the external result appears in the compare picker next to trained models, marked so
   nobody mistakes it for a live model. [empty: a file whose classes match nothing in the set aborts with
   "no shared classes" and lists both sides]

**LabelDesk:** PARTIAL — stored detections can be re-scored at any confidence in the browser
(`apps/frontend/src/features/evaluation/EvalPanel.tsx:42-92` re-derives the confusion matrix from
`ev.detections`), so the "score predictions, not the model" path half exists. There is no import of a
foreign prediction file: `apps/backend/app/services/importers.py` parses COCO *annotations*
(`_coco`, `:120`) and no results format, and `evaluate.py` only ever calls `model.predict` (`:59`).
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a parser plus a scoring pass over the existing helpers; a library
would still need our parser and our tenancy.
**Roboflow overlap:** `5-F5.29` → T-290 (uploaded weights, not uploaded predictions). New card.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>

## 4.6 A metric threshold decides pass or fail
**What it does.** Named metrics get a threshold and a direction (higher is better); a validation call
compares a result against them and raises a specific failure that names the metric, the value and the
threshold. The verdict is what a pipeline gates on. `(MLF: https://mlflow.org/docs/latest/ml/evaluation/)`
**UX flow, click by click.**
1. **Project settings → Models → Release gate** — a table of rules: *mAP50 ≥ 0.80*, *recall(helmet) ≥ 0.90*,
   *median latency ≤ 250 ms*, each with an owner and the last time it blocked a release. [empty: "No
   release gate" with *Add a rule* and three suggested rules for the task]
2. **A model that fails** — the Models list shows a red *Below gate* badge and the tooltip names the rule
   and the gap; the Evaluation panel puts the rule row first, above the KPI strip.
3. **Promote** — the deploy dialog refuses: "This model fails 1 of 3 release rules: recall(helmet) 0.71 <
   0.90", with *Deploy anyway* reserved to owner/admin and audited. [error: a rule whose class was renamed
   reads "rule refers to a class that no longer exists" and does not silently pass]
4. **Pass** — the dialog shows the three rules green with their values, and the deploy proceeds.
5. **A model with no evaluation** — cannot deploy under a gate; the dialog offers *Run evaluation*.

**LabelDesk:** MISSING — nothing gates a model on a metric. `apps/backend/app/services/deployments.py:27`
`_deployable` checks only `status == "ready"`; `apps/backend/app/services/deployments.py:43` `switch` has no
metric precondition. The only thresholds in the codebase are inference thresholds — a model's own confidence
(`apps/backend/app/adapters/catalog.py:85`) and an anomaly station's score threshold
(`apps/backend/app/models/training.py:68`) — which are not release gates. `apps/backend/app/routers/training.py:168`
`leaderboard` sorts by score but never compares it to a number.
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — the rule table, the verdict and the refusal are ours; a library's
threshold object would add a dependency and no behaviour.
**Roboflow overlap:** `5-F5.21` → T-277 (the tuned confidence becomes the served default) is a different
threshold: an inference knob, not a release rule; `5-F5.30` → T-295 gates a deploy on a regression suite,
not on metric thresholds. Both are cited, neither delivers this.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>

## 4.7 A result you can open: metrics, plots, export and the rows behind them
**What it does.** An evaluation returns the metrics, a set of artefacts (plots, tables) and the evaluation
table itself; each row of that table is one test case with its input, prediction, target and, on the GenAI
side, a link to the trace that produced it. The UI renders the same objects. `(MLF:
https://mlflow.org/docs/latest/ml/evaluation/)` `(MLF:
https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/)`
**UX flow, click by click.**
1. **Models → a model → Evaluation** — KPI strip, then per-class AP, the confusion matrix, the F1 sweep,
   calibration, slices, TIDE errors and the worst images.
2. **Drill into a change** — the confidence slider re-derives precision, recall, F1 and the confusion
   matrix live; a cell click lists the images in it.
3. **Open an image** — ground truth and predictions on one canvas, with a per-box confidence and a filter.
4. **Export** — any chart offers *CSV*, *JSON* and *Copy link*; the panel offers the whole report.
5. **A sampled report** — the panel says so: "Derived charts use the stored detail sample: 120 of 820
   images."

**LabelDesk:** HAVE — `apps/backend/app/services/evaluate.py:87-101` returns metrics, per-class rows, the
sweep, confusion, PR curve, worst images, latency and per-image detections;
`apps/frontend/src/features/evaluation/EvalPanel.tsx:42,191` is the interactive panel;
`apps/frontend/src/features/insights/EvaluationTab.tsx:168,247,264,290,326` is the chart surface with CSV
and JSON per chart. Guarded by the area-5 guard (`apps/backend/tests/test_parity_guard_area5.py`, T-005)
and the eval-report permission test (`apps/backend/tests/test_r1_eval_gate.py`).
**Priority:** Must · **Size:** —
**Decision:** Build (kept) — no change proposed.
**Roboflow overlap:** `5-F5.20`, `5-F5.23` → T-005 guard; `5-F5.53`/`5-F5.54` → T-287 owns the sampled
and unavailable states; `5-F5.22` → T-278 owns per-class counts.
**Sources:** <https://mlflow.org/docs/latest/ml/evaluation/>,
<https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/>

## 4.8 Comparing two runs: is the difference real?
**What it does.** Two evaluation runs over the same dataset are compared row by row, not mean by mean: the
tool pairs each candidate row with its baseline row, reports the mean paired difference with a bootstrap
confidence interval and a p-value, names the test it used, counts ties and says when there are too few
pairs to conclude anything. `(MLF:
https://mlflow.org/docs/latest/genai/eval-monitor/comparing-evaluation-runs/)`
**UX flow, click by click.**
1. **Models → Compare** — pick two to four evaluated models on the same set; the header states the set and
   its digest.
2. **Delta table** — one row per metric: baseline, candidate, difference, interval, verdict (*better*,
   *worse*, *no difference*, *too few examples*). [empty: fewer than six shared rows ⇒ the verdict column
   reads "not enough shared rows to compare" instead of a p-value]
3. **Where it changed** — clicking a delta filters the compare view to the rows that flipped, with both
   models' predictions on one image.
4. **Ship or not** — a *Copy summary* action yields "recall +0.04, 95% CI [0.01, 0.07], p = 0.02 on
   n = 200" for the release note. [loading: the interval is computed from the stored per-row values, so
   the table fills in under a spinner that blocks nothing else]

**LabelDesk:** PARTIAL — comparison exists and is good: overlaid PR, per-class AP, a latency-vs-accuracy
frontier and a per-image disagreement detail (`apps/frontend/src/features/insights/CompareTab.tsx:181,295,
317,351`), served by `apps/backend/app/routers/insights_models.py:52`. What is missing is the *statistics*:
`services/insights.py` reports deltas and Pareto dominance but no interval, no p-value and no paired test,
and the UI prints a difference without saying whether it is noise.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a paired bootstrap over rows we already store; no library needed and
none of the GenAI comparison API is portable.
**Roboflow overlap:** `5-F5.27` → T-283 (metric choice, staleness, re-run) and T-284 (the compare screen).
Those build the surface; neither adds significance. New card, depends on T-283.
**Sources:** <https://mlflow.org/docs/latest/genai/eval-monitor/comparing-evaluation-runs/>

## 4.9 Built-in judges for free-text answers
**What it does.** A catalogue of pre-configured judges scores a response against one dimension —
relevance to the query, correctness against expected facts, completeness, fluency, safety, equivalence,
summarisation, guideline adherence, and RAG dimensions such as retrieval groundedness — returning a
pass/fail, a number or a category with an explanation. Each judge declares whether it needs ground truth
or a trace. `(MLF: https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/predefined/)`
**UX flow, click by click.**
1. **Playground → a VLM result → Score this answer** — a drawer listing the judges that apply to an image
   question: *Answers the question*, *Grounded in the image*, *Refuses when the answer is not visible*.
   [empty: a detector result (no free text) shows "this result has no text to judge" and offers nothing]
2. **Pick judges** — each row states what it checks, whether it needs a reference answer, and the model
   that will judge. *Run 3 judges* queues one call per axis.
3. **Result** — each axis shows a verdict, a one-line reason and the judged text, on the same screen as
   the answer. [loading: verdicts arrive one axis at a time; the drawer keeps the already-returned rows]
4. **Failure** — "the judge model is unavailable" with the axis named, never a silent pass.
5. **Aggregate** — the run's summary counts passes per axis over the sample set.

**LabelDesk:** MISSING — there is no judge, no scorer registry and no free-text assessment. Grepped
`judge`, `scorer`, `criteria` across `apps/backend/app` — no hits. The VLM surface that would be judged
exists: `apps/backend/app/adapters/vlm_ad.py:1` (Qwen2.5-VL: grounding, verify, VQA) and its yes/no
comparator `apps/backend/app/services/anomaly.py:176` returns `agrees` with no quality measure.
**Priority:** Could · **Size:** M
**Decision:** Integrate + Build — the judge prompts and the LLM call are ours to own (the VLM is already
ours), the *metric definitions* are the only thing worth borrowing; and they are one paragraph each, so
Build wins: our route, our store, our tenancy.
**Roboflow overlap:** none. No Roboflow card judges free text; `5-F5.24` → T-279 recommends from CV
metrics.
**Sources:** <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/predefined/>,
<https://mlflow.org/docs/latest/genai/eval-monitor/scorers/>

## 4.10 Your own judge, written as criteria
**What it does.** A custom judge is a prompt plus reserved template variables — inputs, outputs,
expectations, the trace, the conversation — that instructs a model how to grade an answer; it can return a
boolean, a number, a category or a set of named criteria, and only the reserved variables are accepted, so
the template cannot be injected with arbitrary fields. `(MLF:
https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/)`
**UX flow, click by click.**
1. **Project settings → Evaluation → Judges → New judge** — a name, a task scope (VLM answer, OCR
   extraction, caption), and a criteria box with the reserved tokens offered as chips: `{{ question }}`,
   `{{ answer }}`, `{{ reference }}`, `{{ image }}`.
2. **Test on real rows** — the editor runs the judge over 5 stored samples and shows each verdict beside
   the answer; a verdict that contradicts an obvious row is visible before saving. [empty: no samples ⇒
   "run the model in the Playground first", with the link]
3. **Save and version** — a judge is immutable once used; editing creates version 2, and results record
   which version judged them.
4. **Use it** — the judge appears in the drawer of 4.9 and can be applied to a whole sample set.
   [error: a criteria box without a reserved token is refused: "the criteria must reference at least one
   of question, answer, reference"]

**LabelDesk:** MISSING — no stored prompt-with-criteria, no judge versioning. The nearest thing is the
Playground's free-text prompt field, which is a per-request form value and is never saved
(`apps/backend/app/routers/playground.py:76,99`).
**Priority:** Could · **Size:** M
**Decision:** Build (our store/UI) — a criteria row plus one LLM call, with our own validation of the
reserved tokens; nothing here is a library contract.
**Roboflow overlap:** none.
**Sources:** <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/custom-judges/>

## 4.11 A judge you can trust: agreement with your reviewers
**What it does.** Alignment compares a judge's verdicts with human feedback recorded under the same
assessment name on the same rows, and reports how far the judge is from the human standard; the documented
workflow is create judge → collect human feedback → align → validate accuracy, and it requires both kinds
of assessment on the same traces. `(MLF:
https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/alignment/)`
**UX flow, click by click.**
1. **Evaluation → Judges → a judge → Agreement** — "Agrees with reviewers on 84% of 120 reviewed answers";
   a breakdown by verdict class and a list of the disagreements.
2. **Review a disagreement** — the row opens with the answer, the image, the judge's reason and the
   reviewer's reason, and *Change the verdict* records which one was right.
3. **Below the bar** — when agreement is under 70% the judge is badged *Not calibrated*, and any score it
   produced is marked with a caution icon wherever it is shown. [empty: a judge with no reviewed rows says
   "no reviewed answers yet — review 20 to see agreement"]
4. **Re-test** — a new judge version can be scored against the same reviewed rows, and the two agreements
   sit side by side.

**LabelDesk:** MISSING — reviewers do record verdicts on images (`SuspectFeedback` in
`apps/backend/app/models/project.py`, exported by `apps/backend/app/services/suspects.py`), but no judge
exists to agree with, and nothing computes agreement between an automated verdict and a reviewer's. The
VLM comparator's `agrees` (`apps/backend/app/services/anomaly.py:191`) is a one-off boolean, not a
calibration measure.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — one join and one percentage over rows we already have; the automated
re-alignment the docs describe is out of reach and not needed to be useful.
**Roboflow overlap:** `6-F6.19`/`6-F6.32` (active-learning caps, review cadence) use reviewer verdicts for
sampling, not for calibrating an automated judge.
**Sources:** <https://mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/alignment/>,
<https://mlflow.org/docs/latest/genai/assessments/expectations/>

## 4.12 Expected answers, stored as records
**What it does.** Expectations are the ground truth for a free-text task: an expected response attached to
a specific input, logged either on a trace or directly on a dataset record, so a judge can grade against
it and a comparison can report correctness rather than similarity. `(MLF:
https://mlflow.org/docs/latest/genai/assessments/expectations/)` `(MLF:
https://mlflow.org/docs/latest/genai/concepts/evaluation-datasets/)`
**UX flow, click by click.**
1. **Data → Evaluation sets → a set → the expected-answer column** — for each image with a question, a text
   box for the answer a person would accept, and a second for "must not say". [empty: rows without an
   expectation show *Add expected answer* and are excluded from correctness, with the count stated]
2. **Fill from a review** — in the Playground or on a suspect row, *Save as expected answer* writes the
   human answer back to the set row it came from.
3. **Use** — correctness-style judges in 4.9 light up once a row has an expectation; rows without one are
   counted in a "n = 88 of 120 have expected answers" line.
4. **Change** — editing an expectation on a pinned set creates a new set version rather than mutating the
   old one, so past scores stay explainable. [error: an expectation saved against an image that left the
   set is refused, naming the image]

**LabelDesk:** MISSING — labels are the expectations for detection (boxes in the version manifest), but
there is no place to store an expected *answer* for a VLM or OCR task, and nothing reads one.
`apps/backend/app/models/project.py` `Version` holds `settings` and `stats`, not per-row text.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — a nullable text field on the set row; no library.
**Roboflow overlap:** `5-F5.30` → T-292's check grammar is the CV analogue for pass/fail on labels; it does
not store free-text expectations.
**Sources:** <https://mlflow.org/docs/latest/genai/assessments/expectations/>,
<https://mlflow.org/docs/latest/genai/concepts/evaluation-datasets/>

## 4.13 A trace is a record of one request, made of spans
**What it does.** One request becomes a trace: `TraceInfo` carries status, duration, tags, user and
session; `TraceData` carries the spans, each with a name, inputs, outputs, start and end, parent and status,
so the whole execution can be replayed step by step. `(MLF:
https://mlflow.org/docs/latest/genai/concepts/trace/)` `(MLF:
https://mlflow.org/docs/latest/genai/tracing/prod-tracing/)`
**UX flow, click by click.**
1. **A prediction, batch run or Playground call** — every inference writes one trace: spans for *decode*,
   *preprocess*, *adapter call*, *postprocess*, each with its own duration, and the model, image and
   confidence as attributes.
2. **Model → Evaluation → a row → Trace** — a waterfall of the spans for that image, with the slowest span
   highlighted and its share of the total. [empty: a run recorded before tracing existed shows "no trace
   for this image" and the reason]
3. **A failed call** — the trace state is *error*, the failing span carries the exception class and the
   message the user saw; the buttons on the row are *Retry* and *Copy diagnostics*.
4. **Retention** — traces older than the workspace's retention window are dropped; the screen says which
   window applies. [loading: a long batch shows partial traces until the run finishes]
**LabelDesk:** MISSING — no trace or span table exists: `apps/backend/app/models/__init__.py:13`
`DOMAIN_MODULES` lists six modules and none of them holds a trace; grepped `trace`/`span_id` across
`apps/backend/app/models` — no hits. Latency is measured but flattened to one number per evaluation
(`apps/backend/app/services/evaluate.py:98`) and per playground call
(`apps/backend/app/routers/playground.py:64`).
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — traces sit next to customer images and prompts, so the store is a
tenancy and retention decision; the wire format we may later accept from an external client is OTel (4.17).
**Roboflow overlap:** `5-F5.26` → T-263 (median latency as a first-class number) surfaces one duration per
run; no existing card stores a per-request breakdown.
**Sources:** <https://mlflow.org/docs/latest/genai/concepts/trace/>,
<https://mlflow.org/docs/latest/genai/tracing/prod-tracing/>

## 4.14 Finding a trace: the list, the filters and the detail view
**What it does.** A trace table lists id, request, response, session, user, name, tokens, duration, request
time, state, run and source, with hidden columns opt-in; filters cover inputs, attributes, tags, assessments
and status, using one query syntax in the UI and the API. Selecting a row opens the span tree, the
assessments attached to it and its inputs and outputs. `(MLF:
https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/)` `(MLF:
https://mlflow.org/docs/latest/genai/tracing/search-traces/)`
**UX flow, click by click.**
1. **Project → Traces** — the newest first: time, image, model, state, duration, token count if the call
   was an LLM. [empty: "No traces yet — run a prediction" plus the link]
2. **Filter** — chips: `state:error`, `model:<name>`, `duration > 2000`, `tag.batch:<id>`, `user:me`, and
   a free-text search over the request. Filters combine with AND. [empty vs no-match are different
   screens: "no traces at all" versus "no trace matches these filters" with *Clear filters*]
3. **Open one** — the span waterfall, the model inputs, the raw response, the assessments, and *Copy trace
   id*. Linkable by URL so a reviewer can paste one into a ticket.
4. **Save a view** — the current filters and columns become a named view, shared with the project.
5. **A slow trace** — sort by duration; the top row names the span that dominated.

**LabelDesk:** MISSING — there is no trace list, no span view, no saved view. The nearest surfaces list
jobs and models (`apps/frontend/src/routes/project/models.routes.tsx`) and event-search frames
(`apps/backend/app/routers/` streams), neither of which is a per-request record.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — a screen over our own table and our own permission gate.
**Roboflow overlap:** none — no Roboflow card lists per-request inference records.
**Sources:** <https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/>,
<https://mlflow.org/docs/latest/genai/tracing/search-traces/>

## 4.15 Instrumentation without hand-decorating every function
**What it does.** A supported library is traced by one autolog call: the framework's own internal calls
become spans in one connected trace, with no per-function work and consistent metadata. Integrations exist
for agent frameworks, model providers and gateways. `(MLF:
https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/automatic/)` `(MLF:
https://mlflow.org/docs/latest/genai/tracing/integrations/)`
**UX flow, click by click.**
1. **Project settings → Tracing** — a table of the components LabelDesk can trace on its own: *Ultralytics
   inference*, *RF-DETR*, *HF transformers*, *SAM 3*, *Qwen-VL over the OpenAI-compatible endpoint*,
   *CLIP embeddings*, each with a switch, its library version and "what it records".
2. **Turn one on** — the row shows *Tracing since 12 Nov* and the last captured trace as a link. [empty:
   a component not installed reads "not available in this install" with the reason]
3. **Run the model** — the trace appears under Traces with the framework's own spans (tokenizer, forward,
   postprocess) without any code change in the adapter.
4. **Turn it off** — the switch stops new spans; existing traces stay until retention drops them. [error:
   an integration that raises on import is reported per component and never fails the request]

**LabelDesk:** MISSING — adapters call libraries directly (`apps/backend/app/adapters/ultralytics_ad.py`,
`rfdetr_ad.py`, `hf_ad.py`, `sam3_ad.py`, `vlm_ad.py`) with no instrumentation hook and no trace store to
write to.
**Priority:** Could · **Size:** M
**Decision:** Build (our store/UI) — one `span` context around each adapter call, opened by the predict
path; the library's autolog would write to their store, and their store is the thing we are not adopting.
**Roboflow overlap:** none.
**Sources:** <https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/automatic/>,
<https://mlflow.org/docs/latest/genai/tracing/integrations/>

## 4.16 Instrumenting a function by hand
**What it does.** A decorator turns any function into a span: parent-child relationships are detected, the
name, inputs, outputs and duration are recorded, exceptions become span events, and it works on sync,
async, generator and async-generator functions alongside autolog. A second form records a span from inside
a block. `(MLF: https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing/)`
**UX flow, click by click.**
1. **A custom workflow block** — a project's workflow step written by a customer is wrapped in the
   decorator, so it appears as its own span inside the run's trace under the name given.
2. **The trace** — the span shows the arguments it received and the value it returned, with the
   exception recorded in red if it failed.
3. **Truncation** — a huge input is truncated with a note, and the full value stays in the run's artefacts.
   [empty: a span whose function returned nothing says "no output" rather than rendering blank]
4. **Nesting** — two decorated functions called from one request appear as parent and child, not two roots.

**LabelDesk:** MISSING — no decorator, no span API, no context. `apps/backend/app/services/workflow_runner.py`
runs blocks with its own logging only.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — the decorator is twenty lines over the context 4.13 introduces.
**Roboflow overlap:** none.
**Sources:** <https://mlflow.org/docs/latest/genai/tracing/app-instrumentation/manual-tracing/>

## 4.17 OpenTelemetry in and out
**What it does.** The server exposes an OTLP endpoint at `/v1/traces`, so any language can send traces in;
traces produced by the SDK conform to the OTel trace spec and GenAI semantic conventions, so they can be
exported to another backend without translation. `(MLF:
https://mlflow.org/docs/latest/genai/tracing/opentelemetry/)`
**UX flow, click by click.**
1. **Project settings → Tracing → OpenTelemetry** — an endpoint URL with a copy button, the header it
   expects, and a one-line example. [empty: tracing not yet enabled shows the two steps to enable it]
2. **Send a trace from elsewhere** — a customer's own service posts to the endpoint; the trace appears in
   Traces with its spans and the service name as its source.
3. **Export** — a *Send traces to* block adds a collector URL and headers; a *Test* button sends one span
   and reports the collector's response. [error: a rejected export names the status and keeps retrying
   with backoff; the queue depth is visible]
4. **Key rotation** — the ingest token can be rotated with a grace window so a live sender does not lose
   traces.

**LabelDesk:** MISSING — no OTLP route, no exporter. `apps/backend/app/routers/__init__.py` `ROUTERS`
contains no tracing router; `services/exporters.py` exports datasets, not telemetry.
**Priority:** Could · **Size:** M
**Decision:** Wire-compatible (OTel) — accept and emit the open protocol, behind our auth, rather than
invent a format; the ingest is a small parser plus our store.
**Roboflow overlap:** none.
**Sources:** <https://mlflow.org/docs/latest/genai/tracing/opentelemetry/>

## 4.18 A prompt you can name, version and point an alias at
**What it does.** A prompt is a named object whose versions are immutable; each version carries a template,
a commit message, an optional structured-output schema and an optional model configuration; an alias points
at a version so a deployment can say "production" instead of "3". Loading is by
`prompts:/<name>/<version-or-alias>`. `(MLF:
https://mlflow.org/docs/latest/genai/prompt-registry/create-and-edit-prompts/)` `(MLF:
https://mlflow.org/docs/latest/genai/prompt-registry/manage-prompt-lifecycles-with-aliases/)`
**UX flow, click by click.**
1. **Workspace → Prompts** — the list: name, latest version, the aliases pointing at it, who last edited,
   and which models use it. [empty: "No prompts yet" plus *Create prompt*]
2. **Create** — name, template with `{{ }}` variables, a commit message, and optional advanced blocks for a
   JSON response schema and model settings (model, temperature, max tokens).
3. **New version** — editing creates version *n+1* with a diff against the chosen base; the old version
   stays readable and copyable. [error: a template with an unclosed `{{` is refused with the position]
4. **Alias** — *production* moves to the new version in one action; the previous target is recorded and
   *Roll back* moves it back. Aliases are visible per prompt, not global.
5. **Where it is used** — a usage panel lists the models and playground runs that resolved this prompt,
   with the version they resolved. [empty: "not used by any model yet"]

**LabelDesk:** MISSING — no prompt entity. The only prompt in the product is a per-request form field on the
playground call (`apps/backend/app/routers/playground.py:76`, `:99` → `kw["prompt"]` at `:54`), and the VLM
adapter's own instruction text lives in code (`apps/backend/app/adapters/vlm_ad.py`). Nothing stores a
template, a version or an alias; grepped `prompt` in `apps/backend/app/models` — no column.
**Priority:** Could · **Size:** M
**Decision:** Build (our store/UI) — a template table with immutable versions is our data model, and our
models must reference it for lineage; the load-by-URI behaviour is a twenty-line resolver.
**Roboflow overlap:** none — `5-F5.7`/`5-F5.9` (recipe editor, speed preset) version a *training*
configuration, not a prompt.
**Sources:** <https://mlflow.org/docs/latest/genai/prompt-registry/create-and-edit-prompts/>,
<https://mlflow.org/docs/latest/genai/prompt-registry/manage-prompt-lifecycles-with-aliases/>,
<https://mlflow.org/docs/latest/genai/prompt-registry/use-prompts-in-apps/>

## 4.19 Try a prompt against models, on real images, and keep the result
**What it does.** A browser surface for prompts: load a registered prompt version, fill its variables,
tune sampling parameters, attach tools, request structured output, replay a multi-turn conversation, and
compare outputs; prompts are evaluated across models and datasets and the results are tracked. `(MLF:
https://mlflow.org/docs/latest/genai/prompt-registry/playground/)` `(MLF:
https://mlflow.org/docs/latest/genai/prompt-registry/evaluate-prompts/)`
**UX flow, click by click.**
1. **Workspace → Playground** — image, up to three models, a question box, and *Compare*. Latency per
   model and the boxes with a confidence filter. (Today.)
2. **Load a prompt** — a select lists the workspace's prompt versions; picking one fills the question and
   pins the version in the header: "using helmet-count v3".
3. **Fill variables** — the template's variables appear as named fields; *Run* substitutes them.
4. **Keep the run** — *Save comparison* stores the prompt version, the models, the latency and the outputs,
   and the run joins the prompt's usage history. [empty: a workspace with no prompt shows "Save this
   question as a prompt" and the one-click path]
5. **Score it later** — a saved comparison can be added to an evaluation set and judged (4.9), closing the
   loop from prompt to number. [error: a model that failed keeps its error per column and never blanks the
   others]

**LabelDesk:** PARTIAL — `apps/frontend/src/features/playground/Playground.tsx:155` runs one image
through up to three models side by side, with a free-text question (`:281`) and a per-model latency badge
(`:91`); `apps/backend/app/routers/playground.py:38` does the work, `:64` times it. Missing: the prompt is
not saved or versioned, the run is not stored, there is no history and no scoring handoff — the response is
computed and discarded.
**Priority:** Could · **Size:** M
**Decision:** Build (our store/UI) — the screen exists; the gap is persistence and a prompt reference,
both ours.
**Roboflow overlap:** none. Roboflow's model playground is a different feature and is not in this backlog.
**Sources:** <https://mlflow.org/docs/latest/genai/prompt-registry/playground/>,
<https://mlflow.org/docs/latest/genai/prompt-registry/evaluate-prompts/>

## 4.20 What each call cost, in time and tokens
**What it does.** Traces carry latency and token usage per step, aggregated on the trace row (input,
output and total tokens) and itemised per span, so a slow or expensive step is visible and cost can be
attributed to a model, a user or a session. `(MLF:
https://mlflow.org/docs/latest/genai/concepts/trace/)` `(MLF:
https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/)`
**UX flow, click by click.**
1. **Traces → duration or tokens column** — sort by either; the row shows input/output/total tokens for a
   VLM call and milliseconds for a detector call.
2. **A model's Costs panel** — calls, median and p95 latency, total tokens, and estimated spend per day for
   the window, with the model's per-token price recorded once in settings. [empty: a model with no priced
   call says "no token cost recorded — add a price to price these calls"]
3. **Drill** — clicking a bar opens the traces behind it, filtered to that model and window.
4. **A budget line** — the panel names the usage this contributes to the workspace's metered quota
   (`metering.summary`), so credits and tokens are not confused. [error: a VLM that returns no usage block
   is recorded as "tokens not reported" and excluded from cost, not counted as zero]

**LabelDesk:** PARTIAL — latency is recorded per evaluation (`apps/backend/app/services/evaluate.py:98`
`latency_ms`) and per playground call (`apps/backend/app/routers/playground.py:64`), and the workspace
meters usage in credits (`apps/backend/app/services/metering.py:27` `record`, `:71` `used`, `:116`
`summary`). There is no per-call record, no token count and no price: `apps/backend/app/models/insights.py`
`UsageEvent` carries a metric name and quantity, not a call.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — one row per call in the store 4.13 introduces; metering already
exists and must not be duplicated.
**Roboflow overlap:** `5-F5.26` → T-263 (median latency per run) is the same number at a coarser grain.
**Sources:** <https://mlflow.org/docs/latest/genai/concepts/trace/>,
<https://mlflow.org/docs/latest/genai/tracing/observe-with-traces/ui/>

## Judgment calls
- **4.1 carries no card.** The docs' entry point is one call, and its two halves are already planned:
  re-running an evaluation exists in T-283 (`POST {P}/models/evaluate`, `eval_model` kind) and choosing the
  data is 4.4's card. Writing a third card would plan the same route twice.
- **4.7 is HAVE and carries no card** although the detail sample is capped at 120 images
  (`services/evaluate.py:28`). The cap is deliberate and stated in the UI
  (`EvaluationTab.tsx:257`); making it visible in every state is T-287's job, so it is cited, not re-planned.
- **4.3 is a declared aggregation, not a Python plugin.** The docs' "custom metric is a function" is a
  library contract; in a multi-tenant SaaS it is remote code execution. The card keeps the behaviour a
  buyer wants (their own number) and drops the mechanism. This is the largest deliberate deviation in the
  area.
- **The GenAI half is Could, not Should, wherever it needs a GenAI surface LabelDesk does not sell.** Of the
  GenAI rows only 4.20 is Should, because latency and cost are already on screen for CV models; 4.9–4.12 and
  4.15–4.19 are Could and sized at 2–3 h each.
- **4.13 (traces) is Should, not Could,** because it improves the CV product without any LLM: "which step of
  this batch run was slow" is a support question we answer by hand today.
- **4.17 is wire-compatible, not integrate.** We accept and emit OTel because that is the protocol a
  customer's own service speaks; adopting the tracing SDK would put a second store behind our tenancy.
- **Two contract objects, one concept.** The classic `EvaluationMetric` and the GenAI `Scorer` are
  documented as not interoperable. One row (4.3) covers both because LabelDesk has one stored eval table;
  the card names both behaviours and implements neither's API.
- **Release-only features rowed where they change a row:** statistical comparison (4.8, in 3.18.0),
  per-step trace cost (4.20, 3.17.0/3.18.0), trace columns and saved views (4.14, 3.16.0). Automatic issue
  detection, skill registry, custom trace views and online code-based evaluation ship only in 3.16–3.18 and
  are named in the pages list as deliberately not rowed — each needs a trace corpus we do not have yet.
- **`automatic-evaluations` (online judges) is not rowed.** It is a mode of 4.9/4.10 over live traffic, and
  LabelDesk's only model-facing LLM call is the VLM comparator. Rowing it now would be a card with no
  traffic to judge.
