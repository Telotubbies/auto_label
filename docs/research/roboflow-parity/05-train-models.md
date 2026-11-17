# Area 5 - Train & Models

Method: 24 fetches, 2026-11-17 - docs index, then `models/train/{train-a-model, cancel-a-training-job, neural-architecture-search, roboflow-instant, train-from-google-cloud, pro-third-party-training-integrations}`, `models/evaluate/{view-trained-models, training-results, evaluate-trained-models, compare-trained-models, training-resolutions-by-model-type}`, `models/{readme, model-ids, model-licenses, versions-trainings-and-models}`, `models/model-weights/upload-custom-weights`, `models/supported-models/sam3`, `models/supported-tasks/anomaly-detection`, `roboflow.com/{pricing,credits}`, two blog posts (regression testing, anomaly detection), blog index. Not opened: weight-download page, Universe checkpoint page, Rapid pages, per-family model pages (only SAM3), forum threads.

Repo notes read for leads: `research_notes/ฟีเจอร์ SaaS ด้าน Computer Vision/training_evaluation.md`, `research_notes/ฟีเจอร์ที่ยังขาดเทียบคู่แข่ง/roboflow_features.md` sections 3-4.
`[inferred]` = not stated on any page I fetched; `(RF: X)` marks a source label only, never copy.

Metric vocabulary (definitions, then what the UI defaults to): **mAP@50:95** = mean AP over ten IoU cut-offs 0.50 to 0.95 step 0.05; **mAP@50 / @75** = one cut-off, 75 rewards tight geometry; **AP S/M/L** = same AP by object area (<32^2, 32^2-96^2, >96^2 px); **AR@1/10/100** = recall with that many detections per image; **P/R/F1 at a cut-off** = after dropping low-confidence detections; **mIoU / mBIoU** for semantic segmentation (plus pixel-level P/R/F1); **mBAP** = boundary AP for instance segmentation; **OKS mAP** for keypoints; **median latency (Cloud API)** = median server time per request incl. pre/post-processing, network excluded. Defaults: detection, instance-seg and keypoint tables headline mAP@50:95; classification comparison headlines F1 (its training page shows accuracy); semantic segmentation headlines mIoU.

---

## 5.1 Model registry

### F5.1 Project model table (RF: Models page)
- **What the user does:** browses every model of one project in a single table.
- **Flow:** 1. Project sidebar -> *Models*. 2. Tab **Fine-tuned** lists Instant + fine-tuned runs. 3. Row shows name, model ID, last-updated, training metrics, architecture, licence, dataset version; the version cell links through; row click -> detail. 4. Filtering and sorting are not documented `[inferred: filter by task/version, sort by date or metric]`. `[empty: no model -> first-run prompt to train]` `[loading: row skeletons, inferred]`
- **Why it is easy:** licence and dataset version sit beside the metric, so "may I ship this?" and "which data is this?" are answered without opening the model.
- **Gates:** viewing is plan-free.
- **Sources:** https://docs.roboflow.com/models/evaluate/view-trained-models.md , https://docs.roboflow.com/models/model-ids.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`, `apps/backend/app/routers/training.py`

### F5.2 Many models per version (RF: multiple trainings on a version)
- **What the user does:** keeps several models on one frozen snapshot and switches between them.
- **Flow:** 1. Version card lists each training with its own graphs and metrics. 2. Training again from the same version appends a row instead of replacing. 3. Select a training on the card to view it.
- **Why it is easy:** the comparison unit is the data, so trying three architectures costs no version churn.
- **Gates:** subject to the one-concurrent-job default (F5.49).
- **Sources:** https://docs.roboflow.com/models/versions-trainings-and-models.md , https://docs.roboflow.com/models/train/train-a-model.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py` (`/{project}/models`)

### F5.3 Workspace registry with a starred-models tab (RF: workspace Models page)
- **What the user does:** sees models across projects; public models they starred live in a separate **Universe** tab and open on their public page.
- **Flow:** 1. Workspace sidebar -> *Models*. 2. Project models tab + starred tab. 3. Public rows leave the app when clicked.
- **Why it is easy:** one org-wide inventory, while public checkpoints stay out of project lists.
- **Gates:** none stated.
- **Sources:** https://docs.roboflow.com/models/evaluate/view-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/workspace/WorkspacePages.tsx`

