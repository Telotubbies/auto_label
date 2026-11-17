# Platform-wide UX/UI and Information Architecture of Computer-Vision SaaS (outside the annotation editor)

Research date: 2026-10-31. Method: web search + direct fetch of official docs where possible. Items marked [search-summary] come from search-result summaries of the cited page rather than a full page read, so verify them before quoting exact wording. Items marked [older] predate 2025.

---

## Q1. Information architecture, navigation, and new-user guidance (Roboflow, Ultralytics Platform, LandingLens, V7, Encord, Labelbox, Supervisely, Edge Impulse)

### Takeaway
Every platform uses the same lifecycle spine: **Data (upload/curate) → Annotate → Snapshot/Version → Train → Evaluate → Deploy → Monitor**. The left sidebar inside a project usually follows those steps in order. Onboarding relies on three levers: forkable sample datasets (Roboflow Universe), fast/preset training (LandingLens Fast Training, Roboflow Instant), and built-in "try it" inference right after training. LabelDesk's sidebar should follow the lifecycle steps in order. The first-run goal should be a model the user can try within one session.

### Cited Findings
**Roboflow**
- Project-level sidebar items cited in the docs: "Models" (click Models in the sidebar to start Roboflow Instant training) and "Deployments" → "Devices" tab for edge-device management — [Roboflow Instant](https://docs.roboflow.com/train/roboflow-instant); [Add a device](https://docs.roboflow.com/deploy/device-manager/add-a-device) [search-summary]
- Training requires a Dataset Version first. A version is a "point-in-time snapshot" of images and labels — [Dataset Versions](https://docs.roboflow.com/datasets/dataset-versions) [search-summary]
- Upload docs cover "Upload Images, Videos, and Annotations" plus cloud import from AWS S3, Azure Blob, and GCS — [Roboflow Docs](https://docs.roboflow.com/annotate/ai-labeling/automated-annotation-with-autodistill) [search-summary]
- Onboarding through public data: "Fork Project" copies a Universe dataset's images and annotations into a new project in the user's workspace. The fork starts with fresh versions and export settings. API: POST `/:workspace/projects/fork` (needs `project:create` scope; async task you poll) — [Fork a Universe dataset](https://docs.roboflow.com/datasets/universe/universe/fork-a-universe-dataset) [search-summary]
- The docs navigation also has "Search a Dataset", "Use CLIP", and "Model Monitoring" (sub-pages: Alerting, Custom Metadata and Inference Result Stats) — [Roboflow Quick start/nav](https://docs.roboflow.com/quick-start); [Monitoring](https://docs.roboflow.com/roboflow-hi/deploy/device-manager/monitoring) [search-summary; page contents not verified]
- Workflows has an AI assistant for building pipelines — [Workflows AI Assistant](https://docs.roboflow.com/workflows/workflows-ai-assistant) [search-summary]

**Ultralytics Platform (successor to HUB, 2025-2026)**
- Documented flow: Upload → Annotate → Train → Export → Deploy. Projects hold Models (checkpoints) and an Activity Log (history of changes) — [Ultralytics Platform docs](https://docs.ultralytics.com/platform)
- Platform docs sections: Overview, Quickstart, Agents, Data, Train, Deploy, Integrations, Account, Explore, REST API. The account menu handles switching workspaces and managing teams — [Ultralytics Platform](https://docs.ultralytics.com/platform)
- Onboarding asks the user to pick a data region (US/EU/AP). The platform measures latency and recommends the closest region. The choice is **permanent**, and changing it requires support — [Ultralytics Platform](https://docs.ultralytics.com/platform)
- Quickstart: sign up → choose region → upload data in Datasets → create project + start cloud training → test and deploy to a dedicated endpoint — [Quickstart](https://docs.ultralytics.com/platform/quickstart) [search-summary]
- Annotation includes manual tools, SAM smart annotation, and YOLO auto-labeling for all 5 task types — [Ultralytics Platform](https://docs.ultralytics.com/platform?h=hub%20cloud%20training) [search-summary]
- Conflicting limits in the docs: ZIP upload max 10 GB vs 50 GB; 43 vs 42 deploy regions; `ultralytics>=8.4.35` vs `>=8.4.0` — [EN docs](https://docs.ultralytics.com/platform); [KO docs](https://docs.ultralytics.com/ko/platform) [search-summary; conflict unresolved]

**LandingLens (Landing AI)**
- Documented 7-step flow: create project → upload images → create classes → label → train → review predictions → deploy. If results fall short, the user improves the dataset and retrains — [LandingLens Workflow](https://docs.landing.ai/landinglens/landinglens-workflow) [search-summary]
- Training offers "Fast Training" (preset) and "Custom Training" (advanced). Predictions appear on the **Build** tab, and detailed metrics (F1, IoU) are in the model's Performance Report. Evaluation sets default to Train/Dev/Test — [Train models](https://docs.landing.ai/landinglens/train-models); [Custom Training](https://docs.landing.ai/landinglens/custom-training); [Models Page](https://landinglens.docs.landing.ai/models-page) [search-summary]
- Deploy options: Cloud Deployment (hosted inside the app) or Docker self-host — [Deployment options](https://docs.landing.ai/landinglens/deployment-options) [search-summary]

**Edge Impulse Studio**
- Sidebar: Dashboard, Data acquisition, Experiments (contains the EON Tuner), Impulse design (Create impulse, processing block, learning block), Retrain, Live classification, Model testing, Deployment. An "impulse" is a pipeline: input block → processing (feature extraction) → learning block — [EON Tuner docs](https://docs.edgeimpulse.com/docs/edge-impulse-studio/eon-tuner); [public project example](https://studio.edgeimpulse.com/public/141212/latest/impulse/1/create-impulse) [search-summary]
- EON Tuner is an AutoML search over the whole pipeline within hardware constraints (RAM/latency of the target device). It now uses Bayesian optimization instead of random search — [EON Tuner](https://docs.edgeimpulse.com/docs/edge-impulse-studio/eon-tuner) [search-summary]
- Public projects are browsable read-only in Studio, which shows how sample projects can serve as templates — [Edge Impulse public tuner page](https://studio.edgeimpulse.com/public/25483/latest/tuner)

**Labelbox / Encord / V7 / Supervisely**
- Labelbox splits the product into **Catalog** (data curation/search) and **Annotate** (labeling) — [Labellerr comparison 2026](https://www.labellerr.com/blog/best-data-annotation-software/); [Catalog overview](https://docs.labelbox.com/docs/catalog-overview)
- Encord's IA puts **Index** (find valuable data, edge cases, quality issues, underrepresented classes) before annotation, and Active is used for model evaluation/failure modes — [Taskmonk 2026](https://www.taskmonk.ai/blogs/best-encord-alternatives); [Lightly](https://www.lightly.ai/blog/data-annotation-tools) [secondary sources]
- V7 Darwin supports 50+ data types, including DICOM/SVS and PDFs. V7 now runs two separate products (Darwin annotation + a separate agent product) — [autolabelling.com V7 review 2026](https://autolabelling.com/v7-labs/); [Labellerr](https://www.labellerr.com/blog/best-data-annotation-software/) [secondary]
- Supervisely is self-hostable, and its IA is extended through "Supervisely Apps" built on its SDK — [Labellerr](https://www.labellerr.com/blog/best-data-annotation-software/) [secondary]

**SaaS onboarding benchmarks**
- Userpilot 2025 benchmark (547 companies; activation/TTV from a 62-company subset): average activation rate 37.5% (median 37.04%). Average time-to-value is 1 day 12 h 23 min. Average onboarding-checklist completion is 19.2% (188 companies) — [Userpilot SaaS Product Metrics](https://userpilot.com/saas-product-metrics/); [Activation rate](https://userpilot.com/blog/activation-rate/) [search-summary; 37.5% also appears in the 2024 report, so it may be carried over]
- PAIR guidance on onboarding: onboard in stages, be up-front about what the product can and can't do on first use, describe the core value first, and introduce features as they are used — [PAIR Mental Models chapter](https://pair.withgoogle.com/chapter/mental-models/)

### Inferences
- Must-have IA for LabelDesk: Workspace switcher → Projects list → project sidebar ordered by lifecycle (Upload, Dataset, Health, Versions, Train/Models, Evaluate, Playground, Deploy, Monitor). This matches Roboflow, Ultralytics, LandingLens, and Edge Impulse.
- Should-have: an "Activity log" per project (Ultralytics), one-click fork of a sample dataset (Roboflow Universe), a "Fast vs Custom" training split (LandingLens).
- A setup checklist alone is weak, since average completion is only 19.2%. Pair it with a sample project that is already trained so the user sees value immediately. The 1.5-day average TTV is a bar to beat.
- If LabelDesk has region/storage choices, avoid irreversible choices during onboarding (Ultralytics' permanent region is a friction point), or label them clearly as permanent.

### Gaps
- No screenshots or official docs verified for the exact top-level sidebar order of Roboflow, V7, Encord, or Supervisely. Their IA claims above come from secondary comparison articles.
- No public data found on any CV platform's time-to-first-model or onboarding-checklist content.
- Roboflow empty states and templates were not verified.

---

## Q2. Screen patterns: upload, dataset browsing/search, health, versions, training, evaluation, comparison, playground, deployment

### Takeaway
The patterns that recur across platforms are: dedupe at upload, with skipped files reported; a gallery with metadata filters plus CLIP-style natural-language and similarity search; a health dashboard of clickable charts (click a bar or region to filter the grid); a version wizard (split → preprocessing → augmentation → generate); presets plus a raw-YAML "Advanced" escape hatch with a live cost estimate; streaming loss/metric curves; and evaluation built on a confidence-slider-driven confusion matrix that links into a GT-vs-prediction viewer, with automated improvement recommendations (Roboflow 2025).

### Cited Findings
**Upload and dedupe**
- Roboflow skips an image that already exists in the project, to avoid train/valid/test leakage. Duplicates across projects in a workspace count toward usage only once — [Manage images](https://docs.roboflow.com/datasets/manage/manage-images.md); [Roboflow FAQ forum](https://discuss.roboflow.com/t/how-are-duplicate-images-counted-in-my-image-usage/3892) [search-summary]
- UX failure mode: users report "uploaded 936, only 120 saved" or "missing images" because dedupe was silent. Sources disagree on whether matching is pixel-hash or similarity — [Forum 3188](https://discuss.roboflow.com/t/i-upload-936-images-but-only-120-get-save-into-roboflow/3188); [Forum 248](https://discuss.roboflow.com/t/not-all-images-will-upload/248) [older, 2023-24]
- Ultralytics Platform accepts images, videos, and dataset files/ZIPs for upload — [Ultralytics Platform](https://docs.ultralytics.com/platform)

**Dataset browsing, semantic search, embeddings**
- Labelbox Catalog: a "Natural language" filter in the gallery view (Visual or Text mode) uses the same network to embed the query and the data rows. The score is cosine distance (0-1), with a slider to adjust the range. Labelbox recommends trying several prompts — [Natural language search](https://docs.labelbox.com/docs/natural-language-search)
- Labelbox similarity search uses L1 (Manhattan) distance, with a default score window of 0.85-1. Users can pick off-the-shelf or custom embeddings — [Similarity](https://docs.labelbox.com/docs/similarity)
- Off-the-shelf embeddings are CLIP-ViT-B-32 (512-d) for images and all-mpnet-base-v2 (768-d) for text. Custom embeddings can be up to 2048-d, with up to 100 per workspace — [Catalog search compatibility](https://docs.labelbox.com/docs/catalog-search-compatibility) [search-summary]
- Encord Active: interactive data exploration with embeddings, plus failure-mode detection and PR curves — [Lightly comparison](https://www.lightly.ai/blog/data-annotation-tools) [secondary]
- Roboflow's docs have "Search a Dataset" and "Use CLIP" pages — [Roboflow Docs nav](https://docs.roboflow.com/quick-start) [contents not verified]

**Dataset health**
- Roboflow Health Check charts: Class balance (per split), Dimension Insights (raw sizes/aspect ratios), an Annotation Heat Map where **dragging over a region shows the matching images**, and an Object-count histogram where **clicking a bar shows those images**. Summary stats: image/annotation counts, average size, median ratio, missing annotations, null annotations. Built-in recommendations: add nulls, fix missing annotations, cover other spatial regions, include 0/1/many-instance images, use resize — [Dataset Health Check](https://docs.roboflow.com/datasets/dataset-health-check)
- Ultralytics dataset statistics: class distribution, split distribution, location heatmaps, bbox dimension analysis, a Classes tab, and a split bar for redistributing train/val — [Ultralytics Platform](https://docs.ultralytics.com/platform)

**Version creation wizard**
- Roboflow "Generate New Version": set the train/valid/test split → "Add Preprocessing Step" (auto-orient, resize, tile...) → "Add Augmentation Step" → choose the output multiplier (capped by plan) → Generate. Versions are frozen snapshots — [Create a Dataset Version](https://docs.roboflow.com/datasets/versions/dataset-versions/create-a-dataset-version); [RF-DETR preprocessing](https://roboflow.com/blog/how-to-preprocess-data-for-rf-detr-training) [search-summary]
- Ultralytics: numbered dataset-version snapshots — [Ultralytics Platform](https://docs.ultralytics.com/platform)

**Training configuration and live charts**
- Ultralytics: "New Model" → dataset → model → GPU → epochs. An "Advanced Settings" YAML editor overrides any training argument. A **live cost estimate** is shown. Loss curves and metrics stream in real time. GPUs range from RTX 2000 Ada at $0.24/h to B300 at $7.39/h, and B200/B300 are gated to Pro/Enterprise. Users can also train on their own hardware and stream metrics to the platform — [Ultralytics Platform](https://docs.ultralytics.com/platform)
- LandingLens: Fast Training vs Custom Training — [Custom Training](https://docs.landing.ai/landinglens/custom-training) [search-summary]
- Edge Impulse EON Tuner: an AutoML grid of candidate pipelines scored against device constraints — [EON Tuner](https://docs.edgeimpulse.com/docs/edge-impulse-studio/eon-tuner) [search-summary]

**Evaluation and comparison**
- Roboflow model evaluation (OD, instance seg, classification, semantic seg): a confusion matrix of GT vs predictions with a **confidence threshold slider** that updates the matrix, precision, and recall. The default is the computed optimal threshold. A vector explorer sits on the trained-model page. API: `matrix[actual][predicted]` (pixel counts for semantic seg) — [Evaluate Trained Models](https://docs.roboflow.com/models/evaluate/evaluate-trained-models); [Confusion matrix API](https://docs.roboflow.com/developer/rest-api/model-evaluations/confusion-matrix); [Launch blog](https://blog.roboflow.com/evaluate-roboflow-models/)
- Roboflow changelog: Model Evaluation for Instant models (Jun 2025). **Automated Model Improvement Recommendations** derived from the confusion matrix, plus a metrics explorer that finds the optimal confidence threshold (Jul 2025) — [Jun 2025](https://docs.roboflow.com/reference/changelog/changelog/june-2025/model-evaluation-for-roboflow-instant-models); [Jul 2025](https://docs.roboflow.com/reference/changelog/changelog/july-2025/automated-model-improvement-recommendations)
- LandingLens: a Performance Report per model (F1/IoU) over evaluation sets (Train/Dev/Test), with predictions overlaid on the Build tab — [Models Page](https://landinglens.docs.landing.ai/models-page) [search-summary]
- Ultralytics has a "Compare" section at the docs top level — [Ultralytics Platform](https://docs.ultralytics.com/platform) [model-comparison screen not verified]

**Playground and deployment**
- Ultralytics in-browser inference test: upload your own images, **webcam capture**, or built-in examples. An Export tab covers 17 formats (ONNX, TensorRT, CoreML, TFLite...). Dedicated endpoints in 43 regions show status (Ready/Stopped), real-time metrics, request logs, and performance dashboards. Endpoints **scale to zero by default**, so a cold start can take up to 1 minute — [Ultralytics Platform](https://docs.ultralytics.com/platform)
- Roboflow Deployments → Devices: a device manager for edge devices, with monitoring and alerting — [Add a device](https://docs.roboflow.com/deploy/device-manager/add-a-device); [Monitoring](https://docs.roboflow.com/roboflow-hi/deploy/device-manager/monitoring) [search-summary]
- LandingLens: cloud deployment inside the app, or Docker — [Deployment options](https://docs.landing.ai/landinglens/deployment-options) [search-summary]

### Inferences
- Must-have: an upload summary that states "N uploaded / M duplicates skipped / K failed", with a reason for each. Silent dedupe is the documented source of support tickets.
- Must-have: health charts that act as filters into the grid (Roboflow's click-bar and drag-heatmap). Should-have: an automatic recommendation list.
- Must-have: an evaluation page with a confidence slider driving the confusion matrix and P/R, where clicking a cell opens the matching images in a GT-vs-pred viewer. Differentiator: automated "what to fix next" recommendations (Roboflow added this only in Jul 2025).
- Training: presets (Fast) plus an Advanced YAML/JSON override, with a live cost/time estimate and streaming charts. Ultralytics has all of these.
- Playground: image upload, webcam, and sample images, with code snippets next to it. Show the cold-start state explicitly if LabelDesk scales GPU workers to zero.
- Differentiator: CLIP natural-language search plus similarity search ("more like this") with a score slider (Labelbox pattern). An embeddings map is a should-have.

### Gaps
- Exact UI of the Roboflow embeddings/"vector explorer" and the Ultralytics model-comparison screen was not verified.
- No verified source for deployment code-snippet panel layouts (language tabs etc.) on any platform.
- Live training chart specifics (which metrics, early stopping UI) were verified only for Ultralytics, at a high level.

---

## Q3. Video analytics / CCTV monitoring UX

### Takeaway
Two layers. (1) **Configuration**: draw zones or lines on a camera frame, set direction (uni/bi), set dwell/time windows, and combine triggers with filters (Verkada Compound Alerts, Spot AI natural-language detections). (2) **Triage**: a severity split (Frigate alerts vs detections), a timeline plus a grid of short previews that are marked reviewed on hover, and filters by camera, label, and date. VLM-based verification of alerts is now the standard way to cut false positives (NVIDIA VSS, Lumana). The geometry is simple. Products differ mostly in the triage and verification layer.

### Cited Findings
**Frigate (open source, 0.14+)**
- The Review page shows review items on a **vertical timeline** and a **grid of low-res, low-fps previews**. Hovering or swiping plays a preview and **marks it reviewed**. Clicking opens the full-resolution recording — [Frigate Review](https://docs.frigate.video/configuration/review)
- Items have two severities. **Alerts** default to person and car, and **detections** are everything else. Both can be narrowed by label and by **required zones**. An empty label list excludes a camera from detections. A review item is a non-overlapping time window that can merge several old "events" — [Frigate Review](https://docs.frigate.video/configuration/review)
- The page can also show motion-only periods, and Motion Search lets the user draw a region and search past recordings for motion in it. Filters: date, object type, camera — [Frigate Review](https://docs.frigate.video/configuration/review); [dev docs](https://docs-dev.frigate.video/configuration/review)
- Current config path: Settings → Camera configuration → Review → Alerts/Detections — [Frigate Review](https://docs.frigate.video/configuration/review) [search-summary]
- Known UX issue: detections outside required zones show counts in the UI but have no recordings. The maintainer planned separate retention for alerts vs detections — [GitHub discussion #13653](https://github.com/blakeblackshear/frigate/discussions/13653) [older, 2024]

**Verkada**
- Line-crossing alerts: a virtual boundary on the camera view, unidirectional or bidirectional, **up to 4 lines**. A crossing is counted when the **bottom-center of the person's bbox** crosses the line — [Camera Event Alerts](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts) [search-summary]
- **Compound Alerts**: a trigger (line crossing/loitering) plus a filter such as a plain-text AI query. The alert fires only when both match the same person or vehicle. Some features need newer camera generations — [Compound Alerts](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts/compound-alerts); [SecurityInfoWatch](https://www.securityinfowatch.com/video-surveillance/video-analytics/product/55397743/verkada-compound-alerts) [search-summary]
- Alarm trigger events can be configured per camera — [Configure Camera Alarm Trigger Events](https://help.verkada.com/en/articles/8234488-configure-camera-alarm-trigger-events)

**Spot AI / Coram / Lumana**
- Spot AI: polygon zones, line-crossing, and **dwell-time thresholds per zone and time window**. Custom detections can be defined in natural language — [Spot AI loitering](https://www.spot.ai/blog/ai-video-analytics-loitering-detection); [Spot AI comparison 2026](https://www.spot.ai/blog/best-ai-video-analytics-companies) [vendor blog]
- Coram: wrong-direction and line-crossing as boundary alerts that also capture movement direction — [Coram 2026](https://www.coram.ai/post/best-ai-video-analytics-companies) [vendor blog]
- Lumana: zone and line alerts are verified by human agents before escalation to emergency services or designated personnel — [Lumana alarm monitoring](https://www.lumana.ai/alarm-monitoring) [vendor page]

**Milestone XProtect**
- Analytics usually come from the camera or a plugin (Axis, Bosch, Hanwha), not from zones drawn in the client. Metadata becomes "analytics events", and those feed Rules and Alarm definitions in the Alarm Manager. How much metadata (direction, trajectory) each integration passes varies by vendor — [Milestone line crossing](https://www.milestonesys.com/articles/line-crossing-analytics-xprotect/); [XProtect Analytics manual](https://milestonedownload.blob.core.windows.net/files/XProtect%20Analytics%202.2a/Manuals/MilestoneXProtectAnalytics_Generic_VA_Administrators_Manual_en-US.pdf) [manual likely older]

**NVIDIA Metropolis VSS blueprint**
- Reference architecture for video agents: real-time **verified alerts**, visual Q&A, summarization, and clip retrieval (VLMs such as Cosmos, LLMs such as Nemotron, RAG) — [VSS GitHub](https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization)
- Two alert modes: **Alert Verification** (CV pipeline + behavior analytics → VLM verifies) and **Real-Time VLM Alerts** (continuous anomaly detection on live streams) — [Alert Verification](https://docs.nvidia.com/vss/vision-agent/agent-workflows/alert-verification); [Real-Time Alerts](https://docs.nvidia.com/vss/vision-agent/agent-workflows/real-time-alerts)
- Agent UI has an Alerts tab with "View Alerts" and "Manage Alerts", and a toggle to show only VLM-verified alerts. VSS 3 uses modular docker-compose profiles, and the base agent deploys in under 5 minutes — [VSS UI](https://docs.nvidia.com/vss/system-components/user-interface); [NVIDIA dev blog](https://developer.nvidia.com/blog/transform-video-into-instantly-searchable-actionable-intelligence-with-ai-agents-and-skills/) [search-summary]
- Documented limitations: the older Gradio UI cannot edit alerts after summarization starts. Deleting one real-time rule on a camera with multiple rules stops the other rules. VLM verdicts can fail to display — [VSS UI app](https://docs.nvidia.com/vss/latest/content/ui_app.html) [search-summary]

**Roboflow Workflows (video blocks)**
- The Line Counter block takes two points defining a segment and needs tracker IDs (a tracking block upstream). It outputs in/out counts. A triggering-anchor option (e.g. CENTER) reduces false counts from objects that only graze the line. The Line Counter Visualization block draws the line and the counts on the frame — [Line Counter](https://docs.roboflow.com/workflows/blocks/blocks/video-processing/line-counter); [Inference docs](https://inference.roboflow.com/workflows/blocks/line_counter/); [Visualization](https://docs.roboflow.com/workflows/blocks/blocks/visualize-predictions/line-counter-visualization)

### Inferences
- Must-have for LabelDesk CCTV: a camera list/grid with live status, a polygon-zone and line editor drawn on a snapshot (with a direction arrow and anchor-point choice), an event list with thumbnail plus clip, filters (camera, class, zone, date), and a "reviewed" state.
- Should-have: an alerts vs detections severity split (Frigate), dwell time and time-of-day schedules (Spot AI), and per-severity retention.
- Differentiators: compound rules (trigger AND natural-language filter, Verkada), a VLM second-pass verification badge with a "verified only" filter (NVIDIA VSS), and natural-language clip search. LabelDesk could also close the loop by sending a false-positive event into the dataset as a labeled hard negative (inferred; no source shows this specific flow).
- Document the anchor semantics (bbox bottom-center vs center) in the UI, since Verkada and Roboflow both expose this detail.

### Gaps
- No verified primary docs for Avigilon, Spot AI, or Coram UI screens (only vendor blogs). Avigilon was not covered.
- No source for a live-camera-grid layout standard (tile counts, auto-cycling) from these products.

---

## Q4. UX for AI trust and transparency in ML tooling

### Takeaway
The HCI guidance agrees on a few points. Make clear what the system can do and how well. Make it easy to correct or dismiss AI output. Calibrate trust rather than maximize it. The empirical work warns that showing confidence or explanations does **not** reliably reduce overreliance. Cognitive-forcing designs (ask the human to decide first, or require confirmation) help more, at the cost of extra effort.

### Cited Findings
- Microsoft's Guidelines for Human-AI Interaction (Amershi et al., CHI 2019): 18 guidelines in 4 phases: **initially, during interaction, when wrong, over time**. They were validated through a 4-step process from 150-160+ candidate recommendations, and the authors say they are not meant to be a simple checklist — [MSR project page](https://www.microsoft.com/en-us/research/project/guidelines-for-human-ai-interaction/); [paper DOI](https://doi.org/10.1145/3290605.3300233)
- Individual guidelines that bear most on ML tooling (paraphrased from the CHI 2019 paper; the verbatim list was not fetched this session, so verify the wording at the DOI): G1 make clear what the system can do; G2 make clear how well it can do it; G9 support efficient correction; G10 scope services when in doubt; G11 make clear why the system did what it did; G15 encourage granular feedback; G16 convey the consequences of user actions; G18 notify users about changes — [paper DOI](https://doi.org/10.1145/3290605.3300233)
- The Google PAIR People + AI Guidebook has 6 chapters: User Needs, Mental Models, Explainability + Trust, Data, Feedback + Control, Errors + Graceful Failure. It is CC-licensed — [PAIR guidebook](https://pair.withgoogle.com/chapter/mental-models/); [Nervegna summary](https://nervegna.substack.com/p/googles-ai-design-playbook-has-six)
- PAIR on calibrating trust: set expectations too high and users overtrust; set them too low and users underuse — [uxdesign.cc summary](https://uxdesign.cc/the-rulebook-for-designing-ai-experiences-a22a50bb063c) [secondary]
- PAIR Feedback + Control distinguishes implicit from explicit feedback and says to tell users what impact their feedback will have. Errors + Graceful Failure says to tell users an error occurred, give them a manual path to finish the task, and avoid dead ends — [Buildo summary](https://www.buildo.com/blog-posts/what-we-learned-from-googles-people-ai-guidebook) [secondary]
- A CHI 2023 case study examines how practitioners actually use the PAIR Guidebook — [ACM DL 10.1145/3544548.3580900](https://dl.acm.org/doi/10.1145/3544548.3580900)
- Vasconcelos et al. (CSCW 2023): explanations can reduce overreliance, but only when they lower the cost of verifying the AI. Other results show that adding explanations alone did not reduce overreliance compared with predictions alone — [arXiv 2212.06823](https://arxiv.org/pdf/2212.06823); [ACM 10.1145/3579605](https://dl.acm.org/doi/abs/10.1145/3579605)
- Zhang, Liao, Bellamy (FAT* 2020): showing confidence scores can help calibrate trust, but local explanations did not improve trust calibration — [arXiv 2001.02114](https://arxiv.org/pdf/2001.02114) [older, 2020; finding as reported in the paper title/abstract]
- In a clinical CDSS study, low AI confidence decreased trust and agreement and increased decision time, with a small performance drop attributed to overreliance — [arXiv 2501.16693](https://arxiv.org/pdf/2501.16693)
- Human self-confidence calibration also affects reliance on AI ("Are you really sure?") — [arXiv 2403.09552](https://arxiv.org/pdf/2403.09552)
- Automation bias review: explanations have produced mixed results as a remedy. Automation bias is also called automation complacency — [ResearchGate review 2025](https://www.researchgate.net/publication/392771285_Exploring_automation_bias_in_human-AI_collaboration_a_review_and_implications_for_explainable_AI)
- Public-sector evidence: "selective adherence" means people follow algorithmic advice when it matches their stereotypes. The evidence for classic automation bias was weaker than expected — [Alon-Barkat & Busuioc, JPART](https://academic.oup.com/jpart/article/33/1/153/6524536)
- 2026 work argues that a displayed confidence % may calibrate perceived reliability without helping operators choose an alternative — [Frontiers Psychology 2026](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1967356/full); see also [Trust → appropriate reliance constructs](https://arxiv.org/pdf/2604.23896)
- Domain example of explaining limits in the UI: Verkada documents the exact geometric rule (bbox bottom-center crossing) — [Verkada](https://help.verkada.com/verkada-cameras/analytics/create-camera-event-alerts) [search-summary]

### Inferences
- Must-have for LabelDesk:
  - Show model metrics per class (G2: "how well"), not just mAP.
  - Show the confidence threshold and let users change it (Roboflow slider).
  - Make AI-suggested labels visually distinct and easy to accept or reject in bulk (G9).
  - Show a "model changed" notice when a new version is deployed (G18).
- Should-have:
  - Show which data the model was trained on and its known weak classes, taken from the confusion matrix ("limits" card).
  - For CCTV, show the trigger reason on each event (zone, rule, confidence, anchor point).
- Differentiator: cognitive forcing in review queues. For example, hide pre-labels for a random audit sample, or require explicit confirmation of low-confidence auto-labels. This turns the research finding (confidence display alone doesn't stop overreliance) into a feature. Track the rate at which AI suggestions are accepted unchanged as an overreliance signal (inferred).

### Gaps
- The verbatim text of all 18 HAX guidelines was not retrieved in this session (the MSR page renders them only as an image). The paraphrases above come from the CHI paper and should be checked.
- Bansal et al. (CHI 2021, complementary team performance) and Buçinca et al. (CSCW 2021, cognitive forcing functions) were surfaced only indirectly, with no direct URL verified. Find their primary sources before citing them.
- No HCI study specific to CV annotation or ML-training dashboards was found in this session.
