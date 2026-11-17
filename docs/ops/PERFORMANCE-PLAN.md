# Performance testing plan — LabelDesk

Owner priority 2026-11-17: after UX/UI, security and monitoring, **performance testing**. Budgets,
a repeatable load test, a committed baseline, and a nightly regression check that never enters the
15-minute merge gate.
Planning lane only: docs and cards, no product code. Baseline `feat/labeldesk-v2` (`2fef0ba`).

Read for this note: `docs/OPENCODE_TEAM_FLOW.md` §1/§4c–4e, `docs/architecture/`, `docs/DEPLOY.md`,
`docs/audits/code/CODE-AUDIT.md` (audit lane 2026-11-17; still untracked on `feat` when this was written),
`docs/research/mcp/MCP-PLAN.md` §9, and the code in §1.
Cards: `T-1318`–`T-1324` (wave O).

New role this plan creates: **performance engineer** (R13). Owns `tools/perf/`, the budgets file, the
baseline and the nightly report; does not change product code without a separate card.

---

## 1. Current state

| Signal | Today | Evidence |
| --- | --- | --- |
| Performance tests | **None.** No locust, k6, vegeta, autocannon or Playwright timing assertion anywhere | `tools/`, `apps/frontend/e2e/`, `.github/workflows/ci.yml` |
| Budgets | **None.** No number exists for a route, a page or a job | — |
| Baseline | **None** | — |
| Bundle budget | **None.** The build prints chunk sizes and nobody reads them | `apps/frontend/vite.config.ts` |
| Frontend lab metrics | **None.** No Lighthouse, no web-vitals (see the monitoring plan, M6) | `apps/frontend/package.json` |
| Query counting | **None.** No N+1 guard, no slow-query log in SQLAlchemy | `app/db.py` |
| Known heavy surface | 1 519 test cases; editor 1 288 lines with Konva per image; two chart toolkits (echarts **and** recharts in `package.json`); a 10k-image grid that already uses `@tanstack/react-virtual` | CODE-AUDIT §2.1, `package.json` |
| Job throughput | `POLL = 1.5 s` claim cadence, one local executor thread, GPU lease per training run | `app/worker.py:44,131-140,276-314` |
| Full API suite | ~1 590 tests, 6–15 min serial; `pytest -n 4` is *slower* and breaks shared SQLite | `docs/OPENCODE_TEAM_FLOW.md` §4c(5), card T-1101 |

The good news: the app is already shaped for this. Lists are paginated and virtualised, jobs are a
database queue with compare-and-set claims, and the heaviest work (training, export) is already a job
rather than a request. What is missing is the measurement, not the architecture.

## 2. Gaps

| # | Gap | Why it matters | Card |
| --- | --- | --- | --- |
| P1 | **No budgets.** "Slow" is an opinion | No card can be accepted or rejected on a number | T-1318 |
| P2 | **No seeded load fixture.** There is demo seed data, but no reproducible 10k-image dataset with annotations, versions, models and jobs | Every measurement would use different data and mean nothing | T-1319 |
| P3 | **No load scenarios.** Browse, annotate-save, export and MCP `list_images` are never exercised under concurrency | Regressions are found in production | T-1319 |
| P4 | **No committed baseline and no comparison.** Even a green run tells nobody whether it got worse | Silent 30 % regressions are the normal outcome | T-1320 |
| P5 | **No frontend timing gate.** LCP/INP/CLS are unmeasured; the monitoring plan only observes real users | A bad bundle ships and is averaged away | T-1321 |
| P6 | **No bundle budget.** `echarts` + `recharts` + `konva` in one dependency list, no per-route ceiling | One import can double the editor's load time | T-1322 |
| P7 | **No N+1 or slow-query visibility.** A list endpoint that fires one query per row passes every test | The classic cause of "the grid takes 6 s" | T-1323 |
| P8 | **No report artefact.** A perf run's numbers live in a scrollback buffer | The owner cannot see progress across weeks | T-1324 |

## 3. Options, with size

### 3.1 Load tool

| # | Option | Footprint | Script LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **locust** (`--headless`, Python, same venv as the API) | ~35 MB of wheels in a venv; no binary to version | ~190 (`locustfile.py` + `seed.py`) | **Chosen.** One language, one venv, and the seed script can import the app models directly instead of re-implementing them over HTTP. |
| 2 | k6 | one 25 MB binary per machine, JS scripts, thresholds as code | ~170 | Rejected: a second toolchain and a download in CI for the same scenarios; its threshold syntax is nicer, the comparison script is still needed for the 10 % rule. Swap-in cost is one file if the owner prefers it. |
| 3 | Vegeta | one 8 MB binary, targets file | ~60 | Rejected: no scenario logic (no login → token → call chain, no job polling), so the four scenarios become shell glue. |
| 4 | pytest + httpx + threads | none | ~140 | Rejected: reinvents a load generator, no percentile reporting, no ramp control. |

