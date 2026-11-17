# Area 6 — Deployment, inference surface, production evaluation, Workflows and edge

Method: fetched 30 pages on 2026-11-17 — the docs index (`llms.txt`), deployment overview/chooser/production
checklist, Serverless Cloud API + its pricing table, Dedicated Deployments, Batch Processing, Cloud Streaming
(overview, sources, workflow lifecycle, manage/monitor), Model Monitoring, Vision Events, Operator Feedback,
Active Learning, Workflows (build, test, blocks catalogue, version + workflow management, deploy, hello-world),
Inference Python package, Inference CLI, Inference Server, Deployment Manager, and `roboflow.com/pricing`.
Not opened: individual block reference pages (catalogue only), Cloud Streaming `pricing-and-limits`,
`consume-results`, `install-a-connector`, `install/minimum-requirements`, `offline-mode`, `license-server`,
`secure-gateway`, Workflow Evals, the Model Monitoring alerting page, `roboflow.com/credits` (rates quoted only
where another fetched page states them), any blog post, and the logged-in app UI.

Feature count: **46** (F6.1–F6.46). Inferred states are marked `[inferred]`.

---

## 6.1 Choosing and paying for a deployment

### F6.1 One chooser that separates real-time from bulk by workload shape (RF: *Choosing a Deployment Option*)
- **What the user does:** lands on a comparison page before touching any endpoint; picks from six runtimes by answering four questions instead of reading six product pages.
- **Flow:** 1. Read a 2-row table split "Roboflow Cloud" / "Self-Hosted" (Deploy chooser page). 2. Read a comparison grid: where it runs (host name), GPU (yes / CPU-or-GPU / device-dependent), latency profile, pricing unit, region, plan availability, "best for". 3. Read a separate billing table that states the per-image vs per-hour split. 4. Walk a 4-step decision flow: real-time or bulk → sync or async → cloud or on-prem → managed or self-managed. 5. Land on the chosen product page with a "production readiness" link.
- **Why it is easy:** the only decision criterion that changes the answer is named up front (a 30 FPS camera is ~108,000 images/hour, so continuous video bills per hour, not per frame); every other dimension follows from it.
- **Gates:** option availability differs by plan — Serverless = "contact sales", Dedicated = Core/Enterprise, Batch = credit workspaces or Enterprise, self-hosted = all plans, edge fleet = Enterprise.
- **Sources:** https://docs.roboflow.com/deployment/choosing-a-deployment.md, https://docs.roboflow.com/deployment/readme.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`, `apps/backend/app/routers/deployments.py`

### F6.2 Per-request endpoint that hides its own cold start (RF: *Serverless Cloud API*)
- **What the user does:** sends one image or one Workflow request and gets predictions back synchronously; no capacity decision.
- **Flow:** 1. Pick the hosted runtime in the editor or the project deploy surface. 2. Send request → `[loading: first call to an idle model pays a multi-second warmup]` → response. 3. Inspect `x-model-cold-start` and `x-processing-time` response headers to see whether this call paid the load cost. 4. If latency matters, send one warmup request before real traffic.
- **Why it is easy:** the cold-start cost is exposed as a header and a documented ~10-minute idle unload, so a developer can prime and monitor it without guessing; uploads over 20 MB are rejected outright rather than half-processed.
- **Gates:** per-image credits by model; images downsized server-side to the model's input size, so oversized uploads are pointless; rate limit answers `429` with no published number.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/serverless-api.md, https://docs.roboflow.com/deployment/production-checklist.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

### F6.3 Private cloud box with explicit dev/prod types and a pause switch (RF: *Dedicated Deployments*)
- **What the user does:** provisions an isolated server on a named subdomain for heavy models, then pauses it to stop the meter.
- **Flow:** 1. Deployments page → create, choose `dev-cpu` / `dev-gpu` / `prod-cpu` / `prod-gpu`, set lifetime and optional startup script. 2. `[loading: status = pending; poll every 30 s until ready]` → `ready` with a `domain`. 3. Point the SDK at `https://<domain>` — only `api_url` changes. 4. Pause / resume / delete (also by sending a request, which auto-resumes). 5. Read logs and per-deployment + workspace usage.
- **Why it is easy:** "dev" and "prod" are a type choice with stated consequences (dev = deleted after 3 h, auto-pause fixed at 1 h, may be evicted; prod = persistent, guaranteed capacity), so nobody accidentally ships on a self-deleting box.
- **Gates:** Core/Enterprise; billed per minute of existence; US data centres only; rolling the backing workspace key migrates the deployment and falls back to the old key if the move fails.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/dedicated-deployments.md
- **LabelDesk hook points:** `apps/backend/app/routers/deployments.py`

### F6.4 Batch job over stored images or video, with no-code and CLI paths (RF: *Batch Processing*)
- **What the user does:** runs one Workflow across thousands of stored files and collects a result set.
- **Flow:** 1. Deployments → Batch tab → "New Batch Job". 2. Pick Workflow → upload files → pick CPU/GPU → create. 3. `[loading: machines provision "typically after a few minutes", no guaranteed start]`. 4. Job row shows live progress; click for stages/tasks. 5. Export result batch to a target directory. Alternative entries: Asset Library multi-select → run Workflow; a Datasource "on sync" trigger; CLI `inference rf-cloud …`.
- **Why it is easy:** the same four fields cover the whole job, and both the ingest and the job-completion webhooks remove polling (`job_state: success | fail`).
- **Gates:** workspaces on the credit system or Enterprise; per machine-hour; 20 MB per image; images chunk into 20,000-file groups, videos "work best under 1,000"; presigned URLs expire in 24 h; signed-URL-file ingestion is Enterprise-only.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/batch-processing.md, https://docs.roboflow.com/workflows/deploy/deploy-a-workflow.md
- **LabelDesk hook points:** `apps/backend/app/routers/streams.py`, `apps/frontend/src/features/project/Workflows.tsx`

### F6.5 Self-hosting that costs no credits and needs no seat licence (RF: *Self-Hosted Inference*)
- **What the user does:** runs the same server on their own machine or cloud and pays only for hardware.
- **Flow:** 1. Install (`pip install inference-cli && inference server start`, or a per-OS Docker guide). 2. Server binds `127.0.0.1:9001` by default. 3. Same SDK, `api_url` swapped. 4. Optional `--dev` for a landing page and a preloaded JupyterLab.
- **Why it is easy:** one interface across hosted, dedicated and self-hosted means the integration code does not change when the runtime does; self-hosted images and video consume zero credits on every plan.
- **Gates:** some model weights need an Enterprise commercial licence to self-host (e.g. 2XL-class RF-DETR, Ultralytics weights); TensorRT packages for private models need Enterprise; `--dev` must not be exposed to untrusted networks.
- **Sources:** https://docs.roboflow.com/deployment/self-hosted/inference-server.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/backend/app/routers/deployments.py`

