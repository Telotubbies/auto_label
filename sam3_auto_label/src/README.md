# sam3_auto_label/src — Core Code

Python code for running SAM 3.1 auto-labeling in batch mode

## All Files

| File | Role | Notes |
|------|--------|---------|
| `config.py` | read YAML → parse typed dataclass → validate config | entry point — all other files import from here |
| `inference.py` | build SAM 3.1 model, segment single image, export COCO/mask/viz | handles device (CUDA > ROCm > MPS > CPU), GPU ops |
| `batch_segment.py` | run batch segmentation across all images in a folder, checkpoint/resume, ETA | CLI entry point — `python src/batch_segment.py` |
| `exporters.py` | export annotations to 11 formats (COCO, YOLO, VOC, LabelMe, CVAT, ...) | select format via `output.formats` in config |
| `tracker.py` | log history for every run (SQLite + JSON) | no MLflow required |

## Execution Flow

```text
batch_segment.py
  ├── load_config()          ← config.py
  ├── build_model()          ← inference.py
  ├── for each image:
  │     segment_image()      ← inference.py
  │     write_image_exports()← exporters.py
  ├── finalize_exports()     ← exporters.py
  └── tracker.end_run()      ← tracker.py
```

## config.py

Main dataclasses:

- `Category` — id, name, prompt, threshold (per-category override; -1 = use global, 0 = accept all)
- `InferenceConfig` — confidence_threshold, resolution, device, gpu_ops, pipeline_export
- `AnnotationConfig` — bbox, segmentation, segmentation_encoding (rle | polygon)
- `OutputConfig` — formats, save_viz, input_dir, output_dir, viz_dpi, viz_figsize
- `Config` — combines all of the above + checkpoint settings

`SUPPORTED_FORMATS` — tuple of 11 formats supported by exporters.py

## inference.py

- `build_model()` — builds the SAM 3.1 model based on detected device
- `segment_image()` — segments a single image, returns a list of annotations
- `save_coco()` / `save_masks()` / `save_viz()` — helper exports
- GPU ops (optional): `robust_rle_encode`, `gpu_mask_iou`, `generic_nms` from `sam3.perflib` — falls back to CPU if import fails

## batch_segment.py

CLI flags:

- `--resume` — resume from checkpoint
- `--fresh` — start fresh, clear checkpoint
- `--threshold <float>` — override confidence threshold
- `--config <path>` — specify config file (default: `config/ppe_6class.yaml`)

`checkpoint.enabled`, `checkpoint.auto_resume`, and `checkpoint.clear_on_success` directly affect checkpoint behavior. Image export must succeed before an image is marked as processed, and the batch will return a non-zero exit code when there are images that failed to process or export

## exporters.py

How each format is written:

| Format | Output | Annotation type |
|--------|--------|-----------------|
| coco | combined JSON | bbox/seg (RLE or polygon) |
| yolo | TXT per image + data.yaml | bbox or polygon |
| voc | XML per image | bbox only |
| labelme | JSON per image | bbox/seg (polygon) |
| cvat | combined XML | bbox/seg (polygon) |
| label_studio | combined JSON | bbox/seg (uncompressed RLE) |
| kitti | TXT per image | bbox only |
| createml | combined JSON | bbox only |
| openimages | combined CSV | bbox only |
| supervisely | JSON per image + meta.json | bbox/seg (polygon) |
| masks | PNG per annotation | seg only |

Note: per-image JSON in `output/coco/{name}.json` is always written; it serves as an internal cache for checkpoint/resume and is independent of `formats`

## tracker.py

`ExperimentTracker` — logs every run:

- SQLite: `experiments.db` in output_dir
- JSON artifacts: `experiments/` folder
- Used via `tracker.start_run()` → `tracker.log_metrics()` → `tracker.end_run()`

## Notes

- Imports use relative paths (`from config import ...`) — must run from within `src/` or add `src/` to `sys.path`
- The `sam3` import in `inference.py` is optional — if GPU ops are unavailable, it falls back to CPU
- If adding a new format, it must also be added to `SUPPORTED_FORMATS` in `config.py`