### F5.4 Row quick actions (RF: Deploy Model, Copy Model ID, View Full Model Evaluation, Delete)
- **What the user does:** acts on a model from the list.
- **Flow:** 1. Row action. 2. *Deploy Model* -> Workflow template chooser wired to this model (or build your own). 3. *Copy Model ID*. 4. *View Full Model Evaluation*. 5. Download weights exists on every plan through the Inference package or MCP; in-app download is Enterprise-only. `[error: deploy fails -> toast, inferred]`
- **Why it is easy:** the four post-training actions are one click from the row.
- **Gates:** in-app weight download and commercial self-host licence = Enterprise add-on.
- **Sources:** https://docs.roboflow.com/models/train/roboflow-instant.md , https://docs.roboflow.com/models/model-ids.md , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`, `apps/backend/app/routers/training.py`

---

## 5.2 Training start, screen by screen

Entry: project nav -> *Train* -> "Custom Training". One long form, six blocks, no wizard.

### F5.5 Engine choice: single architecture or architecture search (RF: training engine / NAS)
- **What the user does:** picks a plain fine-tune or a search that trains dozens of candidates.
- **Flow:** 1. Engine selector at the top of *Train*. 2. Search adds a backbone step and two credit caps and changes the charts later. 3. Only detection, instance seg and semantic seg offer it.
- **Why it is easy:** the alternative engine is a label in the same slot as the architecture picker, not a separate product area.
- **Gates:** search on Core incl. Free Tier, billed at the standard training rate.
- **Sources:** https://docs.roboflow.com/models/train/neural-architecture-search.md , https://docs.roboflow.com/models/train/train-a-model.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx`

### F5.6 Data step: live dataset or frozen version (RF: Current Dataset / saved version)
- **What the user does:** trains on the moving head of the dataset or on a pinned snapshot.
- **Flow:** 1. Data block. 2. *Current Dataset* uses the newest images and annotations and creates the version implicitly at start, named from the card with its splits. 3. A saved version freezes data; its preprocessing and augmentation rows become read-only with a stated reason. 4. "Reuse Preprocessing and Augmentations" copies a version's preprocessing, augmentations, class remap and tag filters into Current Dataset as editable values. `[empty: no version -> Current Dataset keeps the first run unblocked]` `[empty: zero annotations -> start disabled with hint, inferred]`
- **Why it is easy:** no version knowledge needed for a first run, and reproducibility is one click.
- **Gates:** none stated.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx`

### F5.7 Architecture and size picker, pre-filtered by task (RF: architecture list, sizes)
- **What the user does:** picks family then size; only valid families appear.
- **Flow:** 1. Architecture grid. 2. Size axis (RF-DETR Nano to 2XL; keypoint offers a two-stage card with a size per stage). 3. Each size implies a default training resolution - RF-DETR N 384^2, S 512^2, M 576^2, L 704^2, XL 700^2, 2XL 880^2; RF-DETR Seg 312^2 to 768^2; YOLO families 640^2; YOLO26-SEM 1024^2; classification 224^2; SAM3 and Instant 1008^2. 4. Overriding resolution happens in the version's resize step, not here. 5. Access-gated families show a request-access button instead of a start path. `[loading: catalogue -> skeleton cards]` `[error: disabled family prints its reason]`
- **Why it is easy:** an invalid task+architecture pair cannot be selected, so the failure mode is removed rather than handled.
- **Gates:** SAM3 fine-tune = paid plan with usage-based billing + access request; YOLO badges show AGPL (F5.38).
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://docs.roboflow.com/models/evaluate/training-resolutions-by-model-type.md , https://docs.roboflow.com/models/supported-models/sam3.md , https://docs.roboflow.com/models/supported-tasks/anomaly-detection.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx`, `apps/backend/app/routers/training.py` (`/{project}/train/options`)

### F5.8 Starting weights: previous, public, public-dataset, random, ImageNet (RF: Checkpoints)
- **What the user does:** decides what the run starts from.
- **Flow:** 1. Recipe -> *Checkpoint*. 2. Four options: previous checkpoint (faster, only if that model already performed well), public COCO checkpoint (default), public-dataset checkpoint (detection only, source must be starred first), random init (advanced, usually worse). 3. Classification and semantic segmentation offer one ImageNet checkpoint instead. 4. The choice is re-readable on the model's Training Recipe card.
- **Why it is easy:** the default needs no decision and the risky option is labelled risky.
- **Gates:** public-dataset checkpoint requires starring the source model.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (`resume_from` today)

### F5.9 Preset plus recipe editor (RF: speed preset, Customize Training Recipe)
- **What the user does:** flips a fast/accurate preset, or opens the recipe and edits training preprocessing, online augmentations, checkpoint, hyperparameters and (search only) latency band.
- **Flow:** 1. Recipe accordion. 2. Preset `fast` is the default and `accurate` is a paid capability per the SDK parameter table; `[inferred]` that the web form shows the same toggle. 3. On a saved version the preprocessing and augmentation rows stay visible but locked with the reason (baked at generation); on Current Dataset they apply to this run only. 4. Epochs default depends on model type.
- **Why it is easy:** one control moves the cost/quality trade instead of three coupled numbers, and greyed rows explain themselves.
- **Gates:** `accurate` = paid.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (fast/advanced preset)

