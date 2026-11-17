# Monitoring / observability plan — LabelDesk

Owner priority 2026-11-17: after security, **monitoring**. One machine must be able to answer "is it
healthy, what is slow, what failed, and who do I tell" without a hosted APM.
Planning lane only: docs and cards, no product code. Baseline `feat/labeldesk-v2` (`2fef0ba`).

Read for this note: `docs/OPENCODE_TEAM_FLOW.md` §1/§4c–4e, `docs/architecture/`, `docs/DEPLOY.md`,
`docs/runbooks/`, `docs/audits/code/CODE-AUDIT.md` (audit lane 2026-11-17; still untracked on `feat` when
this was written), `docs/research/mcp/MCP-PLAN.md` §9, `docs/research/inference-hub/PLAN.md` §9, and the
code in §1.
Cards: `T-1300`, `T-1301`, `T-1302`, `T-1311`–`T-1317` (wave O).

New role this plan creates: **SRE** (R12 in the dispatch table). Read-only everywhere except its own
files; owns the dashboards, the alert thresholds and the runbooks.

---

## 1. Current state

| Signal | Today | Evidence |
| --- | --- | --- |
| Application logs | Plain text via `logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")`, INFO, to stdout | `app/main.py:21`, `app/worker.py:326` |
| Request correlation | **None.** No request id is generated, accepted or logged; a user report cannot be joined to a log line | repo-wide grep for `request_id` / `X-Request-Id` → 0 hits |
| Liveness | `GET /api/health` → `{"ok":true,"service":"labeldesk"}`. No DB, disk or dependency check, so it is green while the queue is wedged | `app/main.py:84-86`, `docs/runbooks/recovery-after-shutdown.md:66-74` |
| Readiness | **None** | — |
| Metrics | **None.** No Prometheus, no statsd, no counters | repo-wide grep → 0 hits |
| Traces | **None** | — |
| Worker liveness | `Worker` row, `last_seen` beaten every 5 s, stale after `LD_WORKER_STALE_S` (45 s); stale jobs reaped by `remote_reaper` | `app/services/heartbeat.py:1-45`, `app/worker.py:237-256` |
| Queue depth | Counted on demand by the **superadmin** console only (`/api/admin/*`) | `routers/admin.py`, `features/admin/AdminConsole.tsx:35-50,120-132` |
| GPU | Process-local lease ledger with used/budget MB and holders | `app/gpu.py:144-156`, `AdminConsole.tsx:45-50` |
| Disk | Not measured anywhere. The recovery runbook's first step is `df -h` by hand | `docs/runbooks/recovery-after-shutdown.md:20-30` |
| Frontend errors | **Nothing.** No `window.onerror`, no `unhandledrejection`, no error boundary. A blank screen is invisible | `apps/frontend/src/main.tsx` (whole file) |
| Web vitals | **Nothing.** No LCP/INP/CLS capture, no Lighthouse, no budget | `apps/frontend/package.json` |
| Alerting | Product-facing alert channels (LINE/Slack/email) per workspace behind `task_33`, used for stream events. Nothing watches the platform itself | `app/routers/alerts.py`, `app/services/alerts.py`, `models/alerts.py:12-26` |
| Compose stack | 5 services + an `inference` profile. No Prometheus, no Grafana | `deploy/docker-compose.yml` |
| Runbooks | Start local, recover after shutdown | `docs/runbooks/` |

## 2. Gaps

