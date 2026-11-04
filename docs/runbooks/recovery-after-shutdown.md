# Runbook: recovery after an unexpected shutdown

Use this after a power loss, a host crash, an out-of-memory kill, or a container that stopped without a clean `docker compose down`. The goal is to bring the system back without discarding data and to decide what to do with jobs that were running when the process died.

## Before you touch anything

- Do not delete a database volume, `pgdata`, `labeldesk_data`, or the local `apps/backend/data` directory to make startup errors go away.
- Do not rotate or remove `LD_SECRET`. It protects encrypted database values and signed tokens. A lost secret is not recoverable from the application side.
- Do not force-remove a worktree or delete rows in `jobs` as a first response.
- Take a backup before any manual repair. For the Compose stack:

```bash
cd deploy
docker compose exec -T db pg_dump -U labeldesk labeldesk > labeldesk-$(date +%F-%H%M).sql
docker volume ls   # find the labeldesk_data volume for this compose project
```

If the database is not accepting connections, copy the volume or snapshot the VM first.

## 1. Check the host

```bash
df -h
free -h
date
```

PostgreSQL needs free space to replay its write-ahead log. A full disk is the most common reason a restart loops. Fix disk space before starting the database again.

Check that the clock is roughly correct. The application stores timestamps in Unix epoch seconds and compares them for leases, rate limits, and token expiry.

## 2. Start the Compose stack

```bash
cd deploy
docker compose ps
docker compose up -d
```

Start order is handled by `depends_on`, but the database is the critical piece. If the API starts before Postgres is healthy, restart the API after the database is healthy:

```bash
docker compose up -d db
docker compose ps db
docker compose up -d api worker web caddy
```

PostgreSQL performs its own crash recovery on start. Let it finish. Do not interrupt the first startup with repeated `restart` commands.

## 3. Read the logs

```bash
docker compose logs --tail=100 db
docker compose logs --tail=100 api
docker compose logs --tail=100 worker
docker compose logs --tail=100 caddy
```

Signals to look for:

- `api`: schema creation or `ensure_columns` failures, `LD_SECRET must be at least 32 characters`, or a port bind error.
- `worker`: `worker started`, followed by no repeated stack traces.
- `db`: `database system is ready to accept connections`. Earlier `redo` lines are normal crash recovery.
- `caddy`: certificate or upstream errors. A certificate failure does not stop the API from being healthy on the internal network.

## 4. Verify health

```bash
curl -fsS https://$LD_DOMAIN/api/health
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
```

The response should contain `"ok":true` and `"service":"labeldesk"`.

Then sign in and check the admin console if you have `LD_SUPERADMINS` set. Confirm:

- the worker list shows an online worker with a recent heartbeat,
- the queue has no growing backlog,
- the project and image counts match what you expect.

A worker heartbeat older than `LD_WORKER_STALE_S` (45 seconds by default) shows as offline even if the process is alive but stuck. Check the worker logs before assuming it is healthy.

## 5. Handle jobs that were running

Local job kinds are recovered automatically. When the local worker loop starts, `app/worker.py` calls `recover()`:

- `running` local jobs go back to `queued`,
- `cancelling` local jobs become `cancelled`,
- other terminal jobs are left alone.

This covers version, export, health, connector sync, retention, video extraction, tracking, drift, active learning, and insights scans. The job runs again when its turn comes, and it starts from the beginning rather than resuming at the failed step. If a retried export leaves a partial file under `LD_DATA_DIR`, remove only that job's output directory after confirming the job id.

Remote `train` and `autolabel` jobs are not recovered. `recover()` filters on the local job kinds, and the remote claim endpoint only hands out rows in `queued`. A `labeldesk-worker` that died mid-job leaves its row in `running`, or in `cancelling` if someone pressed cancel. There is no timeout reaper and no retry endpoint in the current code.

Until that gap is fixed, treat a stuck remote job as an incident:

