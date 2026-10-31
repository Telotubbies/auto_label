# LabelDesk

A self-hosted computer-vision labeling SaaS modelled on Roboflow's workflow:
**upload → annotate → review → version → train → deploy**, built on the SAM 3.1 / YOLO26 pipeline in this repo.

```
apps/
  api/      FastAPI + SQLAlchemy (SQLite dev / Postgres prod), DB-backed job queue, embedded worker
  web/      React 19 + Vite + Tailwind v4 + TanStack Query + react-konva
  worker/   `labeldesk-worker` pip package: runs train / auto-label jobs on any GPU box over HTTPS
deploy/     docker-compose (Caddy HTTPS + web + api + Postgres), env template
```

## Features

| Area | What works |
|---|---|
| Accounts | Sign-up, login, refresh tokens, profile/password, optional OIDC bearer tokens |
| Workspaces | Multiple per user, switcher, roles (Admin / Reviewer / Labeler), email-less invite links, plan limits, monthly credits, audit log, trash/restore |
| Projects | Object detection, instance segmentation, classification (single/multi-label); folders; rename/move/delete |
| Upload | Drag-drop files/folders/zips, client + server SHA-256 dedupe, imports COCO JSON, YOLO txt + data.yaml, Pascal VOC, class-per-folder; split auto/keep/fixed; tags; batches |
| Annotate | Kanban (Unassigned → Annotating → Review → Dataset) by batch × assignee, assign, submit, approve/reject all, Auto Label (trained model or SAM 3.1 text prompts) |
| Editor | Bounding box, polygon, Smart Polygon (SAM 3.1 box prompt, GrabCut fallback), Label Assist, classification labels, relabel, attributes, tags, comments, history, undo/redo, autosave, approve/reject, keyboard shortcuts |
| Dataset | Virtualised grid, filters (status/split/class/tag/batch/null), sort, bulk split/tag/status/delete/auto-label |
| Analytics | Class balance + imbalance warning, annotations/image, size & aspect histograms, object-centre heatmap |
| Classes & tags | Add, rename, recolor, merge, delete (rewrites annotations) |
| Versions | Rebalance splits, resize stretch/fit, grayscale, contrast, null filter, 10 augmentations with ×1–5 outputs; exports COCO, YOLO, VOC, CreateML, TF CSV, folder, multi-label CSV |
| Train | Ultralytics YOLO n/s/m/l/x from local YOLO26 or COCO weights, live epoch charts, stop, metrics (mAP50, mAP50-95, P, R / top-1, top-5) |
| Deploy | Test-image playground with overlay, hosted inference API (file, URL or base64) with API keys, upload API, weights download, active learning back into the project |

Not included: payment processing (plans are switched by `LD_SUPERADMINS`), outbound email (invites are copyable links), Roboflow Universe/Workflows.

## Run locally

```bash
# API  (http://localhost:8010, seeds demo@labeldesk.dev / demo1234 + 40 PPE images)
cd apps/api && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8010

# Web  (http://localhost:5173, proxies /api to LD_API_PROXY or :8010)
cd apps/web && npm install && npm run dev

# Tests (end-to-end, includes a 1-epoch CPU training run, ~30 s)
cd apps/api && pytest -q
```

Key env vars (all optional in dev): `DATABASE_URL`, `LD_DATA_DIR`, `LD_SECRET`, `LD_LOCAL_JOBS`, `LD_WORKER_TOKEN`,
`LD_CORS_ORIGINS`, `LD_PUBLIC_URL`, `LD_SAM_ENABLED`, `LD_TRAIN_DEVICE`, `LD_SEED_DEMO` — see `apps/api/app/config.py`.

Deployment (free hosting, GPU worker on Kaggle/Colab/home PC): [`docs/DEPLOY.md`](../docs/DEPLOY.md).

## Security & performance

Hardening (each item has an attack-style test in `apps/api/tests/test_security.py`):
SSRF-safe image-URL fetch (public IPs only, redirects re-checked, IP pinned) · zip-bomb / upload-size / pixel-bomb limits ·
filename sanitising · invite links bound to the invited email · per-IP login/signup/refresh/API-key rate limits ·
constant-time login (no account enumeration) · SHA-256-hashed one-time refresh tokens · labelers limited to assigned images ·
strict annotation payload validation · signed, expiring file URLs · security headers + CSP (API, nginx, Vercel, Caddy HSTS) ·
non-root container · secret persisted or required ≥ 32 chars. `npm audit` and `pip-audit`: 0 known vulnerabilities.

Performance (`python tests/perf_bench.py 20000`, 20k images / ~120k annotations, SQLite):

| endpoint | before | after |
|---|---|---|
| image list (page of 200) | 663 ms | 19 ms |
| class counts | 375 ms | 31 ms |
| project detail | 513 ms | 103 ms |
| analytics (cached) | 950 ms | 44 ms |

Class counts/filters use the `image_classes` index kept in sync by `models.set_annotations()` — write annotations only
through it. File URLs are stable per hour so thumbnails are browser-cached; light routes load eagerly to avoid React 19's
300 ms Suspense throttle.