### F5.10 Credit cap with a printed minimum (RF: Credit Cap, Search Credit Cap)
- **What the user does:** caps one run's spend; blank means uncapped.
- **Flow:** 1. Cap field under the estimate; the model's minimum cap is printed beneath it. 2. A cap below the estimate is allowed (run will likely stop early); below the minimum is rejected on submit. 3. While running, the run shows capped credits consumed. 4. Search runs carry two caps; setting one leaves the other uncapped. 5. A cap stop keeps weights, and the remainder can fund a continuation if it still covers the minimum. `[error: field-level message naming the minimum]`
- **Why it is easy:** the floor ("smallest run that can still produce a model") is printed, so nobody guesses it.
- **Gates:** caps need usage-based billing.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://docs.roboflow.com/models/train/neural-architecture-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (`max_minutes`)

### F5.11 Cost and duration estimate, long-run confirmation (RF: training summary)
- **What the user does:** reads expected time and credits before committing.
- **Flow:** 1. Summary block under the form, recomputed on every change. 2. Above one day of training, a confirmation step is inserted before start. 3. Assistant-started runs show a typical and a full-run figure and re-ask if the full figure moves. 4. Action recognition estimates come from video count, length and sampling settings; V-JEPA runs show none. `[loading: shimmer while recomputing]` `[empty: "no estimate for this setup", inferred]`
- **Why it is easy:** money and time in one block, and the expensive case becomes a dialog.
- **Gates:** 1 credit = 30 min GPU training; Free Tier = 10 credits/month.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://roboflow.com/credits , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (`estMinutes`)

### F5.12 Submit and queued acknowledgement (RF: Start Training)
- **What the user does:** starts the run and is told where to watch it.
- **Flow:** 1. *Start Training*. 2. Button enters a busy state; the view returns to the version card, which first says a training machine is starting, then shows live graphs. 3. Email on completion, usually under 24 h. 4. The API returns `204` with no training id, so callers poll or list. `[error: 400 carrying a machine-readable "remedy" field when the version is not trainable]` `[error: plan/credit refusal -> inferred modal pointing at billing]`
- **Why it is easy:** the run appears where its results will live, so the form never dead-ends.
- **Gates:** one concurrent job by default.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://docs.roboflow.com/models/evaluate/training-results.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py` (`POST /{project}/train`)

### F5.13 Instant few-shot model (RF: Instant)
- **What the user does:** gets a usable model minutes after a first annotation batch, free.
- **Flow:** 1. Auto: first approved batch on a project with under 1000 images and no Instant model trains one. 2. Manual: *Models* -> "Train Model" -> Instant -> confirm -> "Create New Instant Model". 3. Ready in minutes. 4. No preprocessing or augmentation allowed. `[empty: over 1000 images -> manual only]`
- **Why it is easy:** removes "I need a model to know if the idea works" without spending credits.
- **Gates:** object detection only; free; confidence usually needs 0.85-0.99.
- **Sources:** https://docs.roboflow.com/models/train/roboflow-instant.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx`

### F5.14 Search backbone step (RF: Fast / Standard / Plus)
- **What the user does:** narrows the search to a latency band by naming a deployment target.
- **Flow:** 1. Backbone cards: Fast = lowest-latency candidates (CPU/edge), Standard = wide range, Plus = most accurate (cloud GPU). 2. Semantic segmentation offers Standard/Plus; instance segmentation skips the step. 3. Next -> caps and estimate. `[error: under 15 validation images -> server rejects; surface it before submit, inferred]`
- **Why it is easy:** the choice is expressed as where it will run, which is what the user knows.
- **Gates:** at least 15 validation images.
- **Sources:** https://docs.roboflow.com/models/train/neural-architecture-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx`

---

## 5.3 Training run detail

### F5.15 Status lifecycle (RF: training states)
- **What the user does:** watches a run move from queued to a terminal state.
- **Flow:** 1. Version card: "training machine starting". 2. Live graphs join it. 3. API terminal states are `finished`, `failed`, `cancelled`, `stopped`; the UI distinguishes stopped-early from failed and marks the row with a tick when the artifact is ready. `[loading: "preparing weights", may take minutes]`
- **Why it is easy:** "stopped early with weights kept" is visually distinct from "failed", which is the difference that decides the user's next action.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/models/evaluate/training-results.md , https://docs.roboflow.com/models/train/cancel-a-training-job.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx` (`STAGES`)