| # | Gap | Why it matters | Card |
| --- | --- | --- | --- |
| M1 | **No request id, no JSON logs.** Grepping `docker compose logs api` for "that save failed at 14:32" is all there is; the browser has nothing to quote | Every support conversation starts with guessing | T-1300 |
| M2 | **`/api/health` is a liveness stub.** It stays green with a dead database session, a full disk or a missing data directory | Compose and Caddy cannot tell "up" from "useful" | T-1301 |
| M3 | **No metrics endpoint at all.** Request rate, errors, latency percentiles, queue depth and job durations exist only as rows and log lines | Cannot answer "is it slower than last week" | T-1302 |
| M4 | **No queue / job / worker / GPU / disk metrics**, so the four owner-named alerts have no source | An alert without a series is a runbook entry nobody can trigger | T-1311 |
| M5 | **No traces.** A slow request that spends 300 ms in SQL and 900 ms in Pillow is indistinguishable from a slow network | Performance work starts blind | T-1312 |
| M6 | **Frontend errors and web vitals are invisible.** The UI's own regressions are found by the owner | The product's most-used surface has no telemetry | T-1313 |
| M7 | **No tenant-visible health surface.** The platform console is superadmin-only and cross-workspace; a workspace owner cannot see their own queue, stuck jobs or disk | Support load lands on the owner | T-1314, T-1315 |
| M8 | **No dashboards.** Even with metrics, nobody wants to write PromQL during an incident | Mean time to understand stays high | T-1316 |
| M9 | **No alert thresholds, no notification path, no runbook per alert** | Nothing wakes anyone; the four owner-named conditions are discovered by a user | T-1317 |

## 3. Options, with size

Production LOC that stays in the repo. Test lines are quoted separately.

### 3.1 Logs and correlation

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **stdlib `logging` + one JSON formatter + one filter that injects a contextvar (`request_id`, `workspace_id`, `user_id`) + one middleware** | none | ~85 | **Chosen.** No dependency, keeps `log.exception` working everywhere, one place to extend. |
| 2 | `structlog` | structlog | ~70 + rewrite of every `log.info` call site (200+) | Rejected: a rewrite is not a feature. |
| 3 | `loguru` | loguru | ~60 + intercept handler | Rejected: replaces the stdlib the app already binds in 30 modules (`labeldesk.*` loggers). |
| 4 | OpenTelemetry log bridge only | otel-sdk | ~40 | Rejected as the primary: logs must be readable with `docker compose logs`, without a collector. |

### 3.2 Metrics

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **`prometheus_client`** (`make_asgi_app` mounted at `/api/metrics`, one middleware for HTTP, gauges computed at scrape time) | prometheus_client (~1 MB, pure Python) | ~150 (T-1302) + ~120 (T-1311) | **Chosen.** The de-facto standard, no daemon, no C extension, works with the owner's Grafana. |
| 2 | OpenTelemetry metrics + Prometheus exporter | 4 packages | ~260 | Rejected: more moving parts for the same four dashboards; OTel is added later for traces only. |
| 3 | statsd to a local telegraf | 2 services | ~120 | Rejected: another container to keep alive on one VM. |
| 4 | Roll our own JSON `/metrics` | none | ~200 | Rejected: Prometheus text format by hand is a bug farm and breaks Grafana. |

Cardinality rule for every series: label by **route template** (`/api/ws/{ws}/projects/{slug}/images`),
never by raw path, never by workspace or user id. This keeps the series count bounded by the OpenAPI
surface (~330 routes, ~30 with meaningful traffic).

### 3.3 Health endpoints

| # | Option | Prod LOC | Verdict |
| --- | --- | --- | --- |
| 1 | **`/api/healthz` (process only) + `/api/readyz` (DB `SELECT 1`, data dir writable, secret present; 200/503 with per-check booleans)** | ~55 | **Chosen.** Two names every orchestrator and runbook already understands. |
| 2 | Deepen `/api/health` in place | ~55 | Rejected: runbooks and the recovery doc assert `{"ok":true,"service":"labeldesk"}`; keep it as the cheap liveness alias. |
| 3 | Ship `/healthz` at the root, outside `/api` | ~15 more (Caddy route) | Rejected: Caddy proxies only `/api` and the SPA owns `/`; one prefix, no proxy change. |

### 3.4 Traces

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **OTel SDK + FastAPI instrumentation + one manual worker span, behind `LD_OTEL=1`** | opentelemetry-sdk, -api, -exporter-otlp-proto-http, -instrumentation-fastapi | ~60 | **Chosen.** Off by default, imported lazily, so the default install gains nothing but a config flag. |
| 2 | Jaeger client | opentracing (deprecated) | ~80 | Rejected. |
| 3 | Tempo/Grafana traces now | +1 container in the profile | 0 code | Deferred: the exporter endpoint is configurable, so the owner can point it at Tempo later without a card. |
| 4 | No traces; logs only | 0 | 0 | Rejected by the owner's brief; also the only way to split SQL from image time. |

