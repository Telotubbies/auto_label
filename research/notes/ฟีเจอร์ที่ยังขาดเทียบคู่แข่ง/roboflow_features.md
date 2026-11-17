# Roboflow feature inventory (2025-2026) for backlog diff

Method: ~14 fetches of docs.roboflow.com (sitemap, pages, changelog) plus searches. A page title in the docs sitemap proves a feature exists; detail is only given where a page was actually read. Items marked (title-only) were not opened. The fetch tool summarizes pages with a small model, so details are secondary; model names in the Auto Label list (e.g. "GPT-6", "Claude Opus 5.5") are as reported by the fetch summary and unverified.
Base: https://docs.roboflow.com  (sitemap: https://docs.roboflow.com/sitemap.md). Relative paths below are under this base.

## 1. Annotate

### Takeaway
Full annotation suite: box/polygon/brush/keypoint/video-segment/multimodal, four AI-labeling modes (Label Assist, Smart Select, Box Prompting, Auto Label), review, comments, history, labeling services.

### Cited Findings (checklist)
- [ ] Bounding boxes — https://docs.roboflow.com/annotate/annotation-tools
- [ ] Polygons — same
- [ ] Brush tool / pixel masks — same
- [ ] Keypoints with editable skeletons — /datasets/annotate/annotate/annotate-keypoints.md , /edit-keypoint-skeletons.md
- [ ] Video segment annotation (action start/end on timeline) — /datasets/annotate/annotate/annotate-video-segments.md
- [ ] Multimodal data annotation (title-only) — /datasets/annotate/annotate/annotate-multimodal-data.md
- [ ] Label Assist (foundation, own, or public model; one image at a time) — https://docs.roboflow.com/annotate/ai-labeling
- [ ] Smart Select (SAM in browser, one-click polygon; earlier "Smart Polygon", legacy version still documented) — same; https://docs.roboflow.com/annotate/use-roboflow-annotate/enhanced-smart-polygon-with-sam
- [ ] Box Prompting (draw example box, find similar instances in the image) — https://docs.roboflow.com/annotate/ai-labeling
- [ ] Auto Label: bulk-label whole dataset with SAM 3 (text prompt), trained model, saved Workflow, or VLM; background job, review after — https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling/auto-label
- [ ] Auto Label with Workflows (any model or custom logic, July 2026) — https://docs.roboflow.com/reference/changelog/changelog/july-2026.md
- [ ] Natural-language annotation (blog) — https://blog.roboflow.com/natural-language-image-annotation/
- [ ] AI labeling billed in credits — https://docs.roboflow.com/annotate/ai-labeling
- [ ] Similarity Search in annotator (title-only) — /datasets/annotate/annotate/use-roboflow-annotate/similarity-search-and-settings.md
- [ ] Annotation Groups (title-only) — /datasets/annotate/annotation-groups.md
- [ ] Annotation attributes (title-only) — /datasets/manage/manage-datasets/create-an-annotation-attribute.md
- [ ] Annotation History (title-only) — /datasets/annotate/annotate/use-roboflow-annotate/annotation-history.md
- [ ] Comment on an Image (title-only) — /datasets/annotate/annotate/use-roboflow-annotate/comment-on-an-image.md
- [ ] Keyboard Shortcuts page (contents not read) — /datasets/annotate/annotate/use-roboflow-annotate/keyboard-shortcuts.md
- [ ] Show/Hide annotations (title-only) — /datasets/annotate/annotate/use-roboflow-annotate/show-and-hide-annotations.md
- [ ] Manage Annotation Workflow: assign and jobs (title-only) — /datasets/annotate/annotate/manage-annotation-workflow.md
- [ ] Collaborate on Labeling (title-only) — /datasets/annotate/annotate/team-collaboration.md
- [ ] Review Mode: approve/reject each image, rejected go back to labeler (also listed in Core plan) — https://blog.roboflow.com/best-image-annotation-tools/ ; https://roboflow.com/pricing
- [ ] Annotation Insights and labeling analytics (title-only; analytics listed in Core) — /datasets/annotate/annotate/annotation-insights.md
- [ ] Roboflow Labeling Services, outsourced labeling (title-only; enterprise add-on per pricing) — /datasets/annotate/annotate/roboflow-labeling-services.md
- [ ] Roboflow Instant model auto-trains after first batch of annotations is approved — https://docs.roboflow.com/models/train/train-a-model.md

### Gaps
- Keyboard shortcuts list, comments behavior, batch jobs detail, outsourced-labeling pricing not opened.

## 2. Dataset management