### F5.16 Live graphs and search-specific charts (RF: Training Graphs, Progress Band, Epoch Snapshot)
- **What the user does:** reads curves during and after the run.
- **Flow:** 1. Open the training from the version card or *Models*. 2. Scroll to Training Graphs; the metric set follows project type (detection P/R/mAP, classification accuracy, segmentation and keypoint mAP, multimodal perplexity). 3. Search runs instead show a gradient band of best/worst candidate per epoch with hover values and a pulsing current-front marker, plus a per-epoch latency-vs-accuracy scatter (lighter = faster); the fast variant falls back to the ordinary line. 4. Graphs persist after the run ends. `[empty: nothing until the first epoch, inferred]`
- **Why it is easy:** the monitor and the post-mortem are the same page, and search uncertainty is drawn as a band rather than a single noisy line.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/models/evaluate/training-results.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F5.17 Stop early vs cancel, consequences stated (RF: Stop Training Early / Cancel Training)
- **What the user does:** ends a run and chooses whether weights survive.
- **Flow:** 1. Open the running training. 2. *Stop Training Early* -> weights saved, credits used are billed, exits at end of current epoch. 3. *Cancel Training* -> weights discarded, refund only if cancelled early. 4. Either way the version can train again. `[error: a job ignoring the stop is killed after about 8 h, shown as failed, credits refunded]`
- **Why it is easy:** the destructive action is separated from the useful one by name and by a consequences table, not a checkbox.
- **Gates:** API cancel of a run older than 30 min needs a second call confirming no refund.
- **Sources:** https://docs.roboflow.com/models/train/cancel-a-training-job.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F5.18 Continue from last checkpoint (RF: Continue Training)
- **What the user does:** adds epochs to a stopped run instead of restarting.
- **Flow:** 1. Open a stopped training -> *Continue Training*. 2. Tooltip states the date the checkpoint expires; after that the button disables and the copy names the fallback. 3. RF-DETR and YOLO families only. `[empty: cancelled run has no checkpoint -> action absent, inferred]`
- **Why it is easy:** the deadline is in the tooltip, so the user learns it before it costs a rerun.
- **Gates:** checkpoint held a few days after the run ends.
- **Sources:** https://docs.roboflow.com/models/train/cancel-a-training-job.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (`resume_from`)

### F5.19 Spend and logs during a run (RF: capped usage; logs not documented)
- **What the user does:** checks credits consumed against the cap.
- **Flow:** 1. Running view shows credits used of the capped total. 2. On stop, used credits are billed. 3. `[inferred]` a log pane and a GPU/host panel exist; no fetched page documents either, and no page documents GPU selection for hosted training.
- **Why it is easy:** cost and progress are read on one screen instead of a billing page.
- **Gates:** 30 min = 1 credit.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://roboflow.com/credits
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

---

## 5.4 Evaluation

