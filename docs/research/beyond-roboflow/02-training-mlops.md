# Group 2 — Training and MLOps for vision

Scope: Ultralytics Platform (ex-HUB), Landing AI (LandingLens, plus what replaced it), Hugging Face AutoTrain, Weights & Biases, ClearML, Voxel51 FiftyOne. Fetched 2026-11-17: the Ultralytics Platform index and its cloud-training page, the Ultralytics benchmark page, the W&B sweeps/registry/artifacts/reports pages, the ClearML docs index and its workers-and-queues page, the FiftyOne Brain page, the Landing AI platform page, the Hugging Face AutoTrain index, and the HF model-card spec. Not opened: W&B Tables and Weave pages, ClearML HPO/autoscaling/dataset pages beyond their nav entries, LandingLens product docs (all Landing AI docs now cover document extraction only), and any logged-in UI.

Two findings shaped the list. First, **AutoTrain is discontinued** — its own docs say no new features and no fixes, and point at Axolotl/TRL; nothing here is copied from it, and it is evidence that a "one-click fine-tune" screen is table stakes rather than a differentiator (https://huggingface.co/docs/autotrain/index). Second, **LandingLens has no public documentation left**: Landing AI's docs describe Agentic Document Extraction only, and `landing.ai/deployment` renders the document product. The one vision page still live is the platform overview, so LandingLens claims here rest on that page and nothing deeper.

Everything below is a capability Area 5 (train/models) and Area 6 (deploy/workflows) do **not** describe. Where our code already does the thing, the card says HAVE and names the remaining gap, so the lead can see which "beyond parity" items are actually behind parity.

---

## 2.1 Running an experiment

### G2.1 Sweep a version across several parameter sets (W&B Sweeps, ClearML)
- **What the user does:** stops picking one learning rate and instead gives a range per field, a metric to maximise and a trial budget; the platform runs the trials and keeps the best.
- **Who uses it:** an ML engineer on the third or fourth iteration of a class that will not learn, and an agency delivering to a fixed latency target.
- **Flow:** 1. Train screen -> *Run one* / *Sweep* toggle. 2. Sweep panel: one row per parameter with min / max / list or a fixed value, plus the metric (`mAP50-95`, `recall@0.5`, or a saved slice from G2.7) and a cap in minutes or credits. 3. Estimate block shows trials x per-trial cost, and a cheap pre-flight trial is offered first `[loading: estimate recomputed on each keystroke]`. 4. Start -> the run list grows row by row with each trial's parameter fingerprint; a trial that is clearly losing is stopped early and marked *pruned*, not *failed* `[error: budget exhausted -> the sweep ends cleanly, best trial kept, remainder refunded]`. 5. Winning row -> *Make this the run*.
- **Why it is easy:** the search space is a form over the fields already on the Train screen, so nobody writes a script, and the trial budget sits in the same block as the price.
- **Products with it:** W&B Sweeps — https://docs.wandb.ai/guides/sweeps (random, grid and Bayesian search; agents parallelise a sweep across machines); ClearML — https://clear.ml/docs/latest/docs/ (hyperparameter optimisation built on the same parameter-override mechanism its agents use).
- **Why it matters for LabelDesk:** our Train screen exposes three numbers (`Train.tsx:23`), so a buyer comparing us to any MLOps tool sees "you cannot even tune", and a sweep is the cheapest way to keep a slow GPU queue busy.
- **LabelDesk code evidence:** no sweep concept — `TrainIn` carries one value per field (`apps/backend/app/routers/training.py:213-223`), a submit builds exactly one `TrainedModel` and one `Job` (`:267-279`), and the screen has one epochs/size/batch triple (`apps/frontend/src/features/project/Train.tsx:23,107-109`); `none found (searched sweep|hyperparam|optuna|tuner|search_space across apps/backend/app)`.
- **Suggested status:** MISSING — one run per submit, no space, no trial loop, no pruning.
- **Suggested priority / size:** Should, L.

### G2.2 The run keeps its exact configuration, and can be exported and re-imported (Ultralytics Platform)
- **What the user does:** opens a finished run and reads the whole argument set it used, copies it as JSON, pastes it into a new run to reproduce it, and sees which values differ from the defaults.
- **Who uses it:** the person answering "what exactly produced this model" six weeks later, and a second engineer reproducing a colleague's result.
- **Flow:** 1. Model page -> *Configuration* card listing every argument with non-default values marked and defaults greyed. 2. *Copy* puts JSON on the clipboard; *Download* gives YAML or JSON. 3. On the Train screen, paste or drop a `.yaml`/`.json` -> fields fill, out-of-range values are clamped with a warning next to the field `[error: unknown key -> named in the paste dialog, not silently dropped]`. 4. If the source run used a dataset version, the destination names that version and warns when it differs.
- **Why it is easy:** the same object goes out and comes back in, so a reproduction is a paste rather than a retyped form.
- **Products with it:** Ultralytics Platform — https://docs.ultralytics.com/platform/train/cloud-training/ (copy a completed model's configuration as JSON, paste or drag a file back in, out-of-range values clamped with warnings, a modified badge).
- **Why it matters for LabelDesk:** our options live on the `Job` row and the model has no configuration field, so deleting the run loses the recipe — a support ticket waiting to happen and an audit answer we cannot give.
- **LabelDesk code evidence:** options are written to `Job.params` (`apps/backend/app/routers/training.py:272-277`) while `TrainedModel` stores only metrics/history/classes/weights/family/variant/licence (`apps/backend/app/models/training.py:34-53`); `model_out` returns no configuration (`routers/training.py:90-98`); the form has three editable numbers plus a name (`features/project/Train.tsx:103-120`).
- **Suggested status:** PARTIAL — the values exist on the job row, with no card, no export, no import.
- **Suggested priority / size:** Should, S.

### G2.3 One ledger row per run, with its configuration as sortable columns (W&B runs table)
- **What the user does:** scans every run of a project in a table whose columns are parameters and metrics, sorts by the metric that matters, pins one run as a baseline and reads the delta on the others.
- **Who uses it:** an ML engineer choosing what to ship, and a reviewer asking "is this run better than the one in production, and why".
- **Flow:** 1. Insights -> *Runs*. 2. Table: name, date, version, architecture, epochs/size/batch, then the metrics; columns toggle and are remembered per user. 3. Click a header to sort; the best value in each column carries a marker. 4. *Pin as baseline* -> every other row prints `+0.03 mAP` and `+12 s`. 5. Row click -> the existing curve overlay for the pinned set `[empty: no completed run -> one line saying what to do first]`.
- **Why it is easy:** the comparison is a table sort, so "which of my nine runs is best at 640 px" is one click instead of opening nine cards.
- **Products with it:** W&B — https://docs.wandb.ai/guides/reports/ (a report is built by selecting runs, charts and panels into one page); sweep results are read as such a run set — https://docs.wandb.ai/guides/sweeps.
- **Why it matters for LabelDesk:** we already overlay curves for chosen runs (`routers/insights_models.py:27-34`), but the only ranked list sorts by AP and hides the configuration; "can I compare runs" is a buyer's first question after "does it train".
- **LabelDesk code evidence:** `GET /leaderboard` returns id/name/variant/task/status/version/ap/latency/created and sorts by AP only (`apps/backend/app/routers/training.py:163-186`); `features/insights/CompareTab.tsx:301-323` has a metric table with CSV/JSON export but no parameter columns and no baseline; `features/project/Models.tsx` renders cards.
- **Suggested status:** PARTIAL — curves overlay and a metric table exist; no parameter columns, no sort by metric, no baseline delta.
- **Suggested priority / size:** Should, M.

### G2.4 Promotion is a request that names an approver, not an alias edit (W&B Registry, ClearML)
- **What the user does:** proposes a model for production, a second person signs it off, and the signed record is what the endpoint points at; a later rollback is a new signed record, not a silent swap.
- **Who uses it:** a QA lead or ML owner at a customer who has to show an auditor who approved the model inspecting their parts.
- **Flow:** 1. Model page -> *Request promotion*, with a target stage (`staging` / `production`), a written reason and the evaluation that justifies it. 2. Request lands in a queue beside the current holder of that stage, both sets of numbers visible `[empty: nothing pending -> the queue says so]`. 3. Approver opens it, compares against what is live, approves or rejects with a note. 4. On approve the alias moves and an append-only event records who, when, from which model, plus the request text. 5. Rollback is a new event pointing at the previous model, same record shape `[error: model was deleted -> the request is refused with the reason, not a 500]`.
- **Why it is easy:** the decision is taken on one screen showing both candidates' numbers, so nobody approves from two browser tabs.
- **Products with it:** W&B Registry — https://docs.wandb.ai/guides/registry/ (promote a version into a collection, track lineage and change history, per-registry permissions, automate downstream steps); ClearML — https://clear.ml/docs/latest/docs/ (model lifecycle stages inside the experiment tracking layer).
- **Why it matters for LabelDesk:** we already have `staging`/`production` aliases, a `previous_model_id` rollback target and an append-only event table — better than parity — but any admin can flip it alone; adding the request object turns an existing strength into an audit artefact.
- **LabelDesk code evidence:** `DeploymentAlias` holds alias, model, `previous_model_id`, `updated_by` (`apps/backend/app/models/training.py:77-89`); `DeploymentEvent` is append-only with `action` and `user_id` (`:91-101`); switch and rollback routes in `apps/backend/app/routers/deployments.py:13-45`; no request, approver or note anywhere — `none found (searched approved_by|sign-off|promote|request)`.
- **Suggested status:** PARTIAL — the pointer and its history exist; the human decision around it does not.
- **Suggested priority / size:** Should, M.

---

## 2.2 Provenance and records

### G2.5 Lineage that carries the inputs, and can re-run from any node (W&B Artifacts)
- **What the user does:** clicks a model in the pipeline graph and sees the exact image set, frozen split, configuration and parent run behind it, then starts a new run from that node.
- **Who uses it:** whoever is asked "where did this model come from" during an incident, and the engineer rebuilding a model after its weights were deleted.
- **Flow:** 1. Insights -> *Lineage* (batches -> versions -> runs -> models -> streams). 2. Click a run node -> side panel with version number, image and annotation counts, the configuration from G2.2, the evaluation summary, and the downstream consumers (aliases, streams) with their current state `[empty: a node with no child says "not deployed" instead of showing nothing]`. 3. *Re-run with these inputs* seeds the Train form from that version and configuration. 4. *Open the exact images* jumps to the dataset grid filtered by that version's frozen manifest.
- **Why it is easy:** the graph is already drawn, so the panel only has to answer "what went in" and offer the two actions that follow.
- **Products with it:** W&B Artifacts — https://docs.wandb.ai/guides/artifacts/ (a run declares dataset inputs and model outputs and lineage is derived from those declarations); the registry shows the same lineage per linked version — https://docs.wandb.ai/guides/registry/.
- **Why it matters for LabelDesk:** we ship a lineage view most competitors at our price do not have, but the run node is a shell — no configuration, no hash, no action. Filling it is days, and it is the story a regulated buyer wants to hear.
- **LabelDesk code evidence:** `apps/backend/app/services/insights_lineage.py:1-5,74-76` builds batch/version/run/model/stream nodes and edges from the frozen manifest, `:53-64` pulls image and annotation counts out of it; the UI is five fixed columns with a counts chart (`apps/frontend/src/features/lineage/Lineage.tsx:15-45`); no configuration, hash or action on a node.
- **Suggested status:** PARTIAL — the graph is real; the node payload and the action are missing.
- **Suggested priority / size:** Should, M.

### G2.6 A model card ships with the weights (Hugging Face model cards)
- **What the user does:** fills one page per model — intended use, known limits, the dataset it learned from, its evaluation, licence — and downloads it as a file beside `best.pt`, so the receiving team has the caveats without asking.
- **Who uses it:** a supplier handing a model to a plant's OT team, and a procurement reviewer who needs a document rather than a dashboard.
- **Flow:** 1. Model page -> *Card* tab, pre-filled from what we already know (version, class list, evaluation numbers, licence, training date, slice results from G2.7). 2. Author fills *intended use*, *not for*, *known failure modes*, *contact*; required markers block publish until all four are filled. 3. Preview renders as the reader will see it `[empty: first visit shows the generated draft and what is missing]`. 4. Publish freezes a revision; a later edit creates revision 2 and the model page names the live one. 5. *Download bundle* gives weights + card + evaluation JSON in one zip.
- **Why it is easy:** most fields derive from data we already store, so the author writes four short paragraphs and gets an artefact a customer can file.
- **Products with it:** Hugging Face — https://huggingface.co/docs/hub/model-cards (Markdown plus YAML metadata: licence, datasets, base model, structured evaluation results, CO2 estimate); W&B keeps the same metrics visible on a linked registry version — https://docs.wandb.ai/guides/registry/.
- **Why it matters for LabelDesk:** exports today are images and labels, and the model leaves with no document; for a Thai factory handing a model to a systems integrator the missing card is why the handover stalls, and it is cheap because the numbers are already computed.
- **LabelDesk code evidence:** the model payload carries licence, classes, metrics and a weights URL and nothing prose-shaped (`apps/backend/app/routers/training.py:90-98`); `TrainedModel` has no description, notes or card column (`apps/backend/app/models/training.py:34-53`); weights are served as a single signed file (`routers/training.py:92`); `none found (searched card|readme|description|intended use)`.
- **Suggested status:** MISSING — no document object, no revisions, no bundled download.
- **Suggested priority / size:** Should, M.

### G2.7 A slice of the score opens into the images that caused it (FiftyOne evaluation, W&B Artifacts)
- **What the user does:** reads "dark images score 0.41 against 0.78 overall", clicks the bar, and lands on the dark images with the objects that were missed or mislabelled highlighted, ready to send to a labelling batch.
- **Who uses it:** the person deciding what to collect or relabel next; on a fixed camera it is usually the night shift that is failing.
- **Flow:** 1. Evaluation tab -> *Slices*, dimension picker (image size, tag, batch, brightness, label source, split). 2. Bars per value with AP, image and instance counts. 3. Click a bar -> gallery of that slice, worst first, with the ground-truth / prediction toggle already used by the confusion view. 4. *Send to labelling* creates a batch from the selection and names the slice in its description `[empty: a slice with no failures says so instead of showing an empty grid]`. 5. The slice definition can be saved and re-run after the next training, so "did the night shift improve" is one click.
- **Why it is easy:** the slice computation already exists; the missing step is carrying its file list into the gallery and the batch action.
- **Products with it:** FiftyOne — https://docs.voxel51.com/brain/index.html (evaluation views filter to a scenario and the same view is mined for more data); W&B — https://docs.wandb.ai/guides/artifacts/ (a table is a first-class run output, so per-image results stay inspectable rather than only aggregated).
- **Why it matters for LabelDesk:** our slice feature is unusual at this price and currently ends at a bar chart, so the user still guesses which images to fix; closing the loop is what turns the chart into collected data.
- **LabelDesk code evidence:** `apps/backend/app/services/insights_eval.py:189-229` groups detections into six dimensions and returns `dimension/value/images/instances/AP/AP50` — it builds the `files` list at `:215` and then drops it; the UI picks a dimension and draws bars (`apps/frontend/src/features/insights/EvaluationTab.tsx:139-183`); the cell-gallery pattern to reuse is at `features/evaluation/EvalPanel.tsx:187-230`.
- **Suggested status:** PARTIAL — slicing computes and charts; no drill-down, no saved slice, no action.
- **Suggested priority / size:** Should, M.

### G2.8 The hold-out score is audited for leakage (FiftyOne leaky splits)
- **What the user does:** asks for the test score twice — once on the split as it stands, once with near-duplicates that also appear in train removed — and sees the gap before quoting a number.
- **Who uses it:** anyone whose customer will run their own acceptance test, and us before we publish a model card (G2.6).
- **Flow:** 1. Evaluation header -> *Leak audit* chip reading `clean` or `12 cross-split pairs`. 2. Open it: pairs listed with thumbnails side by side and their hash distance. 3. *Score without leaks* runs the evaluation on the cleaned set and prints both numbers with the difference. 4. *Exclude from test* can write the cleaned split into a new version `[error: too few clean test images -> the audit says the number cannot be trusted rather than printing a flattering one]`.
- **Why it is easy:** we already group images by perceptual hash when building splits, so the same grouping answers the post-hoc question.
- **Products with it:** FiftyOne — https://docs.voxel51.com/brain/index.html (leaky-splits analysis plus a leak-free view of the same test split, so the two scores can be compared).
- **Why it matters for LabelDesk:** a factory dataset shot on one line has hundreds of near-identical frames; our split code keeps them together, but a re-import or a manual split change can reintroduce the leak and nothing tells the user. Publishing an inflated score is the fastest way to lose a reference customer.
- **LabelDesk code evidence:** `apps/backend/app/services/versioning.py:59-92` union-finds images by pHash Hamming distance and the split path uses those groups; nothing measures leakage afterwards and no surface reports a score gap — `none found (searched leak|overlap|contaminat|duplicate split)`.
- **Suggested status:** PARTIAL — prevention at split time exists; detection and reporting do not.
- **Suggested priority / size:** Should, M.

---

## 2.3 Deciding what data to collect

### G2.9 A coverage report for the conditions the model will meet (FiftyOne Brain)
- **What the user does:** reads which visual conditions the dataset covers densely (day, indoor, one camera) and which it barely covers (rain, night, a second site), then picks the images to collect next.
- **Who uses it:** the person planning the next collection trip, and a reviewer judging whether a model is ready for a new site.
- **Flow:** 1. Data health -> *Coverage*. 2. Scatter of the project's images in embedding space, coloured by tag or batch, with cluster labels and per-cluster counts `[loading: first run embeds the project, with a progress count and a stop button]`. 3. *Thin clusters* list: groups below a share threshold with their image count and the tags that describe them. 4. Click a cluster -> its images; *mark for collection* writes a tag the next upload can be checked against. 5. A limitations line states what the data cannot separate, phrased as a limitation rather than a defect.
- **Why it is easy:** the embeddings already exist for the suspect queue, so the report is a colouring and a threshold rather than a new pipeline.
- **Products with it:** FiftyOne — https://docs.voxel51.com/brain/index.html (uniqueness ranks how much a sample adds, representativeness finds typical modes, and the embeddings panel colours points by any field with lasso selection feeding the sample view).
- **Why it matters for LabelDesk:** buyers here collect in bursts from one site and deploy at another; a coverage argument justifies the second collection round instead of letting the model fail in the field.
- **LabelDesk code evidence:** `apps/backend/app/services/insights_embedding.py:276-306` projects features to 2D for the embeddings tab (`features/project/insights/Embeddings.tsx`); no uniqueness, representativeness or cluster-share score anywhere — `none found (searched uniqueness|representative|coverage|thin cluster)`.
- **Suggested status:** PARTIAL — a scatter exists, the coverage judgement does not.
- **Suggested priority / size:** Could, L.

### G2.10 Suspect labels ranked by what the model is confident about (FiftyOne mistakenness)
- **What the user does:** works a queue of human labels the current model disagrees with, strongest disagreement first, and either fixes the label or dismisses the item.
- **Who uses it:** a reviewer cleaning a dataset before a retrain; on outsourced labelling it is the quality gate.
- **Flow:** 1. Data health -> *Suspect labels*. 2. Rows: thumbnail, the label, the model's competing detection with its confidence, and the reason (wrong class / shifted box / extra box). 3. Click -> the editor on that image with both boxes visible. 4. *Fix* or *Dismiss with reason*, and the decision survives a rescan. 5. The header shows queue precision so the reviewer learns whether the ranking can be trusted `[empty: no ready model -> the page says a model is needed and links to Train]`.
- **Why it is easy:** the ranking comes from the inference pass the health scan already runs, and the verdict is one click on a screen the reviewer knows.
- **Products with it:** FiftyOne — https://docs.voxel51.com/brain/index.html (mistakenness ranks labels the model is confident about and disagrees with, for classification and detection, including missed objects and localisation).
- **Why it matters for LabelDesk:** this is one of the few places we are ahead of parity — queue, reason taxonomy and reviewer feedback all exist; the remaining work is presentation and a batch action, not machinery.
- **LabelDesk code evidence:** scoring in `apps/backend/app/services/suspects.py:1-17` (three kinds, IoU bands, a 0..1 ranking hint), cached queue in `services/suspect_queue.py:1-22`, the scan that fills it in `services/health_scan.py:127-175`, routes at `routers/projects.py:433-455`, verdict storage in `models/project.py:145-147`.
- **Suggested status:** HAVE — scan, ranking, feedback and a precision statistic all work end to end.
- **Suggested priority / size:** Could, S (polish only: batch fix/dismiss, and a link from the queue to Train).

---

## 2.4 Compute and operations

### G2.11 Benchmark sheet: latency and throughput per export format and device (Ultralytics benchmark mode)
- **What the user does:** runs one action that exports the model to several formats and measures each on the machine it will run on, so the format decision is answered with numbers.
- **Who uses it:** an engineer deploying to a Jetson, a mini-PC or a cloud CPU, and the sales engineer quoting a frame rate to a factory.
- **Flow:** 1. Model page -> *Benchmark*. 2. Pick formats (PyTorch, ONNX, OpenVINO, TensorRT, TFLite), precision (FP32/FP16/INT8), image size and device; formats the current worker cannot build are disabled with the reason `[empty: no engine build available -> the row explains why]`. 3. Run -> one row per format as it finishes: build time, ms per image, FPS at batch 1, file size, and the metric measured at the same settings `[error: one format fails -> its row keeps the error, the other rows continue]`. 4. Rows sort by FPS and the cheapest row clearing the accuracy floor is marked. 5. *Attach to model* keeps the table on the model page and inside the card from G2.6.
- **Why it is easy:** the export path already exists for TensorRT, so benchmarking is that job with a timer around it, and the accuracy number is the one evaluation already produced.
- **Products with it:** Ultralytics — https://docs.ultralytics.com/modes/benchmark/ (benchmarks every supported export format with `quantize` 16/8 and a `device` of cpu/cuda/xpu/npu, reporting inference time and the task metric per row).
- **Why it matters for LabelDesk:** buyers ask "how many frames per second on our box" before signing, and today the only latency we publish is a desktop number from evaluation; a per-format table is also the honest way to sell edge deployments without owning the hardware.
- **LabelDesk code evidence:** `apps/backend/app/routers/training.py:349-381` builds only `engine` and caches it; the only timing is the mean per-image inference inside evaluation (`services/evaluate.py:98`), reused by the Playground badge (`features/playground/Playground.tsx:91`) and the compare scatter (`features/insights/CompareTab.tsx:97`); `none found (searched benchmark|throughput|per format)`.
- **Suggested status:** MISSING — one format, one device, one latency number.
- **Suggested priority / size:** Should, M.

### G2.12 Queues with priorities, pools and quotas instead of one worker (ClearML agents)
- **What the user does:** puts a training job into a named pool (`gpu-24gb`, `cpu-batch`), sets its priority against the rest of the team, and sees who is ahead and when the run will start.
- **Who uses it:** an admin running several projects on two GPUs, and an engineer whose auto-label job must not wait behind a twelve-hour train.
- **Flow:** 1. Start dialog -> *Pool* picker showing each pool's GPU class, queue depth and estimated wait `[empty: pool with no worker online -> marked offline with its last heartbeat time]`. 2. Priority selector (interactive / normal / overnight) with the rule printed. 3. Queue page: ordered list per pool, running jobs with elapsed time and spend, and a *move to front* limited to admins. 4. A per-workspace cap on concurrent GPU jobs, enforced with a message naming the cap. 5. A preempted job returns to the queue with its checkpoint rather than to the failed list.
- **Why it is easy:** the queue table already exists, so this is a priority column, a pool column and a scheduler loop that respects both.
- **Products with it:** ClearML — https://clear.ml/docs/latest/docs/fundamentals/agents_and_queues (agents service queues, strict-priority or round-robin across several queues, per-agent GPU assignment, a services mode for controllers, with cloud autoscaling and fractional GPUs alongside); Ultralytics live capacity with failover to the nearest GPU and a free upgrade when spare capacity exists — https://docs.ultralytics.com/platform/train/cloud-training/.
- **Why it matters for LabelDesk:** our scheduler is one in-process VRAM ledger for one card — correct for a single-box install, unusable for an agency with three teams; this is the gap that makes us a tool instead of a platform.
- **LabelDesk code evidence:** `Job` carries `kind/status/executor/progress` and a created time with no priority, pool, deadline or cost columns (`apps/backend/app/models/training.py:9-31`); the worker claims up to five queued rows in creation order and runs one at a time (`apps/backend/app/worker.py:132-149`); the GPU is a single-process VRAM ledger with an exclusive training holder (`apps/backend/app/gpu.py:1-6,45-67`); the admin console lists worker hosts (`features/admin/AdminConsole.tsx:198`) but cannot schedule onto them.
- **Suggested status:** PARTIAL — a real queue and a real GPU ledger for one machine; no pools, priorities, quotas or remote scheduling.
- **Suggested priority / size:** Should, L.

### G2.13 Bring your own GPU, and watch it in our dashboard (Ultralytics remote training)
- **What the user does:** trains on hardware they already own — a workstation, a rented box, an on-prem server — from the same project, and gets the same run page, curves and model record.
- **Who uses it:** a customer with a GPU already bought and a residency rule against our cloud, and us when our own worker is busy.
- **Flow:** 1. Train screen -> *Run on my hardware* generates a copyable command carrying the key, the version and the chosen configuration. 2. Paste it on the box; the run appears in the project within a minute with a *remote* badge and a live heartbeat `[error: no heartbeat for four minutes -> marked stale with the last seen time, not failed]`. 3. Curves, console tail and checkpoints arrive the same way as a hosted run. 4. Interrupting and resuming continues the same model record instead of creating a duplicate. 5. Deploy serves the resulting weights exactly as for a hosted run.
- **Why it is easy:** the worker protocol exists, so the new surface is a generated command and a badge; the run page itself does not change.
- **Products with it:** Ultralytics — https://docs.ultralytics.com/platform/train/cloud-training/ (a pre-configured local command with the API key, metrics streamed to the platform model, resume continuing the same model, a run idle for four hours failed).
- **Why it matters for LabelDesk:** factories here already own a GPU box and will not upload imagery to a cloud trainer; today our remote path is undiscoverable and refuses most options, so the customer's own hardware is a dead end.
- **LabelDesk code evidence:** `apps/backend/app/routers/remote.py:195-211` implements claim/heartbeat/complete with a reaper; `topology.remote_training` gates the path and `_REMOTE_UNSUPPORTED` rejects everything but a YOLO26 variant with no cap and no resume (`routers/training.py:67,252-255`); stale detection is a config value (`config.py:135-137`); no UI generates the command — `none found (searched remote|worker|connect your GPU across apps/frontend/src)`.
- **Suggested status:** PARTIAL — protocol and reaper work; no surface, and most options are refused.
- **Suggested priority / size:** Could, M.

### G2.14 A failed run explains itself and retries with the same arguments (Ultralytics Platform)
- **What the user does:** opens the failed run, reads the useful line from the console tail, gets one or two concrete changes, and retries with the previous configuration restored.
- **Who uses it:** anyone whose first run on a new dataset died at epoch 3, which is most people.
- **Flow:** 1. Run page -> error banner with the extracted line (out of memory, bad label file, missing class) rather than a stack trace. 2. *Console* tab with the last 2 000 lines, timestamps toggleable, copy-all. 3. *What to change* names one or two edits with the field pre-set (`batch 16 -> 8`). 4. *Retry* reopens Train with the same version, architecture and arguments, and notes that the previous weights survive if the rerun is worse. 5. A run that stops reporting is failed by the watchdog with the reason stated `[error: failure before compute started -> stated as free]`.
- **Why it is easy:** the handler already catches exceptions, so the work is extracting the one useful line and carrying the form state into the retry.
- **Products with it:** Ultralytics — https://docs.ultralytics.com/platform/train/cloud-training/ (fatal error detected in the console stream, error banner with a full-log action, a diagnose action, retry restoring the run's own arguments, a four-hour stall watchdog).
- **Why it matters for LabelDesk:** a failed run surfaces `safe_error` text with no console and no retry, so every failure becomes a support thread; failure UX is also the cheapest place to look more finished than a competitor.
- **LabelDesk code evidence:** errors funnel through `safe_error` (`apps/backend/app/routers/training.py:16`) and an eval failure is kept as a note on the model (`handlers/training.py:160-173`); the reaper fails stranded remote runs (`services/remote_reaper.py:1-73`); the model page offers stop only (`features/project/Models.tsx:206-244`) — no console, no diagnosis, no retry-with-previous.
- **Suggested status:** PARTIAL — states and the watchdog exist; the diagnosis surface does not.
- **Suggested priority / size:** Should, M.

### G2.15 Per-run host telemetry, not just loss curves (Ultralytics System tab, ClearML)
- **What the user does:** sees during a run whether the GPU is saturated, whether VRAM is the limit, and whether the dataloader is starving the model — without opening a shell on the box.
- **Who uses it:** whoever decides between buying a bigger card and fixing the data pipeline.
- **Flow:** 1. Run detail -> *System* tab beside the metric charts. 2. Cards for host, GPU model, VRAM total, CPU and RAM. 3. Per-epoch lines for GPU utilisation, VRAM used, temperature, CPU/RAM, disk and network I/O. 4. A hint when utilisation stays under 60% for the whole run: the dataloader, not the GPU, is the constraint `[empty: a remote run reporting no metrics -> the tab names the agent version needed]`.
- **Why it is easy:** the GPU ledger already samples used VRAM and the holder, so the run page only has to keep those samples under the run id.
- **Products with it:** Ultralytics — https://docs.ultralytics.com/platform/train/cloud-training/ (a System tab with host totals plus per-epoch CPU, RAM, GPU utilisation and memory, temperature, network and disk); ClearML — https://clear.ml/docs/latest/docs/fundamentals/agents_and_queues (agents report system metrics continuously and the orchestration page shows each machine's status).
- **Why it matters for LabelDesk:** we tell customers their GPU is the bottleneck without showing it, so "the run was slow" is unanswerable, and it makes our self-hosted story credible beside a managed trainer.
- **LabelDesk code evidence:** `apps/backend/app/gpu.py:45-67` keeps a lock-free snapshot of `used_mb`, `budget_mb`, `holder` and leases, exposed at `GET /api/gpu` (`routers/registry.py:18-23`) and typed in `lib/types.ts:635`; it is a live badge, not a per-run series — `none found (searched utilization|temperature|per-run telemetry)`.
- **Suggested status:** PARTIAL — live VRAM state exists; nothing is recorded per run.
- **Suggested priority / size:** Could, S.

---

## 2.5 Sharing the result

### G2.16 A published run report a non-engineer can read (W&B Reports)
- **What the user does:** assembles charts, a slice table and a written conclusion into one page, shares a read-only link, and exports a PDF for the customer's file.
- **Who uses it:** a project lead closing a delivery, and an agency sending a monthly model update.
- **Flow:** 1. Insights -> *Report* -> *New*. 2. Add blocks: chosen curves, the run table, a slice chart, confusion matrix, a text block, an image from the dataset. 3. Drag to reorder; each block freezes the data it was built from and prints the timestamp, so a later retrain does not rewrite history `[loading: blocks render from cached data]`. 4. *Publish* gives a link that needs no login, plus a PDF. 5. A report can be attached to a model and referenced from its card (G2.6).
- **Why it is easy:** the dashboards feature already renders widgets to PNG, so a report is a document object over the same specs plus prose.
- **Products with it:** W&B — https://docs.wandb.ai/guides/reports/ (pick runs, charts and panels into one page, add commentary, share, export to PDF or a LaTeX zip).
- **Why it matters for LabelDesk:** our insights are strong and trapped in the app; a customer-facing PDF is what an SI needs to invoice a model delivery, and it costs us a document table plus a print stylesheet.
- **LabelDesk code evidence:** `apps/frontend/src/features/dashboards/dashboardExport.ts:41-42,88-101` composes widgets into one PNG download; there is no text block, section ordering, share link or PDF — `none found (searched report pdf|share link|publish report)`.
- **Suggested status:** PARTIAL — a PNG of a dashboard exists; no narrative, no permalink, no PDF.
- **Suggested priority / size:** Should, M.

### G2.17 An extension point for our own and the customer's analysis (FiftyOne plugins)
- **What the user does:** installs a small module that adds a button or a panel — a custom metric, a compliance check, a proprietary pre-processing step — and it appears in the product beside ours.
- **Who uses it:** a customer's ML engineer who needs one house rule enforced, and us shipping niche analysis without bloating the core UI.
- **Flow:** 1. Settings -> *Extensions*: a list with version, author and permissions requested. 2. *Add* takes a package name or an uploaded archive; install lists the capabilities it asks for and refuses anything reaching outside its scope `[error: incompatible API version -> the reason names the supported range]`. 3. Installed extensions add entries to a toolbar or a panel slot; one that throws is disabled with its error and the rest of the page keeps working. 4. Every extension action is written to the audit log with its name.
- **Why it is easy:** if the API is a narrow, versioned function set over an image and its labels, the first three extensions can be ours and the surface stays small.
- **Products with it:** FiftyOne — https://docs.voxel51.com/brain/index.html (Brain methods are exposed through an installable plugin, so the App gains analysis panels without a core release).
- **Why it matters for LabelDesk:** we are small; an extension point lets one customer's domain rule ship in days without us maintaining it, and it is the difference between a tool they use and a platform they build on.
- **LabelDesk code evidence:** `none found (searched plugin|extension point|operator|third-party module across apps/backend/app and apps/frontend/src)`; the nearest thing is the adapter registry (`adapters/catalog.py`), which is server-side and not customer-extensible.
- **Suggested status:** MISSING — no extension mechanism.
- **Suggested priority / size:** Could, L.

---

**Group 2 count:** 1 HAVE · 12 PARTIAL · 4 MISSING (17 features). By priority: 12 Should · 5 Could · 0 Must. By size: 3 S · 10 M · 4 L.

Nothing in this group blocks a trial; the trial blockers live in Area 3 and Area 5 of parity. This is second-meeting material — the questions a technical buyer asks once the demo works: "can I compare runs", "why is my test score high", "what ships with the weights", "how fast on our box", "who approved this".

Order I would build in, if the lead wants four slices out of this file: G2.2 then G2.3 (a run you can reproduce and compare, both small and both visible in a demo), then G2.7 (a chart that opens into work), then G2.9 or G2.11 depending on whether the next customer is a factory floor or an SI. G2.6 is the one to schedule before the first enterprise handover, not before the demo; G2.1 and G2.12 are the two that need a decision about how much of our own GPU fleet we intend to run.

---

## Already covered by PARITY.md

Dropped after grepping the 334 rows, with the row that owns them:

- Hyperparameter **editing** (presets, epochs/size/batch fields) — 5-F5.9. G2.1 and G2.2 add a search space and a durable configuration record, not more fields.
- Time and cost estimate, credit cap, long-run confirmation — 5-F5.10, 5-F5.11, 7-F7.18. G2.12 adds queue position and pool choice, which those rows do not describe.
- Continue from a checkpoint, stop early vs cancel, licence per model, model identity — 5-F5.15–18, 5-F5.33, 5-F5.38. G2.4 is about the approval decision, not the alias.
- Automatic evaluation, threshold explorer, per-class counts, confusion drill-down, recommendations, similarity clusters, accuracy-vs-latency compare, application-level evals — 5-F5.20–28, 5-F5.30. G2.7 is the slice-to-images hop, which 5-F5.23's cell gallery does not cover.
- Custom weight upload and evaluation of uploaded weights — 5-F5.29, 5-F5.31.
- Near-duplicate discovery, pHash-guarded splits — 2-F2.36, 4-F4.12. G2.8 is the post-hoc score audit.
- Annotation heat map, class balance, dimension insights, report caching — 4-F4.39–44. 4-F4.42 stays MISSING; the Ultralytics overview confirms location heatmaps and box-dimension analysis exist elsewhere, which supports that row rather than adding a new one.
- Active learning sampling, production verdicts feeding training, drift and monitoring — 6-F6.14–19. G2.9 asks which conditions are absent from the data, not which images are uncertain.
- Self-hosted inference and edge fleet management — 6-F6.5, 6-F6.46. G2.11 benchmarks formats; it does not manage devices.
- AutoTrain's one-click fine-tune has no card: it is discontinued (https://huggingface.co/docs/autotrain/index), and "click train" is 5-F5.12.

## Title-only / unverified

- **LandingLens explainability heatmaps, defect-mode workflow, camera deployment, no-code retrain loop.** The platform page confirms a label book, automatic mislabel detection, consensus labelling, cloud and edge deployment including a Windows app, and a continuous-learning loop that pulls deployment data back into retraining — but every deeper page now redirects to Agentic Document Extraction (https://docs.landing.ai/ covers ADE only; https://landing.ai/deployment renders the document product). No heatmap or defect-mode claim is confirmed, so none is written as a feature; a "justify this call" card would rest on the marketing page alone.
- **W&B Tables as a per-image results surface** is named on the artifacts page as an evaluation output but the Tables page was not opened, so G2.7 cites artifacts, not tables, for that.
- **W&B Weave / LLM evals** — outside this group's vision scope, not fetched.
- **ClearML dataset versioning, HPO details, cloud autoscaler and fractional GPUs** appear as nav entries under the infrastructure grouping (https://clear.ml/docs/latest/docs/fundamentals/agents_and_queues) but only the overview and the workers-and-queues page were read; no autoscaler cost model is quoted here.
- **Ultralytics advanced-YAML validation** is documented for the form; whether a pasted value is validated server-side rather than clamped in the browser is not stated, so G2.2 asks for clamping on paste and claims no server validator.
- **Hugging Face AutoTrain pricing and GPU choice** unread; the project is discontinued, so no card.
- **Ultralytics label-distribution and box-dimension charts** appear on the platform overview but were not opened; not used as evidence for any card here.
- Not documented anywhere fetched: GPU class choice on a shared queue, the per-run cost of a remote run, and whether any of these products keeps a signed approval record (W&B Registry has permissions and lineage; an approver field was not seen).