### Takeaway
Rich management: search with filters, tags, batches, folders with permissions, merge, health check, versions with 10 preprocessing and 16 augmentation options, ~20 export formats.

### Cited Findings (checklist)
- [ ] Project types: detection, instance seg, semantic seg, keypoint, classification (single/multi), action recognition — /datasets/create-and-upload/create-a-project.md
- [ ] Upload images/videos/annotations; datasources and credentials (title-only) — /datasets/create-and-upload/adding-data.md
- [ ] Import from AWS S3 / GCS / Azure Blob (title-only) — /datasets/create-and-upload/adding-data/upload-data-from-aws-gcp-and-azure/
- [ ] Import from Universe — /datasets/create-and-upload/adding-data/roboflow-universe.md
- [ ] Image metadata (title-only) — /datasets/create-and-upload/adding-data/image-metadata.md
- [ ] Dataset search with filters class:, tag:, split:, filename: — https://docs.roboflow.com/datasets/exporting-data
- [ ] Semantic search exists in dataset search but is not supported in export (search page itself not read) — same
- [ ] Tags on images — /datasets/manage/manage-datasets/add-tags-to-images.md
- [ ] Dataset batches — /datasets/manage/manage-datasets/manage-batches.md
- [ ] Manage/set classes — /datasets/manage/manage-datasets/manage-classes.md
- [ ] Project folders and folder permissions (Core) — /datasets/manage/project-folders.md
- [ ] Merge projects — /datasets/manage/merge-datasets.md
- [ ] Make public, change owner, rename, delete; Trash and soft delete (May 2026) — sitemap; May 2026 changelog
- [ ] Asset Library (workspace-wide images); run Workflows on its images (June/July 2026) — https://docs.roboflow.com/changelog/explore-by-month/june-2026
- [ ] Dataset Health Check (title-only) — /datasets/versions/dataset-health-check.md
- [ ] Train/valid/test splits per version — exporting-data page
- [ ] Dataset versions: create, delete, export — /datasets/versions/dataset-versions/
- [ ] Preprocessing (10): Auto-Orient; Resize (Stretch, Fill center-crop, Fit within, Fit reflect edges, Fit black edges, Fit white edges); Grayscale; Auto-Adjust Contrast (Contrast Stretching, Histogram Equalization, CLAHE); Isolate Objects; Static Crop; Tile (Grid, Fixed Size, Fixed Aspect Ratio); Modify Classes; Filter Null; Filter by Tag (Require/Exclude/Allow) — https://docs.roboflow.com/datasets/image-preprocessing
- [ ] Augmentations (16): Flip, 90 Rotate, Crop, Rotation, Shear, Grayscale, Hue, Saturation, Brightness, Exposure, Blur, Noise, Camera Gain, Motion Blur, Cutout, Mosaic. Cutout/Mosaic are "enhanced" (premium). Bounding-box-level variants for 11 (not Grayscale, Hue, Saturation, Cutout, Mosaic) — https://docs.roboflow.com/datasets/image-augmentation
- [ ] Augmentation multiplier up to 5x per image on Core — https://roboflow.com/pricing
- [ ] Export formats by task — https://docs.roboflow.com/datasets/exporting-data
  - Detection: clip, coco, createml, darknet, multiclass, tensorflow, tfrecord, voc, yolokeras, yolov5pytorch, yolov7pytorch, mt-yolov6, retinanet, benchmarker
  - Instance seg: coco-segmentation, yolov4pytorch, yolov4scaled, yolov5-obb, plus most detection formats
  - Semantic seg: coco-segmentation, png-mask-semantic
  - Keypoint: coco, yolov5pytorch
  - Classification: folder, clip, multiclass
- [ ] MCP tools versions_export / versions_get — same

### Gaps
- Import-format list, health-check contents, tag/search UI details not read.

## 3. Train

### Takeaway
RF-DETR and YOLO families across six task types, NAS, Instant models, rich checkpoint options, multi-model per version.