### 3.2 Baseline and regression

| # | Option | Prod LOC | Verdict |
| --- | --- | --- | --- |
| 1 | **`docs/ops/perf/baseline.json` + a 90-line `tools/perf/compare.py`** (per-metric delta, exit 1 past the threshold) | ~90 | **Chosen.** Reviewable in a PR, no service, works in CI and locally. |
| 2 | `pytest-benchmark` JSON history | ~40 | Rejected: it measures functions, not HTTP p95 under concurrency. |
| 3 | Grafana snapshot comparison | 0 code, needs the monitoring stack up | Rejected as the gate: a nightly gate must not depend on a running dashboard. |

### 3.3 Frontend measurement

| # | Option | Footprint | LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **Playwright + `web-vitals` in the page context, against the real built SPA and a seeded API** | Playwright already installed | ~110 | **Chosen.** Chromium is already in the e2e job; the same library the app ships (T-1313) is the oracle, so lab and field numbers agree. |
| 2 | Lighthouse CI (`@lhci/cli`) | +~40 MB, own Chromium, own assertion format | ~60 config | Rejected: a second browser and a second budget format for pages Playwright already opens. |
| 3 | Chrome DevTools Protocol traces by hand | 0 | ~200 | Rejected: more code, less stable. |

### 3.4 Bundle budget

| # | Option | LOC | Verdict |
| --- | --- | --- | --- |
| 1 | **60-line `scripts/check-bundle.mjs` reading `dist/.vite/manifest.json` and `dist/assets/*.js` gzip sizes against `budgets.json`** | ~60 + 6-line script entry | **Chosen.** Runs in 0.3 s inside the existing web job; no plugin, no service. |
| 2 | `rollup-plugin-visualizer` | ~30 + a 1 MB treemap artefact | Rejected as a gate (it renders, it does not fail); can be added ad hoc when a budget trips. |
| 3 | `vite-bundle-visualizer` | ~20 | Same rejection: a report, not a ceiling. |

### 3.5 Query profiling

| # | Option | Prod LOC | Test LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **SQLAlchemy `before_cursor_execute`/`after_cursor_execute` listener: a per-request counter in tests and a slow-statement log behind `LD_SLOW_SQL_MS`** | ~55 | ~90 | **Chosen.** One listener serves both jobs, zero dependency, works on SQLite and Postgres. |
| 2 | `nplusone` | 0 | ~30 + a dep | Rejected: unmaintained, Flask/Django era, noisy on SQLAlchemy 2. |
| 3 | Postgres `log_min_duration_statement` only | 0 | 0 | Insufficient alone: the default deployment is SQLite and the N+1 guard must run in CI. Documented as the production complement. |

## 4. Chosen design

### 4.1 Budgets (the file the gate reads)

`docs/ops/perf/budgets.json` holds every number; the cards and the nightly job read it, nobody
hard-codes a threshold in a script. Initial values below are **ceilings** to be ratcheted down after
the first baseline (T-1320), not measured facts.

**API p95, single API process, 20 concurrent users, seeded 10k images:**

| Route class | Example | p95 ceiling | p99 ceiling |
| --- | --- | --- | --- |
| Auth write | `POST /api/auth/login` (PBKDF2 260k) | 500 ms | 900 ms |
| Read, detail | `GET /api/ws/{ws}/projects/{slug}/images/{id}` | 150 ms | 350 ms |
| Read, list page | `GET …/images?limit=25` | 250 ms | 550 ms |
| Read, filtered list over 10k | `GET …/images?status=&class_id=&q=` | 600 ms | 1 200 ms |
| Read, aggregate | `GET …/projects/{slug}` (status counts) | 300 ms | 700 ms |
| Write, annotation save (20 boxes) | `PUT …/images/{id}/annotations` | 300 ms | 650 ms |
| Write, bulk move (500 images) | `POST …/board/move` | 1 200 ms | 2 500 ms |
| Upload (10 MB JPEG) | `POST …/upload` | 2 500 ms | 4 500 ms |
| Enqueue | `POST …/versions`, `…/export`, `…/train` | 300 ms | 700 ms |
| File download | `GET /api/files/{rel}` | 200 ms TTFB | 500 ms TTFB, ≥ 20 MB/s |
| Metrics scrape | `GET /api/metrics` | 100 ms | 250 ms |
| MCP tool call | `tools/call list_images` (50 items) | 400 ms | 900 ms |
| Health | `GET /api/healthz`, `/api/readyz` | 20 ms / 60 ms | 50 / 150 ms |
| Error | any 4xx/5xx | 50 ms | 120 ms |

**Pages (Chromium, production build, p75 of 5 runs, warm cache):**