### 3.5 Frontend telemetry

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **`web-vitals` (2 KB) + a 60-line `lib/telemetry.ts` (error, unhandledrejection, ErrorBoundary, vitals) posting to one API route that increments counters and logs** | `web-vitals` | ~150 (frontend) + ~70 (route) | **Chosen.** Smallest way to get LCP/INP/CLS without a browser-per-run; the counters feed the same dashboard. |
| 2 | Self-hosted Sentry / GlitchTip | +2 containers + SDK | ~40 | Rejected for v1: 2 services and a second datastore for what one route and a log line already answer. Named as the upgrade path. |
| 3 | Hand-rolled `PerformanceObserver` | none | ~120 | Rejected: `web-vitals` is 2 KB and encodes the attribution rules; hand-rolling is more code with worse numbers. |
| 4 | Beacon to a third party | external | ~20 | Rejected: telemetry must not leave the deployment (PDPA posture, `docs/DEPLOY.md`). |

**Storage decision:** no new table. Raw samples go to the structured log (searchable per request id);
counters go to `/metrics`; the dashboard reads the counters. A `web_vitals` table would need a
migration, a retention job and a screen — three things nobody asked for.

### 3.6 Health page, dashboards, alerts

| Area | Options | Prod LOC | Chosen |
| --- | --- | --- | --- |
| Tenant health page | (a) a workspace-scoped page reading one aggregate endpoint; (b) extend the superadmin console to workspace admins; (c) embed a Grafana iframe | (a) ~75 backend + ~200 frontend | **(a)** — the superadmin console must stay cross-workspace and superadmin-only; the tenant view answers "my queue, my jobs, my disk" and links to the console. |
| Dashboards | (a) one provisioned Grafana dashboard JSON; (b) the Prometheus expression browser; (c) LabelDesk builds charts | (a) ~0 code, ~180 JSON | **(a)** — one panel row per signal, provisioned from a file so it survives a volume wipe. |
| Alert evaluation | (a) **one worker job (`system_check`, every 5 min) that scrapes `/metrics`, counts the queue and heartbeats in SQL, and emails `LD_OPS_ALERT_EMAIL` (fallback `LD_SUPERADMINS`)**; (b) Prometheus rules + Alertmanager (2 more containers); (c) rules in Prometheus only | (a) ~95 + ~20 config | **(a)** — works on the default stack with no monitoring profile, reuses the existing mailer and job queue, and the four rules live in one file with their thresholds. Prometheus rules are documented as an optional mirror (Q4). |

## 4. Chosen design

### 4.1 Request id and log shape

`X-Request-Id: <8..64 chars of [A-Za-z0-9_-]>` is honoured when present, otherwise `uuid4().hex[:16]`
is generated. It is echoed on the response, stored in a `contextvar`, and injected into every log
record. The frontend generates one per API call (`crypto.randomUUID().slice(0,16)`) and reuses it
across a retry, so "quote the request id from the error toast" joins browser → API. Jobs are joined by
`job_id`: the enqueue log line carries both, and the worker logs `job_id` on claim, progress and
terminal state.

One JSON object per line, keys always present (empty string when N/A):

```json
{"ts":"2026-11-17T14:32:01.412Z","level":"INFO","logger":"labeldesk.images",
 "msg":"image.upload","request_id":"9f2c1ab40d7e4411","user_id":"u_…","workspace_id":"ws_…",
 "method":"POST","route":"/api/ws/{ws}/projects/{slug}/upload","status":200,"duration_ms":183.4,
 "job_id":"","worker_id":""}
```

Uvicorn's access log is turned off for `/api/*` (the middleware logs the same fields once) and kept
for anything else. `LD_LOG_JSON=0` falls back to the current text format, so a developer can still
read a local run.

### 4.2 Metric set (the whole list)

