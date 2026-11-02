# LabelDesk self-hosted inference

A small, single-tenant FastAPI service that serves exported LabelDesk model files from a mounted
directory on your own hardware. It is a standalone container: the hosted **Deploy** page still
documents the hosted API, so point self-hosted clients at this service's `/predict` directly.
There is no workspace, API key or billing code in this service and no secret is read or baked into
the image — deploy one container per tenant.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | model files found, backend dependency availability, service/library versions |
| `GET` | `/models` | every servable file, its backend, and whether the backend's dependencies are installed |
| `POST` | `/predict` | multipart `file`, optional `confidence` (0–1, default 0.4), optional `model` |

`POST /predict` returns the same shape as the hosted API: centre-based boxes in image pixels, plus
the decoded image size and the model that produced the result. Classification models also return
`top`; segmentation models add `points` when the backend provides masks.

```json
{
  "predictions": [
    { "x": 320.5, "y": 210.0, "width": 80.2, "height": 120.4,
      "confidence": 0.91, "class": "helmet", "class_id": 0 }
  ],
  "image": { "width": 1280, "height": 720 },
  "time": 0.042,
  "model": "ppe/best.onnx"
}
```

`model` is the file name from `GET /models`; omit it when exactly one model is mounted. A bad
upload returns `400 not a valid image`, an unknown model `404`, a missing backend `503`. Uploads are
capped at **20 MB** (larger bodies return `413`). `confidence` and `model` are multipart form fields;
the hosted API's `?confidence=` query parameter does not apply to this service.

## Model directory contract

Mount one directory at `LD_INFERENCE_MODELS` (default `/models`). The service scans it recursively
on startup and **refuses to start when it finds no supported files**. Restart after adding or
replacing files.

| File | Backend | Image |
| --- | --- | --- |
| `*.onnx` | onnxruntime, CPU by default (CUDA when the GPU image finds it) | CPU / GPU |
| `*.pt` | ultralytics (YOLO / RT-DETR) | GPU image only; add ultralytics to a custom CPU image |
| `*.engine` | ultralytics + TensorRT | GPU image with the optional TensorRT pin |

The model name is the path relative to the mount, e.g. `ppe/best.onnx`. Names are unique because
the suffix is part of the name, so `best.pt` and `best.onnx` can sit side by side. Labels and other
files are ignored. Keep weights out of git and out of the image; the compose profile mounts the
directory read-only.

ONNX files must be standard Ultralytics **detection** exports (`1 × (4+classes) × anchors`, with the
`names` metadata Ultralytics writes). Segmentation exports are served as boxes only (no `points`).

## Run — CPU (ONNX)

```bash
# from the repository root
mkdir -p deploy/models && cp /path/to/exports/*.onnx deploy/models/
docker compose -f deploy/docker-compose.yml --profile inference up -d --build
curl http://localhost:8010/healthz
python tools/inference_smoke.py --url http://localhost:8010
```

Or without compose:

```bash
docker build -t labeldesk-inference:cpu apps/inference
docker run --rm -p 8010:8010 --read-only --tmpfs /tmp:size=64m \
  -v "$PWD/models:/models:ro" labeldesk-inference:cpu
```

`--read-only` needs a writable `/tmp`: Starlette spools multipart bodies above 1 MB to disk, so
without the 64 MB tmpfs (larger than the 20 MB upload cap) full-size photos fail with
`400 There was an error parsing the body`. The mounted directory must be readable by uid `10001`.
On Linux, `chmod -R a+rX models` is enough.

## Run — GPU (`.pt`, optional `.engine`)

```bash
docker build -f apps/inference/Dockerfile.gpu -t labeldesk-inference:gpu apps/inference
docker run --rm --gpus all -p 8010:8010 \
  -v "$PWD/models:/models:ro" labeldesk-inference:gpu
```

The image starts from `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`, so `.pt` weights run on the
GPU. For TensorRT engines, uncomment the `tensorrt` pin in `apps/inference/requirements-gpu.txt`,
rebuild, and export an `.engine` on the same GPU/version. Env knobs: `LD_INFERENCE_MODELS` only;
the port is baked as `8010` (publish it with `-p` / `LD_INFERENCE_PORT` in compose).

### Jetson (cross-build variant, not tested here)

Jetson is not a published image. Cross-build the GPU Dockerfile on the device (or with `buildx`
for `linux/arm64`) from an NVIDIA JetPack base such as `nvcr.io/nvidia/l4t-pytorch`, keep the
JetPack TensorRT/CUDA packages instead of pip-installing `tensorrt`, and then reuse
`main.py` / `detect.py` unchanged. This repository does not claim a tested Jetson image.

## Tests and smoke check

```bash
cd apps/inference
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_inference.py -q        # scan, mapping, startup refusal, upload validation
```

`tools/inference_smoke.py` runs against a live container (it generates a small PNG when `--image`
is omitted) and prints one `PASS`/`FAIL` line per check:

```bash
python tools/inference_smoke.py --url http://localhost:8010 --model ppe/best.onnx
```
