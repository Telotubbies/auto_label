# LabelDesk and the PPE auto-labeling pipeline

This repository holds two layers that share one history.

The first is a batch pipeline for turning raw PPE images into verified datasets, training YOLO26 detection and segmentation models, evaluating them, and exporting ONNX artifacts. The second is LabelDesk, a self-hosted labeling application built on that pipeline. LabelDesk covers upload, annotate, review, version, train, and deploy, with a FastAPI backend, a React frontend, a database-backed job queue, and an optional remote GPU worker.

> Naming: `apps/frontend` holds the web app and `apps/backend` holds the API. Older documents, including the historical plan under `docs/superpowers/plans/`, may still use the previous folder names.

## Status

| Layer | Path | State |
|---|---|---|
| LabelDesk backend | `apps/backend` | Implemented |
| LabelDesk frontend | `apps/frontend` | Implemented |
| Remote GPU worker | `apps/worker` | Implemented |
| Self-hosted inference | `apps/inference` | Implemented, optional |
| Python SDK and CLI | `apps/sdk` | Implemented |
| SAM and YOLO batch pipeline | `sam3_auto_label`, `yolo26_ppe` | Implemented |

The application has a working self-hosted deployment path. It is not a hardened multi-tenant service. The limits section below lists the known gaps.

## What LabelDesk does

The main workflow is upload, annotate, review, version, train, and deploy. The API serves the application and runs a database-backed job queue. The web app is the only client. Training and auto-labeling can run on a remote GPU box through `labeldesk-worker`, which makes outbound HTTPS calls to the API and never needs an inbound port.

The capability table in [apps/README.md](apps/README.md) is the detailed feature list. Deployment steps are in [docs/DEPLOY.md](docs/DEPLOY.md).

## Repository layout

```text
apps/
  frontend/        React web app
  backend/         FastAPI service, embedded job worker, tests
  worker/          labeldesk-worker package for remote train and auto-label jobs
  inference/       standalone self-hosted inference service
  sdk/             Python client and CLI
packages/          planned shared code; not created yet
deploy/            Docker Compose stack, Caddyfile, env template
tools/             scripts used by apps and tests
tests/             repository-level pipeline tests
docs/              architecture, ADRs, runbooks, deployment
sam3_auto_label/   SAM 3.1 auto-labeling pipeline
yolo26_ppe/        YOLO26 training, evaluation, models, reports
data/              raw batches and SAM outputs; large, not for new commits
```

The approved target layout replaces the two pipeline directories with `ml/yolo26_ppe` and `ml/sam3_auto_label`, and adds `packages/`. Neither change has landed. The pipeline paths above are the current ones.

## Quick start

These commands start the development stack on one machine. They assume Python 3.11+ and Node 20+.

### Backend

```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

Development defaults use SQLite in `apps/backend/data`, enable the embedded job worker, and seed demo data, including `demo@labeldesk.dev` with password `demo1234`. Set `LD_SEED_DEMO=0` to skip the seed. The health endpoint is `GET /api/health`.

### Frontend

```bash
cd apps/frontend
npm ci
npm run dev
```

The dev server listens on `http://localhost:5173` and proxies `/api` to `http://localhost:8010`. Set `LD_API_PROXY` to change the target.

### Tests

```bash
cd apps/backend
pytest -q

cd ../frontend
npm run build
```

The root pipeline tests need the CLI dependencies (`questionary`, `rich`) installed in the active environment:

```bash
python -m pytest tests -q
```

### Compose deployment

```bash
cd deploy
cp .env.example .env
# Edit LD_DOMAIN, LD_SECRET, POSTGRES_PASSWORD, LD_WORKER_TOKEN.
docker compose up -d --build
```

Caddy obtains HTTPS for `LD_DOMAIN`. The `worker` service runs CPU jobs. GPU training runs through `labeldesk-worker` on another machine. See [docs/DEPLOY.md](docs/DEPLOY.md) for the full walkthrough and secret rotation.

## Documentation

| Topic | Document |
|---|---|
| Architecture overview | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Repository layout decision | [ADR 0001](docs/adr/0001-repository-layout.md) |
| Front and back contract | [ADR 0002](docs/adr/0002-front-back-contract.md) |
| Git workflow | [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) |
| Local start runbook | [docs/runbooks/local-start.md](docs/runbooks/local-start.md) |
| Recovery after a shutdown | [docs/runbooks/recovery-after-shutdown.md](docs/runbooks/recovery-after-shutdown.md) |
| Deployment | [docs/DEPLOY.md](docs/DEPLOY.md) |
| Existing pipeline and thesis docs | [docs/README.md](docs/README.md) |

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing code and [SECURITY.md](SECURITY.md) before reporting a vulnerability. Work happens on task branches in separate worktrees, and agents do not push. [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) has the branch and worktree rules.

## Known limits

- The v3 4-class YOLO26m detection model reaches 0.693 mAP50, below the project target of 0.85. The canonical numbers are in `yolo26_ppe/reports/inputs/final_eval_results.json`.
- There is no root license file. Redistribution rights are not established by this repository. Third-party notices are in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
- The root pipeline CLI has no dependency manifest of its own, so `questionary`, `rich`, `pytest`, `ruff`, and `mypy` must be installed separately for the documented commands.
- The frontend types in `apps/frontend/src/lib/types.ts` are written by hand. Generated types from the OpenAPI schema are planned but not in place.
- The app has no payment processor and does not require outbound email. Plan changes go through `LD_SUPERADMINS`, and invites are copyable links.
- The API is designed to run as a single process because rate limits, stream state, and the GPU lease ledger are held in memory.