### F6.6 Cost model printed next to the choice, not behind a quote (RF: *model pricing*)
- **What the user does:** sees the credit rate for each model architecture and size before committing, plus a worked graduated-volume example.
- **Flow:** 1. Pricing page: per-model credits per 1,000 images, sorted by accuracy-per-credit for detection; expandable size rows. 2. Volume bands (first 250K, 250–500K, … over 5M) show the discounted rate per band. 3. Worked example: 600,000 RF-DETR Small images = 91.41 credits. 4. Execution-time section: 1 credit = 500 s for VLMs and custom Python. 5. Plan table: 10 credits free, Core $39/mo with packs from $3.90 down to $2.86/credit, prepaid from $4, on-demand $6.
- **Why it is easy:** billing is a function of (model, size, monthly volume) and nothing else — image size and inference duration do not change a per-image price, which removes the usual estimator argument.
- **Gates:** included credits do not roll over; prepaid expires in a year; `402/408/409/423/429/5xx` do not bill, `401/403/404` do.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/serverless-api/model-pricing.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

### F6.7 Go-live checklist that names what to retry (RF: *Production Readiness Checklist*)
- **What the user does:** runs a hardening pass before switching traffic on.
- **Flow:** 1. Table of status codes with retry / do-not-retry. 2. Backoff pattern with jitter for `429` and `5xx` only. 3. Timeout guidance keyed to cold starts. 4. Upload size cap. 5. `min_replicas`/`max_replicas` sizing guidance plus the auto-pause interaction. 6. "Before you go live" bullet list.
- **Why it is easy:** it answers the two things that actually break integrations — retrying a `400` forever, and a client timeout shorter than a cold start — in one screen.
- **Gates:** none stated; Enterprise support for higher limits.
- **Sources:** https://docs.roboflow.com/deployment/production-checklist.md
- **LabelDesk hook points:** `apps/backend/app/routers/deployments.py`

---

## 6.2 The deploy screen

### F6.8 Runtime picker that rewrites the snippets (RF: *editor runtime selector*)
- **What the user does:** switches where the code will run and copies code that already matches.
- **Flow:** 1. Editor top-left "Running on" selector (cloud / `localhost:9001` / Dedicated). 2. Open Deploy → snippet tabs. 3. `api_url` in every snippet follows the selected runtime; the matching tab is marked recommended; an example image from the last saved preview is filled in. 4. Copy.
- **Why it is easy:** the snippet cannot drift from the runtime because both read the same selector — the commonest "works in the browser, 404s in my app" bug is removed at the source.
- **Gates:** snippets are pre-filled with the workspace key, so copying one into a public repo leaks a key `[inferred risk]`.
- **Sources:** https://docs.roboflow.com/workflows/deploy/deploy-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

### F6.9 Confidence slider on the deploy surface with a live preview (RF: *deploy sidebar threshold*)
- **What the user does:** tunes the threshold that the copied code will use, and sees the effect before copying.
- **Flow:** 1. Deploy sidebar shows a threshold slider only when the underlying Workflow exposes a confidence input. 2. Drag → preview image and predictions re-render. 3. Copy snippet.
- **Why it is easy:** the value in the snippet is the value the user just looked at; no second round-trip to discover the model is too noisy.
- **Gates:** none stated.
- **Sources:** https://docs.roboflow.com/models/rapid/rapid/deploy-a-rapid-model.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx` (already: model select, 0–100 confidence, cURL/Python/JS/URL tabs)

### F6.10 Request shape follows the Workflow, not a fixed schema (RF: *workflow inputs*)
- **What the user does:** reads the input contract off the workflow and sends only those keys.
- **Flow:** 1. Each declared input appears as a key: a `WorkflowImage` takes `{type: "url" | "base64", value}`; plain parameters take scalars. 2. POST to `/infer/workflows/<workspace>/<workflow-id>` with `Authorization: Bearer` and JSON `inputs`. 3. Response returns the declared output fields (JSON plus optional rendered image).
- **Why it is easy:** one endpoint serves every model and every Workflow; the payload shape is discoverable from the workflow definition instead of an API reference per task type.
- **Gates:** workflow runtime capped at 20 s and response payload at 6 MB on the serverless path, so many visualization blocks can fail a request that works in the preview.
- **Sources:** https://docs.roboflow.com/workflows/deploy/deploy-a-workflow.md, https://docs.roboflow.com/deployment/roboflow-cloud/serverless-api.md
- **LabelDesk hook points:** `apps/backend/app/routers/workflows.py`, `apps/frontend/src/features/project/workflowChain.ts`

### F6.11 Model identity is immutable; there is no staging→production pointer (RF: *Model IDs*)
- **What the user does:** copies a model ID of the form `{workspace}/{project}-{version}-{architecture}-t{n}` from the Models page ("Copy Model ID").
- **Flow:** 1. Models page → row shows `ID:`. 2. Copy. 3. Paste into a Workflow model block or an SDK call. 4. Legacy `{project}/{version}` IDs keep working through an alias created by the *first* successful training on that version; a multi-model version with no alias returns an ambiguity error.
- **Why it is easy:** every training is addressable, including several on one version, so "which weights am I calling" has one answer.
- **Gates:** no user-defined alias (`production`, `staging`) and no traffic split are documented; moving production means editing the ID in the client. The legacy alias is frozen to the first training and cannot be re-pointed.
- **Sources:** https://docs.roboflow.com/models/model-ids.md
- **LabelDesk hook points:** `apps/backend/app/routers/deployments.py` (already models aliases + a move-alias endpoint)

### F6.12 Error codes and credit rules written for the caller (RF: *Errors and status codes*)
- **What the user does:** looks up what a failure means and whether it cost money.
- **Flow:** single page covering REST status codes, SDK exceptions and CLI exit codes; the pricing page repeats which codes are free. CLI exit codes: 0 success, 1 error, 2 auth, 3 not found.
- **Why it is easy:** "did this failure bill me" is answered in the same table as the error, and CLI codes are stable enough to branch on in scripts.
- **Gates:** `402/423` mean plan/quota/paused billing and must not be retried.
- **Sources:** https://docs.roboflow.com/deployment/production-checklist.md, https://docs.roboflow.com/workflows/manage/manage-workflows.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

### F6.13 Keys scoped and rotated per workspace, with a publishable key type (RF: *Advanced API Keys*)
- **What the user does:** creates a key per integration, narrows it to scopes (e.g. `vision-events:read`, `device:update`, `video-inference-job:create`), rolls it when leaked.
- **Flow:** 1. Settings → API keys table (badges, warnings, creation date). 2. Create / rename / disable / roll / protect / revoke. 3. "Roll" issues a new value and migrates backing services (a Dedicated Deployment moves to the new key, or stays on the old one if the move fails). 4. Rotation reminders.
- **Why it is easy:** rolling a key is a supported operation with a defined blast radius, so teams rotate instead of avoiding rotation; a key without an explicit scope list is implicitly full-access, which keeps old code working.
- **Gates:** scopes, folder keys and metadata need the Advanced API Keys feature (403 otherwise); publishable keys are rejected by management endpoints.
- **Sources:** https://roboflow.com/pricing, https://docs.roboflow.com/deployment/roboflow-cloud/dedicated-deployments.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx` (shows a key field; no scoping visible)