### F5.20 Automatic evaluation behind a compile gate (RF: Model Evaluation auto-run)
- **What the user does:** gets an evaluation without asking.
- **Flow:** 1. Training ends -> model is compiled into the served package; the model shows "Optimizing for inference". 2. Evaluation waits for that, then runs on test **and** validation splits. 3. Hundreds of images = minutes; thousands = hours. 4. Compile failure or over 24 h -> evaluation starts anyway. 5. Manual re-run from the app. `[error: failed evaluation -> retry entry in the compare panel]`
- **Why it is easy:** it measures the artifact that actually serves requests, so the number matches production rather than a local checkpoint.
- **Gates:** automatic only on paid plans, for trained **and** uploaded models; needs Model Evaluation access; multimodal excluded.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md , https://docs.roboflow.com/models/evaluate/compare-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.21 Threshold explorer driving the deployed default (RF: production metrics explorer)
- **What the user does:** slides confidence and reads precision, recall and F1 until the trade-off fits.
- **Flow:** 1. Model -> *View Full Model Evaluation*. 2. Panel computes P/R/F1 at every threshold and marks the best trade-off. 3. That becomes the model's default inference confidence; per-class values apply where present with the global value as fallback; a request can override with a `confidence` parameter. 4. Dragging updates the class and confusion panels. `[loading: sweep computing -> skeleton]`
- **Why it is easy:** tuning happens once at the model and propagates to every caller, so callers never rediscover their threshold.
- **Gates:** evaluation access.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.22 Per-class performance with counts (RF: Performance by class)
- **What the user does:** sees correct, misclassified, missed and false-positive counts per class.
- **Flow:** 1. *Performance by class* panel. 2. Stacked bars per class; the "All Classes" dropdown filters to one. 3. The threshold slider applies; the table reports each class's P/R/F1 at its own best threshold. `[empty: class with no ground truth -> "not evaluated" row, inferred]`
- **Why it is easy:** counts sit next to ratios, so "4 misses" is not mistaken for "1 miss out of 2".
- **Gates:** evaluation access.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.23 Confusion matrix with drill-down and GT/prediction flip (RF: confusion matrix, Ground Truth toggle)
- **What the user does:** finds confused class pairs, then judges each error against the label.
- **Flow:** 1. Matrix opens at the optimal threshold. 2. Rows = ground truth, columns = prediction, plus false-positive and false-negative columns. 3. Click a cell -> thumbnails of those images. 4. Click an image -> viewer with a *Ground Truth* / *Model Predictions* toggle. 5. Keypoints draw predictions only. 6. The slider changes the matrix. `[empty: cell has no images -> empty drawer naming the threshold]`
- **Why it is easy:** every wrong number is two clicks from the picture that caused it, on one canvas with one set of class colours.
- **Gates:** evaluation access.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.24 Recommendations and assistant handoff (RF: model improvement recommendations, Improve My Model)
- **What the user does:** reads concrete fixes, then hands the worst images to a helper.
- **Flow:** 1. Recommendations list: too many false negatives, too many false positives, often confused classes, classes needing more data, splits too small. 2. *Improve My Model* opens a chat scoped to this evaluation: failing images beside their labels, suggested data/training changes, likely label errors batched into one review job. 3. It asks before moving images out of someone else's job. `[empty: not generated -> API returns "generated: false"; placeholder copy, inferred]`
- **Why it is easy:** the diagnosis is written as actions ("add images of class X") rather than as advice to read a matrix.
- **Gates:** evaluation access; assistant usage consumes credits.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.25 Visual-similarity failure clusters (RF: Vector Analysis)
- **What the user does:** finds groups of look-alike images where the model is weak.
- **Flow:** 1. *Vector Analysis* panel. 2. Scatter of test images by visual similarity, coloured by F1. 3. Click a point, a lassoed area or a named cluster -> those images, worst first. `[empty: too few images -> panel hidden, inferred]`
- **Why it is easy:** turns "accuracy 0.82" into "night shots of the loading bay are 0.4", which is a collectable dataset task.
- **Gates:** evaluation access.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.26 Median latency as a first-class number (RF: Latency (Cloud API))
- **What the user does:** compares speed beside accuracy on the same rows.
- **Flow:** 1. Evaluation shows median server round time over the test images. 2. The same value appears on model list and card. 3. If test images carry at least twice the model input pixels, a capture-resolution recommendation is added.
- **Why it is easy:** one agreed latency figure in every surface, with its definition stated, so comparisons are not apples-to-oranges.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.27 Side-by-side comparison on one version (RF: Compare)
- **What the user does:** plots accuracy against latency for every model on a dataset version.
- **Flow:** 1. *Models* -> *Compare*. 2. Pick a version. 3. Chart holds models that have latency plus the selected metric; clicking a point opens its card. 4. Metric selector: detection offers mAP@50, mAP@50:95, mAP@75, precision, recall, F1; instance seg adds mBAP@50/50:95/75; semseg adds mBIoU. 5. Default frontier metric: mAP@50:95, or mIoU, or F1 by task. 6. "Some models need evaluation updates" panel with *Run* / *Update* / *Retry Evaluation* and *Update All* (queued and running models excluded). 7. Before any result, the tab shows the next step ("Train a Model", "View Training", "Run Evaluations", "Update Evaluations"). `[error: no evaluation access -> upgrade prompt replaces the tab]`
- **Why it is easy:** the frontier makes "the cheaper model is nearly as good" visible, which is the decision most teams face.
- **Gates:** same-version only; latest completed evaluation only, no fallback.
- **Sources:** https://docs.roboflow.com/models/evaluate/compare-trained-models.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py` (`/{project}/leaderboard`)

