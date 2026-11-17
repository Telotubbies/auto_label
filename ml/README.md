# ml/

The offline ML layer and its entry points. Nothing here is imported by the app at
runtime except through the env-var contract below.

- `sam3_auto_label/` — SAM 3.1 auto-labeling pipeline.
- `yolo26_ppe/` — YOLO26 training, evaluation, exports and reports.
- `pipeline_cli.py` — the interactive CLI that drives both (`sam`, `yolo`, `pred`).
- `auto_label.sh` — thin bash wrapper around the CLI.
- `setup.sh` — one-shot environment setup, then launches the pipeline.
- `tests/` — the pytest suite for this layer; run `python -m pytest -q` from this directory.

Model weights, dataset bytes and run artefacts are **not committed**:
`ml/**/models/`, `ml/**/data/` and `ml/**/artifacts/` are ignored, and
`tools/check_large_files.py` rejects a commit that adds one.

The app reaches this layer through three env vars. `LD_SAM_ROOT` (default
`../labeldesk-ml/sam3_auto_label`), `LD_PRETRAINED_DIR` (default
`../labeldesk-ml/yolo26_ppe/models/pretrained`) and `LD_DEMO_MODEL_RUN` (the demo seed's
training run, same sibling default) all point at a sibling checkout of this repo, so the backend
repo keeps working when it is absent. Datasets stay in the app repo's `data/`, read only by this
layer.