---

## 6.3 Evaluating models in production

### F6.14 Monitoring dashboard that is honest about being replaced (RF: *Model Monitoring*)
- **What the user does:** reads request volume, average confidence and average inference time across models, then drills into single requests.
- **Flow:** 1. Workspace → Model Monitoring. 2. Totals with % change vs the previous equal period; default range = last week. 3. Models table → per-model stats + detections per class. 4. Inferences table → one row per request, custom metadata visible. 5. Click a row → request detail; the image appears only if it was saved. `[empty: a model with no traffic is absent from the table]`.
- **Why it is easy:** inference images are *not* stored by default, and the page says so plus names the two ways to start storing them — the privacy default and the opt-in are on the same screen.
- **Gates:** banner states it will be deprecated in favour of Vision Events; the stats API is Enterprise, 50 req/min per key.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/model-monitoring.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Models.tsx`

### F6.15 Typed production event store with per-purpose groupings (RF: *Vision Events / Use Cases*)
- **What the user does:** records what production actually saw as queryable events instead of rows of logs.
- **Flow:** 1. Create a Use Case (defines the metadata vocabulary, e.g. `line_id`, `shift`). 2. Deployed code sends an event: `eventType` ∈ `quality_check | inventory_count | safety_alert | custom | operator_feedback`, plus images, up to 4 clips, predictions, source metadata, custom metadata. 3. Query in the dashboard, in natural language via the assistant, or over the API with pagination. 4. `[empty: a use case with no events shows an empty list plus the send instructions]`.
- **Why it is easy:** five fixed event types cover QA, counting and safety without designing a schema, and `lookbackDays` is returned in every query response so a reporting job knows how far back its data can go.
- **Gates:** retention default 14 days (configurable), 14 days on Core, custom on Enterprise; export to a warehouse is Enterprise; event images count against image quotas.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/vision-events.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/backend/app/routers/streams.py` (StreamEvent), `apps/frontend/src/features/streams/StreamDetail.tsx`

### F6.16 Human verdicts on production predictions, visible in the list (RF: *Operator Feedback*)
- **What the user does:** opens an event, writes an optional comment, and marks the result correct / incorrect / inconclusive.
- **Flow:** 1. Click an event → detail sidebar → feedback section. 2. Click a verdict; it saves immediately, attributed to the user. 3. List rows gain a green thumbs-up, red thumbs-down or yellow marker. 4. Activity stream lists every reviewer, verdict, comment and timestamp; delete an entry (Manage permission) to clear that reviewer's verdict and re-enable the form. 5. Filter the list by feedback status.
- **Why it is easy:** one click is the whole taxonomy, and multiple reviewers are allowed so the record is a discussion rather than a single overwritable field.
- **Gates:** API-submitted feedback has no verified reviewer and shows as "Unknown"; deleting feedback is audited.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/vision-events/operator-feedback.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/QA.tsx`

### F6.17 Review session that turns bad events into training rows (RF: *Operator Feedback Review*)
- **What the user does:** walks images from reviewed events one at a time and routes each to dataset, annotation queue, reject, or snooze.
- **Flow:** 1. Use case → "Operator Feedback Review" tab → choose the model to improve → "Start Review Session". 2. For each image: add to dataset / send to annotation queue / reject / snooze. 3. "Save & Exit". 4. `[blocked: another reviewer holds the session; the tab shows who and when, plus "Check Again"]`.
- **Why it is easy:** the single-reviewer lock prevents two people double-labelling the same queue, and the session auto-releases after 10 minutes of no decision.
- **Gates:** on by default for Enterprise and the earlier Growth plan.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/vision-events/operator-feedback.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Suspects.tsx`

### F6.18 Watchdog and digest alerts that do not need a dashboard visit (RF: *No-Events Alerts / Automations / Summary Reports*)
- **What the user does:** gets mail when a camera stops producing events, when a matching event should be filed automatically, or on a schedule.
- **Flow:** 1. No-events alert: pick camera/stream/workflow, get one email when it goes quiet. 2. Automations: rule on event fields → send image into a project, or email an alert. 3. Summary reports: recurring email with headline numbers and a link to the full report.
- **Why it is easy:** silence is treated as a signal, which is the failure mode a threshold-based alert never catches.
- **Gates:** recipients must be workspace members; report/automation availability by plan `[inferred for summary reports]`.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/vision-events.md, https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/manage-and-monitor.md
- **LabelDesk hook points:** `apps/backend/app/routers/alerts.py`

### F6.19 Active learning as a rules form, not a training loop (RF: *Active Learning*)
- **What the user does:** says which production images are worth keeping and how many, then reviews them in batches.
- **Flow:** 1. Project sidebar → Active Learning → toggle on (requires a trained model + an active cloud deployment). 2. "Edit" Collection Limits: sampling rate (e.g. 0.5%), per-minute/hourly/daily caps, compression and max dimensions, batch recreation cadence (daily/weekly/monthly/never), persist predictions yes/no. 3. "Edit" Conditions: confidence threshold, classes of interest, detection-count requirements. 4. Images page shows counts ready vs in review → "Review Images" → batches by status (Not Started / In Progress), sorted by date, size or progress. 5. Assign reviewers: pick members, images per person, instructions, optional shuffle. 6. Reviewers are notified; reassignment allowed.
- **Why it is easy:** the collection policy is four plain numbers plus two filters, so a team can start collecting in one screen instead of writing a sampling job.
- **Gates:** needs a cloud deployment and the Annotation Review feature; collected images count as uploads for credits/quotas; each config change saves and deploys a new base-Workflow version.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/active-learning.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Suspects.tsx`, `apps/backend/app/routers/insights.py`

### F6.20 Retention stated per surface and per plan (RF: *lookback / trash windows*)
- **What the user does:** checks how long data survives before relying on it.
- **Flow:** events → `lookbackDays` (default 14, 14 on Core, custom on Enterprise); deleted projects/versions/workflows → Trash for 30 days; workflow versions → everyone sees the 3 most recent.
- **Why it is easy:** the retention number travels in the API response, not only in a pricing table.
- **Gates:** as stated; Vision Events data export is Enterprise.
- **Sources:** https://docs.roboflow.com/deployment/monitoring-and-analytics/vision-events.md, https://roboflow.com/pricing, https://docs.roboflow.com/workflows/manage/manage-workflow-versions.md
- **LabelDesk hook points:** `apps/backend/app/routers/audit.py`

---

## 6.4 Workflows — builder UX

### F6.21 Canvas builder with assisted wiring and three help levels (RF: *Builder Assist / auto layout*)
- **What the user does:** assembles a pipeline by adding blocks and connecting them, choosing how much the editor does for them.
- **Flow:** 1. Open a Workflow → editor canvas with a left/right block palette and an Outputs node. 2. Add a block: "Add a Block" opens the block sidebar; or press "+" on the underside of an existing block to insert after it. 3. Connect by wiring a compatible output port to an input port; the builder positions a block beside its input. 4. Top-right toggle: Auto (default — wires compatible fields on connect/insert and repairs downstream references when a block is removed) / Quick (suggests, applies only on accept) / Manual. Mode persists locally. 5. Toolbar sitemap button = arrange once; chevron → "Arrange now" or "Arrange automatically" (re-lays out on every add/connect; dragging pauses it). Saved per workflow, locally.
- **Why it is easy:** on a graph editor the expensive step is not dragging, it is remembering which port feeds which — Auto mode removes that, and Manual mode exists for people who want determinism.
- **Gates:** none stated for wiring; block availability can be restricted workspace-wide by block governance.
- **Sources:** https://docs.roboflow.com/workflows/build/build-a-workflow.md, https://docs.roboflow.com/workflows/blocks/blocks.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`, `workflowChain.ts` (12-block linear chain today)