### F5.28 Metrics that follow the task (RF: OKS / mIoU / boundary metrics)
- **What the user does:** gets metrics that fit the project type instead of a forced mAP.
- **Flow:** 1. Keypoint -> OKS-matched mAP. 2. Semantic segmentation -> mIoU headline, pixel-level P/R/F1, per-class IoU and optimal threshold, confusion matrix in pixel counts, mBIoU plus a Boundary IoU column. 3. Instance segmentation -> boundary AP under *Show Detailed Metrics*. 4. Classification -> accuracy/F1. `[empty: older evaluations lack boundary metrics -> the selector asks for an update]`
- **Why it is easy:** units are named on screen, which is what prevents "object counts or pixels?".
- **Gates:** evaluation access.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md , https://docs.roboflow.com/models/evaluate/compare-trained-models.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.29 Evaluation for uploaded weights (RF: uploaded models are evaluated too)
- **What the user does:** brings external weights in and still gets the full evaluation page.
- **Flow:** 1. Upload weights onto a version (F5.31). 2. A paid workspace auto-runs the evaluation, same panels. 3. Model joins the version's compare chart.
- **Why it is easy:** external models land on the same yardstick instead of a separate backwater.
- **Gates:** paid plan for automatic evaluation.
- **Sources:** https://docs.roboflow.com/models/evaluate/evaluate-trained-models.md , https://docs.roboflow.com/models/model-weights/upload-custom-weights.md
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

### F5.30 Application-level regression evals (adjacent, RF: Workflow Evals)
- **What the user does:** pins test images with known answers and re-runs a whole pipeline after any change, comparing against a baseline.
- **Flow:** 1. Evals -> Create Eval (five steps: workflow, ground-truth images or a dataset test split, outputs to check, checks, review plus credit estimate). 2. Run baseline. 3. Swap a model block and run again -> checks-passed vs latency overview, per-image heatmap, per-check metrics, vector analysis coloured by pass/fail. 4. Optional deploy gate blocks publishing below a minimum pass rate. `[empty: all checks pass -> every dot one colour]`
- **Why it is easy:** test set and rules are data, so "did the update break counting?" is one button, and the gate makes it enforceable.
- **Gates:** about 1/10,000 credit per execution plus inference.
- **Sources:** https://blog.roboflow.com/computer-vision-regression-testing/
- **LabelDesk hook points:** `apps/frontend/src/features/evaluation/EvalPanel.tsx`

---

## 5.5 Custom weights and bring-your-own training

### F5.31 Weight upload, versioned or workspace-wide (RF: Upload / deploy custom weights)
- **What the user does:** imports externally trained weights for hosting and evaluation.
- **Flow:** 1. Required metadata: family (`model_type`), directory holding the file (default `weights/best.pt`), and - workspace-wide mode only - a model name (at least one letter, letters/numbers/dashes). 2. Versioned mode attaches to a dataset version (several allowed; useful for model evolution, label assist, or as a later checkpoint). 3. Workspace mode deploys into several projects at once. 4. Appears under *Models*. `[error: unsupported family rejected; YOLOv5/v7/v9/v10 uploads no longer accepted, existing ones keep serving]` `[error: framework-version mismatch - YOLOv8 needs ultralytics 8.0.196, YOLO11 8.3.40 or lower, YOLOv12 the sunsmarterjie fork]`
- **Why it is easy:** two named modes with the reason to pick each, and only the metadata needed to serve the file.
- **Gates:** accepted families RF-DETR (`rfdetr-nano` to `2xlarge`, `-seg-*`, `-keypoint-preview`), YOLO26 (`-seg`/`-pose`/`-sem`), YOLOv12, YOLO11, YOLOv8, YOLO-NAS, PaliGemma 2 (incl. `-peft`), Florence 2; upload included on all plans.
- **Sources:** https://docs.roboflow.com/models/model-weights/upload-custom-weights.md , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/backend/app/routers/training.py`, `apps/frontend/src/features/project/Models.tsx`

### F5.32 Train elsewhere, import back (RF: Azure / Google Cloud integrations)
- **What the user does:** exports a version in a provider's format, trains there, imports the weights.
- **Flow:** 1. Version -> export as provider format. 2. Provider UI opens with the dataset (Azure needs a stored training key and endpoint; over 1000 images needs the S0 tier). 3. Train there. 4. Import via F5.31. `[error: provider not connected -> the export step explains what to paste where]`
- **Why it is easy:** the export is one named choice, so nobody hand-builds a manifest.
- **Gates:** Enterprise plans only.
- **Sources:** https://docs.roboflow.com/models/train/train-from-google-cloud.md , https://docs.roboflow.com/models/train/pro-third-party-training-integrations.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py` (`/{project}/models/{mid}/export`)

---

## 5.6 Model lifecycle

