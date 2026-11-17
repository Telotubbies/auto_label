# ml/

The offline ML layer and its entry points. Nothing here is imported by the app at
runtime except through the env-var contract below.

- `sam3_auto_label/` — SAM 3.1 auto-labeling pipeline.
- `yolo26_ppe/` — YOLO26 training, evaluation, exports and reports.
- `pipeline_cli.py` — the interactive CLI that drives both (`sam`, `yolo`, `pred`).
- `auto_label.sh` — thin bash wrapper around the CLI.
- `setup.sh` — one-shot environment setup, then launches the pipeline.

Model weights, dataset bytes and run artefacts are **not committed**:
`ml/**/models/`, `ml/**/data/` and `ml/**/artifacts/` are ignored, and
`tools/check_large_files.py` rejects a commit that adds one.

The app reaches this layer through two env vars, both with a default that points
here: `LD_SAM_ROOT` (default `ml/sam3_auto_label`) and `LD_PRETRAINED_DIR`
(default `ml/yolo26_ppe/models/pretrained`). Datasets stay at the repo root in
`data/`, read only by this layer.
