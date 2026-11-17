# Multi-model training pipelines and model evaluation in CV SaaS platforms

Research date: 2026-10-31. Sources were fetched this session unless marked "(not re-fetched this session)". In those cases the URL is canonical and the fact is well established, but the report writer should treat it as lower confidence.

---

## Q1. Training features offered by Roboflow, Ultralytics, LandingLens, NVIDIA TAO, Edge Impulse, V7, Encord, SuperAnnotate, Supervisely, Azure Custom Vision and Vertex AI

### Takeaway
The baseline in 2025-2026 is a hosted "pick architecture + size → pick checkpoint → (optional) tweak hyperparameters → train on cloud GPU with a credit cap → live charts → auto-evaluation". Roboflow and Ultralytics Platform set the bar. Ultralytics is ahead on transparency: per-hour GPU pricing, a 50+ parameter YAML editor, and bring-your-own-GPU with metrics streaming. Roboflow is ahead on checkpoint choice and NAS. Other tools stand out with AutoML/HPO (TAO), with a pluggable "training app" SDK (Supervisely), or with a novice/expert split (LandingLens Fast Train vs Custom Training). The hyperscaler AutoML products are being retired.

### Cited Findings

**Roboflow Train**
- Object detection architectures include RF-DETR ("best accuracy"). Other tasks: RF-DETR Seg (Preview) for instance segmentation, an RF-DETR "Two-Stage" for keypoints (detect objects, then predict keypoints, with a size per stage), and RF-DETR (Nano–2XL) for semantic segmentation. YOLO architectures such as YOLO11 and YOLO26 are also offered, and SAM3 is available with credit-based billing — [Roboflow docs: Train a model](https://docs.roboflow.com/models/train/train-a-model.md)
- RF-DETR sizes are Nano, Small, Medium, Large, XL and 2XL. Available sizes vary by architecture — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- Checkpoint choices (transfer learning):
  - Previous checkpoint (continue from an earlier version of your model; "use it only when that model already performs well")
  - Public COCO checkpoint (default)
  - Universe project checkpoint (object detection only; you star the project first)
  - Random initialization
  - Classification and semantic segmentation use one ImageNet checkpoint

  — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- Neural Architecture Search (NAS) trains and evaluates several configurations and recommends one. It needs at least 15 validation images, exposes a "Latency Band", and has separate training and search credit caps — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- A customizable "training recipe" covers Training Preprocessing, Online Augmentations and Hyperparameters. For saved dataset versions the preprocessing and augmentation rows are locked, because they were applied at version generation. The SDK `epochs` default depends on model type — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- Billing is by length of the training job. An optional per-run "Credit Cap" requires usage-based billing, and each model has a minimum cap. A capped run stops and keeps its weights. A run stopped with credit left can be continued within the remaining cap. Manual early stop also keeps the weights — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- Training can be started from the web app, HTTP API, Python SDK (`Version.train()`), CLI (`roboflow train start`), MCP Server and "Roboflow Agent" — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)