### F5.33 Model identity and copyable ID (RF: Model IDs)
- **What the user does:** references one specific model in code, workflows and tickets.
- **Flow:** 1. ID is `{workspace}/{project}-{version}-{architecture}-t{n}`. 2. Assigned when the run starts, so it is known while training. 3. Counters are never reused - failed and cancelled runs burn theirs. 4. Search candidates append `--{6-char hash}`. 5. *Copy Model ID* on list, detail and version table.
- **Why it is easy:** an ID that is stable, parseable and available before the model exists removes "which run do you mean?" from every conversation.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/models/model-ids.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F5.34 Legacy alias with stated exceptions (RF: legacy `{project}/{version}` IDs)
- **What the user does:** keeps old snippets working while adopting per-model IDs.
- **Flow:** 1. The first successful training on a version aliases the old-style ID to that model permanently. 2. If the first run fails or is cancelled, no alias is created, ever. 3. One model and no alias still resolves; several models and no alias -> ambiguous request fails and the caller must use the model ID.
- **Why it is easy:** compatibility comes with rules, so old code fails loudly instead of silently hitting a different model.
- **Gates:** applies to trainings started after 2026-06-30.
- **Sources:** https://docs.roboflow.com/models/model-ids.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py`

### F5.35 No explicit "production" state - the gap (RF: none)
- **What the user does:** `[inferred]` would mark one model per project as the deploy target.
- **Flow:** no fetched page documents a promote, mark-production or deprecate action. Serving follows the oldest training on a version until it is deleted (F5.37); search candidates reach the model picker only by being starred (F5.36); deployments bind a model ID explicitly.
- **Why it matters:** lifecycle is expressed by ID wiring and deletion order, so "which model is live for this project?" is not answerable from one field. This is a place to do better than parity.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/models/versions-trainings-and-models.md , https://docs.roboflow.com/models/train/neural-architecture-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F5.36 Starring search candidates (RF: star models)
- **What the user does:** shortlists candidates from a search run.
- **Flow:** 1. Results page -> star any dot. 2. Starred models appear in the workflow model picker; unstarred stay on the results page. 3. Starring a finished model also triggers its evaluation if it has none. 4. Free and reversible.
- **Why it is easy:** an explicit shortlist contains the blast radius of a 40-model search, and starring does the useful follow-up automatically.
- **Gates:** evaluation only in workspaces with Model Evaluation.
- **Sources:** https://docs.roboflow.com/models/train/neural-architecture-search.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F5.37 Delete a training, serving consequence stated (RF: Delete / Move to Trash)
- **What the user does:** removes a run and is told what happens to live traffic.
- **Flow:** 1. Version card -> *Delete*. 2. Type the model name to confirm. 3. *Move to Trash*, 30-day restore window. 4. Running trainings cannot be deleted. 5. The dialog names the consequence: the oldest training owned the legacy ID, so serving moves to the next oldest or stops until a new run finishes.
- **Why it is easy:** name-typing plus a named side effect on serving are the two things that prevent accidental outages.
- **Gates:** `version:update` scope for the API variant.
- **Sources:** https://docs.roboflow.com/models/versions-trainings-and-models.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py` (`DELETE /{project}/models/{mid}`)

### F5.38 Licence shown per model and per deploy target (RF: model license column)
- **What the user does:** sees the licence on the row and learns what it permits where.
- **Flow:** 1. Licence column on every row. 2. Deploying on the host cloud includes a commercial licence for AGPL and platform-licence models on every plan. 3. Commercial self-hosting needs the Enterprise add-on or AGPL-3.0 open-sourcing. `[error: restricted self-host without the add-on -> inferred upsell]`
- **Why it is easy:** licence risk appears at the moment of choosing a model, not in a legal page.
- **Gates:** Apache-2.0 covers RF-DETR N to L detection and all Seg sizes; the platform licence covers XL/2XL detection, RF-DETR semantic segmentation, the two-stage keypoint head and search results; YOLO families are AGPL-3.0.
- **Sources:** https://docs.roboflow.com/models/model-licenses.md , https://docs.roboflow.com/models/train/train-a-model.md , https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Train.tsx` (licence badge)

### F5.39 Permissions split train from read (RF: Train Model / List Versions, scoped keys)
- **What the user does:** grants training and evaluation reading separately.
- **Flow:** 1. Starting a run, or asking the assistant to, needs Train Model and List Versions. 2. API scopes: `training-job:create`, `model-eval:read`, `version:update`. 3. Custom roles, folder permissions and scoped keys are Enterprise; Core has admin seats only. `[error: missing scope -> 403, inferred copy]`
- **Why it is easy:** train and read are separate capabilities, which matches how teams split work.
- **Gates:** RBAC and scoped keys = Enterprise.
- **Sources:** https://docs.roboflow.com/models/train/train-a-model.md , https://roboflow.com/pricing , https://docs.roboflow.com/models/evaluate/compare-trained-models.md
- **LabelDesk hook points:** `apps/backend/app/routers/training.py`, `apps/frontend/src/features/project/Models.tsx` (`useProjectPermissions`)