### F6.22 Block config panel where optional params are the defaults nobody changes (RF: *block properties*)
- **What the user does:** selects a block and edits only the required ports plus the few knobs that matter.
- **Flow:** 1. Select a block → side panel lists required inputs (e.g. image) and optional ones. 2. Model block shows class filter, confidence, IoU, max detections, class-agnostic NMS. 3. Reference values by picker or by `$steps.<name>.<output>` / `$inputs.<name>` expression. 4. Validation errors surface inline on the offending field/canvas node `[inferred: the fetched pages describe errors indirectly via "repairs downstream references" and deploy gates]`.
- **Why it is easy:** required ports are separated from the eight optional ones, so a first pipeline needs one field.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/workflows/build/build-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/WorkflowBlocks.tsx`

### F6.23 Run panel: image, video file with a time window, or live camera (RF: *Test a Workflow*)
- **What the user does:** tests a draft against representative input before deploying.
- **Flow:** 1. "Run" / "Test Workflow" opens the run panel. 2. Media tab: File (JPG/PNG/WEBP) → Run; or upload a video → Run, with a gear for "Start (ms)" / "End (ms)". 3. Live: pick a stream → cloud preview starts; `[loading: "Starting" while models load]`; `[error: needs an image output for annotated video — JSON-only workflows run but return no video]`. 4. Outputs render as JSON and/or an image thumbnail; click the thumbnail for the full frame. 5. Multi-video: one video per image input, up to four; all read the same frame number and stop at the shortest, so equal frame rates are required.
- **Why it is easy:** the same panel tests a still, a clip and a camera, and the camera option needs no extra infrastructure — which is where most "it worked on my image" failures get caught.
- **Gates:** previews and stream tests consume credits; block cache off for multi-video runs.
- **Sources:** https://docs.roboflow.com/workflows/build/test-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`

### F6.24 Per-block caching with an explicit uncache (RF: *block cache*)
- **What the user does:** stops re-paying for the expensive upstream model while iterating on a downstream viz block.
- **Flow:** 1. Gear in the test pane → "Use Block Cache". 2. Each block shows "Cached" or "Not Cached". 3. Select a block → "Uncache" to force one fresh run. 4. Caching applies only to browser test runs — never to deployed workflows, batch jobs or API calls; sinks, notifications, secrets and custom Python blocks always run; disabled blocks always run.
- **Why it is easy:** the honest "Cached" badge means the developer can trust that a change really re-ran, instead of guessing why the output looks identical.
- **Gates:** setting stored per workflow in the browser; caching has no effect in production.
- **Sources:** https://docs.roboflow.com/workflows/build/test-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`

### F6.25 Sinks switch that protects test runs from side effects (RF: *Sinks toggle*)
- **What the user does:** tests a workflow that writes to a dataset or webhook without writing.
- **Flow:** 1. "Sinks" switch above Run — on by default, one switch for File, Webcam and Stream. 2. Off for the next run only. 3. Does not change the saved Workflow, batch jobs or API calls. 4. Assistant camera previews default to off unless explicitly enabled.
- **Why it is easy:** the risky half of a pipeline is muted by one control, and the safe default is chosen for the agent path rather than the human path.
- **Gates:** none.
- **Sources:** https://docs.roboflow.com/workflows/build/test-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`

### F6.26 Outputs node that is editable and reorderable (RF: *Outputs block*)
- **What the user does:** decides what the endpoint returns and in what order.
- **Flow:** 1. Run once with only a model block → output is the model JSON. 2. Add a visualization block via "+" → it appears as a candidate output. 3. Select Outputs → "Move Up" to put the image above the JSON. 4. Toggle Visual to see the larger render.
- **Why it is easy:** the response contract is a draggable list on the canvas, so "what will my client receive" is visible rather than inferred from the definition JSON.
- **Gates:** payload cap 6 MB on serverless, so many image outputs can fail a request.
- **Sources:** https://docs.roboflow.com/workflows/tutorials/hello-world.md, https://docs.roboflow.com/workflows/deploy/deploy-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`

### F6.27 Save is manual, publish is gated, and the two are visibly separate (RF: *save / publish / deploy gates*)
- **What the user does:** saves a draft freely, then publishes only what passed checks.
- **Flow:** 1. Edit → "Save" writes a draft (no autosave). 2. Publish runs required gates: an Eval gate (may consume inference credits) and/or manual approval by an eligible person. 3. Poll gate status; publish only when `publishable` is true. 4. Auto-Publish mode: the latest saved draft publishes once every gate passes. 5. Publishing can stage a pin on production devices as a `configProposal` awaiting approval — the docs insist you check each device before claiming it runs the new version.
- **Why it is easy:** draft and live are different objects with a named gate between them, so "someone saved a half-finished pipeline" cannot reach an endpoint.
- **Gates:** deploy gates are workspace-configured; a direct `updateWorkflow` API call is rejected on a gated workflow; API cannot grant manual approval.
- **Sources:** https://docs.roboflow.com/workflows/manage/manage-workflows.md, https://docs.roboflow.com/workflows/build/build-a-workflow.md
- **LabelDesk hook points:** `apps/backend/app/routers/workflows.py`