| Series | Type | Labels | Source |
| --- | --- | --- | --- |
| `labeldesk_http_requests_total` | counter | `method`, `route`, `status_class` | middleware |
| `labeldesk_http_request_duration_seconds` | histogram | `method`, `route` | middleware |
| `labeldesk_http_exceptions_total` | counter | `route`, `type` | exception handler |
| `labeldesk_http_inflight` | gauge | — | middleware |
| `labeldesk_jobs` | gauge | `status` (queued/running/failed_24h) | scrape-time SQL, 5 s cache |
| `labeldesk_job_oldest_queued_seconds` | gauge | — | same query |
| `labeldesk_job_duration_seconds` | histogram | `kind` | worker |
| `labeldesk_job_outcomes_total` | counter | `kind`, `status` | worker |
| `labeldesk_workers_online` | gauge | — | `Worker.last_seen` |
| `labeldesk_worker_heartbeat_age_seconds` | gauge | `worker` | `Worker.last_seen` (worker ids: bounded, operators only) |
| `labeldesk_disk_free_bytes` | gauge | `volume` | `shutil.disk_usage` |
| `labeldesk_gpu_vram_used_mb`, `labeldesk_gpu_budget_mb`, `labeldesk_gpu_leases` | gauge | — | `gpu.scheduler.state()`; no CUDA driver ⇒ absent, never 0 |
| `labeldesk_db_up` | gauge | — | `/readyz` check, cached 10 s |
| `labeldesk_build_info` | gauge 1 | `version` | `app/main.py` |

Scrape cost: one `COUNT(*) … GROUP BY status` per scrape (≤ 1 per 15 s, 5 s cache) plus three file
`stat` calls. Measured acceptance: `GET /api/metrics` p95 < 100 ms with 10k jobs in the table.

### 4.3 Health and readiness

| Endpoint | Answers | Checks | Failure |
| --- | --- | --- | --- |
| `GET /api/healthz` | is the process alive | none | only when the process is gone |
| `GET /api/readyz` | can it serve requests | `SELECT 1`, data dir writable (temp file write/delete), `LD_SECRET` non-empty, embedded worker thread alive when `LD_EMBEDDED_WORKER=1` | 503 with `{"ok":false,"checks":{…}}`, no internals |
| `GET /api/health` | unchanged, back-compat | none | — |

Compose gains `healthcheck: curl -fsS localhost:8000/api/readyz` on `api` (2 s interval, 10 retries)
and `depends_on: api: {condition: service_healthy}` on `web`, so a cold start no longer serves a
broken SPA. `worker` healthchecks on its heartbeat age via the same endpoint only when embedded, and
otherwise stays on process liveness.

### 4.4 Traces (optional)

`LD_OTEL=1` + `LD_OTEL_ENDPOINT` (OTLP/HTTP). Spans: HTTP server (FastAPI instrumentation) and one
`job.run` span per worker job with `job.kind`, `job.id`, `job.status`. SQLAlchemy is **not**
instrumented (noisy, and the query-count card covers N+1). Without `LD_OTEL` the module is not
imported at all — no import cost, no dependency load.

### 4.5 Frontend telemetry

`apps/frontend/src/lib/telemetry.ts` sends three kinds to `POST /api/telemetry/web`:
`error` (message, sanitised stack ≤ 2 KB, route, request id), `rejection` (reason string) and
`vital` (`lcp|inp|cls|ttfb` + value + page class). The route rate-limits to 60/min per session,
scrubs query strings, drops anything that looks like a token, increments a counter and writes one log
line. A top-level `ErrorBoundary` in `App.tsx` replaces the current white screen with a card that
shows the request id and a "Report" button. No table, no migration, no third party.

### 4.6 System health page

Route `/:ws/system`, `Gate min="admin"`, footer nav entry next to Admin (owner/admin only). One
aggregate endpoint `GET /api/ws/{ws}/system/health` returns, for the caller's workspace:

```json
{"queue":{"queued":3,"running":1,"oldest_queued_s":42,"failed_24h":2},
 "jobs":[{"kind":"export","status":"running","progress":61,"age_s":120}],
 "workers":[{"id":"gpu-1:4271","online":true,"heartbeat_age_s":4,"current_job":"j_…"}],
 "disk":{"free_gb":38.2,"used_ratio":0.74},
 "gpu":{"used_mb":6100,"budget_mb":8192,"leases":["train:…"]},
 "api":{"requests_5m":812,"errors_5m":3,"p95_ms":180},
 "alerts":[{"rule":"queue_stuck","since":1763…}]}
```

