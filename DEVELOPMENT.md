# Development Guide

Fast-track guide for developers continuing this project. Read this first.

## 30-second overview

SAM 3.1 model that segments objects in images by text prompt. Two ways to use it:
1. **Batch CLI** — process a folder of images, write COCO/masks/viz, resume on crash
2. **REST API** (FastAPI) — send image, get back annotations (bbox + mask + score)

No web UI. No compliance checking. Pure detection + segmentation.

## Architecture (1 diagram)

```
config/ppe.yaml
      │
      ▼
┌─────────────────────────────────────────────────┐
│                  src/config.py                   │
│  Config dataclass + load/save YAML               │
│  gpu_ops, pipeline_export toggles                │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐      ┌─────────────────────┐
│  src/service.py  │      │ src/batch_segment.py│
│  FastAPI server  │      │  Folder processing  │
│  /segment /config│      │  checkpoint/resume  │
│                  │      │  pipeline export    │
└────────┬─────────┘      └──────────┬──────────┘
         │                           │
         ▼                           ▼
┌──────────────────────────────────────────────────┐
│              src/inference.py                     │
│  build_model() → Sam3Processor                   │
│  segment_image() → list of annotations           │
│  GPU RLE encode (robust_rle_encode)              │
│  GPU mask IoU NMS (perflib.mask_iou)             │
│  Single CPU-GPU sync (1 instead of 18)           │
│  OpenCV visualization (replaces matplotlib)      │
└──────────────────────┬───────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐      ┌─────────────────────┐
│ src/exporters.py │      │  src/tracker.py     │
│ COCO/YOLO/VOC/…  │      │  SQLite experiments │
│ RLE ↔ polygon    │      │  run tracking       │
└──────────────────┘      └─────────────────────┘
```

## File map (what to edit for what)

| Want to… | Edit |
|----------|------|
| Add/change detection categories | `config/ppe.yaml` → `categories` |
| Change confidence filtering | `config/ppe.yaml` → `threshold` per category or global |
| Toggle GPU ops / pipeline | `config/ppe.yaml` → `inference.gpu_ops` / `pipeline_export` |
| Change how masks are encoded | `config/ppe.yaml` → `annotation.segmentation_encoding` |
| Add a new output format | `src/exporters.py` → add function + register in `SUPPORTED_FORMATS` |
| Change model loading | `src/inference.py` → `build_model()` |
| Change segmentation logic | `src/inference.py` → `segment_image()` |
| Change GPU NMS / RLE | `src/inference.py` → `_gpu_nms()` / `masks_batch_to_rle_gpu()` |
| Change API endpoints | `src/service.py` |
| Change batch processing flow | `src/batch_segment.py` → `main()` |
| Change config schema | `src/config.py` (dataclass + loader + saver) |
| Change experiment tracking | `src/tracker.py` |

## Source files (6 files — clean)

```
src/
├── inference.py       23KB — GPU RLE + GPU NMS + OpenCV viz + segment_image
├── batch_segment.py   17KB — batch runner + pipeline export + prefetch
├── config.py          8.5KB — YAML loader with gpu_ops + pipeline_export
├── exporters.py       26KB — 11 output formats (COCO/YOLO/VOC/...)
├── tracker.py         8.7KB — SQLite experiment tracking
└── service.py         16KB — FastAPI REST API (optional, not needed for batch)
```

## Config schema

```yaml
categories:              # what to detect
- id: 1                  #   unique int
  name: person           #   COCO category name
  prompt: person         #   text prompt for SAM 3.1
  threshold: 0.7         #   -1 = use global, 0 = accept all, >0 = min score

inference:
  confidence_threshold: 0.25  # global default (used when category threshold = -1)
  resolution: 1008            # input image resize for model
  device: auto                # auto → CUDA > MPS > CPU
  gpu_ops: true               # GPU RLE encode + GPU mask IoU NMS
  pipeline_export: true       # overlap CPU export with GPU inference

annotation:
  bbox: true                  # include bounding boxes
  segmentation: true          # include masks
  segmentation_encoding: rle  # rle (compact) or polygon (outline)

output:
  formats: [coco]             # which dataset formats to export
  save_viz: true              # save visualization PNGs (OpenCV)
  input_dir: input
  output_dir: output

checkpoint:
  enabled: true               # save progress for resume
  auto_resume: true           # resume automatically if checkpoint exists
  clear_on_success: false     # keep checkpoint after successful run
```

