# SAM 3.1 Auto-Labeling

Module for automatic annotation using **SAM 3.1** (Segment Anything Model 3.1) for PPE images with 6 classes

Takes raw images from `../data/raw/` → detects via text prompt → exports to COCO/YOLO and 9 other formats → stores at `../data/sam_outputs_ground_truth/`

## Structure

```text
sam3_auto_label/
├── src/                     # Core code (config, inference, batch_segment, exporters, tracker)
├── config/                  # YAML config for each dataset
├── sam3/                    # SAM 3.1 source code (vendored — do not modify)
├── checkpoints/             # SAM 3.1 model weights (auto-downloaded)
├── setup.py                 # Environment setup based on hardware (CUDA/ROCm/CPU)
├── requirements.txt         # dependencies (except torch, which is installed separately)
├── Dockerfile               # container for deployment
├── docker-compose.yml       # orchestration
├── RELEASE_NOTES_v1.0.0.md  # release notes
└── sam3_source_locked.zip   # snapshot of sam3/ (backup)
```

## Installation

```bash
cd sam3_auto_label
python setup.py              # full setup — create venv + install torch + download checkpoint
python setup.py --check      # check hardware only, install nothing
python setup.py --force-cpu  # force CPU-only
```

`setup.py` automatically detects hardware:
- GPU: NVIDIA CUDA / AMD ROCm / Apple MPS / CPU
- Selects the correct PyTorch index URL
- Downloads `sam3.1_multiplex.pt` from Hugging Face

## How to Run

```bash
# Use default config (config/ppe_6class.yaml)
python src/batch_segment.py

# Resume from checkpoint (if a previous run was interrupted)
python src/batch_segment.py --resume

# Start fresh (clear checkpoint)
python src/batch_segment.py --fresh

# Override threshold
python src/batch_segment.py --threshold 0.5
```

Or run via the main CLI: `../auto_label.sh --sam --batch <batch_name>`

## Key Features

- **Text-prompted segmentation** — uses class names as prompts; no manual bbox drawing required
- **GPU acceleration** — RLE encode + mask IoU NMS on GPU, BF16 autocast
- **Pipeline export** — overlaps CPU export with GPU inference → GPU utilization ~100%
- **Checkpoint/resume** — saves progress; can resume if the computer crashes mid-run
- **Multi-format export** — COCO, YOLO, VOC, LabelMe, CVAT, Label Studio, KITTI, CreateML, OpenImages, Supervisely, masks
- **Experiment tracking** — SQLite + JSON (no MLflow server required)
- **Visualization** — overlay image for every file (OpenCV, 10-50x faster than matplotlib)

## config

See `config/README.md` for details on each configuration file

Main config: `config/ppe_6class.yaml` — defines 6 classes, threshold, resolution, output format, and paths

## Notes

- `sam3/` is vendored SAM 3.1 source — **do not modify**; to update, download fresh from upstream
- `sam3_source_locked.zip` (63 MB) is a backup snapshot
- `checkpoints/` stores large model weights — included in `.gitignore` unless using Git LFS
- Paths in config are absolute paths for WSL2 (`/mnt/e/...`) — override with `--input`/`--output` when running elsewhere