| Page | LCP | INP | CLS |
| --- | --- | --- | --- |
| Login → Home | 1.8 s | 200 ms | 0.05 |
| Projects list (30 projects) | 2.0 s | 200 ms | 0.05 |
| Dataset grid (10k images, 25 rendered) | 2.5 s | 250 ms | 0.10 |
| Editor open (1 image, 40 boxes) | 2.5 s | 250 ms | 0.10 |

**Bundle (gzip, from the build manifest):**

| Chunk class | Ceiling |
| --- | --- |
| Entry (`index-*.js`) | 400 KB |
| Any lazy route chunk | 300 KB |
| Any single chunk | 500 KB |
| Cold route total (entry + its route chunk + shared) | 900 KB |

**Jobs (one local worker thread, CPU):**

| Measure | Ceiling |
| --- | --- |
| Claim latency (queued → running) p95 | 3 s (poll 1.5 s) |
| `version` job, 10k images | 120 s |
| `export` job, 1k images COCO | 30 s |
| 100 light jobs (`health`, small exports) drained | 10 min |
| Job duration regression vs baseline | +10 % |

**Database:**

| Measure | Ceiling |
| --- | --- |
| Queries per list request | 25, and **equal** for `limit=10` and `limit=100` (no N+1) |
| Queries per editor open | 60 |
| Any single request | 200 queries (catch-all failure) |
| Slow statement logged above | `LD_SLOW_SQL_MS` (200 ms dev, off by default; Postgres `log_min_duration_statement=200` in production) |

### 4.2 Scenarios (`tools/perf/locustfile.py`)

Fixed, documented, and the same four the owner named:

| Scenario | Weight | What it does |
| --- | --- | --- |
| `browse_10k` | 6 | login → `GET /projects` → `GET images?limit=25` pages 1, 20 and 200 (deep offset) → one filtered query → 6 thumbnails through signed URLs |
| `annotate_save` | 3 | open a random image → `PUT` 20 boxes twice (replace, then review status) |
| `export` | 1 | `POST` a version export → poll the job every 1 s to terminal (bounded 60 s) |
| `mcp_list_images` | 1 | JSON-RPC `tools/call` over the MCP HTTP transport with an `ld_` key, `limit=50` |

20 users, spawn 2/s, 5 minutes, fixed seed for image selection, `--csv` output. Every request records
its scenario so the report is per class, not one blob. Auth tokens are minted once per user at start
(not per request), so the test measures the product, not the password hasher.

### 4.3 Seed (`tools/perf/seed.py`)

Builds a throwaway SQLite database in `B:/02_Projects/ld-tmp/perf/` (never the dev database):
1 workspace, 1 owner, 4 projects, 30 classes, 10 000 images across projects (200 real 12 KB JPEGs
copied and shared by sha so disk stays under 3 MB), 40 000 annotations, 20 versions, 5 models,
200 terminal jobs and 20 queued jobs. Deterministic (`random.Random(1337)`), idempotent (`--reset`),
and it writes the demo credentials and ids to `perf-seed.json` for the scenarios. Runs in under 20 s.

### 4.4 Nightly job (outside the gate)

`.github/workflows/nightly-perf.yml`, `schedule: cron "0 3 * * *"` and `workflow_dispatch`. It is a
**separate workflow** with no `paths` filter and it is **not** in the `gate` aggregator, so it cannot
block a merge and cannot leave a required check pending.

Steps: install → seed → start `uvicorn` on 8011 → wait on `/api/readyz` → locust headless → Playwright
perf spec → bundle check → `tools/perf/compare.py` against `baseline.json` → write
`docs/ops/perf/report-<sha>.{json,md}` → upload artefact (90 days).