---

## 5.7 Failure and edge cases

| ID | Case | What happens / what the user is told | Source |
|---|---|---|---|
| F5.40 | Too few images | No documented minimum for a normal fine-tune; the few-shot path exists for small sets (under 1000 images). Search refuses fewer than 15 validation images. | train-a-model, NAS, instant |
| F5.41 | Class imbalance | Not a blocking validation. Appears after training as a recommendation ("classes that need more data"). | evaluate-trained-models |
| F5.42 | Small validation or test split | Recommendation text only; never blocks. | evaluate-trained-models |
| F5.43 | Version not ready / invalid | 400 with a machine-readable `remedy`; locked rows on saved versions explain why editing is impossible. | train-a-model |
| F5.44 | Unsupported task plus architecture | Impossible by construction - the catalogue is filtered, disabled families print a reason, gated families show request-access. | train-a-model, sam3 |
| F5.45 | Licence restriction | Licence column plus deploy matrix; fine-tuned SAM3 cannot run on the serverless API at all (dedicated or self-host). | model-licenses, sam3 |
| F5.46 | Credit cap reached | Run stops itself, weights kept, cap consumption shown live; a partial cap funds a continuation only if the remainder covers the minimum. | train-a-model |
| F5.47 | Workspace out of credits | Job is stopped; if it never answers the stop it is killed after about 8 h, reported failed, no weights, credits refunded. | cancel-a-training-job |
| F5.48 | Out of memory / GPU fault | Undocumented. Only the generic `failed` state and the 8-hour watchdog are documented. | training-results |
| F5.49 | Concurrent runs | "By default, users can train one model at a time." No plan-based concurrency table published. | roboflow.com/pricing |
| F5.50 | Ambiguous training reference | Version endpoints return 409 when a version has several trainings; caller must pass `trainingId`. | cancel-a-training-job, model-ids |
| F5.51 | Long or expensive run | Estimate in the summary; over one day adds a confirmation; assistant-started runs re-confirm if the full-run figure changes. | train-a-model, NAS |
| F5.52 | Anomaly-project data rules | Trains on normal images only; anomalies in the train split are skipped and used for thresholding; preprocessing limited to auto-orient plus stretch, no augmentation; without anomalous validation images the threshold flags about 1% of normals. | anomaly-detection, blog |
| F5.53 | Evaluation unavailable | No access -> upgrade prompt instead of the Compare tab; multimodal has no Test page; semseg and keypoint substitute their own metrics rather than failing. | compare-trained-models, training-results |
| F5.54 | Evaluation stalled | Compile failure or over 24 h -> evaluation proceeds anyway instead of blocking the model. | evaluate-trained-models |

---

## Title-only / unverified

- Weight download page - mechanics unread; only the plan rule is confirmed (in-app = Enterprise, otherwise Inference package or MCP).
- Universe checkpoint picker inside the train form - only the "star it first" gate is confirmed.
- Rapid / video-to-model path - outside this area, unread beyond index titles.
- Per-family model pages (RF-DETR, YOLO26, YOLO11, YOLOv8, PatchCore, FoundAD) - only SAM3 opened; per-family size tables and warnings unverified.
- Failure copy - no page quotes the message a user sees on a failed run, so F5.48 is unverified and any LabelDesk wording must be ours.
- Not documented anywhere I fetched: GPU class choice, live log streaming, per-run loss export, early-stopping patience for hosted training, webhooks on training state change.
- Per-image evaluation records exist as an API shape (`image-predictions`, `includeGeometry`) but no page documents the screen; screen behaviour inferred.
- Filtering the model list and table sorting are absent from docs (F5.1).

## Coverage gaps and what to check next

1. **Failure UX is the biggest unknown.** Someone with app access should capture one failed and one cancelled run: message text, retry affordance, whether partial artifacts survive.
2. **Registry filtering and sorting** (F5.1) is the weakest evidenced registry part; note the actual chips and row menu if parity matters.
3. **Test vs validation separation** - evaluation mixes both splits; confirm whether the UI can show them apart, since test-only reporting is a cheap improvement for us.
4. **Evaluation re-runs** - comparison uses "latest completed evaluation" only; how a re-run supersedes an old evaluation on the evaluation page itself is untested.
5. **Lifecycle** - confirm whether any undocumented production/archive badge exists before we treat F5.35 as a Roboflow gap rather than a documentation gap.
6. **Search economics** - one documented planning range (about 2,500 images = 18 h = 36 credits; instance seg 1.5-2x) plus the repo's forum anecdote (3,000 images, over 10.5 h, over 20 credits, stuck at epoch 12); no independent confirmation of the typical case.
