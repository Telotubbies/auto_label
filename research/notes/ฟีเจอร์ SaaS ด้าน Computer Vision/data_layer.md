# Data Layer of CV Dataset/Labeling SaaS: Ingest, Health/EDA, Preprocessing, Augmentation, Versioning

Research date: 2026-10-31. Sources are mostly vendor docs read live in October 2026. Older items are flagged. Notes are organised by the four key questions.

## Q1. What ingest features are standard across platforms?

### Takeaway
Table stakes are: import of COCO, YOLO and Pascal VOC (often plus the vendor's own JSON); cloud bucket connection to S3, GCS and Azure (read-only IAM role or signed URLs); an HTTP API plus Python SDK/CLI; and exact-duplicate skipping by content hash. Roboflow goes further with video frame sampling, "Bucket Mirror" auto-sync, and per-upload batch/tag/metadata/split fields. Many competitors (SuperAnnotate, LandingLens, Encord cloud sidecars) accept only their native format or one format directly and require conversion for the rest.

### Cited Findings
**Roboflow**
- Web app accepts "40+" annotation formats; available formats depend on project type. Annotations must be uploaded together with their images, not added to images already in the dataset — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data)
- Image types: JPG, PNG, WEBP, BMP; video: MOV, MP4. Max image 20 MB and 16,400 x 10,900 px — [Roboflow Upload Data help](https://help.roboflow.com/cn_CN/get-started/dataset-upload-roboflow-data-types); [Roboflow Upload API](https://docs.roboflow.com/api-reference/images/upload-api)
- Video frame extraction in the web app samples from 60 fps down to 1 frame per 60 s, with trimming and manual frame picking. Action-recognition projects keep videos whole. The HTTP API takes videos up to 3 GB (prepare, PUT to signed URL, poll status). The CLI handles images only, so videos must be split first — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data)
- Cloud: for S3/GCS/Azure the docs recommend "Datasources" with "Bucket Mirror", which syncs images and metadata automatically. Signed-URL uploads cover one-off imports — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data)
- CLI `roboflow import` / `roboflow image upload` (zip support). Python SDK `Workspace.upload_dataset()`. Zip archives up to 8 GB and 100,000 files — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data)
- Dedupe: images already in a project are skipped. A removed image that is re-uploaded comes back with its prior annotations and status. Identical content is counted once toward usage, and the API returns a duplicate flag — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data); [Roboflow Upload API](https://docs.roboflow.com/api-reference/images/upload-api); [Roboflow image deduplication page (marketing)](https://roboflow.com/ai/image-deduplication)
- Upload API has optional `batch`, `tag`, `metadata`, `split` fields. Every upload lands in a batch shown on the Annotate page — [Roboflow docs: Adding data](https://docs.roboflow.com/datasets/adding-data)
- EXIF: handled at the preprocessing stage. "Auto-Orient" applies and strips EXIF orientation so stored pixels match what is displayed — [Roboflow Preprocessing docs](https://docs.roboflow.com/datasets/dataset-versions/image-preprocessing)

**CVAT**
- Supported dataset formats include COCO 1.0, COCO Keypoints, CVAT for images/video 1.1, Datumaro, PASCAL VOC 1.1, YOLO 1.1, Ultralytics YOLO (detection, segmentation, pose, OBB) and classification, KITTI, LabelMe, MOT/MOTS, Open Images V6, Cityscapes, CamVid, ImageNet, Segmentation Mask, ICDAR, WIDER Face, and more. The format page does not separate import from export per format — [CVAT dataset formats](https://docs.cvat.ai/docs/dataset_management/formats/)
- Cloud storage: Amazon S3, Azure Blob, Google Cloud Storage, and Backblaze B2 (via the S3-compatible option). Credentials can be key+secret, account name+token, anonymous, or a key file. Bucket import uses a `manifest.jsonl` file — [CVAT Attach cloud storage](https://docs.cvat.ai/docs/workspace/attach-cloud-storage/); [CVAT Cloud storages](https://docs.cvat.ai/docs/workspace/cloud-storages/)

**Label Studio (HumanSignal)**
- Source/target storage connectors for S3 (and S3-compatible such as MinIO), GCS and Azure, with a "Sync Storage" action to pull in new objects — [HumanSignal support: Import/Export](https://support.humansignal.com/hc/en-us/categories/39646675435533-Import-Export); [Alauda mirror of LS quickstart (secondary)](https://docs.alauda.io/ai/2.8/develop/components/label_studio/quickstart.html)
- Target storage writes native JSON only. COCO, VOC and YOLO come from converting exported JSON with the SDK or label-studio-converter. The staff statement on this is from an older version (1.12.1), so it is flagged as possibly outdated — [Label Studio community thread](https://community.labelstud.io/t/export-to-target-storage-in-voc-format/237)

**V7 Darwin**
- CLI import formats: Darwin JSON, Pascal VOC, COCO, CSV tags, CSV video tags, Labelbox, SuperAnnotate, Dataloop, NIfTI. Importing onto items that already have annotations overwrites them — [V7 docs: Import annotations with CLI](https://docs.v7labs.com/docs/import); [V7 docs: Import annotations made outside of V7](https://docs.v7labs.com/docs/import-annotations-made-outside-of-v7)
- AWS/GCP/Azure integration is claimed only by a third-party review. No official setup doc was found — [autolabelling.com review (secondary)](https://autolabelling.com/v7-labs/)

**Encord**
- Labels can be ingested from the cloud as sidecar files next to the data, in two formats only: Encord JSON and YOLO .txt. Sidecar limit is 300 MB — [Encord docs: Import Labels (Curation)](https://docs.encord.com/platform-documentation/Curate/import-labels-cloud)
- Integrates with AWS, Google Cloud, Azure, and Open Telekom Cloud OSS. This comes from Encord's own blog, i.e. marketing — [Encord blog](https://encord.com/blog/supervisely-alternatives/)

**Labelbox**
- Recommends "IAM Delegated Access": a read-only role in the customer's AWS/GCP/Azure account that Labelbox assumes. The alternative is signed URLs, which expire (e.g. 7 days) — [Labelbox docs: Connect to cloud storage](https://docs.labelbox.com/docs/connect-to-cloud-storage); [Labelbox Azure delegated access guide](https://labelbox.com/guides/how-to-set-up-a-delegated-access-integration-between-azure-and-labelbox/)

**SuperAnnotate**
- Supports its own JSON plus COCO, YOLO, VOC, but non-native formats must be converted to SuperAnnotate format first. The SDK converts from VOC, Supervisely, Labelbox, Dataloop, VGG, VoTT, SageMaker, Google Cloud, YOLO and to/from COCO. Annotation upload from local or S3 folder. Uploaded annotations override existing ones — [SuperAnnotate docs: Import annotations](https://doc.superannotate.com/docs/import-annotations); [superannotate on PyPI](https://pypi.org/project/superannotate)

**Supervisely**
- Cloud import from S3, GCS, Azure Blob and S3-compatible stores. The import wizard auto-detects the format (Supervisely, COCO, YOLO, Pascal VOC, Cityscapes, etc.) — [Supervisely docs: Import from Cloud](https://docs.supervisely.com/import-and-export/import/import-from-cloud); [Supervisely: How to import](https://docs.supervisely.com/getting-started/how-to-import)

**Landing AI (LandingLens)**
- Image types: PNG (recommended), BMP, JPG/JPEG, MPO. Labeled object detection data is imported as Pascal VOC only, with helper scripts to convert COCO/YOLO to VOC. Up to 10,000 images per OD/segmentation/classification project. Duplicates are blocked by MD5 checksum — [LandingLens docs: Upload images (Dec 2024)](https://support.landing.ai/docs/upload-images); [LandingLens: Upload pre-labeled images to OD](https://landinglens.docs.landing.ai/videos/upload-pre-labeled-images-to-object-detection-projects)
- Snowflake-stage loading exists for LandingLens on Snowflake. VOC upload is not supported on that path — [LandingLens docs: Upload images](https://support.landing.ai/docs/upload-images)

### Inferences
- **Must-have:** COCO/YOLO/VOC import with auto-detection (Supervisely-style), zip upload, API+Python SDK, exact-dup skip by content hash (MD5/SHA, as Roboflow and LandingLens do), batch/tag/split on upload, EXIF auto-orient.
- **Should-have:** S3/GCS/Azure connectors (signed URL first, then IAM-role delegated access like Labelbox), video upload with fps-based frame sampling, CVAT XML and Label Studio JSON import (lets users migrate from the two biggest open-source tools), Ultralytics YOLO seg/OBB variants.
- **Differentiator:** continuous bucket mirroring/sync (Roboflow Bucket Mirror, Label Studio Sync), near-duplicate detection at ingest (Roboflow only does this through Workflows), lossless re-upload that keeps annotations.

### Gaps
- No official docs found for V7, Encord or SuperAnnotate on GCS/Azure annotation import. Label Studio's official import-format page was not retrieved directly (only secondary mirrors and the support portal).
- The full list behind Roboflow's "40+ formats" was not enumerated (see roboflow.com/formats).
- EXIF metadata capture (GPS, timestamp, camera) as searchable metadata: no platform doc found that confirms it.

## Q2. What do dataset health check / data curation tools do?

### Takeaway
Roboflow Health Check is descriptive EDA: counts, class balance per split, image size/aspect, null/missing annotations, an annotation location heatmap, and an objects-per-image histogram. Curation tools (FiftyOne Brain, Encord Active/Index, Lightly, Cleanlab) add embedding-based analysis: UMAP plots, exact and near duplicates, train/test leakage, uniqueness/representativeness, image-quality heuristics (blur, brightness), and model-assisted label-error scores.

### Cited Findings
**Roboflow Health Check**
- Reports image and annotation totals, average image size, median aspect ratio, image-dimension insights, missing and null annotation counts, class balance across train/valid/test, an annotation heatmap (where boxes sit in the frame), and an object-count histogram per image where clicking a bar filters images. The HTTP API returns counts, class balance and histogram but not heatmaps or dimensions. A cached report can be stale, so the API takes `regenerate=true` — [Roboflow docs: Dataset Health Check](https://docs.roboflow.com/datasets/dataset-health-check)

**FiftyOne Brain (Voxel51)**
- `compute_visualization()` projects embeddings with UMAP (default), t-SNE, PCA or manual, shown in an Embeddings panel linked to the sample grid — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)
- Similarity index for image/object similarity search — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)
- Leaky splits: finds duplicates/near-duplicates across splits that inflate evaluation scores — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)
- Near duplicates and exact duplicates (flags duplicates whether or not filenames match) — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)
- Uniqueness: label-free per-image score, useful for choosing what to label. Representativeness: typical vs. outlier images — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)
- Mistakenness: label-error score from model predictions (works best with logits). For detection it covers missed objects and localization errors. Hardness: per-sample difficulty from predictions — [FiftyOne Brain docs](https://docs.voxel51.com/brain/index.html)

**Encord Active / Index**
- Label-free data quality metrics on images/frames: brightness, colour, aspect ratio, blurriness/sharpness, and more. Custom quality metrics can be written — [Encord docs: Active quality metrics](https://docs.encord.com/docs/active-quality-metrics)
- Hosted shortcut thresholds: sharpness 0.0–0.005 flagged "blurry", brightness 0.0–0.1 "too dark", 0.7–1.0 "too bright". These may differ from open-source defaults — [Encord docs: issue shortcuts](https://docs.encord.com/platform-documentation/Validation/active-basics/active-issue-shortcuts-prediction-types)
- Label quality metrics run on boxes, polygons and polylines (e.g. per-object brightness). The "Low Annotation Quality" shortcut compares a classification with its 60 most similar images. "Label Duplicates" ranks labels likely to be the same object. "Polygon Shape Anomaly" flags outlier polygon shapes — [Encord docs: Label quality metrics](https://docs.encord.com/docs/active-label-quality-metrics); [Encord docs: issue shortcuts](https://docs.encord.com/platform-documentation/Validation/active-basics/active-issue-shortcuts-prediction-types); [Encord docs: embedding plots (validation)](https://docs.encord.com/platform-documentation/Validation/embeddings-plots-validation)
- Index embedding plots: 2D UMAP, box-select subsets, used to find clusters, outliers and coverage gaps. Embeddings also unlock diversity/uniqueness metrics. The docs advise dense clusters → duplicate detection before annotating — [Encord docs: Embedding plots](https://docs.encord.com/platform-documentation/Curate/embedding-plots); [Encord docs: Annotation and curation](https://docs.encord.com/solutions-documentation/applied-ai/annotation-and-curation)

**Lightly (LightlyOne / LightlyStudio)**
- Embedding-based sampling: diversity (cover the embedding space), typicality, active learning (least-confident model predictions), and metadata balancing. Strategies can be combined — [LightlyStudio sampling](https://docs.lightly.ai/studio/concepts_and_tools/sampling); [Lightly selection strategies](https://docs.lightly.ai/docs/selection-strategies)
- Diversity alone skews class distribution (the cats-vs-dogs example), so Lightly recommends typicality together with diversity. Typicality was introduced in LightlyOne 3.0 — [Lightly selection strategies](https://docs.lightly.ai/docs/selection-strategies); [LightlyOne 3.0 blog](https://www.lightly.ai/blog/lightlyone-3-0)

**Cleanlab**
- `cleanlab.object_detection.filter.find_label_issues(labels, predictions, ...)` flags likely mislabeled images. `rank.get_label_quality_scores` gives per-image scores. Predictions should be out-of-sample (cross-validation). Input format matches MMDetection/Detectron2 — [Cleanlab docs: object_detection.filter](https://docs.cleanlab.ai/master/cleanlab/object_detection/filter.html); [Cleanlab OD tutorial](https://docs.cleanlab.ai/master/tutorials/object_detection.html)

### Inferences
- **Must-have** (cheap, no model needed): counts, class balance per split, image size/aspect histogram, null/missing annotations, objects-per-image histogram, box-size distribution, annotation heatmap, exact duplicates via hash. These match Roboflow, the closest competitor.
- **Should-have:** CLIP/DINO embeddings plus UMAP view, near-duplicate clustering, cross-split leakage check, blur/brightness heuristics with Encord-style thresholds.
- **Differentiator:** model-assisted label-error detection (ObjectLab/Cleanlab-style or FiftyOne mistakenness) using our own SAM3/YOLO predictions, uniqueness/typicality-based "what to label next" sampling, custom metrics.

### Gaps
- Exact near-duplicate algorithms (thresholds, embedding model) for FiftyOne and Encord were not in the pages read.
- Roboflow's in-app near-duplicate/embedding features beyond Health Check (e.g. CLIP search) were not verified from docs.

## Q3. What does research say about label noise, data quality and dedup/leakage in detection?

### Takeaway
Label errors in benchmark datasets are common and big enough to change model rankings. For detection the main error is *missing* boxes, especially small, occluded or crowded objects. Near-duplicate leakage between train and test is also documented. Practical tools are confident learning / ObjectLab, loss-inspection methods, and embedding-based semantic dedup.

### Cited Findings
- **Northcutt, Athalye, Mueller — "Pervasive Label Errors in Test Sets Destabilize Machine Learning Benchmarks", NeurIPS 2021 Datasets & Benchmarks Track (2021).** Looks at 10 test sets and finds an average of 3.3% errors, with 2,916 errors (6%) in the ImageNet validation set. Crowdworkers confirmed 54% of algorithm-flagged candidates. On corrected CIFAR-10, VGG-11 beats VGG-19 once originally mislabeled examples rise by just 5%. Older (2021) but foundational — [arXiv:2103.14749](https://arxiv.org/abs/2103.14749); [NeurIPS D&B proceedings PDF](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/file/f2217062e9a397a1dca429e7d70bc6ca-Paper-round1.pdf). One secondary article reports about 3.4%, which conflicts with the abstract's 3.3% — [AI Business](https://aibusiness.com/document.asp?doc_id=768400)
- **Northcutt, Jiang, Chuang — "Confident Learning: Estimating Uncertainty in Dataset Labels", JAIR vol. 70, pp. 1373–1411 (2021).** Prunes noisy data and counts with probabilistic thresholds to estimate the joint noise distribution. Won the 2024 IJCAI-JAIR best paper prize — [MIT DSpace record](https://dspace.mit.edu/entities/publication/39b0f8e0-b673-42c6-99f6-0af829bef7f5); [JAIR news](https://jair.org/index.php/jair/News)
- **Tkachenko et al. — "ObjectLab: Automated Diagnosis of Mislabeled Images in Object Detection Data" (2023)** is the method behind cleanlab's object-detection module. The cleanlab README cites it as "ICML '23". It may have been an ICML workshop paper, so the exact venue needs checking — [Cleanlab docs](https://docs.cleanlab.ai/stable); [Cleanlab OD tutorial](https://docs.cleanlab.ai/master/tutorials/object_detection.html)
- **Schubert, Riedlinger, Kahl, Kröll, Schoenen, Šegvić, Rottmann — "Identifying Label Errors in Object Detection Datasets by Loss Inspection", WACV 2024 (arXiv 2023).** Adds a benchmark with simulated label errors and a loss-based detector. Argues COCO, VOC and KITTI contain too many real errors to act as clean benchmarks — [arXiv:2303.06999](https://arxiv.org/abs/2303.06999)
- **Penquitt et al. — "Object Detection Benchmarks are Incomplete: The Role of Label Errors and Annotation Uncertainty", arXiv 2609.21822 (Sept 2026, preprint).** Re-annotates COCO, Pascal VOC, Cityscapes and KITTI. Missing annotations dominate, and re-annotation adds up to about 40% more objects on COCO and about 60% on KITTI, mostly small, occluded or dense instances. Adds benchmarks built on real label errors — [arXiv:2609.21822](https://arxiv.org/abs/2609.21822)
- **Singh et al. — "Benchmarking Object Detectors with COCO: A New Path Forward" (arXiv 2403.18819, 2024).** Finds imprecise mask boundaries, non-exhaustive annotations and mislabeled masks in COCO-2017, and releases the corrected COCO-ReM — [arXiv:2403.18819](https://arxiv.org/abs/2403.18819)
- **"Pseudo-Labeling Driven Refinement of Benchmark Object Detection Datasets via Analysis of Learning Patterns" (arXiv 2506.00997, 2025).** Releases MJ-COCO, a re-annotated COCO, and reports gains for models trained on it — [arXiv:2506.00997](https://arxiv.org/pdf/2506.00997)
- **"From Label Error Detection to Correction: A Modular Framework and Benchmark for Object Detection Datasets" (arXiv 2508.06556, 2025).** Covers the detect-then-correct pipeline. Only the reference list was retrieved — [arXiv:2508.06556](https://arxiv.org/pdf/2508.06556)
- **Barz & Denzler — "Do We Train on Test Data? Purging CIFAR of Near-Duplicates", Journal of Imaging 6(6):41 (2020).** 3.3% of CIFAR-10 and 10% of CIFAR-100 test images have near-duplicates in training. They release ciFAIR with replacement images. Older (2020) — [arXiv:1902.00423](https://arxiv.org/abs/1902.00423); [MDPI J. Imaging](https://www.mdpi.com/2313-433X/6/6/41)
- **Abbas, Tirumala, Simig, Ganguli, Morcos — "SemDeDup: Data-efficient learning at web-scale through semantic deduplication" (arXiv 2303.09540, 2023).** Uses pretrained-model embeddings to remove "semantic duplicates". Reports up to 50% data removal with minimal performance loss at web scale. A talk page lists it under ICLR 2023, likely a workshop, so the venue is unconfirmed — [SlidesLive talk](https://slideslive.com/39000469/semdedup-dataefficient-learning-at-webscale-through-semantic-deduplication); [NVIDIA NeMo SemDeDup docs](https://docs.nvidia.com/nemo-framework/user-guide/25.04/datacuration/semdedup.html)
- **Zha et al. — "Data-centric Artificial Intelligence: A Survey" (arXiv 2303.10158, 2023; ACM Computing Surveys, DOI 10.1145/3711118).** Frames the field as training data development, inference data development, and data maintenance — [arXiv:2303.10158](https://arxiv.org/abs/2303.10158v3); [DOI listing](https://www.citedrive.com/en/discovery/data-centric-artificial-intelligence-a-survey). Companion paper: Zha et al., "Data-centric AI: Perspectives and Challenges" (arXiv 2301.04819) — [arXiv:2301.04819](https://arxiv.org/abs/2301.04819v2)

### Inferences
- For detection the highest-value health check is **"possible missing box"**: a confident model prediction with no matching ground truth. The 2024 and 2026 COCO re-annotation papers say missing labels dominate. This fits LabelDesk's SAM3 auto-label pipeline (prediction vs. GT disagreement).
- Out-of-sample predictions (k-fold) are needed for honest label-error scores (Cleanlab guidance), so this is a paid/GPU-tier feature rather than free EDA.
- Cross-split near-duplicate checks should run when a version is generated, because leakage measurably inflates test metrics (ciFAIR).

### Gaps
- ObjectLab's exact venue (main ICML vs. workshop) and SemDeDup's venue were not confirmed from primary pages.
- No detection-specific dedup/leakage paper (as opposed to classification/CIFAR) was found within the search budget.

## Q4. Preprocessing, augmentation (offline vs online), tiling/SAHI, and dataset versioning

### Takeaway
Roboflow is the reference design. A "version" is a frozen snapshot built from split + preprocessing (applied to all splits) + offline augmentation (train split only, multiplied by an output multiplier capped per plan). Training frameworks (Ultralytics) instead augment online at train time. Tiling for small objects is grounded in SAHI. Content-addressed hashing (DVC-style) is the standard way to make snapshots cheap and immutable.

### Cited Findings
**Preprocessing (Roboflow)**
- Auto-Orient (EXIF). Resize with six modes: Stretch to, Fill (center crop), Fit within, Fit with reflect/black/white edges; annotations follow except in Fill. Grayscale. Auto-Adjust Contrast (contrast stretching 2–98 percentile, histogram equalization, CLAHE). Isolate Objects (box crops → classification dataset). Static Crop. Tile (Grid / Fixed Size / Fixed Aspect Ratio with overlap and padding; at least 224 px per side; runs before resize). Modify Classes (omit/rename in the version only). Filter Null. Filter by Tag (require/exclude/allow) — [Roboflow Preprocessing docs](https://docs.roboflow.com/datasets/dataset-versions/image-preprocessing)
- Preprocessing applies to train, valid and test. Augmentation applies to train only — [Roboflow Preprocessing docs](https://docs.roboflow.com/datasets/dataset-versions/image-preprocessing)

**Augmentation**
- Roboflow image-level: flip, 90° rotate, crop, rotation, shear, grayscale, hue, saturation, brightness, exposure, blur, noise, camera gain, motion blur. "Enhanced": cutout, mosaic. Bounding-box-level variants exist for flip, rotate, crop, shear, brightness, exposure, blur, noise, camera gain, motion blur. Enhanced and bbox-level augmentations are premium. The output multiplier is capped by plan — [Roboflow Augmentation docs](https://docs.roboflow.com/datasets/dataset-versions/image-augmentation)
- Roboflow augments **offline** at version generation and justifies this by reproducibility, shorter training and lower GPU cost — [Roboflow Augmentation docs](https://docs.roboflow.com/datasets/dataset-versions/image-augmentation)
- Ultralytics YOLO augments **online** through train hyperparameters: e.g. `mosaic: 1.0`, `mixup: 0.0`, `hsv_h 0.015 / hsv_s 0.7 / hsv_v 0.4`, `close_mosaic: 10` (turn off mosaic for the last epochs). Defaults vary by version. These values come from mirrored config files, not the official page — [Ultralytics default.yaml mirror](https://huggingface.co/spaces/Ean7/YOLOv10/blob/main/ultralytics/cfg/default.yaml); [Ultralytics hyperparameter tuning guide](https://docs.ultralytics.com/guides/hyperparameter-tuning)
- The YOLO26 training recipe scales mixup/copy-paste with model size and suggests lowering mosaic/mixup for datasets under 1,000 images — [Ultralytics YOLO26 training recipe (Vietnamese page)](https://docs.ultralytics.com/vi/guides/yolo26-training-recipe)

**Tiling / SAHI**
- **Akyon, Altinuc, Temizel — "Slicing Aided Hyper Inference and Fine-tuning for Small Object Detection", arXiv 2202.06934 (2022; widely cited as IEEE ICIP 2022, venue not confirmed in pages read).** Overlapping slices, per-slice inference, merged with NMS. On VisDrone/xView it adds +6.8 / +5.1 / +5.3 AP (FCOS / VFNet / TOOD) for inference only, and +12.7 / +13.4 / +14.5 AP with slice-aided fine-tuning. Integrated with Detectron2, MMDetection and YOLOv5 (obss/sahi) — [arXiv:2202.06934](https://arxiv.org/abs/2202.06934v1)
- ASAHI (arXiv 2604.19233, 2026) says SAHI's fixed slice size wastes compute in a resolution-dependent way and proposes adaptive slicing — [arXiv:2604.19233](https://arxiv.org/pdf/2604.19233)

**Versioning**
- A Roboflow version is a frozen snapshot: later project edits do not change it. You generate it after choosing split, preprocessing and augmentation. The SDK's `Project.generate_version()` returns a version number — [Roboflow: Create a dataset version](https://docs.roboflow.com/datasets/create-a-dataset-version)
- Split rebalancing (70/20/10 suggested) with modes "move as few as possible", "random shuffle", or shuffle per batch/job. Can be limited to selected classes. REST `splits/rebalance` takes relative weights. Large rebalances run as background tasks — [Roboflow: Create a dataset version](https://docs.roboflow.com/datasets/create-a-dataset-version); [Roboflow JP docs](https://docs.roboflow.com/roboflow-jp/datasets/dataset-versions/create-a-dataset-version)
- DVC model: content-addressable cache keyed by an MD5 of file content (deduplicates identical files), stored as `cache/files/md5/ab/cdef...`. Directories get a `.dir` JSON manifest listing each file's hash and relative path. Small `.dvc` pointer files hold the hashes in git — [DVC docs: internal files](https://doc.dvc.org/user-guide/project-structure/internal-files)
- Export formats: CVAT exports the long format list in Q1 (COCO, VOC, YOLO, Ultralytics YOLO, Datumaro, etc.) — [CVAT dataset formats](https://docs.cvat.ai/docs/dataset_management/formats/)

### Inferences
- **Must-have:** immutable versions (split + preprocess + offline augment), auto-orient, resize (stretch/fit-with-pad at minimum), train-only augmentation with a multiplier, export to YOLO/COCO/VOC, deterministic seed.
- **Should-have:** tiling with overlap (Roboflow-style grid/fixed-size), class remap/omit per version, filter null/tag, split rebalance with minimal moves, a per-version health report snapshot.
- **Differentiator:** store each version as a manifest of content hashes (DVC-style `.dir`) so versions cost almost nothing and are diffable (image added/removed, label changed). Record augmentation recipes as data and export them as Ultralytics/Albumentations online-aug config rather than baking images in (saves storage, which matters on a free-tier Oracle VM). SAHI-sliced inference for auto-labelling small objects (IC defects). Lineage: version → training run → model.

### Gaps
- Official Ultralytics augmentation doc page and Albumentations docs were not fetched. Defaults are from mirrored configs.
- How Encord, Labelbox, V7 and Supervisely implement dataset versioning/snapshots was not researched within the budget.
- Roboflow's per-plan augmentation multiplier caps are only on its pricing page (not retrieved).