### Cited Findings (checklist)
- [ ] RF-DETR detection (Nano, Small, Medium, Large, XL, 2XL) and semantic seg — https://docs.roboflow.com/models/train/train-a-model.md
- [ ] RF-DETR Seg (preview) instance seg; RF-DETR Two-Stage keypoint; RF-DETR Keypoint Preview (June 2026) — same; June 2026 changelog
- [ ] YOLO11, YOLO26 (AGPL), YOLO26 semantic segmentation — same
- [ ] YOLOLite (beta, March 2026) — https://docs.roboflow.com/reference/changelog/changelog/march-2026
- [ ] SAM3 fine-tune (Core, credits) — train-a-model
- [ ] Cosmos 3 Edge and V-JEPA 2.1 for action recognition — same
- [ ] Tasks: detection, instance seg, keypoint, semantic seg, classification, action recognition — same
- [ ] Neural Architecture Search (min 15 validation images; training and search credit caps; latency band; fast backbone June 2026) — https://docs.roboflow.com/models/train/neural-architecture-search.md
- [ ] Roboflow Instant model — /models/train/roboflow-instant.md
- [ ] Credit cap per run; stop/cancel job — train-a-model; /models/train/cancel-a-training-job.md
- [ ] Customize recipe: training preprocessing, online augmentations, checkpoint, hyperparameters, epochs — train-a-model
- [ ] Checkpoints: previous version, public COCO, Universe project (detection only), random init, ImageNet (classification/semseg) — train-a-model; /models/train/roboflow-universe-checkpoints.md
- [ ] Speed presets fast/accurate (SDK) — train-a-model
- [ ] Multiple models per version, side-by-side compare (July 2026) — July 2026 changelog
- [ ] Train via Roboflow Agent / MCP server — train-a-model; changelog
- [ ] Train from Azure Vision, Google Cloud — /models/train/pro-third-party-training-integrations.md , /train-from-google-cloud.md
- [ ] Upload custom weights, also via MCP (July 2026) — July 2026 changelog

### Gaps
- GPU type selection not documented in fetched content.

## 4. Evaluate and monitor

### Takeaway
Auto-run evaluation for paid users with confusion matrix, optimal-threshold metrics and vector analysis; production monitoring via Vision Events and Active Learning.

### Cited Findings (checklist)
- [ ] View Evaluation per version, auto-run for paid users including uploaded models — https://docs.roboflow.com/train/evaluate-trained-models
- [ ] Confusion matrix at optimal threshold (pixel counts for semseg) — same
- [ ] Production metrics explorer; optimal confidence balancing P/R/F1 becomes default inference threshold; threshold slider — same
- [ ] Vector analysis / explorer (details not retrieved) — same
- [ ] Model Monitoring, Vision Events (dashboards, detection feedback, natural-language query via MCP), Active Learning (June 2026) — /deployment/monitoring-and-analytics/

### Gaps
- Vector analysis detail and PR curves not retrieved.

## 5. Deploy

### Takeaway
Serverless, dedicated, batch, cloud streaming, self-hosted Inference (free), edge fleet management (enterprise), plus large Workflows block catalogue.