1. Confirm the remote worker process is gone and will not reconnect. Check its machine and logs.
2. Record the job id and the linked model id. For a training job, the `TrainedModel` row may still say `training` and have no usable weights.
3. Prefer restoring from the last backup if the row is part of a larger inconsistency.
4. If you decide to close the row by hand, back up first and use a reviewed one-off script inside the API container. Set the job to `failed` with a clear error, and set its model to `failed` for a training job. Do not delete the row; the workspace usage and audit history refer to it.

   This example uses the application models, not raw SQL. It is a repair action, not a supported endpoint. Check every value before you run it.

   ```bash
   docker compose exec -T api python - <<'PY'
   from app.db import SessionLocal
   from app.models import Job, TrainedModel, now

   job_id = "JOB_ID_HERE"
   with SessionLocal() as db:
       job = db.get(Job, job_id)
       if job is None:
           raise SystemExit("job not found")
       job.status = "failed"
       job.error = "remote worker lost after host shutdown"
       job.finished = now()
       if job.kind == "train":
           model_id = (job.params or {}).get("model_id")
           model = db.get(TrainedModel, model_id) if model_id else None
           if model is not None:
               model.status = "failed"
       db.commit()
   print("closed", job_id)
   PY
   ```

5. Re-submit the training or auto-label job from the UI after the row is closed. A remote training run that lost its temp directory must start over; its weights are uploaded to the API only when the job completes.

Do not run a second remote worker against the same job id. The claim endpoint uses a compare-and-set on `queued`, so a `running` row will not be handed out twice, but a manually requeued row can be claimed while the old worker is still alive.

## 6. Restart streams

Streams are in-process. The API startup marks every stream row `stopped` because the old workers are gone with the process. This is expected after a restart, not a data loss.

Start each stream again from the Streams screen and confirm the live view and event log resume. A stream that was reading from a local file may need its path checked; a remote RTSP source may need the camera to come back online.

## 7. Check webhooks

Signed webhook deliveries are stored in the database. The worker's flush loop picks up due `pending` rows when it runs. Deliveries that exhausted their attempts stay `failed`; the current code does not replay them automatically. Check the workspace's webhook delivery list, if available in the build, or the delivery rows, and tell the affected integration owner which events were missed.

## 8. Local development recovery

If the shutdown was your development machine rather than a server:

1. Close any stale `uvicorn` or Vite process.
2. Restart the API from `apps/backend`. The embedded worker calls `recover()` on start.
3. Restart Vite from `apps/frontend`.
4. Check `http://localhost:8010/api/health` and sign in.

The SQLite file lives in `apps/backend/data/labeldesk.db` unless `LD_DATA_DIR` or `DATABASE_URL` says otherwise. If you suspect corruption, stop the API and copy the database before running a check:

```bash
cp apps/backend/data/labeldesk.db apps/backend/data/labeldesk.db.bak
sqlite3 apps/backend/data/labeldesk.db "PRAGMA integrity_check;"
```

`ok` is the expected result. Any other output means the database needs recovery from a backup. Do not run `VACUUM` or repair commands against the only copy.

SQLite writes are durable at commit, but a power loss can still lose the most recent transaction. Do not treat the local development database as a backup.

## 9. Post-recovery checks

- [ ] `GET /api/health` returns ok.
- [ ] The worker heartbeat is current.
- [ ] The queue drains or shows only expected queued work.
- [ ] A project opens and an image loads through its signed URL.
- [ ] A version export or a small job completes.
- [ ] Streams that should be live show `live`.
- [ ] The last backup is newer than the incident and is stored off the failed host.

## Known gaps in the current code

- Remote `train` and `autolabel` jobs are not requeued after a worker crash. This runbook describes the manual path because no API endpoint exists.
- The API is a single process by design. Rate limits, stream workers, and the GPU lease ledger are in memory, so a restart resets them.
- There is no built-in periodic backup. The Compose stack persists data in volumes, but volumes are not backups.
- The local development SQLite database has no replication. Only a copy is a backup.