### F6.28 Version history with a "Live" marker, naming and restore (RF: *Workflow Version History*)
- **What the user does:** looks back at what ran, labels a good version, and restores an old one.
- **Flow:** 1. Clock icon in the right sidebar → version list. 2. The published version is marked Live; a newer saved draft can sit unpublishable while waiting for gates. 3. Three-dot menu → Rename. 4. Three-dot → Restore: the definition loads into the editor, unsaved; Save creates a *new* version containing the restored definition. 5. Publishing then follows F6.27.
- **Why it is easy:** restore is non-destructive and reversible — you cannot lose the version you were on — and the Live badge answers "what is production running" without opening the API.
- **Gates:** everyone sees their 3 most recent versions; full history, naming and restore need the Teams add-on or Enterprise (Core lists "Workflow Versions: not included").
- **Sources:** https://docs.roboflow.com/workflows/manage/manage-workflow-versions.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/WorkflowVersions.tsx`, `apps/backend/app/routers/workflows.py` (list versions + restore)

### F6.29 Disable a node instead of deleting it (RF: *disable individual nodes*)
- **What the user does:** mutes one block to isolate a failure, keeping its config.
- **Flow:** toggle on the node; disabled blocks always execute as no-ops in tests (cache never skips them). `[inferred: the canvas shows a dimmed node and downstream validation flags consumers of its outputs]`
- **Why it is easy:** bisecting a broken pipeline becomes a click per node rather than a delete-and-rebuild.
- **Gates:** none stated.
- **Sources:** https://docs.roboflow.com/workflows/build/test-a-workflow.md (disabled blocks always run; changelog title "Disable individual nodes in Workflows" from `llms.txt`)
- **LabelDesk hook points:** `apps/frontend/src/features/project/workflowChain.ts`

### F6.30 Nesting a workflow inside a workflow (RF: *Inner Workflow*)
- **What the user does:** reuses a pipeline as a component with mapped parameters.
- **Flow:** add the Inner Workflow block → point at another workflow → map parent ports to the child's inputs; the compiler inlines it, so the child's steps appear in the parent's execution graph.
- **Why it is easy:** the same block type serves team templates (e.g. "our crop→classify sub-pipeline") without copy-paste drift.
- **Gates:** none stated; block governance can hide block types workspace-wide.
- **Sources:** https://docs.roboflow.com/workflows/blocks/blocks.md (Inner Workflow block listing), https://docs.roboflow.com/workflows/developer-guide/developer-guide/inner-workflows.md (title only, from `llms.txt`)
- **LabelDesk hook points:** `apps/backend/app/routers/workflows.py`

### F6.31 Sharing, forking and folder permissions (RF: *share a workflow / fork*)
- **What the user does:** sends a link that others can view, run or copy, and controls whether their runs use their key or yours.
- **Flow:** 1. Share link → recipient can view, run and fork. 2. Run access is tied to a key choice. 3. Fork copies the definition into the recipient's workspace. 4. Folders: create with the folder-plus button; three-dot → "Move Workflow"; per-folder "Set Permissions" for read/edit.
- **Why it is easy:** a pasteable JSON definition means a shared workflow is a template, not a live dependency — the fork diverges safely.
- **Gates:** folder permissions need a role that can manage them; folder-scoped API keys place created workflows by the same rules.
- **Sources:** https://docs.roboflow.com/workflows/manage/manage-workflow-versions.md (share link title from `llms.txt`), https://docs.roboflow.com/workflows/manage/manage-workflows.md
- **LabelDesk hook points:** `apps/backend/app/routers/rbac.py`

