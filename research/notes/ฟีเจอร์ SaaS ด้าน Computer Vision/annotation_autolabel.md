# Annotation Tooling, Model-Assisted Auto-Labeling and Active Learning in CV Labeling SaaS

Research date: 2026-10-31. Scope: inventory for tiering LabelDesk features (SAM 3.1 + 7B VLM via vLLM). Vendor-published numbers are marked [vendor]. Pre-2024 information is marked [older].

## 1. Standard annotation tools and workflows across platforms

### Takeaway
Bbox, polygon, keypoint/skeleton, classification, and AI-assisted polygon/mask (SAM-class click tools) are table stakes on every major platform. The enterprise differentiators are QA machinery: review/rework stages, ground-truth/benchmark scoring, consensus (multiple annotators per item) and per-labeler performance dashboards. CVAT, Labelbox and V7 all ship these, and Roboflow's are lighter.

### Cited Findings
**Roboflow**
- Roboflow Annotate supports manual bounding boxes and polygons, Label Assist (uses your trained model checkpoints to recommend annotations), and Smart Polygon (polygon in a few clicks) — [Roboflow Annotate docs](https://docs.roboflow.com/annotate/annotation-tools)
- Project-type/annotation compatibility: keypoints (skeleton) for keypoint detection, polygons or masks for segmentation, polygons auto-converted to boxes for detection, image-level labels for classification — [Roboflow annotation tools](https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools)
- Roboflow docs note that boxes are faster to draw while polygons are more precise and "may slightly improve performance" — [Roboflow annotation tools](https://docs.roboflow.com/datasets/annotate/annotate/annotation-tools)
- Roboflow has team annotation workflows (assignment of batches to labelers and review) — [Roboflow team annotation blog](https://roboflow.com/blog/team-image-annotation-workflow)
- I could not confirm oriented/rotated bounding box (OBB) annotation support in Roboflow from the docs retrieved (see Gaps).

**CVAT**
- CVAT QA consists of Ground Truth (GT) jobs, Honeypots, consensus replicas, job validation on finish, a review mode for problems found, and quality analytics — [CVAT QA & Analytics](https://docs.cvat.ai/docs/qa-analytics/)
- A task can have at most one GT job. CVAT docs suggest 5-15% of the data is usually enough for quality estimation — [CVAT Quality control](https://docs.cvat.ai/docs/qa-analytics/quality-control/)
- Honeypots reuse validation frames mixed into regular jobs. These frames are excluded from export and used only for quality scoring. They are not available for video or 3D tasks and must be set up at task creation — [CVAT Automated QA, Review & Honeypots](https://docs.cvat.ai/docs/qa-analytics/auto-qa/); [CVAT honeypots blog](https://www.cvat.ai/resources/blog/annotation-qa-honeypots)
- Consensus: "replicas" are copies of a job annotated by different people. They are merged into the parent job along with consensus scores. GT jobs cannot have replicas — [CVAT Consensus-based annotation](https://docs.cvat.ai/docs/qa-analytics/consensus/)
- Quality reports classify conflicts such as missing_annotation and extra_annotation — [CVAT quality control (third-party mirror, less authoritative)](https://www.mintlify.com/cvat-ai/cvat/projects/quality-control)
- Video: a SAM 2 tracker propagates polygons and masks (not rectangles) from the first frame across subsequent frames and can track multiple objects at once. The Nuclio version is Enterprise/self-hosted only and needs Redis for tracking state. An "AI agent" variant runs on the user's own hardware for CVAT Online — [CVAT SAM 2 Tracker](https://docs.cvat.ai/docs/annotation/auto-annotation/segment-anything-2-tracker/); [CVAT Enterprise SAM2 tracker](https://docs.cvat.ai/docs/enterprise/segment-anything-2-tracker)
- An anecdotal user report in a CVAT GitHub issue says an AI tracker was "vastly more accurate than interpolation" [older, anecdotal] — [CVAT issue #5686](https://github.com/cvat-ai/cvat/issues/5686)

**Labelbox**
- Labelbox has two quality modes. Benchmarks compare labels against a designated reference label. Consensus measures agreement among multiple labelers on the same asset, configured per batch as a coverage percentage plus the number of labels per asset — [Labelbox: evaluate & optimize labeling results](https://labelbox.com/guides/how-to-evaluate-and-optimize-your-data-labeling-projects-results/)
- Custom multi-step review workflows let different groups (core team, SMEs) review in turn. Rejected items go automatically to "Rework" — [Labelbox: customize review process](https://labelbox.com/guides/how-to-customize-your-annotation-review-process/); [Labelbox: new way to queue & review](https://labelbox.com/guides/a-new-way-to-queue-review/)
- The performance dashboard tracks per-labeler and per-project metrics, including the average consensus score over time — [Labelbox Performance dashboard](https://docs.labelbox.com/docs/performance-dashboard)
- Labelbox notes that consensus measures agreement, not accuracy — [Labelbox data factory blog](https://labelbox.com/blog/inside-the-data-factory-how-labelbox-produces-the-highest-quality-data-at-scale/)

**V7 Darwin, Encord, Supervisely, Label Studio**
- V7 Auto-Annotate generates polygon/mask annotations from a box or click. Secondary sources say V7 runs it on SAM 2 and also offers MedSAM and SAM 2 video auto-tracking (secondary sources, not confirmed in V7 docs) — [Lightly: best CV tools 2026](https://www.lightly.ai/blog/best-computer-vision-tools); [V7 (Wikipedia)](https://en.wikipedia.org/wiki/V7_(company))
- V7 is described as having consensus stages in workflows (comparison-site claim) — [aiagentstore comparison](https://aiagentstore.ai/agentic-ai-and-workflow-automation/en/top-10-data-labeling-qa-and-annotation-operations-agents)
- Encord docs say SAM 2 handles tracking and SAM 3 handles object labeling. Auto-annotation is toggled in the UI or with Shift+A, and SAM can produce boxes, polylines and keypoints, not only masks — [Encord SAM Segmentation & Tracking docs](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-sam)
- Encord's product is split into Index (curation), Annotate, and Active (model/data evaluation). This framing comes from a competitor page — [Lightly vs Encord (competitor marketing)](https://lightly.ai/competitor/encord)
- Supervisely video labeling offers automatic tracking, detection and segmentation using SAM, MixFormer, RITM, ClickSeg and EiSeg (vendor-adjacent blog) — [Encord: best video annotation tools (lists Supervisely)](https://encord.com/blog/best-video-annotation-tools-for-healthcare/)
- Label Studio supports SAM 2 for both images and video (July 2024) through its ML backend — [Label Studio SAM integration](https://labelstud.io/integrations/models/segment-anything-model)

### Inferences
- **Must-have:** bbox, polygon, brush/mask, keypoints with skeleton templates, image classification tags, a class/attribute schema, click-to-segment (SAM), keyboard shortcuts, per-image review (approve/reject → rework), and batch/job assignment to users. Every comparable platform ships these.
- **Should-have:** rotated boxes (OBB; the YOLO-OBB ecosystem needs them), polylines, video with SAM 2/3 propagation (better than linear interpolation), comments/issues on an annotation, a GT/benchmark job with a quality score (CVAT-style 5-15% validation subset), and per-labeler throughput/accept-rate dashboards.
- **Differentiator for a small SaaS:** consensus replicas with automatic merge, honeypots, and SME multi-stage review. These are enterprise-grade (CVAT, Labelbox), and Roboflow is weaker here.

### Gaps
- Could not retrieve SuperAnnotate's or Scale's QA/consensus docs, so no cited claims for them.
- Did not confirm Roboflow OBB annotation support or Roboflow's labeler-performance metrics from primary docs.
- Label Studio Enterprise agreement metrics and reviewer workflow docs were not retrieved. From prior knowledge it has inter-annotator agreement matrices, but this is not cited here.
- Supervisely "Smart Tool" docs not found.

## 2. Foundation models for auto-labeling (SAM family, open-vocab detectors, VLMs)

### Takeaway
The 2025-2026 standard is text-prompted, batch auto-labeling of whole datasets with SAM 3 (Roboflow, Encord), plus SAM-class click tools and SAM 2/3 video propagation. Open-vocabulary detectors (Grounding DINO, YOLO-World, OWLv2) remain the box workhorses. Generalist VLMs such as Qwen2.5-VL are measurably worse than task-specific detectors at exhaustive multi-object detection, so they suit verification, classification, attribute filling and complex referring queries better than primary box generation.

### Cited Findings
**SAM family**
- SAM (2023) data engine: average per-mask annotation time fell from 34 s to 14 s as the model improved [older] — [Kirillov et al., Segment Anything, arXiv 2304.02643](https://arxiv.org/pdf/2304.02643)
- SAM 2 (2024) video data engine: per-frame annotation went from 37.8 s (Phase 1, SAM per frame) to 7.4 s, about 5.1x faster. Note the baseline is SAM per frame, not fully manual annotation — [SAM 2, arXiv 2408.00714](https://arxiv.org/pdf/2408.00714)
- SAM 3 introduces Promptable Concept Segmentation (PCS). It detects, segments and tracks all instances of a concept in an image or short video (≤30 s), prompted by a short noun phrase, image exemplars (positive/negative boxes), or both. It is published at ICLR 2026 — [SAM 3, arXiv 2511.16719](https://arxiv.org/html/2511.16719v1); [ICLR 2026 poster](https://iclr.cc/virtual/2026/poster/10007181)
- SAM 3 reaches zero-shot LVIS mask AP of 48.8, against 38.5 for the previous best. On SA-Co/Gold its cgF1 is more than double the strongest baseline (OWLv2*) and reaches about 74% of estimated human performance. On SA-Co/VEval video it exceeds 80% of human pHOTA — [SAM 3 arXiv](https://arxiv.org/html/2511.16719v1). Ultralytics lists 47.0 LVIS AP, possibly a different setting — [Ultralytics SAM 3 docs](https://docs.ultralytics.com/models/sam-3). Secondary SA-Co/Gold numbers: SAM 3 54.1 cgF1, humans 72.8, OWLv2* 24.6 — [alphaXiv SA-Co benchmark](https://www.alphaxiv.org/benchmarks/meta-superintelligence-labs/sa-co)
- SAM 3 has a "presence head", a global token that predicts whether the concept is present at all and so decouples recognition from localization (+1.5 cgF1 in ablation). It runs at about 30 ms per image on an H200 even with 100+ objects. Video latency scales with object count (near real-time for about 5 concurrent objects) — [SAM 3 arXiv](https://arxiv.org/html/2511.16719v1)
- SAM 3 data engine: fine-tuned Llama 3.2 "AI verifiers" check mask quality and exhaustivity, roughly doubling annotation throughput over human-only annotation. The dataset has 4M unique phrases and 52M masks (high-quality set), plus a 38M-phrase / 1.4B-mask synthetic set. SA-Co has 207K unique concepts — [SAM 3 arXiv](https://arxiv.org/html/2511.16719v1)
- SAM 3 limitations: it is designed for simple noun phrases, not long referring or reasoning queries. It struggles with out-of-domain terms, which may need fine-tuning, and with ambiguous phrases. Complex queries are handled by pairing it with an MLLM as a "SAM 3 Agent" (strong zero-shot results on ReasonSeg and OmniLabel) — [SAM 3 arXiv](https://arxiv.org/html/2511.16719v1)
- SAM 3 code, checkpoints and the SA-Co benchmark are open-sourced — [github.com/facebookresearch/sam3 via arXiv](https://arxiv.org/html/2511.16719v1). SA-Co datasets are hosted on Hugging Face and Roboflow — [SAM 3 evaluation overview (mirror)](https://www.mintlify.com/facebookresearch/sam3/evaluation/overview)

**Platform implementations**
- Roboflow (Nov 2025): "Auto Label with SAM 3" lets users enter text prompts, test prompts and confidence thresholds on samples, then auto-label an entire batch with "SAM 3 (Masks)" — [Roboflow changelog Nov 2025](https://docs.roboflow.com/changelog/explore-by-month/november-2025/auto-label-data-with-sam-3); [Roboflow AI labeling](https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling)
- Roboflow positions three AI aids. Smart Select / Smart Polygon is SAM-based one-click masks, suggested for a first dataset version or new classes. Label Assist uses your own trained model. Auto Label is batch zero-shot labeling. Roboflow claims Label Assist can cut human labeling time by up to 95% [vendor] — [Roboflow AI labeling docs](https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling)
- Roboflow's own docs say SAM 3 suits common objects but not fine-grained variants (for example crack types or product-specific defects), and that tiny objects or rare defects need manual annotation — [Roboflow Auto Label docs (KO)](https://docs.roboflow.com/datasets/ko/annotate/annotate/ai-labeling/auto-label.md); [Roboflow natural-language annotation blog](https://roboflow.com/blog/natural-language-image-annotation)
- A community report describes a SAM 3 Auto Label job finishing with 0 annotations while consuming credits. This is a UX lesson: preview before charging — [Roboflow forum](https://discuss.roboflow.com/t/auto-label-with-sam-3-completed-with-0-annotations-but-consumed-credits/12302)
- Autodistill (Roboflow, open source) uses a "base model" (a large zero-shot model such as Grounding DINO / Grounded SAM / OWLv2) to label images, then trains a small "target model" (for example YOLO) on the result, with no manual labels — [autodistill GitHub](https://github.com/autodistill/autodistill) (from prior knowledge of the repo; not re-fetched this session)
- Label Studio ML backend: a separate server exposes an API that Label Studio calls for predictions or training. Examples include Grounding DINO + Grounding SAM (with an optional MobileSAM, lighter but less accurate) with text-prompt auto-annotation in the labeling UI. BOX_THRESHOLD and TEXT_THRESHOLD control confidence. The examples are development-grade — [Label Studio Grounding SAM tutorial](https://labelstud.io/guide/ml_tutorials/grounding_sam); [Label Studio Grounding DINO blog](https://labelstud.io/blog/using-text-prompts-for-image-annotation-with-grounding-dino-and-label-studio)
- CVAT runs AI tools as Nuclio serverless functions (self-hosted) or as "auto-annotation functions" run by an agent on the user's own hardware — [CVAT AI models](https://docs.cvat.ai/docs/annotation/auto-annotation/ai-models/); [CVAT SAM2 tracker](https://docs.cvat.ai/docs/annotation/auto-annotation/segment-anything-2-tracker/)
- Encord: SAM 3 for labeling, SAM 2 for tracking — [Encord SAM docs](https://docs.encord.com/platform-documentation/Annotate/automated-labeling/annotate-sam); [Encord SAM blog [older]](https://encord.com/blog/sam-automate-data-labeling-encord/)

**Open-vocabulary detectors**
- Grounding DINO: 52.5 AP zero-shot on COCO with no COCO training data [2023, older] — [arXiv 2303.05499](https://arxiv.org/abs/2303.05499)
- Grounding DINO 1.5 Edge: 45.0 zero-shot COCO AP and 36.2 LVIS-minival AP at 800×1333. The same paper lists YOLO-World v2-L at 32.9 LVIS-minival — [arXiv 2405.10300](https://arxiv.org/pdf/2405.10300). Secondary sources give Pro-variant numbers that conflict with each other (54.3 vs 55.4 for 1.6 Pro, API-only) — [Roboflow best detection models 2026](https://roboflow.com/blog/best-object-detection-models); [Forasoft guide](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/open-vocabulary-detection-grounding-dino-florence-2-rtdetr-rfdetr)
- YOLO-World: 35.4 zero-shot LVIS AP at 52 FPS on V100 (real-time open-vocab) — [Roboflow best detection models](https://roboflow.com/blog/best-object-detection-models); original paper [arXiv 2401.17270](https://arxiv.org/abs/2401.17270)
- Florence-2: only a secondary, possibly unreliable figure (~34.7 zero-shot COCO mAP) was found — [Forasoft](https://www.forasoft.com/learn/ai-for-video-engineering/articles-ai/open-vocabulary-detection-grounding-dino-florence-2-rtdetr-rfdetr). Treat it as unverified.

**VLM grounding for boxes (Qwen2.5-VL etc.)**
- RF100-VL (100 datasets, 564 classes, 164,149 images from Roboflow Universe): generalist MLLMs (Qwen2.5-VL, Gemini 2.5 Pro) perform worse at object detection than task-specific open-vocab detectors like Grounding DINO. Grounding DINO had the best few-shot performance. Multimodal annotator instructions gave inconsistent benefits to MLLMs and sometimes degraded them — [Roboflow100-VL, arXiv 2505.20612](https://arxiv.org/pdf/2505.20612); [review summary](https://www.themoonlight.io/en/review/roboflow100-vl-a-multi-domain-object-detection-benchmark-for-vision-language-models)
- On challenging medical datasets, Grounding DINO and Qwen2.5-VL reach <2% zero-shot accuracy — [RF100-VL arXiv](https://arxiv.org/pdf/2505.20612)
- Protocol caveat: Qwen2.5-VL's self-reported ODinW numbers used a referential-grounding protocol, not the detector protocol of prompting with all classes. They are not directly comparable to detector mAP — [RF100-VL arXiv](https://arxiv.org/pdf/2505.20612)
- RefCOCO-style REC is near-saturated (>85% for SOTA MLLMs), but the labels are noisy: error rates of 14% / 24% / 5% in RefCOCO / RefCOCO+ / RefCOCOg. Cleaning the labels raised LMM scores by 1.57-3.08 points — [Revisiting REC evaluation, arXiv 2406.16866](https://arxiv.org/html/2406.16866v1)
- Tight-box weakness, illustrated with NVILA (not Qwen): one base model scored >80% at IoU 0.5 but <5% at IoU 0.9 — [Chain-of-Caption, arXiv 2602.08211](https://arxiv.org/pdf/2602.08211)
- "Grounding hallucination", meaning boxes predicted for non-existent objects, is under-measured by current benchmarks — [CVPR25 REC paper](https://cse.hkust.edu.hk/~gchan/papers/CVPR25_REC.pdf)
- In a diagnostic VQA study, the Qwen2.5-VL family peaked at 67.8% grounding accuracy and outperformed Llama and GPT-5 variants on box prediction, suggesting that explicit grounding training matters — [CRAG-MM-Diagnostics, arXiv 2607.21155](https://arxiv.org/pdf/2607.21155)
- Qwen2.5-VL technical report (Feb 2025) for its absolute-coordinate grounding design — [arXiv 2502.13923](https://arxiv.org/abs/2502.13923) (not re-fetched; specific numbers not extracted)

### Inferences
- For LabelDesk, use SAM 3.1 as the primary box/mask generator: text prompt → all instances, plus exemplar refinement with positive/negative boxes. Use the 7B VLM as (a) a verifier/filter that rejects false-positive crops (mirroring SAM 3's own Llama-based AI verifiers, which doubled throughput), (b) a parser that turns complex user requests into simple noun phrases ("SAM 3 Agent" pattern), and (c) a filler for attributes and image-level classes. Do not rely on 7B-VLM boxes as primary geometry. RF100-VL and the IoU-0.9 data show poor exhaustiveness and tightness.
- Must-have: click-to-segment (SAM), text-prompt batch auto-label with a preview on a sample and a confidence slider before committing (Roboflow pattern; avoids the "0 annotations but charged" failure).
- Should-have: exemplar-based "find more like this" (SAM 3 visual exemplars), video propagation (SAM 2/3), and model-assisted labeling with the user's own trained model (Label Assist).
- Differentiator: VLM-verified auto-labels and VLM attribute/caption filling, Autodistill-style "auto-label → train small YOLO" one-click, and domain warnings for fine-grained defects. Roboflow itself says SAM 3 is weak there, so steer those users to few-shot or exemplar workflows.

### Gaps
- No primary-source Qwen2.5-VL RefCOCO / RF100-VL mAP numbers were extracted. Florence-2 and OWLv2 primary numbers were not verified.
- V7 Auto-Annotate details come from secondary sources only.
- SAM 3.1 (the specific point release LabelDesk uses) was not separately researched. Numbers above are for SAM 3.

## 3. Human-in-the-loop design and measured speedups

### Takeaway
The dominant pattern is pre-label → human correct → review. It is controlled by a confidence threshold tuned on a sample, with low-confidence or uncertain items routed to humans. Rigorous measured speedups from pre-labeling are moderate (about 23-35% in controlled studies, up to 60-80% in narrow segmentation domains). Vendor claims of 50-95% are self-reported.

### Cited Findings
- Roboflow workflow: test prompts and confidence thresholds on a few images, run on the batch, then review a few masks and fix errors before training — [Roboflow SAM 3 auto-label changelog](https://docs.roboflow.com/changelog/explore-by-month/november-2025/auto-label-data-with-sam-3)
- Label Studio pre-annotation confidence is set with BOX_THRESHOLD / TEXT_THRESHOLD (0-1) — [Label Studio Grounding SAM tutorial](https://labelstud.io/guide/ml_tutorials/grounding_sam)
- Labelbox "Model-Assisted Labeling" (MAL) imports model predictions as editable pre-labels. Labelbox proposed an "automation efficiency score" to measure whether pre-labeling saves time vs. labeling from scratch [2022, older; vendor] — [Labelbox MAL blog](https://labelbox.com/blog/model-assisted-labeling/); [Labelbox automation efficiency score](https://labelbox.com/blog/measure-and-improve-pre-labeling-workflows-with-the-automation-efficiency-score)
- Labelbox claims 50-70% cost reductions from automation [vendor] — [Labelbox: use automation to reduce labeling time](https://labelbox.com/blog/use-automation-to-reduce-your-labeling-time-and-spend/)
- Roboflow claims Label Assist can reduce human labeling time by up to 95% [vendor] — [Roboflow AI labeling](https://docs.roboflow.com/datasets/annotate/annotate/ai-labeling)
- Hybrid video annotation study (2025): model pre-annotations cut annotation time by a median of 35% for most participants on high-ambiguity spatiotemporal footage — [arXiv 2510.21798](https://arxiv.org/pdf/2510.21798)
- Industrial semantic segmentation (2026): deep-learning pre-annotations saved 78% on average (72.66%-82.81% by defect type). Small, domain-specific sample — [arXiv 2606.19934](https://arxiv.org/pdf/2606.19934)
- Civil-infrastructure model-assisted labeling: about 52% saving, but based on users' self-estimates, which the authors call a conservative lower bound [2022, older] — [arXiv 2209.11159](https://arxiv.org/pdf/2209.11159)
- SAM data engine: 34 s → 14 s per mask (~59% less) [older] — [SAM arXiv](https://arxiv.org/pdf/2304.02643). SAM 2: 37.8 → 7.4 s per frame (~5.1x vs SAM-per-frame) — [SAM 2 arXiv](https://arxiv.org/pdf/2408.00714). SAM 3 AI verifiers about 2x throughput vs human-only verification — [SAM 3 arXiv](https://arxiv.org/html/2511.16719v1)
- ScribblePrompt (interactive biomedical segmentation) cut annotation time by 28% and improved Dice by 15% vs. SAM in a user study — [ScribblePrompt](https://scribbleprompt.csail.mit.edu)
- Interactive SAM annotation article (Intel), a practitioner perspective on speeding time-to-model [vendor] — [Intel developer article](https://www.intel.com/content/www/us/en/developer/articles/community/interactive-annotation-sam.html)
- Pitfall to design for: consensus measures agreement, not accuracy — [Labelbox](https://labelbox.com/blog/inside-the-data-factory-how-labelbox-produces-the-highest-quality-data-at-scale/). CVAT addresses accuracy with GT jobs and honeypots — [CVAT QA](https://docs.cvat.ai/docs/qa-analytics/)

### Inferences
- Must-have: predictions stored as a distinct "prediction / unreviewed" state, visually distinct from human-confirmed labels. Also a per-class confidence threshold with a live preview, bulk accept/reject by class or threshold, and a reject → rework loop.
- Should-have: measure LabelDesk's own speedup (time-on-image with vs. without pre-labels, and the % of predictions edited or deleted, i.e. a Labelbox-style automation efficiency score). This gives honest marketing numbers and also reveals when pre-labels hurt.
- Differentiator: VLM "second opinion" flags (for example "the VLM disagrees this crop is a 'scratch'") to prioritize review queues, mirroring SAM 3's AI-verifier result.
- Pitch speedups conservatively, at about 30-60%. Independent studies cluster there, and the 95% claims are vendor marketing.

### Gaps
- No independent controlled study was found that measures SAM 3 text-prompt auto-label speedup vs. manual for bbox detection datasets.
- No published guidance was found on optimal default confidence thresholds for SAM 3 auto-label.

## 4. Active learning for object detection

### Takeaway
The detection-specific active learning literature (MI-AOD 2021, CALD, PPAL CVPR 2024) shows consistent but often modest gains over random sampling. Cross-paper numbers are not comparable, and reality-check studies find several methods barely beat random. In practice, platforms implement simple, robust heuristics: low-confidence sampling from production inference (Roboflow), uncertainty plus diversity scoring (Lightly, Encord Active).

### Cited Findings
**Papers**
- MI-AOD (CVPR 2021): multiple-instance active learning that models instance-level uncertainty and reweights it into image-level selection. The authors report large margins over prior methods on RetinaNet and SSD, especially with small labeled sets [older] — [arXiv 2104.02324](https://arxiv.org/pdf/2104.02324)
- CALD (consistency-based active learning for detection) is included in ALBench. SSD+CALD on VOC07 reached 68.50 mAP after four cycles vs. 66.48 for random [older] — [ALBench, arXiv 2207.13339](https://arxiv.org/pdf/2207.13339)
- ALBench exists because detection active learning methods are evaluated under different settings, which makes fair comparison hard. Its defaults are VOC07/12 + SSD300, and its baselines are Random, Entropy, ALDD and CALD — [ALBench](https://ar5iv.labs.arxiv.org/html/2207.13339)
- PPAL (Yang, Huang, Crowley, CVPR 2024): a two-stage plug-and-play method. It uses Difficulty Calibrated Uncertainty Sampling (category-wise difficulty coefficients balancing classification and localization difficulty), then diversity sampling via modified k-means++ with a Category Conditioned Matching Similarity (CCMS). It needs no architecture or training-pipeline changes and beats prior SOTA on COCO and VOC across detectors. Code is on MMDetection — [CVPR 2024 OpenAccess](https://openaccess.thecvf.com/content/CVPR2024/html/Yang_Plug_and_Play_Active_Learning_for_Object_Detection_CVPR_2024_paper.html); [arXiv 2211.11612](https://arxiv.org/abs/2211.11612v2); [GitHub](https://github.com/ChenhongyiYang/PPAL/blob/main/README.md)
- Classification Committee for active deep object detection (2023) is an alternative committee-based uncertainty method — [arXiv 2308.08476](https://arxiv.org/pdf/2308.08476)
- Non-redundant informative sampling (2023): +3.4 mAP over random in cycle 2 on VOC, and 90% of fully-supervised performance with 60% of samples — [arXiv 2307.08414](https://arxiv.org/pdf/2307.08414)
- Scalable Active Learning for Object Detection (NVIDIA, 2020) is an industry-scale study [older] — [arXiv 2004.04699](https://arxiv.org/pdf/2004.04699)
- Core-set (diversity) approach, Sener & Savarese (ICLR 2018) [older] — [arXiv 1708.00489](https://arxiv.org/abs/1708.00489)
- "Deep Active Learning: A Reality Check" (2024): BALD and variation ratio only slightly beat random. Entropy and Core-Set performed best. The authors caution that detection gains may be smaller than in classification — [arXiv 2403.14800](https://arxiv.org/pdf/2403.14800)
- Domain case (BoxAL, fish detection, 2024): 39.0±1.6 mAP with active learning vs. 34.8±1.8 random after 10 iterations (+12.1%) — [arXiv 2410.04880](https://arxiv.org/pdf/2410.04880)

**Platforms**
- Roboflow Active Learning samples production inferences by configurable rules (confidence thresholds, class filters, detection counts) and uploads them for labeling. It requires a cloud deployment. The Workflows "Dataset Upload" block placed after a filter uploads only low-confidence detections. The SDK `active_learning()` method uses a `confidence_interval` such as [0, 60] — [Roboflow Active Learning docs](https://docs.roboflow.com/deployment/monitoring-and-analytics/active-learning); [Roboflow SDK active learning](https://docs.roboflow.com/developer/python-sdk/active-learning); [Roboflow Dataset Upload block](https://inference.roboflow.com/workflows/blocks/roboflow_dataset_upload/)
- Lightly supports uncertainty sampling (least confidence, margin, entropy), diversity sampling, and CORAL (combined). It has a Detectron2 detection active-learning tutorial. A customer claims +32% recall / +10% F1 [vendor] — [Lightly practitioner guide](https://lightly.ai/blog/active-learning-in-machine-learning); [Lightly + Detectron2](https://lightly.ai/post/active-learning-using-detectron2)
- Encord Active is an open-source toolkit to test, validate and evaluate models and to surface, curate and prioritize the most valuable data for labeling. It focuses on high-uncertainty samples, edge-case clusters and weak coverage — [encord-active on PyPI](https://pypi.org/project/encord-active/0.1.73); [Encord data lifecycle docs](https://docs.encord.com/solutions-documentation/applied-ai/data-lifecycle.md)

### Inferences
- Must-have, cheap: "low-confidence sampling" from the inference API, plus a dataset-health view of class counts and per-image prediction confidence. This matches Roboflow and needs no research-grade active learning.
- Should-have: an image-level acquisition score combining uncertainty (entropy/margin from SAM 3 presence scores or the trained detector) with embedding-based diversity (k-means++/coreset on image embeddings). This is the same two-stage structure as PPAL and Lightly CORAL, implemented simply.
- Differentiator: PPAL-style difficulty-calibrated per-class uncertainty, and disagreement between SAM 3 and the user's trained model (or the VLM verifier) as a committee signal, conceptually similar to committee methods (arXiv 2308.08476). Show random-baseline comparisons honestly. Reality-check studies show gains are modest, so position active learning as "smarter queue ordering", not magic.

### Gaps
- "ALFA" (named in the brief) could not be identified or sourced. No claims are made about it.
- No study was found on whether active learning gains persist when the initial labels come from strong foundation-model pre-labels (SAM 3 / Grounding DINO). This is an open question relevant to LabelDesk.
- Encord Active's current (2025-2026) maintenance status and its exact acquisition functions were not verified.