- Anecdote on cost risk: a user reported an RF-DETR run on about 3,000 images that took more than 10.5 hours and over 20 credits without progressing past epoch 12 — [Roboflow forum](https://discuss.roboflow.com/t/rf-detr-training-glitch-10-5-hours-20-credits-and-no-progress-past-epoch-12/9320)
- Roboflow says it is an authorized licensor of Ultralytics models, and that custom-trained versions of these models remain AGPL-3.0 — [Roboflow: Ultralytics](https://roboflow.com/ultralytics)
- Not documented on the training page: custom/self-hosted GPU training, live metric charts, and configurable early stopping (the page only links to results) — [Roboflow docs](https://docs.roboflow.com/models/train/train-a-model.md)

**Ultralytics Platform (successor of Ultralytics HUB)**
- Cloud training supports YOLO26 (recommended), YOLO11, YOLOv8 and YOLOv5 official models, plus fine-tuning from your own completed models. RT-DETR and YOLO-World are **not** listed for cloud training — [Ultralytics Platform: Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- About 30 cloud GPU types are offered, from RTX 2000 Ada at $0.24/h to B300 at $7.39/h. The recommended default is RTX PRO 6000 (96 GB, $2.09/h). Signup credit is $5 for personal and $25 for company emails. Billing is metered from the balance while the job runs, and a cancelled job is charged for GPU time used. B200/B300 GPUs need a Pro or Enterprise plan, and on-premise training needs Enterprise — [Ultralytics Platform: Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
  - Conflict: a Platform FAQ was reported to list B200 at $10.38/h, H200 at $5.38/h and RTX PRO 6000 at $3.68/h. These differ from the cloud-training page, so prices are volatile — [Ultralytics pricing](https://www.ultralytics.com/pricing); [Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- An "Advanced Settings" YAML editor exposes 50+ task-aware parameters (optimizer, learning rate, loss weights, augmentation), with import/export as YAML or JSON — [Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- Live Metrics, Loss and Learning Rate charts stream during training. Console and System subtabs show logs and host resource use. The best checkpoint is uploaded periodically during the run — [Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- Early stopping uses `patience` (default 100; 0 disables it). Resume uses `yolo train resume`, which continues the same Platform model — [Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- "Remote training" runs on your own hardware and streams metrics to the Platform. It needs Python 3.11+ and ultralytics 8.4.120+. Note that a search snippet elsewhere says ">=8.4.0" — [Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- Legacy HUB allowed only one cloud training job at a time and required the Pro plan. The new Platform page implies several concurrent runs, and the pricing page mentions 10 concurrent cloud jobs on one plan — [legacy HUB Cloud Training](https://docs.ultralytics.com/hub/cloud-training/); [Ultralytics pricing](https://www.ultralytics.com/pricing)

**Landing AI LandingLens**
- There are two modes. Fast Train is the default: LandingLens tunes settings automatically, and it is recommended for non-ML users. Custom Training lets you set resize/rescale-with-padding, crop, augmentations, epochs and model size, and it is "for users with ML background" — [LandingLens Custom Training](https://landinglens.docs.landing.ai/custom-training.md)
- Model menu:
  - Object detection: RtmDet-[9M] (fastest), RepPoints-[20M], RepPoints-[37M], ODEmbedded-[23M]
  - Segmentation: FastViT-[14M], SegFormer-[14M]
  - Classification: ConvNeXt-[16M], ConvNeXt-[29M], ConvNextEmbedded-[16M]
  - Anomaly: RD4AD-[160M]

  — [LandingLens Custom Training](https://landinglens.docs.landing.ai/custom-training.md)
- Augmentations each have a probability and a range: Random Brightness, Blur, Motion Blur, Gaussian Blur, HSV, Random Contrast, H-Flip, V-Flip, RandAugment and Random Rotate — [LandingLens Custom Training](https://landinglens.docs.landing.ai/custom-training.md)
- Custom Training settings can change the per-image inference credit cost, which may be more or less than 1 credit — [LandingLens Custom Training](https://landinglens.docs.landing.ai/custom-training.md)

**NVIDIA TAO Toolkit (6.x; 7.0 docs exist)**
- Object detection: DINO, Deformable DETR, Grounding DINO, RT-DETR, EfficientDet and others. Instance segmentation: Mask2Former, MAL, Mask Grounding DINO. Semantic: SegFormer, Mask2Former. Panoptic: Mask2Former. Also classification, OCD/OCR, pose, re-ID, Visual ChangeNet, CenterPose and action recognition — [TAO 6.25.10 overview](https://docs.nvidia.com/tao/tao-toolkit/6.25.10/text/overview.html)
- More than 100 pretrained models on NGC, plus foundation models (NvDINOv2, C-RADIOv2, NVCLIP) and backbones (ViT, Swin, ResNet) — [TAO overview](https://docs.nvidia.com/tao/tao-toolkit/6.25.10/text/overview.html)
- Built-in AutoML runs hyperparameter sweeps. Release 6.26.03 added BOHB, BFBO, ASHA, PBT, DEHB and Hyperband-ES, an AutoML metric override, a `--automl-settings key=value` CLI option, and an "RT-DETR Warehouse 2D" model — [TAO 6.26.03 release notes](https://docs.nvidia.com/tao/tao-toolkit/6.26.03/text/release_notes.html)
- Other capabilities: self-supervised pretraining, domain adaptation, pruning, distillation and ONNX export. Finetuning Microservices (FTMS) run as REST API on Kubernetes or Docker Compose. Containers come from NGC and support x86 and ARM64 with discrete GPUs (6.0.0+) — [TAO overview](https://docs.nvidia.com/tao/tao-toolkit/6.25.10/text/overview.html)
- The TAO 7.0.1 RT-DETR docs include "Creating an Experiment Specification File" and "Distilling the Model", so the workflow is YAML spec-driven — [TAO 7.0.1 object detection](https://docs.nvidia.com/tao/tao-toolkit/7.0.1/text/cv_finetuning/pytorch/object_detection/index.html)

**Edge Impulse**
- Built-in object detection learning blocks include MobileNetV1 (FOMO/SSD), YOLOv5, YOLOX and a newer "YOLO-Pro" family. The EON Tuner searches across learning blocks within target-device constraints and is recommended for choosing YOLO-Pro settings — [Edge Impulse YOLO-Pro](https://docs.edgeimpulse.com/studio/projects/learning-blocks/blocks/object-detection/yolo-pro.md); [EON Tuner](https://docs.edgeimpulse.com/nordic/edge-impulse-studio/eon-tuner)
- An NVIDIA TAO learning block exists — [Edge Impulse NVIDIA TAO](https://docs.edgeimpulse.com/nordic/edge-impulse-studio/learning-blocks/nvidia-tao)
- BYOM accepts uploads in SavedModel, ONNX or TFLite format — [Edge Impulse BYOM](https://docs.edgeimpulse.com/nordic/edge-impulse-studio/bring-your-own-model-byom)

**V7 Darwin**
- "Train a Model" offers instance segmentation, object detection and classification. Training does not support slotted items. V7 reports loss and emails the user when training finishes. Training is light, not a core differentiator — [V7 docs: Train a Model](https://docs.v7labs.com/docs/train-a-model)

**SuperAnnotate**
- SuperAnnotate positions itself for "building, fine-tuning, iterating, and managing" models, with increasing focus on LLM fine-tuning, evaluation and red-teaming. I found no detailed CV training spec — [SuperAnnotate docs overview](https://doc.superannotate.com/docs/superannotate-overview)

**Encord**
- Encord's documented strength is evaluating imported predictions (Encord Active) rather than hosted training. Predictions must be imported before Model Evaluation works — [Encord: Model Predictions and Evaluation](https://docs.encord.com/docs/active-model-evaluation)

**Supervisely**
- Training is delivered as ecosystem "apps": Train RT-DETRv2 (Apache-2.0, GPU, updated Feb 2026), YOLOv8–v11, "YOLO v8 - v12", YOLOv5, and Train MMDetection 3.0 (a dashboard for configuring, starting and monitoring training) — [Supervisely train catalog](https://ecosystem.supervisely.com/train); [RT-DETRv2 train app](https://ecosystem.supervisely.com/apps/rt-detrv2/supervisely_integration/train)
- The TrainApp SDK supplies the GUI, train/val split, data conversion, project versioning, evaluation, export and experiment storage. Details are under Q2 — [Supervisely custom training](https://docs.supervisely.com/neural-networks/custom-model-integration/integrate-custom-training)

**Azure Custom Vision / Vertex AI AutoML Vision**
- Azure Custom Vision retires on 2028-09-25. Microsoft points users to Azure ML AutoML for image classification and object detection — [Azure notice AZ502914](https://mc.merill.net/message/AZ502914); [Roboflow blog (vendor)](https://blog.roboflow.com/azure-custom-vision-deprecation/)
- Legacy AutoML Vision Object Detection was deprecated on 2023-01-23 and shut down on 2024-03-31, with features moved to Vertex AI — [Google deprecation notice (JA)](https://cloud.google.com/vision/automl/object-detection/docs/deprecations?hl=ja); [Vertex migration](https://cloud.google.com/vertex-ai/docs/start/migrating-applications?hl=en)

### Inferences
- **Must-have:**
  - Architecture + size picker
  - COCO-pretrained checkpoints, plus "continue from previous version"
  - Epochs/imgsz/batch with sensible presets
  - Train-time augmentation
  - Live loss/mAP charts
  - Cancel with weights kept
  - Credit or time cap
  - Auto-evaluation on completion
- **Should-have:**
  - Advanced hyperparameter YAML editor with import/export
  - Resume from checkpoint
  - Early stopping (patience)
  - A user-run "remote trainer" that streams metrics (fits our pip GPU-worker plan)
  - Periodic checkpoint upload
  - Novice/expert split ("Fast" vs "Custom")
- **Differentiators:**
  - HPO/AutoML sweeps (ASHA/Hyperband, as in TAO)
  - NAS / latency-band model selection (Roboflow)
  - Using community checkpoints as init
  - TAO model families via FTMS
  - Pruning/distillation
- Hyperscaler AutoML Vision is exiting (Azure 2028, Google legacy 2024). That leaves an opening for easy-mode training aimed at former Custom Vision users.

### Gaps
- Roboflow's current list of non-RF-DETR architectures per plan (YOLO-NAS, YOLOv12 and Roboflow 3.0 appeared in older docs) and credit-to-GPU-hour conversion were not confirmed.
- Ultralytics GPU price tables conflict across pages. Use the live billing page.
- I found no detailed current CV training docs for SuperAnnotate or Encord. V7's training details are thin.
- Vertex AI's current AutoML image object detection status (beyond the 2024 legacy shutdown) was not verified.

---

## Q2. How multi-framework training systems abstract model families, and the practical issues

### Takeaway
Every serious system ends up with the same three-part contract per model family: (a) a model catalogue entry (name, task, checkpoint URL, config), (b) a hyperparameter schema with defaults, and (c) a train entrypoint that consumes a normalised dataset export (usually COCO JSON or YOLO txt) and returns a standard artifact bundle (best/last checkpoint, metrics, logs). Dependency isolation is done per framework, typically one container or app per family. Metric normalisation means re-evaluating every model with one evaluator rather than trusting each framework's own mAP.

### Cited Findings
- **Supervisely TrainApp contract:**
  - `models.json` lists model configs, each with `task_type`, `model_name` and `model_files` (checkpoint URL, config path).
  - `hyperparameters.yaml` holds defaults.
  - `app_options.yaml` toggles `model_benchmark`, `export_onnx_supported` and `train_logger`.
  - A `@train.start` function must return `model_name`, `model_files`, `checkpoints` and `best_checkpoint`. If one is missing, the training is treated as failed.

  — [Supervisely docs](https://docs.supervisely.com/neural-networks/custom-model-integration/integrate-custom-training)
- Supervisely converts data via built-in converters (e.g. `to_coco`) from `train.sly_project`. Auto-benchmarking after training needs a registered inference class. `@train.export_onnx` and `@train.export_tensorrt` hooks handle export. Artifacts go to `/experiments/{project}/{task}_{framework}/` with `experiment_info.json`, `model_meta.json` and `app_state.json`, which allows reproducible re-runs — [Supervisely docs](https://docs.supervisely.com/neural-networks/custom-model-integration/integrate-custom-training)
- Each Supervisely trainer (RT-DETRv2, YOLO, MMDetection 3.0) is a separate app, so each framework runs in its own environment — [Supervisely train catalog](https://ecosystem.supervisely.com/train)
- TAO ships each framework inside NGC Docker containers with dependencies preinstalled. Training is driven by YAML experiment spec files, and FTMS exposes it as a REST service — [TAO overview](https://docs.nvidia.com/tao/tao-toolkit/6.25.10/text/overview.html); [TAO 7.0.1 RT-DETR spec](https://docs.nvidia.com/tao/tao-toolkit/7.0.1/text/cv_finetuning/pytorch/object_detection/index.html)
- Ultralytics uses one Python package with a unified `model.train(**hyperparameters)` API. Settings are task-aware and import/export as YAML or JSON — [Ultralytics Platform Cloud Training](https://docs.ultralytics.com/platform/train/cloud-training)
- RF-DETR's `rfdetr` package auto-detects COCO JSON and also accepts YOLO format (`dataset_file="yolo"`). It supports `resume`, `grad_accum_steps`, DDP via `torchrun`, and TensorBoard, W&B and MLflow logging (not ClearML). It exports to ONNX, TFLite and TensorRT — [RF-DETR docs](https://rfdetr.roboflow.com/llms-full.txt)
- HuggingFace Transformers:
  - Object detection uses `AutoModelForObjectDetection`, `TrainingArguments` and `Trainer`, with evaluation done externally through `torchmetrics.detection.mean_ap.MeanAveragePrecision` — [Albumentations/Roboflow RT-DETR tutorial](https://albumentations.ai/docs/integrations/roboflow/train-rt-detr-on-custom-dataset-with-transformers)
  - D-FINE was added to Transformers on 2025-04-29 (`DFineForObjectDetection`) — [HF D-FINE docs](https://huggingface.co/docs/transformers/model_doc/d_fine)
  - An RT-DETRv2 fine-tuning pipeline pins `torchmetrics>=1.4.0` and `pycocotools>=2.0.7` for COCO mAP — [Union.ai tutorial](https://www.union.ai/docs/v2/union/tutorials/computer-vision/detr-object-detection/)
- Metric definitions differ between tools. Encord says its mAP can differ from pycocotools and TorchMetrics, because it includes classes that have no ground truth in the evaluated images — [Encord: evaluating detection models](https://docs.encord.com/docs/active-evaluate-detection-models)
- MMDetection 3.x/MMEngine uses Python config files with `_base_` inheritance and a registry. RTMDet and RTMDet-Ins configs live under `configs/rtmdet`. The license is Apache-2.0 — [MMDetection GitHub](https://github.com/open-mmlab/mmdetection) (not re-fetched this session)
- Detectron2 uses YACS/LazyConfig and is Apache-2.0 — [Detectron2 GitHub](https://github.com/facebookresearch/detectron2) (not re-fetched this session)

### Inferences
- LabelDesk should copy the Supervisely-style contract:
  - A `ModelFamily` plugin with `catalog()`, `hyperparam_schema()` (JSON Schema, used to render the form) and `prepare_dataset(export_format)`
  - `train(cfg, callbacks)`, `evaluate()` and `export()`
  - One Docker image (or pinned venv) per family: `ultralytics`, `rfdetr`, `mmdet` (with mmcv/mmengine, CUDA-pinned and fragile), `tao` (NGC container), and `transformers`

  This avoids torch/CUDA/mmcv version conflicts.
- Dataset conversion: export a canonical COCO JSON as the source of truth, and derive YOLO txt for Ultralytics. TAO and MMDet consume COCO directly. Ultralytics' own mAP uses a different interpolation and matching than pycocotools, so numbers must be normalised.
- Metric normalisation: every family emits raw predictions on the frozen test split, and LabelDesk computes all leaderboard metrics with one evaluator (pycocotools or faster-coco-eval). Framework-reported mAP is shown only as "training-time val".
- Progress and metric streaming should use a common callback schema (`epoch`, `loss_*`, `val_map50`, `val_map50_95`, `lr`), with an adapter per framework.

### Gaps
- I did not verify MMDetection's current maintenance status. My understanding is that the last major release was in early 2024, which would be a risk for a production dependency. Check GitHub releases.
- I found no published write-up quantifying the mAP discrepancy between Ultralytics' validator and pycocotools on the same predictions.
- I found no documentation of how Supervisely isolates dependencies (it is presumably a Docker image per app).

---

## Q3. Key facts on the target model families: accuracy, latency and license

### Takeaway
On COCO, the 2025-2026 real-time frontier is DETR-style: RF-DETR (up to 60.1 AP), D-FINE and RT-DETR, alongside YOLO26 (40.9–57.5 AP, optional NMS-free). The licensing split is decisive for a SaaS. Ultralytics (YOLOv8/11/26, and its RT-DETR/YOLO-World wrappers) is AGPL-3.0 or Enterprise, and Ultralytics says the AGPL covers SaaS and trained weights. RT-DETR (original repo), D-FINE, RTMDet/MMDetection and RF-DETR N–L are Apache-2.0.

### Cited Findings
- **RT-DETR** (Zhao et al., "DETRs Beat YOLOs on Real-time Object Detection", arXiv 2304.08069, v3 Apr 2024; published at CVPR 2024 per common citation):
  - NMS-free end-to-end detection, with a hybrid encoder and uncertainty-minimal query selection
  - Decoder depth can be adjusted at inference without retraining
  - R50/R101 reach 53.1/54.3 AP at 108/74 FPS on a T4, and 55.3/56.2 AP with Objects365 pretraining
  - R50 is +2.2 AP over DINO-R50 at about 21× the FPS

  — [arXiv 2304.08069](https://arxiv.org/abs/2304.08069)
- **RTMDet** (Lyu et al., arXiv 2212.07784, 2022): 52.8% AP on COCO at 300+ FPS on an RTX 3090, and state of the art for real-time instance segmentation (RTMDet-Ins). The abstract gives no mask AP numbers — [arXiv 2212.07784](https://arxiv.org/abs/2212.07784). Implemented in MMDetection (Apache-2.0) — [MMDetection](https://github.com/open-mmlab/mmdetection) (not re-fetched). LandingLens ships RtmDet-[9M] as its fastest OD option — [LandingLens](https://landinglens.docs.landing.ai/custom-training.md)
- **YOLO-World** (Cheng et al., arXiv 2401.17270, v3 Feb 2024; CVPR 2024 per common citation): open-vocabulary YOLO with RepVL-PAN and a region-text contrastive loss, reaching 35.4 AP on LVIS at 52.0 FPS on a V100 — [arXiv 2401.17270](https://arxiv.org/abs/2401.17270). The official AILab-CVC repo license should be checked; I recall GPL-3.0, which would be copyleft (not verified this session) — [YOLO-World GitHub](https://github.com/AILab-CVC/YOLO-World)
- **D-FINE** (Peng et al., arXiv 2410.13842): fine-grained distribution refinement plus self-distillation. D-FINE-L/X reach 54.0/55.8 AP at 124/78 FPS on a T4, and 57.1/59.3 AP with Objects365 pretraining. Applied to other DETRs it adds up to +5.3 AP — [arXiv 2410.13842](https://arxiv.org/abs/2410.13842). Available in HF Transformers since 2025-04-29 — [HF docs](https://huggingface.co/docs/transformers/model_doc/d_fine)
- **RF-DETR** (Roboflow, "RF-DETR: Real-Time Detection Transformers", arXiv 2511.09554, ICLR 2026, NAS-based), on a T4 with TensorRT FP16, batch 1:

  | Size | Detection AP50:95 | Detection latency | Params | Segmentation AP50:95 | Segmentation latency |
  |---|---|---|---|---|---|
  | N | 48.4 | 2.3 ms | 30.5M | 40.3 | 3.4 ms |
  | S | 53.0 | 3.5 ms | | 43.1 | |
  | M | 54.7 | 4.4 ms | | 45.3 | |
  | L | 56.5 | 6.8 ms | | 47.1 | |
  | XL | 58.6 | 11.5 ms | | 48.8 | |
  | 2XL | 60.1 | 17.2 ms | 126.9M | 49.9 | 21.8 ms |

  — [RF-DETR docs](https://rfdetr.roboflow.com/llms-full.txt)
- **RF-DETR license split:**
  - Apache-2.0: the `rfdetr` package, Detection N–L, all Segmentation sizes, and Keypoint (Preview)
  - Roboflow Platform Model License (PML 1.0): Detection XL/2XL, the Atto/Femto/Pico detection models (via `rfdetr[plus]`) and NAS models. Commercial self-hosting of these requires an Enterprise add-on

  Older sources describe the whole family as Apache-2.0, so this split is recent — [RF-DETR docs](https://rfdetr.roboflow.com/llms-full.txt); [Roboflow blog](https://blog.roboflow.com/rf-detr-nano-small-medium/)
- **YOLO26** (Ultralytics; the docs say "released January 2026", unveiled at YOLO Vision 2025 in London in September 2025):
  - Drops DFL, adds an optional one-to-one NMS-free head (`nms=False`), and uses the MuSGD optimizer (SGD + Muon), ProgLoss and STAL small-target label assignment
  - Tasks: detect, instance segmentation, semantic segmentation, depth, classification, pose (RLE) and OBB
  - COCO results:

  | Model | mAP50-95 | T4 TRT10 | CPU ONNX | Params |
  |---|---|---|---|---|
  | n | 40.9 | 1.7 ms | 38.9 ms | 2.4M |
  | s | 48.6 | 2.5 ms | | |
  | m | 53.1 | 4.7 ms | | |
  | l | 55.0 | 6.2 ms | | |
  | x | 57.5 | 11.8 ms | 525.8 ms | 55.7M |

  — [Ultralytics YOLO26 docs](https://docs.ultralytics.com/models/yolo26/); release context from [arXiv 2509.25164](https://arxiv.org/pdf/2509.25164v1) and a third-party analysis at [arXiv 2601.12882](https://arxiv.org/pdf/2601.12882)
- The Ultralytics license is "AGPL-3.0 and an Enterprise license" for code, models and docs — [YOLO26 docs](https://docs.ultralytics.com/models/yolo26/)
- Ultralytics says its trained models fall under AGPL-3.0 by default and that the requirement covers SaaS/API deployment and internal use, unless you hold an Enterprise License (custom pricing). This is vendor marketing, not the license text — [Ultralytics license page](https://ultralytics.com/license); [pricing](https://www.ultralytics.com/pricing)
- Roboflow says custom-trained Ultralytics models remain AGPL-3.0 — [Roboflow: Ultralytics](https://roboflow.com/ultralytics)
- AGPL-3.0 §13 ("Remote Network Interaction") requires that, if you modify the Program, users interacting with it remotely over a network get an opportunity to receive the Corresponding Source of your version. The fetch was rate-limited (HTTP 429), so this paraphrase is from the canonical text — [GNU AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.en.html)
- In Supervisely's catalogue, RT-DETRv2 is listed as Apache-2.0 — [Supervisely RT-DETRv2 app](https://ecosystem.supervisely.com/apps/rt-detrv2/supervisely_integration/train)

### Inferences
- **SaaS implication.** If LabelDesk runs the `ultralytics` package on its servers, its hosted training/inference service is arguably network interaction with AGPL code. Ultralytics' own reading also extends to the produced weights. That points to three options:
  1. Open-source the LabelDesk backend that links ultralytics under AGPL
  2. Buy an Ultralytics Enterprise License or resell through an authorized arrangement, as Roboflow does
  3. Isolate Ultralytics in a separately-distributed worker the *user* installs and runs (e.g. our pip GPU worker), keep the weights user-owned, and tell users that AGPL obligations pass to them

  This needs legal review. Ultralytics' claim that weights are covered is legally contested and not settled by the license text.
- **Apache-2.0 default family for a closed SaaS:** RF-DETR N/S/M/L (detection and segmentation), D-FINE, RT-DETR/RT-DETRv2 (original lyuwenyu repo, or HF Transformers), and RTMDet/RTMDet-Ins (MMDetection). Offer YOLO26/11/v8 as a "bring your own license / AGPL" option.
- YOLO-World (open vocabulary) is mostly useful for zero-shot pre-labelling and prompt-based detection. Fine-tuning it is less common. Its repo license needs checking. The Ultralytics port is AGPL.
- TAO models carry NVIDIA's own model licenses and run in NGC containers. Treat TAO as an enterprise/on-prem differentiator, not core.

### Gaps
- The YOLO-World repo license and the TAO pretrained model license terms were not verified this session.
- The Ultralytics Enterprise License text (scope of SaaS and weights) is not public. Only marketing claims were found.
- RTMDet-Ins mask AP numbers, and RT-DETRv2 (arXiv 2407.17140) numbers, were not fetched.
- YOLOv8 and YOLO11 benchmark tables were not fetched this session. They are in the Ultralytics docs.
- YOLO26's docs cite an arXiv ID (2606.03748) that conflicts with the "January 2026" release wording. Unresolved.

---

## Q4. Evaluation: metrics, error analysis, calibration, slices and leaderboards

### Takeaway
Table stakes are the COCO 12-metric summary (AP@[.5:.95], AP50, AP75, AP S/M/L, AR@1/10/100, AR S/M/L), per-class AP, a confusion matrix at an optimal confidence threshold, and PR/F1 curves. Differentiators are TIDE-style error decomposition, slice/metadata-based performance (Encord "performance by metric", FiftyOne views, Roboflow vector clusters), calibration, and multi-model comparison on a frozen test set.

### Cited Findings
- **COCO evaluation (pycocotools):**
  - 12 summary stats: AP @ IoU .50:.95, AP@.50, AP@.75, AP small/medium/large, AR maxDets 1/10/100, and AR small/medium/large
  - IoU thresholds run from 0.50 to 0.95 in steps of 0.05 (10 values)
  - Area ranges: small < 32², medium 32²–96², large > 96²
  - Detection maxDets is [1, 10, 100]
  - Recall uses 101 interpolation points

  — [pycocotools cocoeval.py](https://raw.githubusercontent.com/cocodataset/cocoapi/master/PythonAPI/pycocotools/cocoeval.py); COCO also documents this at [cocodataset.org detection eval](https://cocodataset.org/#detection-eval) (the page did not render for the fetcher)
- **TIDE** (Bolya, Foley, Hays, Hoffman, arXiv 2008.08115, 2020; ECCV 2020 per common citation; older but still the reference):
  - A drop-in replacement for mAP computation that runs on prediction files only
  - Splits errors into six types (classification, localization, both, duplicate, background, missed) and measures each type's isolated contribution to mAP
  - Validated on 4 datasets and 7 models

  — [arXiv 2008.08115](https://arxiv.org/abs/2008.08115)
- **Roboflow Model Evaluation:**
  - Opened with "View Evaluation" on any trained version, and run automatically for all versioned models trained on, or uploaded to, Roboflow by paid users
  - The confusion matrix runs the test and validation sets at the model's computed *optimal threshold*
  - "Vector analysis" is an interactive embedding explorer that finds image clusters where the model does well or poorly
  - Gives model-improvement recommendations based on the confusion matrix, and has an API endpoint that lists evaluations

  — [Roboflow: Evaluate trained models](https://docs.roboflow.com/models/evaluate/evaluate-trained-models)
- **Encord Active:**
  - Per-class AP/AR and PR curves
  - Automatic mAP, mAR, "Metric Importance" and "Metric Correlation" for chosen classes and IoU threshold
  - "Performance by Metric", which plots precision and FNR against data-quality metrics (slice analysis)
  - For classification: accuracy, precision, recall, F1 and a confusion matrix
  - A model performance comparison page

  — [Encord: evaluating detection models](https://docs.encord.com/docs/active-evaluate-detection-models); [Encord: classification](https://docs.encord.com/docs/active-evaluate-classification-models); [Encord: compare model performance](https://docs.encord.com/platform-documentation/Active/active-how-to/active-compare-model-performance)
- **FiftyOne (Voxel51):**
  - `evaluate_detections()` uses COCO-style matching by default and respects `iscrowd`, storing per-object TP/FP/FN under an `eval_key`. Multiple eval keys allow model comparison
  - Interactive confusion matrices: click a cell to select objects, and the matrix updates to the current view (slice)
  - A Model Evaluation panel in the App, plus the `@voxel51/evaluation` plugin

  — [FiftyOne: Evaluating Models](https://docs.voxel51.com/user_guide/evaluation/index.html)
- **LandingLens** shows training information and metrics per model — [LandingLens training information](https://landinglens.docs.landing.ai/training-information) (not fetched in detail)
- **Supervisely** "model_benchmark" auto-generates an evaluation report with metrics and visualisations after training — [Supervisely docs](https://docs.supervisely.com/neural-networks/custom-model-integration/integrate-custom-training)
- **Calibration** (older, foundational):
  - Guo et al. 2017, "On Calibration of Modern Neural Networks": ECE and temperature scaling — [arXiv 1706.04599](https://arxiv.org/abs/1706.04599) (not re-fetched)
  - Küppers et al. 2020: detection-specific calibration (D-ECE) that conditions on box position and size — [arXiv 2004.13546](https://arxiv.org/abs/2004.13546) (not re-fetched)
- **Slice discovery** (older): Eyuboglu et al. 2022, "Domino", finds underperforming slices automatically through cross-modal embeddings — [arXiv 2203.14960](https://arxiv.org/abs/2203.14960) (not re-fetched)

### Inferences
- **Must-have:**
  - COCO 12-metric summary computed by one shared evaluator on a frozen test split
  - Per-class AP table
  - Confusion matrix at a selectable or optimal confidence threshold, including a "background" row/column
  - PR curve and F1-vs-confidence curve, with a recommended threshold
  - Side-by-side visual prediction viewer (GT vs prediction, FP/FN highlighting)
- **Should-have:**
  - TIDE breakdown (pure Python, cheap to add: `tidecv`)
  - Comparing 2+ model versions on the same test set (leaderboard), with latency and params alongside mAP
  - Size-based (S/M/L) and metadata/tag slices
  - Click-through from a metric cell to the images
- **Differentiators:**
  - Embedding-cluster failure analysis (Roboflow vector analysis, FiftyOne)
  - Calibration plot / D-ECE
  - Auto slice discovery
  - "Metric importance" (Encord)
  - Active-learning loop: send FP/FN images back to labelling
- **Test-set hygiene:**
  - Lock the test split per dataset version, and refuse to train on it
  - Dedupe or near-dedupe across splits (embedding similarity)
  - Record which dataset version and threshold each evaluation used
  - Evaluate every family with the same evaluator (see the Encord vs pycocotools discrepancy)

  Roboflow's evaluation uses both test *and validation* images, which mixes model-selection data into reported metrics. LabelDesk can do better with test-only reporting.
- Roboflow reports confusion-matrix values for segmentation as pixel counts, per a search snippet of its docs. Specify the unit explicitly in LabelDesk.

### Gaps
- I found no source documenting calibration or TIDE as a built-in feature of any commercial CV SaaS. This appears to be an open differentiator, but absence of evidence is not proof.
- Details of Roboflow's "Production Metrics Explorer" were not found.
- LandingLens evaluation page specifics (confusion matrix, threshold tuning) were not fetched.
- I found no standard published guidance on test-set hygiene specific to these platforms. The recommendations above are inference.