**Runner honesty.** A shared GitHub runner varies by roughly ±20 % on the same commit, so a 10 %
threshold there would flake. The job therefore compares with `regression_pct: 10` when it runs on a
self-hosted runner labelled `perf` (the owner's box, the only place the number means something) and
with the `shared_runner_pct: 25` allowance otherwise, and the report header states which one ran. The
strict 10 % check is also one command locally: `python tools/perf/compare.py --strict`. Owner
question Q1.

### 4.5 Report artefact

`tools/perf/report.py` turns the locust CSV + Playwright JSON + bundle output + query counts into one
markdown file (a table per budget class: budget, baseline, run, delta, verdict) and one JSON file with
the same data. The JSON is the machine input for `compare.py`; the markdown is what the owner reads.

## 5. Phases

| Phase | Cards | Ships | Depends on |
| --- | --- | --- | --- |
| **P0 Budgets** | T-1318 | `budgets.json`, the numbers above, one page that explains how each is measured | none |
| **P1 Harness** | T-1319 | seed + four scenarios, runnable by hand in one command | T-1318 |
| **P2 Baseline and night run** | T-1320, T-1324 | first committed baseline, `compare.py`, nightly workflow, report artefact | P1, and T-1302 (`/api/metrics` for error and queue numbers in the report) |
| **P3 Frontend** | T-1321, T-1322 | web-vitals gate, bundle budgets | P1 (seeded API), T-1313 (vitals in the app) |
| **P4 Database** | T-1323 | query-count guard, slow-statement log | none (can run in parallel with P1) |

P0, P1 and P4 touch no product behaviour and can start immediately. Nothing in this plan joins the
15-minute gate except the bundle check (0.3 s) and the query-count tests (~10 s).

## 6. Test strategy

| Layer | Proves | Where |
| --- | --- | --- |
| Budgets file | schema: every class present, all values positive, floors below ceilings, no class without a route example | `tools/tests/test_perf_budgets.py` |
| Seed | 10k images, 40k annotations, 200 terminal jobs, deterministic across two runs, `--reset` is clean, under 3 MB on disk | `tools/tests/test_perf_seed.py` |
| Scenarios (dry) | every scenario resolves its routes from the OpenAPI document, so a renamed route fails the nightly instead of 404-ing silently | `tools/tests/test_perf_routes.py` |
| Compare | 9 % delta passes, 11 % fails, a missing metric fails, a new metric warns, `--strict` vs shared-runner mode | `tools/tests/test_perf_compare.py` |
| Budgets in CI (cheap) | bundle sizes within ceilings, built from a real `vite build` | `apps/frontend/tests/bundle-budget.test.mjs` or the script's own `--check` |
| Frontend lab | LCP/INP/CLS per page against the same `budgets.json` | `apps/frontend/e2e/perf.spec.ts` (nightly, not the gate) |
| N+1 | list at `limit=10` and `limit=100` issue the same number of queries; editor open ≤ 60; no request over 200 | `apps/backend/tests/test_perf_queries.py` (in the gate) |
| Slow log | a statement over `LD_SLOW_SQL_MS` writes exactly one structured line with `request_id` and no bound values | `apps/backend/tests/test_slow_query.py` (in the gate) |
| Job throughput | a scripted 100-job drain under the budget, marked `slow` and skipped unless `LD_PERF=1` | `apps/backend/tests/test_perf_jobs.py` (nightly only) |

The 15-minute gate gains ~10 s (query counts, slow log, bundle check). The nightly job is the only
place that starts a server and drives load.

## 7. Owner questions

1. **Nightly runner.** Is a self-hosted runner (the GPU/VM box) available, so the nightly uses the
   real 10 % threshold? Without one, the nightly reports against a 25 % shared-runner allowance and
   the strict check is a command the owner runs. Which do you want as the default?
2. **Baseline ratchet.** After the first measured baseline, do budgets tighten to "baseline + 5 %" so
   the app can only get faster, or stay at the ceilings in §4.1 until the UI work settles?
3. **Where the night job runs.** GitHub Actions only, or also a Windows Task Scheduler entry on the
   owner's machine (`tools/perf/run.ps1`)? The GPU box is where numbers are stable.
4. **Job throughput target.** The §4.1 job numbers are educated ceilings (export 1k ≤ 30 s, version
   10k ≤ 120 s). If the demo expects 10k exports in a minute, that is a different card (streaming
   writer) and should be decided before P2.
5. **Bundle ceiling.** 400 KB entry / 900 KB cold route assumes the two chart libraries stay. Dropping
   `recharts` (the code audit found two chart toolkits) would buy ~120 KB; is that in scope for this
   wave or a separate cleanup card?
6. **Concurrency profile.** 20 users is a laptop number. What is the deployment's real concurrent
   user count on the free VM (likely 3–5), so the report can state a realistic headroom?
7. **Retention of reports.** 90-day artefacts in CI plus the committed baseline, or commit every
   nightly report to `docs/ops/perf/history/`?

## 8. Definition of done

- [ ] `docs/ops/perf/budgets.json` exists with every class in §4.1 and is validated by a test.
- [ ] `tools/perf/seed.py` builds the 10k-image fixture deterministically in under 20 s.
- [ ] `locust --headless -f tools/perf/locustfile.py` runs the four scenarios and writes CSV.
- [ ] `docs/ops/perf/baseline.json` contains the first measured run with its machine, commit and date.
- [ ] `tools/perf/compare.py` fails on a >10 % regression in strict mode and prints the per-class delta.
- [ ] The nightly workflow produces `report-<sha>.md` and `.json` and is not part of `gate`.
- [ ] The bundle check fails the web job past an entry ceiling and passes on a clean build.
- [ ] The N+1 test fails when a `limit`-dependent query loop is introduced (proved by a deliberate
      temporary change in the card's RED step) and passes on the real code.
- [ ] No performance test runs inside the 15-minute merge gate except the bundle check and the
      query-count file.
