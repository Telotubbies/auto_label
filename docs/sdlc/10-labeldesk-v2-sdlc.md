---
title: "LabelDesk v2 SDLC: Model Hub, Auto-label, Playground, CCTV Streams"
category: "SDLC"
order: 20
status: "Draft"
---

# LabelDesk v2 SDLC: Model Hub, Auto-label, Playground, CCTV Streams

| Field | Value |
| --- | --- |
| SDLC Phase | 1-7 (all) |
| Status | Draft, awaiting approval |
| Audience | Developers reviewing the final demo |
| Last Updated | 2026-10-31 |
| Builds on | `apps/` (LabelDesk v1), [labeldesk-plan.md](../labeldesk-plan.md) |
| Demo date | 2026-11-01 |

---

## Phase 1: Planning

### 1.1 Intent

LabelDesk v1 is a Roboflow-style labeling SaaS (`apps/`), but its ML is hard-wired: auto-label is SAM 3.1 only and training is Ultralytics YOLO only. v2 turns the ML side into a **pluggable model hub** so that *any* vision model (detectors, segmenters, open-vocabulary models, and 7B vision-language models) can be used for four things through one interface:

1. **Auto-label** dataset images.
2. **Train** on a dataset version.
3. **Test** in a playground (single image / video, side-by-side comparison).
4. **Run continuously** on CCTV / RTSP streams with events and alerts.

### 1.2 Audience and success

The audience is developers watching a final demo. They want to see **the whole process end to end**, not slides:

> upload images → auto-label (SAM 3.1 *or* another model) → review → version → pick any model family and train → test in playground → attach to a CCTV stream → see live detections and events → push a bad frame back into the dataset.

Success = that loop runs live on the demo machine without manual patching.

### 1.3 Goals / non-goals / anti-goals

| Type | Item |
| --- | --- |
| Goal | One adapter interface; every model plugs in once and works in all four modes |
| Goal | Train page lists model families (YOLO, RT-DETR, YOLO-World, RTMDet, RTMDet-Ins), not just YOLO sizes |
| Goal | VLM (7B, 4-bit) served by **vLLM**, usable for auto-label (grounding), playground Q&A, and stream checks |
| Goal | CCTV stream: live overlay preview, event timeline, snapshot → dataset. The feature must be fully supported, but the demo only runs it for minutes; 24/7 operation is not tested |
| Non-goal | Billing, email, multi-tenant hardening, horizontal scale, HA (demo only) |
| Non-goal | Full NVIDIA TAO Toolkit integration |
| Non-goal | Training VLMs (VLMs are inference-only) |
| Anti-goal | Demo crashes from GPU OOM because two models fight over 12 GB VRAM |
| Anti-goal | A model listed in the UI that silently fails; unavailable adapters must show as disabled with a reason |

### 1.4 Constraints