### F6.32 Batch run over the workspace image library (RF: *Asset Library → Run Workflow*)
- **What the user does:** selects images (or a whole search result) and runs one workflow over them.
- **Flow:** 1. Asset Library → select images or "all matching search". 2. "Run Workflow" → pick a published workflow with exactly one `image` input (`source_id` is filled per image). 3. Job appears in the job list with a "Source and type" row showing the query used, plus an "Open in Asset Library" link. 4. `[error: workflow with a different input shape is rejected before the job starts]`.
- **Why it is easy:** the selection that defines the job is preserved and re-openable, so "which 4,000 images did this run on" is answerable later.
- **Gates:** credits per machine-hour; role needed to manage batch automations.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/batch-processing.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Dataset.tsx`

### F6.33 Deploying a workflow to an endpoint or a device from one button (RF: *Deploy*)
- **What the user does:** chooses a destination and gets runtime-appropriate instructions.
- **Flow:** 1. Editor → "Deploy". 2. Options: Cloud Streaming (live source) / HTTP API / Dedicated / self-hosted video / Batch / Inference CLI / Python package. 3. Cloud Streaming path: select source → fill required Workflow Inputs → pick "Visual Preview Output" (image output) → review hourly estimate → "Start Processing". 4. Device path: publishing stages a pin awaiting approval (F6.27).
- **Why it is easy:** deploy is a chooser with a one-line "best for" per row, not six separate tutorials; the estimate is labelled an hourly rate, not a total.
- **Gates:** Cloud Streaming for managed cameras; devices need Deployment Manager (Enterprise).
- **Sources:** https://docs.roboflow.com/workflows/deploy/deploy-a-workflow.md, https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/run-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

---

## 6.5 Block catalogue (188 blocks by category, per the blocks page)

Counts are what a fetched page states; representative blocks only. First-release cut is our planning suggestion, not Roboflow's.

| Category | Blocks | Representative blocks and what they are for | Suggested first release |
|---|---|---|---|
| Run a model | largest category; ~70 listed incl. every VLM vendor | Object / instance-seg / semantic-seg / keypoint / single-label & multi-label classification blocks; Anomaly Detection; SAM 2, SAM 3, SAM 3 Interactive (point+box prompts), YOLO-World (text-prompted); OCR family (DocTR, EasyOCR, PP-OCR, GLM-OCR, Google Vision OCR, TrOCR); Barcode and QR read; Depth Estimation; CLIP / Perception Encoder embeddings and Clip Comparison; LMM, LMM-for-Classification, OpenAI, Anthropic Claude, Gemini, Qwen family, Florence-2, Moondream2, SmolVLM2, OpenRouter, OpenAI-compatible endpoint, Roboflow Visual Search Classifier | detection, seg, classification, anomaly, barcode/QR, OCR, SAM-2 polygon conversion |
| Visualize predictions | ~30 | Bounding box, label, rich label, mask, polygon, keypoint, classification label, heatmap (from detections), anomaly heatmap, trace, polygon-zone mask, line-counter mask, grid, text display, blur / pixelate (privacy), crop enlarge, model-comparison | box + label + polygon + zone mask |
| Logic and branching | 9 | Continue If (stop a branch), Switch Case, Detections Filter, Per-Class Confidence Filter, Overlap Filter, Detections Consensus (multi-model vote), Delta Filter (proceed only on change), Rate Limiter, Inner Workflow | detections filter, continue-if, switch-case, rate limiter |
| Data storage / sinks | ~10 | Dataset Upload, Vision Events, S3 Sink, Webhook Sink, Local File Sink, CSV Formatter, Data Aggregator (time-window stats), Asset Library Attributes, Write Vision Event Bundle (air-gapped tar) | dataset upload, webhook, S3, CSV |
| Notifications | 4 | Email, Slack, Twilio SMS, Twilio SMS/MMS | email + Slack |
| Video processing | ~22 | ByteTrack, BoT-SORT, SORT, OC-SORT, ByteTracker, SAM2/SAM3 video trackers; Line Counter; Time in Zone; Velocity; Motion Detection; Background Subtraction; Path Deviation; Detections Stabilizer; Track Class Lock (majority-vote the class); Frame Delay; Buffer; Image Stack; Identify Outliers / Identify Changes (embedding-based); PTZ Tracking (ONVIF); Action Recognition | ByteTrack, line counter, time-in-zone, velocity, motion detection |
| Transformations | 12 | Dynamic Crop, Absolute / Relative Static Crop, Bounding Rectangle, Detections Merge / Combine / Transformation, Detection Offset, Stitch Images, Camera Calibration, GeoTag Detection (pixels→GPS), QR Code Generator | dynamic crop, static crop, detections merge |
| Classical CV | ~20 | Blur, threshold, grayscale, morphological transform, contours, template matching, SIFT / SIFT comparison, pixel color count, dominant color, contrast enhance/equalize, size & distance measurement, mask area measurement, mask edge snap, camera focus score, auto-rotate on edges, image preprocessing | threshold + contours + camera focus |
| Advanced | ~24 | Expression, Current Time, JSON Parser, String Template (dynamic prompts), Cache Get/Set, Environment Secrets Store, First Non-Empty-or-Default, Dimension Collapse, Detections Roll-Up/Stitch/Difference, Overlap Analysis, Image Slicer (SAHI tiling), Perspective Correction, Dynamic Zone, Property Definition, VLM-as-Classifier, VLM-as-Detector, Model-Monitoring aggregator, Custom Metadata, Visual Search | property definition, expression, image slicer, secrets |
| Custom code | — | Custom Python blocks, dynamic Python blocks defined inline in the definition, custom-block plugins, Salesforce work-order example | custom Python (gated) |
| Enterprise | — | Connectors to enterprise systems/protocols (MQTT/OPC/PLC triggers sold as a manufacturing add-on) | not first release |

- **Sources:** https://docs.roboflow.com/workflows/blocks/blocks.md, https://roboflow.com/pricing (MQTT/OPC/PLC add-on).

### F6.34 Worked example A — the five-minute pipeline, exact click order (RF: *Hello World*)
- **Flow:** 1. Empty workflow (`localhost:9001/build`, "Create a Workflow", choose "Build My Own" in detached mode) → empty canvas. 2. "Add a Block" → block sidebar → object detection block. 3. Choose a model: COCO-pretrained, or a workspace model, or a Universe model → block appears with an `image` input. 4. "Test Workflow" (top right) → add an image → Run → output is the model JSON. 5. "+" under the model block → add Bounding Box Visualization, then Label Visualization. 6. Outputs block → "Move Up" on the visualization → Run again → image above JSON. 7. Click the thumbnail / toggle Visual for the full frame. 8. "Deploy" for the snippet.
- **Why it is easy:** five actions, each one visible on the canvas, and step 4 produces a working result before any visualization work.
- **Gates:** none on the cloud path (free account); detached mode drops remote deployment, monitoring, model hub and dataset integration, and you own access control.
- **Sources:** https://docs.roboflow.com/workflows/tutorials/hello-world.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/Workflows.tsx`

### F6.35 Worked example B — detect, count, draw (RF: *Build a Workflow*)
- **Flow:** 1. Object Detection Model block → pre-trained `yolov8n`, core params: class filter, confidence, IoU, max detections, class-agnostic NMS. 2. Property Definition block → Data = model predictions, operation = "Count Items". 3. Bounding Box Visualization → image = the input image, predictions = model results. 4. Label Visualization → its own image input is the *bounding box output image*, so labels draw on top. 5. Text param switches between class name, confidence, or both. 6. Save → publish after checks.
- **Why it is easy:** the chaining rule is demonstrated with the one subtlety that trips people up (feed the previous visualization, not the original image), and it is explained as "so the labels draw on top".
- **Gates:** save is manual; publish gated.
- **Sources:** https://docs.roboflow.com/workflows/build/build-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/WorkflowBlocks.tsx`

### F6.36 Worked example C — two-stage detect→crop→classify→write back (RF: *two-stage Workflow*)
- **Flow:** 1. Object Detection (`rfdetr-small`). 2. Dynamic Crop: Image = `$inputs.image`, Predictions = model predictions → emits `crops`. 3. Classification Model on `$steps.dynamic_crop.crops`. 4. Detections Classes Replacement: object-detection predictions + classification predictions → detections carrying the crop's class. 5. Bounding Box Visualization on the input image, Label Visualization on the first viz image, both reading the replaced detections. 6. Outputs: replaced detections + final image. The docs also print the full definition JSON so it can be pasted into the editor.
- **Why it is easy:** the crop→classify→write-back pattern is the standard way to get per-object classes, and shipping the definition JSON makes it copy-exact rather than screenshot-exact.
- **Gates:** crops sit one level deeper than images, so results nest — the page points at the execution model rather than hiding it.
- **Sources:** https://docs.roboflow.com/workflows/build/build-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/project/workflowChain.ts`

---

## 6.6 SDKs and CLI

### F6.37 Two Python entry points: in-process library and HTTP client (RF: *inference / inference-sdk*)
- **What the user does:** either loads a model inside their own process or talks to a server.
- **Flow:** 1. `pip install inference` (GPU: `pip install --extra-index-url https://download.pytorch.org/whl/cu124 inference-gpu`). 2. `get_model(model_id="rfdetr-small").infer(path)`. 3. Or `pip install inference-sdk` → `InferenceHTTPClient(api_url=…, api_key=…)`, `.configure(InferenceConfiguration(api_key_transport="header"))`, `.infer(...)` / `.run_workflow(...)`. 4. Backends auto-selected: ONNX, TensorRT, Hugging Face, PyTorch — TensorRT preferred when an engine exists for the platform.
- **Why it is easy:** the same model ID and the same result shape work in both, so moving from a notebook to a service is a constructor change.
- **Gates:** `api_key_transport="header"` recommended; servers older than Inference 1.5.0 only read query/body keys (`"both"` is the bridge); a key without transport config keeps the key in URLs and logs.
- **Sources:** https://docs.roboflow.com/reference/inference/inference-python.md, https://docs.roboflow.com/deployment/roboflow-cloud/serverless-api.md
- **LabelDesk hook points:** `apps/backend/app/routers/devapi.py`