## Run locally (WSL2 + AMD GPU — primary target)

```bash
# Install PyTorch ROCm
pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2
pip install -r requirements.txt

# Set ROCm env vars for RDNA3
export HSA_ENABLE_DXG_DETECTION=1
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1

# Batch process images
python src/batch_segment.py --fresh --input input/ --output output/
python src/batch_segment.py --resume        # continue after crash/stop

# Start API server (optional)
python src/service.py
# → http://localhost:8000/docs
```

## Run locally (Windows/Linux/macOS)

```bash
pip install -r requirements.txt
# Install torch for your hardware (CUDA / CPU)
python src/service.py
python src/batch_segment.py --fresh
```

## GPU optimization details

| Optimization | What it does | Impact |
|-------------|-------------|--------|
| OpenCV viz | Replaces matplotlib with cv2 drawing | 10-50x faster viz |
| GPU RLE encode | `robust_rle_encode` from SAM 3.1 perflib | RLE on GPU, no CPU sync |
| GPU mask IoU NMS | `perflib.mask_iou` (matmul, Tensor Core) | Faster + more accurate than bbox IoU |
| Single CPU-GPU sync | All 6 prompts run on GPU, 1 batched `.cpu()` at end | 1 sync instead of 18 |
| Pipeline export | `ThreadPoolExecutor` for save_coco + save_viz | CPU export overlaps GPU → 100% GPU util |
| Prefetch image load | Background thread loads next image | I/O overlaps with inference |

Measured on AMD RX 7800 XT (RDNA3, 16GB VRAM), WSL2, ROCm 6.2:
- Model inference: ~0.65s/image
- Total end-to-end: ~0.7s/image
- GPU utilization: ~100%
- 432 images: ~5 minutes

## Common tasks

### Add a new category

1. Edit `config/ppe.yaml` → add to `categories` list
2. No code change needed — categories are config-driven

### Add a new output format

1. Add export function in `src/exporters.py`
2. Add format name to `SUPPORTED_FORMATS` in `src/config.py`
3. Add row to README output formats table

### Debug detection on one image

```bash
python src/batch_segment.py --fresh --input input/ --output output/
# Check output/viz/{image}.png and output/coco/{image}.json
```

### Check what was detected

```python
import json
d = json.load(open('output/coco/0001.json'))
for a in d['annotations']:
    print(f"cat={a['category_id']} score={a['score']:.3f} bbox={a['bbox']}")
```

### Toggle GPU ops

```yaml
# config/ppe.yaml
inference:
  gpu_ops: false          # use CPU RLE + CPU bbox NMS (fallback)
  pipeline_export: false  # sequential export (GPU waits for CPU)
```

## Gotchas

1. **SAM 3.1 checkpoint has 4 missing keys** — `backbone.vision_backbone.convs.3.*`. Known issue, model still loads.

2. **CPU is slow** — ~30-40s/image at 1008px. GPU strongly recommended.

3. **`output/coco/{image}.json` is always written** — even if `coco` is not in `output.formats`. It's the internal checkpoint/resume cache.

4. **Threshold = 0 vs -1** — `0` means "accept all detections, no score filtering". `-1` means "use the global `inference.confidence_threshold`".

5. **`sam3/` is a git submodule** — the SAM 3.1 source code. Don't edit it unless necessary.

6. **`models/sam3/` is gitignored** — the 3.3GB checkpoint. Must be downloaded separately.

7. **Batch inference doesn't work** — SAM 3.1 `set_image_batch` merges images into one feature map. `forward_grounding` outputs `queries: [1, 200, 256]` regardless of batch size. Detections can't be mapped back to individual images. Use sequential per-image inference (already optimized to ~100% GPU util via pipeline).

8. **ROCm env vars required** — `HSA_ENABLE_DXG_DETECTION=1` and `TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1` for RDNA3 (RX 7800 XT).

9. **No compliance checking** — the system only detects and segments objects. It does not judge whether PPE rules are satisfied.

## Docker

```bash
# AMD ROCm (primary target)
docker compose --profile rocm up --build

# NVIDIA CUDA
docker compose --profile cuda up --build

# Inside container
docker compose exec ppe-segmentation-rocm python src/batch_segment.py --fresh
```

The checkpoint is mounted at `models/sam3/sam3.1_multiplex.pt`. Don't bake it into the image.

## Git workflow

```bash
git add <files>
git commit -m "Description of change

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
git push origin main
```