### Cited Findings (checklist)
- [ ] Serverless Cloud API, per-image credits (RF-DETR Nano 0.000125 cr/img; SAM 3 0.0005 cr/img) — https://docs.roboflow.com/deployment/overview ; https://roboflow.com/pricing
- [ ] Dedicated Deployments (private CPU/GPU, hourly, US only) — /deployment/roboflow-cloud/dedicated-deployments.md
- [ ] Batch Processing (async images/video) — /deployment/roboflow-cloud/batch-processing.md
- [ ] Cloud Streaming (managed live camera Workflows) — /deployment/roboflow-cloud/cloud-streaming.md
- [ ] Self-hosted Inference server (Docker/pip; CPU, CUDA, Jetson; free), bring-your-own-cloud — /deployment/self-hosted/self-hosted.md
- [ ] Enterprise deployment; Deployment Manager for edge fleets (remote monitoring, custom SSL, network config, Activity tab) — /deployment/self-hosted/enterprise.md; Apr/Jul 2026 changelog
- [ ] Production readiness checklist; choosing a deployment option — sitemap
- [ ] Inference Python package, InferencePipeline, benchmarks, offline weights, Inference SDK (WebRTC, workflows, model mgmt), Inference CLI (server, infer, workflows, cloud, benchmark) — /reference/inference/
- [ ] Workflows blocks (full catalogue at https://docs.roboflow.com/workflows/blocks):
  - Run a Model: detection, instance/semantic seg, keypoint, classification (single/multi), anomaly detection, SAM 3, SAM 3 Interactive, SAM 2, YOLO-World, Florence-2, CLIP, Perception Encoder, Depth Estimation, Gaze, OCR (EasyOCR, PP-OCR, GLM-OCR, Google Vision), Barcode, QR, Action Recognition, Visual Search Classifier, VLMs/LLMs (OpenAI, Claude, Gemini, Gemma, Qwen family, Llama 3.2 Vision, Moondream2, SmolVLM2, CogVLM, Mistral, Kimi, OpenRouter, OpenAI-compatible, Cosmos 3), Stability AI generate/inpaint/outpaint
  - Classical CV: auto rotate, contrast, blur, contours, grayscale, threshold, morphology, template matching, SIFT, dominant color, pixel color count, distance/size/mask-area measurement, mask edge snap, nearest-neighbor match
  - Transformations: static/relative/dynamic crop, bounding rect, camera calibration, detection offset/combine/merge/transform, GeoTag, QR generator, stitch images
  - Logic: Continue If, Delta/Overlap/Per-class confidence filters, Detections Consensus/Filter, Inner Workflow, Rate Limiter, Switch Case
  - Advanced: cache get/set, cosine similarity, dynamic zone, image slicer and detections stitch (SAHI-style), perspective correction, expression, JSON parser, string template, secrets store, VLM-as-detector/classifier, visual search, custom metadata, event log
  - Video: ByteTrack, BoT-SORT, OC-SORT, SORT, SAM2/SAM3 video trackers, Line Counter, Time in Zone, Path Deviation, Velocity, Motion Detection, Background Subtraction, PTZ tracking (ONVIF), Detections Stabilizer, Track Class Lock, Frame Delay, Buffer, Identify Changes/Outliers
  - Visualization: about 28 (bbox, mask, polygon, label, halo, heatmap, trace, blur, pixelate, keypoint, zone, model comparison, etc.)
  - Data storage / notifications: Dataset Upload, Vision Events, S3 sink, local file sink, webhook sink, CSV formatter, aggregator; Email, Slack, Twilio SMS/MMS
  - Platform: custom blocks, blocks governance, nested workflow, disable nodes, version restore, run on Asset Library images

## 6. Universe

### Cited Findings (checklist; all title-only from sitemap)
- [ ] Universe search, find dataset, find model — /datasets/universe/universe/universe-search.md , find-a-dataset-on-universe.md , find-a-model-on-universe.md
- [ ] Explore images, fork dataset, download dataset, project analytics, project description — /datasets/universe/universe/
- [ ] Star a Universe project to use as training checkpoint (verified) — train-a-model page

## 7. Integrations, SDK, CLI, API

### Cited Findings (checklist)
- [ ] REST Platform API with OpenAPI and async tasks — /reference/platform/rest-api.md
- [ ] Python SDK; Platform CLI — /reference/platform/python-sdk.md , /reference/platform/cli.md
- [ ] API keys: rotation, scoped keys, key management API — /reference/authentication/
- [ ] OAuth 2.1 / Sign in with Roboflow — /reference/authentication/authentication/oauth.md
- [ ] MCP Server (Cursor marketplace, Claude directory, NL Vision Events query) — June/July 2026 changelog
- [ ] Cloud-storage import; Azure/Google Cloud training — sitemap
- [ ] Changelog — https://docs.roboflow.com/reference/changelog/changelog

## 8. Team, enterprise, pricing

### Cited Findings (checklist)
- [ ] Workspaces, invite/change/remove members, roles; custom roles, folder permissions, billing folders — /platform/workspaces/team-members.md ; https://roboflow.com/pricing
- [ ] SSO (self-serve, Active Directory group sync), audit logs (Mar 2026) — changelog
- [ ] Free $0: 10 credits/mo, private projects, weight downloads, unlimited admin seats — https://roboflow.com/pricing
- [ ] Core $39/mo: 20 credits, 20 projects, 5x augmentation, Vision Events 14-day, review mode, labeling analytics, SSO, RBAC, workflow version restore; packs $2.86-3.56/credit; prepaid $4; on-demand $6 — same
- [ ] Enterprise custom: SLA, US/EU data sovereignty, custom rate limits, managed clusters, edge deployment, labeling services, onsite install — same
- [ ] Self-hosted inference free on all plans; some model commercial licenses are add-ons — same

## Recent 2026 changelog (recency)
- Mar: audit logs, S3 sink, Qwen3.5-VL, SORT/OC-SORT, YOLOLite
- Apr: Nested Workflow, custom SSL, MCP server, NAS, Vision Events
- May: AD group sync, Vision Events dashboards/feedback, disable nodes, OpenRouter, Qwen 3.5, soft delete
- Jun: Active Learning, Depth Anything serverless, NAS fast backbone, RF-DETR keypoint preview, SAM 3 point prompt and video tracking, Track Class Lock, YOLO26 semseg
- Jul: Auto Label with Workflows, multiple models per version, Visual Search Classifier, self-serve SSO, Asset Library
Sources: https://docs.roboflow.com/changelog/explore-by-month/june-2026 , https://docs.roboflow.com/reference/changelog/changelog/july-2026.md