`api.*` comes from the in-process metrics registry (same process in the default single-API deploy;
in Compose the page shows "unavailable" rather than a wrong number, which is honest). Layout follows
the glass system: `PageHeader`, solid `Card`s (the override keeps glass on chrome only), the existing
`Progress`/`Stat`-style markup from `AdminConsole.tsx`, 375 px single column, light/dark. Empty state:
"Nothing is queued." Error state: `ErrorLine` with a retry, never a blank page.

### 4.7 Alerts (four rules, one file, one runbook each)

| Rule | Condition | Severity | Runbook |
| --- | --- | --- | --- |
| `disk_low` | `labeldesk_disk_free_bytes{volume="data"} < 5 GiB` | critical | `docs/runbooks/alerts/disk-low.md` |
| `queue_stuck` | `labeldesk_job_oldest_queued_seconds > 900` **and** `labeldesk_workers_online == 0` for 15 min | critical | `alerts/queue-stuck.md` |
| `error_rate_spike` | `rate(labeldesk_http_requests_total{status_class="5xx"}[5m]) / rate(labeldesk_http_requests_total[5m]) > 0.02` for 10 min, with ≥ 20 rps | high | `alerts/error-rate.md` |
| `worker_missing` | `labeldesk_workers_online == 0` for 5 min while jobs are queued | high | `alerts/worker-missing.md` |

Thresholds live in `app/config.py` (`LD_ALERT_DISK_GB=5`, `LD_ALERT_QUEUE_S=900`,
`LD_ALERT_ERROR_RATE=0.02`, `LD_ALERT_WORKER_S=300`) and are read by the checker, so a deployment can
tune them without editing code. Deduplication: one email per rule per hour, state in a module dict
(no table). When neither `LD_OPS_ALERT_EMAIL` nor `LD_SUPERADMINS` is set, the job logs at CRITICAL
and the health page still shows the red state.

### 4.8 Compose profile

`docker compose --profile monitoring up -d` adds:

| Service | Image | Purpose |
| --- | --- | --- |
| `prometheus` | `prom/prometheus:v2.55` | scrapes `api:8000/api/metrics` every 15 s, 15-day retention on a named volume |
| `grafana` | `grafana/grafana:11.2` | one provisioned dashboard, anonymous access off, admin password from `LD_GRAFANA_PASSWORD` |

Pinned tags, no `latest`; both bind to the internal network only (Caddy does **not** route them);
Grafana is reached through an SSH tunnel or a temporary `LD_GRAFANA_PORT` publish, documented in the
runbook. Off by default so the free VM keeps its RAM for the app.

## 5. Phases

| Phase | Cards | Ships | Depends on |
| --- | --- | --- | --- |
| **M0 Foundation** | T-1300, T-1301 | request id + JSON logs; healthz/readyz; compose healthcheck | none |
| **M1 Numbers** | T-1302, T-1311 | HTTP metrics; queue/job/worker/GPU/disk metrics | T-1300 (middleware seam), T-1302 (registry) |
| **M2 Client and tenant** | T-1313, T-1314, T-1315 | frontend errors + vitals; aggregate endpoint; System health page | T-1302 (counters), T-1301 (disk check) |
| **M3 Operations** | T-1316, T-1317 | Prometheus/Grafana profile + dashboard; four alerts + four runbooks | T-1311 (the series the alerts read) |
| **M4 Optional** | T-1312 | OTel traces behind `LD_OTEL` | T-1300 (context), T-1302 |

M0 and M1 are the cheapest and change nothing a user sees. M2 is the first visible surface. M4 can
slip without blocking anything.

## 6. Test strategy

