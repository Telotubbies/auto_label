# LabelDesk SDK

Python client and CLI for the LabelDesk developer API (`/api/v1`). It depends only on `httpx`;
the operation map in `labeldesk/_generated.py` is generated from the FastAPI schema.

## Install

```bash
pip install -e apps/sdk
```

## Auth

| Variable | Meaning |
| --- | --- |
| `LABELDESK_API_KEY` | workspace API key (or pass `--api-key`) |
| `LABELDESK_URL` | API root, default `http://localhost:8010` (or pass `--base-url`) |

Create a key in the workspace settings, or `POST /api/ws/{ws}/keys` with an admin token.
Keys carry scopes: `read`, `upload`, `train`, `infer`.

## CLI

```bash
export LABELDESK_API_KEY=ld_...
export LABELDESK_URL=http://localhost:8010

labeldesk whoami
labeldesk upload ppe-detection ./images/*.jpg --batch "Site A" --split auto --tags ppe
labeldesk export ppe-detection <version-id> --format coco --wait -o ppe-coco.zip
labeldesk train ppe-detection <version-id> --variant yolo26n --epochs 30 --wait
labeldesk predict <model-id> ./site.jpg --confidence 0.25
labeldesk models
```

`labeldesk export` without `--wait` prints the queued job; with `--wait` it polls the job and writes
`-o PATH` (default `VERSION-FORMAT.zip`). `labeldesk train --wait` prints the trained model.

Add `--json` for single-line output. The CLI is also runnable as `python -m labeldesk.cli`.

## Python

```python
from labeldesk import LabelDesk

ld = LabelDesk(api_key="ld_...", base_url="http://localhost:8010")
ld.upload("ppe-detection", ["a.jpg", "b.jpg"], batch_name="Site A")
version = ld.versions("ppe-detection")[0]
job = ld.export("ppe-detection", version["id"], fmt="coco")
job = ld.job(job["id"], wait=True)
ld.download(job["url"], "ppe-coco.zip")
model = ld.train("ppe-detection", version["id"], epochs=30)
ld.job(model["jobId"], wait=True)
print(ld.predict(model["id"], "site.jpg"))
```

Errors raise `LabelDeskError` with `.status` and `.detail`.

## Verifying webhooks

Every delivery carries `X-LabelDesk-Signature: sha256=<hex>`, `X-LabelDesk-Timestamp` (unix seconds)
and `X-LabelDesk-Delivery` (stable across retries). The signature is
`HMAC-SHA256(secret, "<timestamp>." + raw_body)`; compute it over the raw request bytes, not a
re-serialised object. Reject timestamps older than 300 s (the SDK's `verify(..., max_age=300)`
default) to bound replay, and dedupe on `X-LabelDesk-Delivery` so a retried delivery is processed
once. The signing secret is returned only when the webhook is created.

## Regenerating

After any `/api/v1` change, regenerate from the repo root and commit the result:

```bash
python tools/gen_sdk.py
```

The drift test (`apps/api/tests/test_sdk_cli.py`) fails when `_generated.py` is stale.