### F6.38 Video pipeline object for webcams, files and RTSP (RF: *InferencePipeline*)
- **What the user does:** runs a model over a video source with a callback per prediction and a choice of sinks.
- **Flow:** `InferencePipeline.init(model_id=…, video_reference=<webcam id | file | URL | RTSP | list>, on_prediction=<callable>, api_key=…)` → `start()` → `join()`. Sinks: `render_boxes`, UDP JSON, multi-sink, video file. `init_with_workflow(spec | workspace+workflow_id)` and `init_with_custom_logic(callable)` swap the body of the loop.
- **Why it is easy:** one object covers "my webcam", "this mp4" and "this camera URL", so the same prototype moves to production unchanged.
- **Gates:** no retry/timing parameters documented for reconnect; profiling behind an env flag.
- **Sources:** https://docs.roboflow.com/reference/inference/inference-python.md, https://docs.roboflow.com/reference/inference/inference-pipeline.md (from `llms.txt`; behaviour per prior repo note)
- **LabelDesk hook points:** `apps/backend/app/streams/manager.py` (path from router import)

### F6.39 Two CLIs with a stated boundary (RF: *inference CLI vs roboflow CLI*)
- **What the user does:** uses `inference …` for runtime work and `roboflow …` for platform work, and does not mix them up.
- **Flow:** `inference server start|status`, `inference infer <path> -m <project/version>` (with `-c`, `-o`, `-t`, `--json`), `inference workflows process-images-directory -i -o --workspace_name --workflow_id` (writes per-file `results.json` plus `aggregated_results.csv`), `inference benchmark`, `inference cloud` (SkyPilot to AWS/GCP). Platform side: `roboflow auth login`, `roboflow workflow list|get|create|update|fork|version list`, `roboflow deployment list|create|get|log|usage|pause|resume|delete`, `roboflow batch create|status|list|abort|restart`, `roboflow infer`, `roboflow api-key`, `roboflow asynctasks wait`, all with `--json`.
- **Why it is easy:** the split is stated in one line on both pages, and every command has `--json` so shell scripting is a first-class path rather than an afterthought.
- **Gates:** CLI exit codes 0/1/2/3; `batch restart` can consume credits; signed-URL ingestion is Enterprise.
- **Sources:** https://docs.roboflow.com/reference/inference/inference-cli.md, https://docs.roboflow.com/workflows/manage/manage-workflows.md, https://docs.roboflow.com/deployment/roboflow-cloud/dedicated-deployments.md, https://docs.roboflow.com/deployment/roboflow-cloud/batch-processing.md
- **LabelDesk hook points:** `apps/backend/app/routers/devapi.py`