| Constraint | Value / consequence |
| --- | --- |
| Hardware | 1× RTX 3080 Ti **12 GB VRAM**, 32 GB RAM, i5-13500, Windows 11 |
| VLM runtime | **vLLM** (OpenAI-compatible server). vLLM has no native Windows build → runs in **WSL2** (or Docker Desktop with GPU) |
| VLM quantization | 4-bit (AWQ/GPTQ, which is vLLM's mature 4-bit path) |
| Timeline | ~1 day to demo |
| Codebase | Extend `apps/` (FastAPI + React 19 + DB job queue + `labeldesk-worker`), do not rewrite |

---

## Phase 2: Requirements

### 2.1 Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | Model registry: list built-in zoo models, in-platform trained models, uploaded weights, and VLMs, each with `capabilities` (detect / segment / classify / open-vocab / vqa) and `available` + `reason` | P0 |
| FR-2 | Auto-label job accepts `model_ref` + class prompts; providers: SAM 3.1 (primary geometry), YOLO-World, trained models. VLM roles: **verifier** (crop → yes/no keep), **prompt parser** (free text → short noun phrases → SAM 3.1), and rough grounding whose boxes are always refined by SAM 3.1 (3.3). Preview on 3–5 images before the batch runs | P0 |
| FR-3 | Train page: pick family → variant → hyperparameters; families: Ultralytics YOLO (v8/11/26), RT-DETR, YOLO-World | P0 |
| FR-4 | Apache-2.0 families: RF-DETR N–L (`rfdetr` package) and D-FINE / RT-DETRv2 (HF Transformers) as P1; RTMDet / RTMDet-Ins via MMDetection as P2 | P1 / P2 |
| FR-4b | Every registry model carries a `license` (e.g. `AGPL-3.0`, `Apache-2.0`) shown as a badge on Train and Models pages | P0 |
| FR-5 | Playground: upload image or short video, run 1-3 models side by side, show overlay, latency, FPS; VLM free-text question box | P0 |
| FR-6 | Streams: create stream (RTSP URL or video file, model, sample FPS, zones, rules); start/stop; live annotated preview | P0 |
| FR-7 | Stream rules: object count threshold, zone intrusion, line crossing, dwell time per track, VLM yes/no question every N seconds (e.g. "is anyone without a helmet?") → event | P0 (count, zone, line), P1 (dwell, VLM) |
| FR-8 | Event timeline with snapshot; "send to dataset" adds the frame to the project for labeling | P0 |
| FR-9 | Export trained Ultralytics model to TensorRT engine (NVIDIA fast path) and use it in playground/streams | P1 |
| FR-10 | Upload custom weights (`.pt` Ultralytics, MMDet config + checkpoint) as a registry model | P2 |

### 2.2 Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-1 | Stream processing ≥ 5 FPS (measured in the stream loop: inference + annotate + JPEG encode) with a YOLO-s model on the 3080 Ti; preview latency < 1.5 s |
| NFR-2 | Never exceed 12 GB VRAM: a GPU scheduler enforces budgets (see 3.6) |
| NFR-3 | A stream survives RTSP drops: reconnect with backoff plus a frozen-frame watchdog, status shown in UI |
| NFR-4 | Adding a new model family = one adapter file + registry entry, no changes to routers or UI |
| NFR-5 | Unified prediction schema for all adapters (see 3.3) |

---

## Phase 3: Design

### 3.1 Architecture

```text
 Browser (React)
   │  Auto-label · Train · Models · Playground · Streams · Events
   ▼
 API process (FastAPI, apps/api, single uvicorn process, no --reload)
   ├─ routers (sync playground predict, MJPEG, CRUD)
   ├─ GPU scheduler (VRAM ledger, LRU evict, exclusive training)
   ├─ Adapter registry  apps/api/app/adapters/
   │    ultralytics │ sam3 │ vlm (HTTP→vLLM) │ mmdet │ tensorrt
   ├─ embedded job worker thread (existing): version, export, train, autolabel
   └─ StreamManager: one thread per running stream (not a queued job)
        │                                   DB (SQLite) ── files (LD_DATA_DIR)
        ▼
 vLLM server (separate process, :8000, OpenAI API)
 Qwen2.5-VL-7B-Instruct-AWQ
```

**Everything runs in one API process on the demo machine**, so a single scheduler sees every loaded model. The existing job queue, remote-worker protocol (`/claim`, `/progress`, `/complete`, `/fail`) and Roboflow-style prediction format are reused. The pip worker (`apps/worker`) stays as it is for remote `train` / `autolabel`; porting the adapters into it is roadmap work (Phase 7).

### 3.2 Adapter interface

Every model family implements one class in `apps/api/app/adapters/`; `services/ml.py` and `services/segment.py` become thin wrappers over them so v1 call sites and tests keep working:

```python
class Adapter(Protocol):
    family: str                       # "ultralytics" | "sam3" | "vlm" | "mmdet" | "tensorrt"
    def probe(self) -> Availability   # installed? weights present? server reachable? VRAM need
    def capabilities(self, ref) -> set[str]
    def load(self, ref) -> Handle     # cached, LRU, GPU-scheduler-aware
    def predict(self, h, image, *, classes=None, prompt=None, conf=0.4, iou=0.5) -> Prediction
    # optional
    def train(self, ref, dataset_dir, opts, on_epoch, should_stop) -> TrainResult
    def export(self, ref, fmt) -> Path
```

| Family | Models | predict | train | Notes |
| --- | --- | --- | --- | --- |
| `ultralytics` | YOLOv8/11/26 n–x (det/seg/cls), RT-DETR-l/x, YOLO-World-s/m/l | ✓ | ✓ | `YOLO`, `RTDETR`, `YOLOWorld` classes; YOLO-World uses `set_classes()` for open-vocab |
| `sam3` | SAM 3.1 | ✓ (text/box prompt → polygons) | — | wraps existing `services/segment.py` |
| `vlm` | Qwen2.5-VL-7B AWQ (default), any vLLM-served VL model | ✓ (grounding → boxes; VQA → text) | — | HTTP client to vLLM; no torch in the worker process |
| `mmdet` | RTMDet-t/s/m, RTMDet-Ins-t/s/m | ✓ | ✓ | needs its own env (mmcv/torch pin); dataset = existing COCO export |
| `tensorrt` | engines exported from Ultralytics models | ✓ | — | `model.export(format="engine", half=True)` |
| `rfdetr` (P1) | RF-DETR N/S/M/L (det/seg) | ✓ | ✓ | Apache-2.0 for N–L; XL/2XL are under Roboflow's own license and not offered |
| `hf` (P1) | D-FINE, RT-DETRv2 via HF Transformers | ✓ | ✓ | Apache-2.0; trains from the cached COCO export |

**Licensing.** Everything in the `ultralytics` family (YOLO, and RT-DETR / YOLO-World *as packaged by Ultralytics*) is AGPL-3.0 or a paid Enterprise license, and Ultralytics states this covers SaaS use and trained weights. The demo uses it freely (internal, not offered to users). For a public SaaS the Apache-2.0 families become the default, and `ultralytics` is "bring your own license" or runs only in the user's own pip worker. The final call needs legal review (Decisions).

`probe()` results feed the registry so the UI shows unavailable models greyed with the reason (e.g. "vLLM server not reachable at :8000", "mmdet not installed on this worker").

### 3.3 Unified prediction schema

Extends v1's Roboflow-style output (`services/ml.py:predict`):

```json
{
  "model": "ultralytics:yolo11s",
  "image": {"width": 1920, "height": 1080},
  "time": 0.021,
  "predictions": [
    {"class": "person", "class_id": 0, "confidence": 0.91,
     "x": 410.5, "y": 300.0, "width": 120.0, "height": 340.0,
     "points": [{"x": 0, "y": 0}], "track_id": 7}
  ],
  "text": "optional VLM answer"
}
```

`points` only for segmenters, `track_id` only in streams, `text` only for VLMs. `ml.to_annotations()` keeps converting this into editor annotations.

**Box-only model on a segmentation project** (RT-DETR, YOLO-World, detect-only YOLO): when SAM 3.1 is available, each box is passed to SAM as a box prompt and saved as a polygon. Otherwise the box is saved as a bbox annotation. The auto-label dialog states which of the two will happen.

**VLM boxes on any project type** are always refined: each box goes to SAM 3.1 as a box prompt and the mask (segmentation) or the mask's bounding box (detection) replaces it. VLM grounding is loose (good at IoU 0.5, poor at IoU 0.9), so raw VLM boxes are never saved as-is. If SAM is unavailable the VLM provider is disabled for auto-label. Every auto-label annotation carries `source` (`sam3`, `vlm+sam3`, `trained:<id>` …); `vlm+sam3` items sort to the top of Review.

### 3.4 VLM via vLLM

- Serve (WSL2):

  ```bash
  VLLM_SERVER_DEV_MODE=1 vllm serve Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
    --host 127.0.0.1 --port 8000 --quantization awq \
    --max-model-len 4096 --gpu-memory-utilization 0.55 --max-num-seqs 4 \
    --limit-mm-per-prompt '{"image": 1}' \
    --mm-processor-kwargs '{"max_pixels": 589824}' \
    --enable-sleep-mode
  ```

  `max_pixels` ≈ 768×768 caps image tokens on 12 GB. `VLLM_SERVER_DEV_MODE=1` is required for the sleep endpoints, which are dev-mode endpoints, so vLLM binds to **127.0.0.1 only**. Pin a vLLM release with Qwen2.5-VL support at setup time.
- Weights ≈ 6–7 GB at 4-bit; utilisation 0.55 ≈ 6.6 GB cap, which leaves ~4.5 GB for SAM/YOLO.
- **Structured output:** use the OpenAI-compatible `response_format: {"type": "json_schema", ...}` or `extra_body={"structured_outputs": {...}}`. The old `guided_json` / `guided_choice` parameters were **removed in vLLM v0.12.0**; code samples using them will fail.
- **Grounding:** JSON schema `[{"label": enum(class names), "bbox_2d": [x1,y1,x2,y2]}]`, so out-of-class labels are impossible. Coordinates are absolute pixels of the resized input (`smart_resize`, factor 28); the adapter rescales them to the original image, then SAM 3.1 refines them (3.3). `confidence = 0.5` (VLMs give no calibrated score); the `conf` threshold is **not** applied to VLM output and the UI hides the slider for VLMs. Schema-constrained output makes parse failures rare; a failure still returns an empty result.
- **Verify:** crop each candidate (with margin) → `structured_outputs: {"choice": ["yes", "no"]}` `"Is this a {class}?"` → drop "no". Used after SAM/YOLO-World auto-label when the user ticks "VLM verify".
- **Prompt parser:** free-text request ("workers not wearing helmets near the forklift") → JSON list of short noun phrases → SAM 3.1 text prompts.
- **VQA (playground):** free-text answer → `text`. **Stream rule:** `choice: ["yes", "no"]`, no token parsing.
- Fallback: if Qwen 7B misbehaves, switch the env var to `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`, which fits more easily.

### 3.5 Streams

```text
RTSP / file ─► Grabber (OpenCV, own thread, keeps latest frame only)
            ─► sampler (N fps) ─► adapter.predict ─► tracker (ByteTrack via ultralytics `track`)
            ─► rule engine ─► events (DB row + snapshot JPEG)
            ─► annotated JPEG ─► in-memory latest-frame slot (same process)
Browser ◄── GET /api/ws/{ws}/streams/{id}/mjpeg?token=…  (multipart/x-mixed-replace)
```

- Runs in the API process under **StreamManager** (one thread per running stream), not in the job queue, so streams never block other jobs and can be paused by the scheduler.
- Stream models are limited to the families that support tracking: `ultralytics` and `tensorrt`. The VLM joins only through the VLM rule. SAM, VLM and MMDet are not offered as the stream's main model.
- Zone test uses the **bottom-centre point** of the box (feet position) inside the zone polygon. A count rule counts track IDs present in the current frame.
- MJPEG auth uses a token in the query string (`<img>` can't send headers). The token is signed, bound to the stream, and valid for 12 h. Expiry is checked only when the connection opens.
- Sources: an RTSP/HTTP URL, **no SSRF filter for streams** (LAN cameras must be reachable, demo only), or an uploaded video (`POST .../streams/upload-video`, stored under `LD_DATA_DIR/videos/`, looped).
- On restart, streams are not auto-resumed: every stream starts `stopped`.

- **Stream** row: `id, project_id, name, source (rtsp url | uploaded video), model_ref, sample_fps, zones (polygons, normalized), rules (JSON), status, last_error, worker_id`.
- **StreamEvent** row: `id, stream_id, ts, rule, summary, snapshot_path, predictions`.
- Rules (P0): `count(class) >= k for t seconds`, `class enters zone`, `track crosses line` (direction in / out / both, anchor = bottom-centre, a track counts once per crossing). P1: `dwell(class, zone) > t seconds` per track, `vlm_question every N s` (yes → event). Events are de-duplicated with a cooldown.
- Reconnect: exponential backoff 1→30 s; status `reconnecting` is shown in the UI.
- **Watchdog**, separate from reconnect: if the grabber delivers no new frame for 10 s, or the same frame hash repeats for 10 s, the capture is torn down and reopened. RTSP stacks are known to hang without raising errors.
- Video files loop, so the demo does not depend on a real camera. An RTSP phone app (e.g. IP Webcam) serves as the live source.
- "Send to dataset" copies the snapshot into the project as a new unlabeled image (optionally pre-labeled with the stream's predictions).

### 3.6 GPU scheduler (12 GB budget)

| Resident | VRAM (approx.) | Notes |
| --- | --- | --- |
| Windows desktop | ~0.8 GB | |
| vLLM (Qwen2.5-VL-7B AWQ) | ≤ 6.6 GB | capped by `--gpu-memory-utilization` |
| SAM 3.1 | ~3–4 GB | loaded on demand |
| YOLO / RT-DETR inference | 0.3–1.5 GB | |
| Ultralytics training | 3–8 GB | depends on model/batch |

Policy: the worker keeps a VRAM ledger per loaded handle and evicts the LRU handle before loading a new one. **Training is exclusive**: before a train job, the worker unloads SAM and puts vLLM to sleep (`POST /sleep?level=1`, which moves weights to CPU RAM and frees the KV cache; check `GET /is_sleeping`; requires `VLLM_SERVER_DEV_MODE=1` + `--enable-sleep-mode`, see 3.4; fallback: stop the vLLM process), then calls `POST /wake_up` afterwards. Streams pause while training (state shown in the UI). The scheduler controls the local GPU only; remote pip workers manage their own GPU. If sleep mode fails in the Phase 5 smoke test, the default VLM becomes **Qwen2.5-VL-3B-AWQ** and vLLM is stopped/started around training (≈1 min stall, announced in the UI). Measured numbers replace these estimates during Phase 5.

**Verification-box measurements (2026-11-02, real AMD GPU — not the RTX 3080 Ti demo target).** Owner hardware: AMD Radeon RX 7800 XT 16 GB through WSL Ubuntu 24.04, ROCm 6.4.1, 47 GB host RAM. SAM 3.1 (bf16) took 3.4 GB and 2.2 s for a 1477×1108 frame (five person masks, scores ≈0.93). Gate-camera stream runs, one row per run: (a) the 60 s smoke window took 30 FPS samples and reached min 9.5 / avg 9.9 FPS (frame and detection counts were not recorded for this window); (b) a separate 20 s sample produced 470 frames and 1,813 detections at ≈10.0 FPS. Peak dedicated VRAM, sampled from the Windows GPU counters because `nvidia-smi` does not exist on this box, was **8,287 MiB** with SAM + YOLO26n + desktop. A YOLO26s run (24 images: 18/4/2 train/valid/test, batch 4, 640 px, 1 epoch) trained in 304 s and evaluated in 7 s (mAP50 0.321, mAP50-95 0.285). vLLM 0.11.1 on ROCm reports sleep mode as unsupported (`Platform.is_sleep_mode_available` is CUDA-only), so `/sleep` and `/wake_up` are unavailable; the smoke reports the sleep/wake/train check as FAIL and training is verified separately after stopping vLLM. A Qwen2.5-VL-3B bf16 load restarted the WSL VM once under load; the 7B AWQ path did not start in the owner's env (torch/triton ABI mismatch), so VLM grounding is still unverified on this box. Fill the RTX 3080 Ti numbers (vLLM ≤ 6.6 GB, sleep/wake times) on the demo target.

**Rehearsal (spec 1.2 loop).** BLOCKED on the verification box: no vLLM server ever served a model (the 3B bf16 load restarted the WSL VM; the 7B AWQ path failed to import in the owner env), so the seed → VLM→SAM auto-label → train → stream → playground loop was never run end to end and its wall time is unknown. The legs were timed separately: SAM text auto-label 76.2 s for 596 annotations; YOLO26s 1 epoch, 304 s train + 7 s evaluate; gate stream 60 s at 9.5/9.9 FPS. The owner or Integrator must run `python tools/demo_smoke.py` twice on the RTX 3080 Ti demo target and record both timings here before the demo.

### 3.7 Data model changes

- `TrainedModel`: add `family` (`ultralytics` | `rfdetr` | `hf` | `mmdet`), `variant` (e.g. `rtdetr-l`), `license`, `runtime_refs` (e.g. `{"pt": ..., "engine": ...}`).
- New `RegistryModel` (zoo + uploaded + VLM): `id, workspace_id (nullable = global), family, variant, name, capabilities, license, source, weights`.
- Annotations gain `source` (who produced it: `human`, `sam3`, `vlm+sam3`, `trained:<id>`) and keep `confidence`; a human edit sets `source = human`. This feeds Review ordering and the automation-efficiency metric (share of AI labels accepted unchanged).
- New `Stream`, `StreamEvent` (3.5).
- `Job.kind` gains `infer_video`, `export_engine` (local only; not added to `REMOTE_JOB_KINDS`).
- `model_ref` string format everywhere: `<family>:<variant>` for zoo/VLM models (e.g. `ultralytics:rtdetr-l`, `vlm:qwen2.5-vl-7b`) and `trained:<id>` for in-platform models. Old endpoints that take a model id keep their parameter, and `model_ref` is an added optional field. Existing `TrainedModel` rows default to `family = "ultralytics"`.
- Migration: the repo uses `create_all` only (no Alembic). New tables are created automatically. New columns are added by a small idempotent `ALTER TABLE … ADD COLUMN` helper in `bootstrap.py`. The demo DB is disposable and is re-seeded by task 8.
- Credits: playground, stream and VLM calls are **not** charged (demo). Roles: Admin creates/starts/stops streams; everyone in the project can view.

### 3.8 API additions

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/ws/{ws}/registry` | all models + availability + capabilities |
| GET | `.../train/options` | becomes families → variants (replaces sizes) |
| POST | `.../train` | body adds `family`, `variant` |
| POST | `.../autolabel` | body adds `model_ref`, `prompts` |
| POST | `/api/ws/{ws}/playground/predict` | image + `model_refs[]` (≤3) + optional `prompt` |
| POST | `/api/ws/{ws}/playground/video` | short video → job → annotated MP4 + per-frame JSON |
| CRUD | `.../streams`, `POST .../streams/{id}/start` and `/stop` | streams |
| POST | `.../streams/upload-video` | video file source |
| GET | `.../streams/{id}/mjpeg?token=`, `.../streams/{id}/events` | live view, timeline |
| POST | `.../streams/{id}/events/{eid}/to-dataset` | active learning |
| POST | `.../models/{mid}/export` | TensorRT engine |

### 3.9 UI changes

- **Train:** family cards (YOLO, RT-DETR, YOLO-World, RF-DETR, D-FINE, RTMDet, RTMDet-Ins) → variant chips → hyperparameters; each card has a license badge; disabled cards show the reason.
- **Auto Label dialog:** model dropdown from registry (filtered to detect/segment/open-vocab), prompt list prefilled from class names, "VLM verify" checkbox, free-text box for the prompt parser. **Preview** runs on 3–5 sample images and shows instance counts per class before the batch starts; a batch that produces 0 annotations is not charged.
- **Playground (new):** drop image/video, choose up to 3 models, results side by side with latency; VLM question box.
- **Streams (new):** list with status dots; detail page = live MJPEG + zone editor (draw polygons on a frame) + rules form + event timeline with "send to dataset".
- **Models:** shows family/variant badges and an "Export TensorRT" button.

### 3.10 ML pipelines (SaaS view)

Four pipelines share one lineage chain. Every artifact records the ID of the artifact it came from, so any prediction can be traced back to the images and settings that produced it:

```text
Images ─► [P1 Ingest] ─► Dataset (live, editable) ─► [P2 EDA / Health] ─► report + warnings
                                   │
                                   ▼
                        [P3 Preprocess + Version] ─► Version (frozen, hashed)
                                   │
                                   ▼
                              [P4 Train] ─► Model (weights + eval + recipe)
                                   │
                                   ▼
                            [P5 Inference] ─► auto-label · playground · API · streams
                                   │
                                   └──► low-confidence frames / events ─► back to Dataset (active learning)
```

Legend: **[v1]** already exists in `apps/`, **[demo]** built for the demo, **[later]** designed, built after the demo.

#### P1 Ingest

| Step | Detail | Status |
| --- | --- | --- |
| Receive | Drag-drop files/folders/zip, upload API, URL import (SSRF-safe), stream snapshot | [v1] |
| Validate | Decode check, pixel-bomb and size limits, filename sanitising | [v1] |
| Normalise | EXIF auto-orient, convert to RGB, keep original file untouched | [v1] |
| Dedupe | Exact: SHA-256 (client and server). Near-duplicate: perceptual hash (pHash, Hamming ≤ 6), flagged rather than dropped | exact [v1], pHash [later] |
| Metadata | width, height, file size, brightness, blur score (variance of Laplacian), stored on the `Image` row for EDA | w/h [v1], rest [later] |
| Import labels | COCO, YOLO, VOC, class-per-folder → internal schema (normalized bbox/polygon), unknown classes auto-created | [v1] |
| Assign | split (auto / keep / fixed), batch, tags | [v1] |

#### P2 EDA / Dataset Health Check

Computed per project, cached and invalidated by an annotation signature (existing `_analytics` cache). Large projects compute it as a background job.

| Group | Checks | Output / warning |
| --- | --- | --- |
| Volume | images per split, labeled vs. null, annotations per image | "valid split has < 30 images" |
| Classes | instance count per class, images per class, imbalance ratio (max/min) | imbalance warning when ratio > 10 [v1] |
| Geometry | box size buckets (COCO small < 32², medium, large) relative to train `imgsz`, aspect-ratio histogram, object-centre heatmap [v1] | "41 % objects are small at 640 → try 1024 or tiling" |
| Images | dimension histogram [v1], brightness/blur distribution | "12 images are very blurry" (link to filter) |
| Label quality | boxes < 4 px, out of bounds, zero-area polygons, same-class duplicates with IoU > 0.9, images with an unusually high object count | fix list with links into the editor |
| Leakage | near-duplicate pairs across train/valid/test (also enforced in P3 step 3) | "8 near-duplicate pairs span train and valid" |
| Possible missing boxes | SAM 3.1 / trained-model predictions with no matching GT (IoU < 0.3) on approved images. Research on COCO/KITTI re-annotation shows missing boxes are the dominant label error | "23 likely unlabeled objects in 14 images" → open in editor with the suggestion shown [demo] |

The health check also produces **recommendations**: training `imgsz` from the median object size, preprocessing toggles (grayscale when colour variance is low, tiling when there are many small objects), and augmentations to apply (for example flip only when the classes are left/right symmetric). They are prefilled into P3 and P4 forms as suggestions, never applied silently.

Demo scope: v1 checks plus box-size buckets, label-quality checks, possible-missing-box check and recommendations. Leakage uses pHash at version time [demo]; embedding-based leakage is [later].

#### P3 Preprocess + Version

A version is an **immutable snapshot**. Its `manifest.json` stores the config, the source image IDs and SHA-256s, and a `version_hash` over all of these, so the same inputs always produce the same version.

1. **Select:** approved images (`status = done`), optional filters by tag, class or batch. Null images are dropped when `filter_null` is on [v1].
2. **Class ops:** remap, merge, or drop classes for this version only (the live dataset is unchanged) [later].
3. **Split:** keep existing, or rebalance train/valid/test. v1 shuffles randomly; v2 **stratifies by class** (iterative stratification over each image's class set) so that rare classes appear in valid [demo]. **Near-duplicate groups (pHash Hamming ≤ 6, which catches stream frames) are assigned to one split together**, so test never contains a near-copy of a train image [demo].
4. **Preprocess, applied to every split:** auto-orient, resize (stretch / fit with letterbox / fill crop) [v1], grayscale [v1], contrast (CLAHE) [v1], tiling (N×M with overlap; annotations are clipped and boxes smaller than 20 % of their original area are dropped) [later].
5. **Augment, train split only, ×1–5 outputs:** flip, rotate, crop, brightness, exposure, blur, noise, hue, mosaic-style cutout and similar [v1 has 10]. Augmentation never touches valid/test, which keeps evaluation honest [v1].
6. **Write:** images + `manifest.json` [v1]. Format exports (YOLO, COCO, VOC …) are created on demand and cached per format under `versions/<id>/exports/<fmt>/` so every training family reuses them [demo].
7. **Preprocess recipe:** the resize / grayscale / contrast settings are saved as `recipe.json` on the version. The model inherits it and P5 replays it at inference, so the model always sees inputs the way it saw them in training [demo].

Note that training-time augmentation inside the trainer (Ultralytics mosaic, HSV, scale and so on) is separate from P3's offline augmentation. P4 exposes it as the "online augmentation" preset (default / light / off).

#### P4 Train

A training run is a job with a fixed stage sequence. Each stage writes a status line to the job log, which the UI shows as a stepper.

| # | Stage | Detail |
| --- | --- | --- |
| 1 | Queue | Job created with `family`, `variant`, hyperparameters and `version_id`. Credits checked (v1); the user sets a max-credit / max-time cap per run, and training stops at the cap with the best checkpoint kept. Queue priority FIFO per workspace [v1] |
| 2 | Acquire GPU | Scheduler: wait for an exclusive GPU lease, unload SAM, put vLLM to sleep, pause streams (3.6) [demo] |
| 3 | Materialise data | From the version's export cache: `ultralytics` → YOLO txt + `data.yaml` (classify → folder layout); `mmdet` → COCO JSON + generated config [demo / mmdet later] |
| 4 | Resolve weights | Local pretrained (`yolo26_ppe/models/pretrained`), else hub name, or a previous model's `best.pt` when the user chooses "continue from model" (fine-tune chaining) [demo] |
| 5 | Build config | family defaults ⊕ health-check suggestions ⊕ user values. Batch `auto` uses the trainer's auto-batch (~60 % VRAM). AMP on. Seed fixed. Early stopping `patience`. Final config saved as `train_config.json` |
| 6 | Train | Adapter `train()` with callbacks: per-epoch metrics normalised to common keys (table below) → `/progress` → live charts [v1]. Cancel = stop at epoch end [v1]. Checkpoints `last` and `best`. A no-progress watchdog fails the job if no epoch reports within 3× the median epoch time. A failed or stopped run can **resume** from `last` [demo] |
| 7 | OOM guard | CUDA OOM in the first epoch → retry once with half the batch, logged in the job [demo] |
| 8 | Evaluate | **One evaluator for every family**: run `adapter.predict` on the **test** split (fallback valid), score the raw predictions with pycocotools (or faster-coco-eval) → the 12 COCO metrics, per-class AP, confusion matrix at the F1-optimal confidence (stored as the model's default threshold), PR and F1 curves, gallery of the worst images (FP/FN). Family-native validation numbers (e.g. Ultralytics `val()`) are shown only as training charts, never on the leaderboard. TIDE error breakdown (cls / loc / both / dupe / bkg / missed) [P1] |
| 9 | Register | `TrainedModel` = weights + `metrics.json` + eval plots + `train_config.json` + `recipe.json` + `version_hash` + env (torch, CUDA, family lib versions) |
| 10 | Export (optional) | ONNX / TensorRT engine (`half=True`) as an extra `runtime_ref` [P1] |
| 11 | Release | Free GPU, wake vLLM, resume streams, status `ready`, audit log [demo] |

Normalised metric keys, so the UI and leaderboard handle every family the same way:

| Common key | Ultralytics | MMDet |
| --- | --- | --- |
| `train/loss` | sum of `tloss` | `loss` |
| `val/map50` | `metrics/mAP50(B)` or `(M)` | `coco/bbox_mAP_50` or `segm_mAP_50` |
| `val/map5095` | `metrics/mAP50-95(B)` or `(M)` | `coco/bbox_mAP` or `segm_mAP` |
| `val/precision`, `val/recall` | `metrics/precision(B)`, `metrics/recall(B)` | computed in eval stage |

**Model leaderboard** [demo]: all models of a project evaluated on the same version's test split, sortable by mAP and by latency (ms/image measured during evaluate on the demo GPU). Models trained on different versions are marked "not directly comparable".

#### P5 Inference

One path serves auto-label, playground, the hosted API and streams. Only the consumer at the end differs.

```text
input ─► decode + EXIF orient ─► replay model recipe (grayscale, contrast; resize is left to the adapter's letterbox)
      ─► scheduler.lease(model)  (load or LRU-evict, warm-up on first load)
      ─► adapter.predict(conf, iou, classes | prompt)
      ─► postprocess: NMS (class-aware; class-agnostic optional), rescale to original pixels,
                      mask → polygon (approxPolyDP, ε = 0.4 % of perimeter), map class ids → names
      ─► optional refine: box → SAM 3.1 box prompt → polygon (segmentation projects)
      ─► unified schema (3.3)
      ─► consumer
```

| Consumer | What happens after the schema |
| --- | --- |
| Auto-label (batch job) | Map class names → project classes (unknown names dropped or created, user choice); option to skip images that already have annotations; annotations saved with `source = model_ref` and `confidence`; images move to the Review column, never straight to Dataset; progress per image [v1 + demo] |
| Playground | Up to 3 models in parallel on the same image, returns schema + latency per model; threshold slider re-filters client-side without re-running [demo] |
| Hosted API | API key, Roboflow-style response [v1] |
| Stream | Tracker → rules → events → MJPEG (3.5) [demo] |

Defaults: `conf` = the model's F1-optimal threshold from evaluate (fallback 0.4); `iou` 0.5. VLM: no `conf` (3.4).

#### Active learning loop [demo]

Inference feeds the dataset back:

- Auto-label puts low-confidence predictions (< default threshold + 0.15) at the top of the Review queue.
- Streams: an event snapshot, or a frame where max confidence falls in the 0.3–0.5 "uncertain band", can be sent to the dataset (manual button for the demo; automatic sampling with a daily cap [later]).
- New labels → new version → retrain with "continue from model" → leaderboard shows whether the new model beats the old one on the same test split.

#### SaaS concerns across the pipelines

| Concern | Design |
| --- | --- |
| Tenant isolation | All files under `LD_DATA_DIR/<workspace>/…`; every job and model row carries `workspace_id`; signed file URLs [v1] |
| Reproducibility | `version_hash` + `train_config.json` + seed + env versions on every model |
| Lineage | image → version → model → predictions (`source = model_ref`) → events, all queryable from the model page |
| Quotas | credits per train/infer [v1]; per-workspace concurrent-job limit and GPU-minutes [later] |
| Observability | job log stages, per-epoch metrics, worker heartbeat, scheduler state (who holds the GPU) in an admin panel [demo: GPU holder badge in the header] |
| Storage lifecycle | export caches and `train_data` deleted after training [v1]; old versions' images kept while any model references them [later] |

---

## Phase 4: Implementation plan

Order is chosen so the end-to-end demo works as early as possible; P1 items come after.

| # | Task | Priority | Est. |
| --- | --- | --- | --- |
| 1 | Adapter protocol, registry (with `license`), prediction schema, annotation `source`; port `ml.py` (Ultralytics) and `segment.py` (SAM) into adapters with no behaviour change; v1 tests stay green | P0 | 2 h |
| 2 | Ultralytics families: RT-DETR + YOLO-World train/predict; `train/options` → families; Train page family cards with license badges; run cap + resume | P0 | 2.5 h |
| 3 | vLLM setup in WSL2 (dev mode, 127.0.0.1, max_pixels) + `vlm` adapter: schema-constrained grounding, verify, prompt parser, VQA + probe | P0 | 2.5 h |
| 4 | Auto-label with `model_ref` (SAM / YOLO-World / trained / VLM→SAM) + dialog: dropdown, preview, VLM verify, free-text prompt | P0 | 1.5 h |
| 5 | Playground image endpoint + page (side by side, VLM question) | P0 | 1.5 h |
| 6 | Streams: models, StreamManager, grabber/sampler/tracker, watchdog, MJPEG, page with live view + timeline, count/zone/line rules, to-dataset | P0 | 4.5 h |
| 7 | GPU scheduler: ledger, LRU evict, exclusive training with vLLM sleep | P0 | 1.5 h |
| 7b | Pipelines (3.10) demo items: stratified split + pHash leakage grouping, per-format export cache, `recipe.json` replay, train stage stepper + OOM retry + no-progress watchdog, single pycocotools evaluator on test (12 metrics, per-class AP, confusion matrix, F1-optimal threshold), model leaderboard, EDA box-size / label-quality / possible-missing-box checks + recommendations | P0 | 4 h |
| 8 | Demo script + seed (project, version, trained model, looping video stream) + pre-download weights: YOLO26 n/s/m (det/seg) are already in `yolo26_ppe/models/pretrained/`; RT-DETR-l, YOLO-World-s/m (+ its CLIP text encoder) and the vLLM model must be fetched once | P0 | 1 h |
| 9 | VLM stream rule + dwell rule | P1 | 1.5 h |
| 10 | TensorRT export (engine pre-built before the demo, persistent engine cache) | P1 | 1 h |
| 11 | `rfdetr` adapter (RF-DETR N–L) + `hf` adapter (D-FINE, RT-DETRv2) | P1 | 3 h |
| 12 | TIDE error breakdown on the evaluate page | P1 | 1 h |
| 13 | MMDet adapter (RTMDet, RTMDet-Ins) in separate env | P2 | 3 h |
| 14 | Playground video, custom weights upload | P2 | — |

P0 totals about 23 h, more than one working day. **Cut order if time runs short:**

1. Task 7 shrinks to "evict on load + stop vLLM before training".
2. Task 7b drops the leaderboard, EDA recommendations and possible-missing-box check (evaluate stays).
3. Task 6 drops the zone editor (rules use count only).
4. Task 5 drops side-by-side and shows one model at a time.

The auto-label → train → stream loop itself is never cut.

Execution: each task is handed to an implementation subagent with this document plus the task; the PM (main session) reviews each diff before the next task.

---

## Phase 5: Testing

| Level | What | How |
| --- | --- | --- |
| Unit | Prediction-schema conversion per adapter, VLM response handling (schema output, rescale from `smart_resize`, empty on failure), rule engine (count, zone, line crossing, cooldown), watchdog trigger, VRAM ledger eviction, pHash split grouping, evaluator against pycocotools reference numbers | pytest, no GPU (adapters mocked) |
| Contract | Every registered adapter: `probe()` returns a reason when unavailable, `predict()` output validates against the schema | pytest parametrised over registry |
| Integration | Existing `test_e2e` (1-epoch CPU YOLO) + auto-label with YOLO-World on 3 images; 1-epoch RT-DETR marked `@pytest.mark.slow` (GPU box only) | pytest |
| GPU smoke | On the 3080 Ti: vLLM up, VLM→SAM grounding on 5 images, SAM text auto-label, `/sleep?level=1` → `/is_sleeping` = true → train YOLO-s 3 epochs → `/wake_up` (sleep and wake times recorded), `nvidia-smi` peak < 11.5 GB | scripted checklist `tools/demo_smoke.py` |
| Stream check | Looping video for 5 min: ≥ 5 FPS, events fire, stop/start works, reconnect after killing an RTSP source once. Long-run (24/7) soak is out of scope for the demo | manual + log |
| Demo rehearsal | Full loop from 1.2 twice, timed | manual |

Exit criteria: P0 tests green, GPU smoke passes, one clean rehearsal.

---

## Phase 6: Deployment (demo machine)

1. **WSL2** (Ubuntu): NVIDIA driver on Windows, CUDA visible in WSL (`nvidia-smi`).
2. **vLLM** in a WSL venv (or `vllm/vllm-openai` container): the exact command in 3.4 (`VLLM_SERVER_DEV_MODE=1`, `--enable-sleep-mode`, `--host 127.0.0.1`, port 8000). Never expose port 8000 beyond localhost. Env `LD_VLM_URL=http://localhost:8000/v1`, `LD_VLM_MODEL=Qwen/Qwen2.5-VL-7B-Instruct-AWQ`.
3. **API + embedded worker in WSL2**, next to vLLM, because the working SAM 3.1 env (`sam3_auto_label/sam3_venv`, `run_*.sh`) is already Linux/WSL: `uvicorn app.main:app --host 0.0.0.0 --port 8010` (single process, no `--reload`), `LD_SAM_ENABLED=1`, `LD_TRAIN_DEVICE=0`, `LD_DATA_DIR` on the WSL filesystem (not `/mnt/e`, which is slow). API → vLLM is WSL-local `localhost:8000`.
4. **Web**: `npm run dev` on Windows or WSL. The browser on Windows reaches WSL services via localhost forwarding. The Vite proxy must not buffer the MJPEG route; if it does, the `<img>` points straight at `:8010`.
5. **MMDet (P1)**: separate WSL venv running a second `labeldesk-worker --adapters mmdet`, pulling only `mmdet` jobs.
6. **Pre-demo checklist**: models pre-downloaded (no network dependency), TensorRT engines pre-built into a persistent cache (first compile can take 15+ minutes), demo video in place, smoke script green, browser tabs pre-opened.

---

## Phase 7: Maintenance and roadmap

- Add families by dropping in an adapter: Grounding DINO / Florence-2 (auto-label), NVIDIA TAO models via exported ONNX/TensorRT.
- Multi-GPU / multi-worker scheduling, stream sharding across workers; port adapters into the pip worker.
- Alert sinks (LINE / webhook), event search.
- Data: S3/GCS/Azure connectors (BYO storage), video → frame extraction job, CVAT XML / Label Studio JSON import, embedding explorer (UMAP) and embedding-based leakage, Python SDK/CLI.

### 7.1 SaaS hardening

- RBAC at two levels (workspace: owner/admin/billing; project: manager/reviewer/labeler), custom roles later.
- API keys with scopes plus publishable (inference-only) keys; MFA; SSO (OIDC exists, add SAML/SCIM).
- Audit log covering logins, key use, exports, and **every view of stream footage**.
- Metering: GPU-seconds (train), stream-hours, AI calls (SAM / VLM), storage; per-workspace concurrent-job limits.
- Object storage + BYO bucket; MJPEG auth beyond signed tokens; re-enable the SSRF filter for streams outside self-hosted workers.
- Licensing outcome applied (Decisions): Apache-2.0 families as default, Ultralytics behind a license gate.

### 7.2 PDPA (Thailand) for CCTV

- Faces in CCTV footage count as personal data; biometric use falls under sensitive data (PDPA s.26), with fines up to THB 5 million.
- Per-project retention with automatic deletion of frames, snapshots and events.
- Face blurring before frames enter a dataset (default on for stream-to-dataset).
- No face recognition by default; any biometric feature requires explicit opt-in and a documented legal basis.
- Data processing agreement template (LabelDesk as processor), RTSP credentials encrypted at rest, data residency in Thailand as a selling point (competitors offer US/EU).
- Track the PDPC sector guidelines on CCTV analytics (draft, hearing April 2026).

### 7.3 Production ML

- Drift monitoring: embedding two-sample test between training data and recent stream frames → items pushed to the active-learning queue.
- Deployment aliases (`production`, `staging`) with rollback to a previous model version.
- Automatic active-learning sampling (uncertainty + diversity) with a daily cap.

---

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| vLLM + SAM + YOLO exceed 12 GB | Demo crash | Scheduler (3.6), vLLM utilisation cap, 3B fallback, exclusive training |
| vLLM sleep mode unsupported/buggy in WSL | Training can't free VRAM | Fallback: stop/start the vLLM process (slower, ~1 min) |
| MMDet/mmcv install fails against current torch | RTMDet not trainable | Isolated env; RTMDet is P1 and shows as "not installed" rather than breaking anything |
| VLM grounding boxes are loose / hallucinated | Weak auto-label demo | VLM boxes always refined by SAM 3.1; VLM used as verifier and prompt parser; SAM 3.1 stays the primary auto-labeler |
| vLLM API changes (`guided_*` removed in v0.12) | VLM adapter breaks on upgrade | Use `response_format` / `structured_outputs` only; pin the vLLM version |
| AGPL-3.0 of Ultralytics in a public SaaS | Forced source release or license fee | License field + badges now; Apache-2.0 families (P1); legal review before launch |
| RTSP camera flaky on demo day | Stream demo fails | Looping video file as the primary demo source |

---

## Decisions made by the author (review these)

- "NVIDIA YOLO" interpreted as **TensorRT export** of trained models (FR-9), not TAO Toolkit.
- Default VLM **Qwen2.5-VL-7B-Instruct-AWQ** (4-bit; it fits 12 GB alongside SAM and supports grounding).
- One API process hosts adapters, scheduler and streams (StreamManager threads, not queued jobs); the browser sees MJPEG from the API.
- Everything runs in WSL2 on one machine; remote-worker support is kept but not exercised.
- A box-only model on a segmentation project is refined into polygons by SAM 3.1 box prompts.
- Streams accept only tracking-capable models (Ultralytics, TensorRT); the VLM joins through a rule.
- Streams are fully built, but only verified for minutes, not 24/7.
- No credits charged for playground/stream/VLM; streams are Admin-managed.
- TensorRT, RF-DETR and D-FINE are P1; RTMDet / RTMDet-Ins moved to P2 (mmcv install risk, maintenance status unverified).
- **AGPL decision (needs legal review before launch):** the demo uses Ultralytics freely. For a public SaaS, choose between an Ultralytics Enterprise license, Apache-2.0 families as default with Ultralytics as bring-your-own-license, or open-sourcing the backend under AGPL.
- VLM is a verifier and prompt parser first; its boxes never reach the dataset without SAM 3.1 refinement.
- Leaderboard numbers come only from the shared pycocotools evaluator on the test split.