| Layer | Proves | Where |
| --- | --- | --- |
| Unit — log formatter | every key present, JSON parses, no secret or password field survives, fallback text format | `tests/test_logging_request_id.py` |
| Integration — request id | header echoed when supplied, generated when absent, rejects `\n`/`"`/2 000-char values, appears on the same line as the 500's traceback | same file |
| Unit — health | `/api/healthz` touches no DB (a broken session factory still returns 200), `/api/readyz` 503 with the failing check named and no internals | `tests/test_healthz.py` |
| Unit — metrics | route label is the template not the path; a 404 route does not create a series; histogram buckets present; `/api/metrics` 401 without `LD_METRICS_TOKEN`, 200 with it | `tests/test_metrics.py` |
| Unit — scrape-time gauges | queue depth matches a seeded queue; a failed count query yields a stale gauge, not a crash | `tests/test_metrics_system.py` |
| Unit — worker metrics | one outcome counter and one duration observation per job; cancelled and failed both counted | same file |
| Contract — telemetry route | 429 past the budget, oversized stack truncated, `?token=` scrubbed, no writer for an invalid `vital` name | `tests/test_telemetry.py` |
| API — system health | per-workspace isolation (workspace B's counts never appear), member 403, worker heartbeat age, disk shape | `tests/test_system_health.py` |
| Node — page | renders queue/worker/disk cards from a fixture, shows the empty state, shows the error state, no `any` in the API type | `apps/frontend/tests/system-health.test.mjs` |
| Alert checker | each rule fires exactly once per hour, each threshold boundary (4.9 vs 5.0 GiB), the no-recipient path logs and does not raise | `tests/test_system_check.py` |
| E2E | the page loads, shows live numbers after one job is queued, and 375 px has no horizontal scroll | `apps/frontend/e2e/system-health.spec.ts` |
| Compose | `--profile monitoring` config parses, API service has a healthcheck, Prometheus can reach `/api/metrics` (asserted by a `docker compose config` test only — no container start in CI) | `tools/tests/test_deploy_config.py` |

The 15-minute gate gains: three small test files (~15 s). Nothing here starts a container.

## 7. Owner questions

1. **Where do platform alerts go?** Plan: `LD_OPS_ALERT_EMAIL`, falling back to `LD_SUPERADMINS`.
   A dedicated Telegram/LINE channel would need a second delivery path (~40 lines).
2. **Is the tenant "System health" page for workspace owners, or superadmin only?** Plan: owner/admin
   of that workspace see their own numbers; superadmins keep the existing console.
3. **Retention.** Grafana/Prometheus keep 15 days on the volume (~2 GB). Longer needs a bigger volume
   on the free VM.
4. **Prometheus rules instead of the in-product checker?** If you will always run the monitoring
   profile, the four thresholds can live as PromQL rules and the checker card can be dropped (~95
   lines saved, plus Alertmanager to send mail).
5. **Log destination.** JSON to stdout (plan) means `docker compose logs` is the store and a log
   rotation policy matters (`max-size=50m`, `max-file=3`). Loki is the alternative (+1 container).
6. **Grafana exposure.** SSH tunnel only (plan) or a `grafana.<domain>` subdomain behind Caddy with a
   local admin password?
7. **Trace backend.** Point `LD_OTEL_ENDPOINT` at an external collector, or keep traces off until
   there is a local Tempo/Jaeger container?

## 8. Definition of done

- [ ] Every API log line is one JSON object carrying `request_id`, `route`, `status`, `duration_ms`;
      the browser sends and shows the same id.
- [ ] `/api/healthz` and `/api/readyz` behave as in §4.3, and Compose waits on readiness.
- [ ] `/api/metrics` serves the series in §4.2, is closed without `LD_METRICS_TOKEN`, and never
      exposes a raw path label.
- [ ] The System health page shows live queue, worker, disk, GPU and API numbers for its own
      workspace only, in light/dark/375 px, with empty and error states.
- [ ] `docker compose --profile monitoring up -d` yields a dashboard with request rate, error rate,
      p50/p95/p99, queue depth, job durations, worker heartbeat, GPU and disk, with no manual setup.
- [ ] Four alert rules fire with a test each, and each has a runbook that names the first three
      commands to run.
- [ ] No secret, token, password, image path or user email appears in any log line or metric label.
- [ ] R7 has signed off on T-1300, T-1313 (untrusted input) and T-1308's metrics token.