### F6.40 Key resolution that works in a notebook, a container and CI (RF: *authentication*)
- **What the user does:** passes the key as env var, explicit argument, or interactive login; the SDK finds it.
- **Flow:** `ROBOFLOW_API_KEY` env var → `login()` for a cached credential → explicit `api_key=` argument. REST accepts `Authorization: Bearer`, with `?api_key=` and body field kept for legacy. Config or all options in one page; per-key scopes for what the key may touch.
- **Why it is easy:** the three paths cover notebook (login), container (env) and library (argument) without a config file format to learn.
- **Gates:** publishable keys are rejected by management endpoints; a key with no scope array is full access.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/serverless-api.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/frontend/src/features/project/Deploy.tsx`

---

## 6.7 Video, streams and cameras

### F6.41 Source types with different lifetimes, stated as a table (RF: *Connect a Source*)
- **What the user does:** adds a camera and knows immediately whether it can become a permanent deployment.
- **Flow:** 1. Deployments → Cloud Streaming → "Add Video Source". 2. Tabs: connector (USB / RTSP / ONVIF, up to 50 cameras per connector), Camera URL (RTSP/RTSPS/HLS, no connector), RTMP (pilot), Verkada (org API key), webcam / phone (QR, one-time, expires in 5 min). 3. RTSP by URL: name + full URL + separate username/password. 4. ONVIF: "Add" a camera found on the network → credentials → pick a profile → wait for "Applied" and live video. 5. `[error: "Rejected by the connector" with a reason; "Settings rejected" leaves the camera on its last settings]`.
- **Why it is easy:** the lifetime column tells the user before they build that a webcam preview cannot become a deployment, and camera discovery removes the RTSP-URL typo class.
- **Gates:** `Manage Source Video` permission for RTMP and for starting/stopping; RTMP not available in the EU region; saved passwords cannot be read back; editing a camera can interrupt its stream.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/connect-a-source.md
- **LabelDesk hook points:** `apps/frontend/src/features/streams/Streams.tsx`, `apps/backend/app/routers/streams.py`

### F6.42 Capture settings only where they can actually apply (RF: *Capture and codec settings*)
- **What the user does:** fixes resolution/FPS for a USB camera and learns not to try it on RTSP.
- **Flow:** 1. Source menu → "Capture Settings" → pick a mode the camera reports → wait for "Applied". 2. RTSP path: the camera's own encoded stream is used without re-encoding, so change the camera profile instead. 3. Codec guidance: H.264 baseline, no B-frames, else relay works but browser playback fails.
- **Why it is easy:** it says which knob is inert for which source type, which is the actual failure mode (users lowering FPS in the app and seeing no change).
- **Gates:** applying settings can restart the stream.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/connect-a-source.md
- **LabelDesk hook points:** `apps/frontend/src/features/streams/StreamDetail.tsx`

### F6.43 Zones, lines and counters as workflow blocks, drawn on an image (RF: *Line Counter / Time in Zone / PolygonZone*)
- **What the user does:** draws a polygon or a line over the frame, then counts crossings or measures dwell from track IDs.
- **Flow:** 1. In the editor, use the zone/line drawing surface on a still frame to get polygon coordinates. 2. Feed them to Line Counter (count per direction) or Time in Zone (enter/exit timestamps per track). 3. Add the matching visualization block so the operator sees the zone on the live video. 4. Add Track Class Lock so a track's class stops flickering while it is inside.
- **Why it is easy:** the geometry is captured by drawing rather than by typing coordinates, and the visualization block guarantees the operator and the model see the same zone.
- **Gates:** needs a tracker upstream; counters are in-memory, so a restart resets them.
- **Sources:** https://docs.roboflow.com/workflows/blocks/blocks.md, https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/run-a-workflow.md
- **LabelDesk hook points:** `apps/frontend/src/features/streams/ZoneEditor.tsx`

### F6.44 Live results, event history and "what happened when the camera died" (RF: *job states / Activity / auto-recovery*)
- **What the user does:** watches a running deployment, reads its state, and recovers from a drop.
- **Flow:** 1. Source page → Workflow runs, with previews listed separately from deployments. 2. State text: Waiting for video / Waiting for capacity / Starting / Processing (check frame counts advance) / Reconnecting or Retrying / Adjusting resources / Needs attention / Recovery suspended or Failed / Stopped. 3. "Activity" tab lists the last 30 lifecycle changes when recovery is on — explicitly *not* prediction history. 4. Recovery auto-enables after 30 s of steady processing; a camera drop leaves the deployment enabled and waiting, and it resumes when video returns. 5. Recovery pauses after 5 failures, 15 minutes without processing, or 10 starts in an hour → "Needs attention". 6. Restart / Restart All Streams / Stop (with confirm). 7. Offline emails: workspace-level opt-in, default 5-minute threshold, reminders at 30 min → 1 → 2 → 4 h → every 6 h, 2/hour and 10/day caps, test email, no recovery email.
- **Why it is easy:** "camera online" and "workflow processing" are separate states with separate wording, so a healthy camera with a stopped job is diagnosable from one screen; and closing the browser never silently leaves a bill running (the page says it explicitly).
- **Gates:** previews bill; `Manage Source Video` to change; offline notifications are excluded for previews, direct sources and blocked workflows; rate-limited device endpoints return `429`.
- **Sources:** https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/manage-and-monitor.md, https://docs.roboflow.com/deployment/roboflow-cloud/cloud-streaming/run-a-workflow.md
- **LabelDesk hook points:** `apps/backend/app/streams/manager.py`, `apps/frontend/src/features/streams/StreamAnalytics.tsx`

---

## 6.8 Self-hosting and the edge fleet

### F6.45 Install paths per platform, with a one-command default (RF: *Install Inference Server*)
- **What the user does:** gets a server running on Linux, Windows, macOS, Jetson, Raspberry Pi, or their own cloud.
- **Flow:** 1. `pip install inference-cli && inference server start` → pulls the right image, publishes `127.0.0.1:9001`. 2. `inference server status`. 3. Per-platform guides for manual `docker run`, with Linux/Windows/macOS/Jetson/Pi anchors. 4. Own cloud: `inference cloud` via SkyPilot on AWS/Azure/GCP. 5. Jetson: JetPack-specific containers, compiled TensorRT engines cached on a volume (first compile can exceed 15 minutes — from prior repo note; not re-verified today).
- **Why it is easy:** the CLI detects the platform and picks the container, so the "which image do I need for this JetPack version" question is asked once, by the tool.
- **Gates:** JetPack 4 deprecated; Mac has no GPU path in Docker (MPS outside Docker); server binds localhost by default for safety.
- **Sources:** https://docs.roboflow.com/deployment/self-hosted/inference-server.md, https://docs.roboflow.com/deployment/choosing-a-deployment.md
- **LabelDesk hook points:** `apps/backend/app/routers/remote.py`

### F6.46 Fleet management with per-device config, approval and maintenance windows (RF: *Deployment Manager*)
- **What the user does:** provisions devices, assigns cameras, pushes workflow/config changes, and watches health from one list.
- **Flow:** 1. Deployments → Edge Devices: devices seen in the last 7 days first; columns for healthy Services, running Streams, last heartbeat (offline after 5 minutes). 2. Version groups by Inference / JetPack, updated automatically, not renameable. 3. Add device → returns an `installId` used by the installer; a device can be duplicated from another device's config. 4. Config change → can come back `staged: true` with a `configProposal` waiting for approval, then `deferred: true` until the maintenance window; `forceApply` / `immediateDelta` do not bypass approval. 5. Config history per device; service-version pin with optimistic-concurrency check. 6. Commands are queued and picked up on the device's next poll. 7. Per-device alerts for connectivity, disk usage, camera FPS and inference FPS; snooze; capture a frame to a project; sample a live frame (URL valid 1 hour).
- **Why it is easy:** a config change that went to 200 devices cannot silently go live — staged → approved → windowed is visible at each step, and reading the config back is explicitly called out as *not* proof of running state, which sets the right expectation.
- **Gates:** Enterprise only; supported hardware = bought from Roboflow (Jetson / x86 Debian+NVIDIA unsupported, macOS and Windows unsupported); device needs internet except in prepared offline mode; API scopes `device:read`/`device:update`; log reads 120/min per workspace, telemetry 60/min per device with a 10-per-10s burst.
- **Sources:** https://docs.roboflow.com/deployment/self-hosted/enterprise/deployment-manager.md, https://roboflow.com/pricing
- **LabelDesk hook points:** `apps/backend/app/routers/remote.py`, `apps/backend/app/routers/ops.py`

---

## Title-only / unverified

- Workflow Evals, block governance, Cloud Streaming `pricing-and-limits` (GPU sizes `gpu-s-v1` fallback), `consume-results` (WebSocket live feed, snapshot/clip saving), `install-a-connector`, Secure Gateway, offline mode, License Server, parallel HTTP API, Stream Management API, Event Store retention numbers, RTSP Simulator — titles and one-line descriptions only from `llms.txt`.
- A JavaScript/browser snippet on the deploy surface: the Rapid page says "snippets in various programming languages" without naming them; `inferencejs` exists as a separate browser product. Exact tab list unverified.
- Whether the deploy screen shows rate limits numerically: no number was published anywhere except Deployment Manager endpoints; the Serverless path only documents "on a 429, back off".
- Alias/`production` pointer: no user-defined alias or traffic split found. Cannot rule out an undocumented feature.
- Model Monitoring alerting thresholds and delivery (title only).
- Self-hosted hardware minimums (`install/minimum-requirements`) and the full device support matrix beyond Deployment Manager's list.
- Credit rates for dedicated GPU sizes and stream-hour prices by GPU class beyond the pricing page excerpt (0.1 credits/h base, SAM 3 0.4/h, Qwen3-VL "starting at … up to 0.2 credits / 5h").
- Legacy/deprecated surfaces not inspected: `*.roboflow.com` task hosts, Serverless Video Streaming API, `inference server` WebRTC specifics.

## Coverage gaps and what to check next

1. **The deploy screen itself** deserves one pass on a logged-in free account (public docs never enumerate the tabs): exact snippet languages, where the key is masked, whether there is a "test in browser" playground distinct from the Workflow preview, and what an empty project with no ready model shows.
2. **Block-level parameter schemas** for the 8–10 blocks we plan to ship first (detection, filter, tracker, line counter, zone, viz, dataset upload, webhook) — each has its own page we did not open.
3. **Workflow Evals** (gate that compares versions against labelled cases) — this is the missing link between "version history" and "publish", and our parity matrix will otherwise show publish as ungated.
4. **Cloud Streaming economics**: GPU size tiers, per-second vs per-hour rounding, and what happens to credits when a job sits in "Waiting for video".
5. **Vision Events query language** (filters, facets, natural-language path) and the export shape, since our `stream-analytics` page would feed the same surface.
6. **Air-gapped / offline**: cached weights, bundle upload (`Write Vision Event Bundle`), and the licence-server path — relevant if LabelDesk is sold into Thai factories with no egress.
