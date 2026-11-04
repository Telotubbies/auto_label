# Runbook: start LabelDesk locally

Use this runbook for a development machine. It starts the API and the web app from source, with SQLite and the embedded worker. For a server deployment, use [docs/DEPLOY.md](../DEPLOY.md) instead.

## What you need

- Python 3.11 or newer.
- Node 20 or newer with npm.
- Git.
- Free ports `8010` for the API and `5173` for the web app.
- No GPU for the default path. Training and auto-labeling need either a CPU fallback or a remote worker.

The planned directory names are `apps/backend` and `apps/frontend`. They are still `apps/api` and `apps/web`. The commands below use the current paths.

## Start the backend

From the repository root:

```bash
cd apps/api
python -m venv .venv

# Linux or macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

On first start the API creates the SQLite database under `apps/api/data`, applies the schema, and seeds demo data because `LD_SEED_DEMO` defaults to `1` outside production. The demo account is `demo@labeldesk.dev` with password `demo1234`. Set `LD_SEED_DEMO=0` before the first start if you do not want it.

The API process also runs the local job worker by default (`LD_EMBEDDED_WORKER=1`). The default `LD_LOCAL_JOBS` list covers version, export, health, connector sync, retention, video frame extraction, tracking, drift, active learning, and insights scans, and it also includes `train` and `autolabel`. A Train or Auto-label click therefore runs in the API process, on CPU when the machine has no GPU, so it competes with request handling for the length of the run. That is the default path, not a stalled queue. To hand those two kinds to `labeldesk-worker` instead, remove them from `LD_LOCAL_JOBS`, for example `LD_LOCAL_JOBS=version,export,export_engine,health,connector_sync,retention,extract_frames,track_forward,drift,active_learning,insights_images,insights_leakage,insights_embedding`; set `LD_EMBEDDED_WORKER=0` as well if the API process should claim no jobs at all. A remote worker can only claim a row that no local worker has taken.

Useful environment variables for a local start:

| Variable | Default | Effect |
|---|---|---|
| `LD_DATA_DIR` | `apps/api/data` | Database, uploads, versions, exports, and weights |
| `DATABASE_URL` | SQLite in `LD_DATA_DIR` | Point at PostgreSQL when needed |
| `LD_SECRET` | generated and stored as `LD_DATA_DIR/.secret` | Token signing and secret encryption; at least 32 characters if set |
| `LD_SEED_DEMO` | `1` in development, `0` in production | Demo account and sample data |
| `LD_EMBEDDED_WORKER` | `1` | Run local job kinds in the API process |
| `LD_SAM_ENABLED` | `auto` | `auto`, `1`, or `0`; controls SAM auto-label availability |

Changing or deleting `.secret` after first start invalidates sessions and makes encrypted database values unreadable. Keep it with the data directory.

## Start the frontend

In a second terminal, from the repository root:

```bash
cd apps/web
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/__mail` to `http://localhost:8010`. Set `LD_API_PROXY` if the API is on another host or port.

If you only need a production bundle check:

```bash
npm run build
```

## Check that it works

```bash
curl -fsS http://localhost:8010/api/health
```

A healthy API returns `{"ok":true,"service":"labeldesk"}`. Then:

1. Sign in with the demo account, or create an account if the seed is off.
2. Open a project and load an image. The signed image URL is served by the API.
3. Open the job tray or the project jobs list and confirm the queue is empty or moving.

## Stop it

Stop each development server with `Ctrl+C`. The SQLite database and uploads remain under `apps/api/data`.

Do not delete `apps/api/data` to reset the app unless you intend to lose every local account, annotation, model, and export.

## Compose path

For a local production-like run:

```bash
cd deploy
cp .env.example .env
# Set LD_DOMAIN to localhost or a test domain.
# Replace LD_SECRET, POSTGRES_PASSWORD, and LD_WORKER_TOKEN; the placeholders are too short.
docker compose up -d --build
```

`LD_SECRET` must be at least 32 characters and `LD_WORKER_TOKEN` at least 24, or the API refuses to start. Caddy serves the app on port 80 and tries to obtain a certificate for `LD_DOMAIN`; use a resolvable name for HTTPS.

Check the stack:

```bash
docker compose ps
docker compose logs --tail=50 api worker
curl -fsS http://localhost/api/health
```

The Compose stack sets `LD_SAM_ENABLED=0`; SAM auto-labeling is not available there until you enable it and provide a checkpoint. GPU training still runs through `labeldesk-worker` on another machine.

Stop without deleting data:

```bash
docker compose down
```

Do not add `-v` unless you intend to delete the Postgres database and the `labeldesk_data` volume.

## Common failures

| Symptom | Likely cause | Check |
|---|---|---|
| API exits with `LD_SECRET must be at least 32 characters` | Short or placeholder secret | Generate with `openssl rand -hex 32` |
| API exits with `LD_WORKER_TOKEN must be at least 24 characters` | Short worker token | Generate a longer token |
| `address already in use` on 8010 or 5173 | Another process owns the port | Stop it or pass `--port` / set the Vite port |
| Frontend loads but API calls 404 or fail | Proxy target is wrong | Set `LD_API_PROXY` and restart Vite |
| Jobs stay `queued` | No process claims that kind | Check `LD_LOCAL_JOBS` and whether a worker is online |
| Images or annotations vanish after a restart | A different `LD_DATA_DIR` or database | Compare `LD_DATA_DIR` and `DATABASE_URL` across both starts |
