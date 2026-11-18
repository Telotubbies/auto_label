# Security plan — LabelDesk

Owner priority 2026-11-17: after UX/UI, **security first**, then monitoring, then performance.
This note answers "what security work does the whole product need, in what order, at what size".
Planning lane only: no product code, no merge, baseline `feat/labeldesk-v2` (`2fef0ba`).

Read for this note: `docs/OPENCODE_TEAM_FLOW.md` §1/§4c–4e, `docs/OPENCODE_PM_RULES.md`,
`docs/architecture/`, `docs/DEPLOY.md`, `docs/runbooks/`, `docs/audits/code/CODE-AUDIT.md` (audit lane
2026-11-17; still untracked on `feat` when this was written),
`docs/research/inference-hub/PLAN.md` §5, `docs/research/mcp/MCP-PLAN.md`, and the code named in §1.
Cards: `T-1303`–`T-1310` in `docs/research/roboflow-parity/backlog/` (wave O).

The product is one repository with six trust boundaries: the browser, the API process, the job
worker, remote `labeldesk-worker` hosts, the MCP server, and the future inference hub. Each one is
already partly defended; this plan closes the gaps a reviewer would find, in the cheapest order.

---

## 1. Current state (measured, not remembered)

| Area | What exists | Evidence |
| --- | --- | --- |
| Sessions | JWT HS256, access 15 min, refresh 30 days stored **hashed**; rotation on login, MFA enrol/remove and password change, which revokes every other session | `app/security.py:14-16`, `routers/auth.py:68,135-140,233-246,359,382,415` |
| Passwords | PBKDF2-SHA256, 260 000 rounds, `hmac.compare_digest` | `app/security.py:18,21-30` |
| MFA | TOTP, recovery codes hashed, workspace-level "MFA required" | `app/totp.py`, `routers/workspaces.py:67` |
| Login history | `LoginEvent(ok, method, ip, user_agent)` per attempt | `routers/auth.py:75-79` |
| RBAC | Workspace role + per-project role + custom-role grants (`need()` and `perm()`); **known divergence** for custom grants | `app/deps.py`, `app/rbac.py`; CODE-AUDIT §6.5 |
| Workspace isolation | Every query filters `workspace_id`; trained models resolve through `resolve(ref, db, workspace_id=…)`; no row-level security | `docs/architecture/overview.md:41` |
| API keys | `ld_` workspace keys and `ld_pub_` publishable keys, stored as a hash, scopes `read|upload|train|infer`, publishable forced to `infer`, `?api_key=` refused except publishable, 600 lookups/60 s/IP, throttled `apikey.use` audit row | `app/apikeys.py:21-23,39-41,67-93`, `routers/workspaces.py:255-256` |
| Uploads | `MAX_UPLOAD_MB` budget per request, filename sanitising, Pillow decode, face blur fail-closed | `routers/images.py:39-43,171-177`, `services/faceblur.py` |
| Outbound URLs | `safefetch`: http(s) only, every resolved address must be global unicast, NAT64 blocked, connection pinned to the vetted IP, every redirect hop re-checked, one total deadline, 20 MB cap; webhook POST never follows redirects | `services/safefetch.py:26-190` |
| Webhooks / connectors | Signing secret and connector credentials encrypted with `enc:v1:`; `LD_SECRET` rotation via MultiFernet + startup migration | `services/secretbox.py:1-113` |
| PLC/OT | `LD_OT_ALLOW_CIDR` opt-in, drivers fail safe when the optional package is absent | `app/config.py:156`, `app/ot/` |
| MCP | Per-request bearer key, scope-filtered tool list, `confirm` gate on spend/write, recursive scrubber, `Origin`/`Host` allowlist, publishable keys refused, `mcp.tool` audit row per call | `apps/mcp/labeldesk_mcp/`, `app/apikeys.py:90-92`, `tests/test_mcp_isolation.py` |
| Remote workers | Outbound-only HTTPS, `LD_WORKER_TOKEN` ≥ 24 chars, compare-and-set claim, stale job reaper | `app/worker.py:131-140,240-256`, `app/services/remote_reaper.py` |
| Installers | Exact pins with `source_url`, digest-pinned containers, no user index URL (planned hub) | `docs/research/inference-hub/PLAN.md` §5 |
| Secrets | `LD_SECRET` ≥ 32 chars enforced at startup, rotation documented and tested | `app/config.py`, `docs/DEPLOY.md:141-150` |
| Headers | API: `nosniff`, `Referrer-Policy`, `X-Frame-Options`, `no-store` + `default-src 'none'` CSP on `/api/*`. SPA: full CSP in `nginx.conf` and `vercel.json`, HSTS at Caddy and Vercel | `app/main.py:66-76`, `apps/frontend/nginx.conf`, `deploy/Caddyfile` |
| Rate limits | 18 sites: login 30/5 min/IP and 8/5 min/IP+email, signup, MFA, refresh, forgot/reset, verify, password check, comments, VLM suggest, API-key lookup | `app/ratelimit.py`, `routers/auth.py`, `routers/images.py:634,672`, `apikeys.py:81` |
| Audit log | 67 write sites across auth/workspace/project/image/stream/train/OT/webhook/connector/keys/privacy/RBAC, plus `audit.export` and CSV/JSON export | `app/deps.py:177-179`, `routers/audit.py` |
| Gates | CI runs ruff (pyflakes only, `ruff.toml` `select = ["F"]`) over `apps/backend`, the API suite, the web build, node tests, pipeline tests and a large-file check | `.github/workflows/ci.yml`, `ruff.toml` |

The defensive work already done is real: the SSRF guard, secretbox, scoped keys, MCP confirm gate and
the audit trail are stronger than the average project this size.

## 2. Gaps

Each gap is owned by exactly one card. "Block" means the CI gate fails on it.

| # | Gap | Why it matters | Card |
| --- | --- | --- | --- |
| S1 | **No SAST beyond pyflakes.** `ruff select = ["F"]` sees unused imports, not `eval`, `subprocess` with a shell, `try/except: pass`, weak crypto, hard-coded passwords. 825 broader ruff findings were measured in the code audit. | Injection and swallowed-error classes ship silently | T-1303 |
| S2 | **No dependency vulnerability scan** in CI, on either side. `requirements.txt` uses `>=` ranges with no lock and no hashes. | A CVE in FastAPI/SQLAlchemy/Pillow/Ultralytics reaches production with no notice | T-1303 |
| S3 | **No secret scanning.** A key pasted into a test or a doc is invisible until it is abused. | Key leak is a workspace takeover (`ld_` keys are admin keys to `/api/v1`) | T-1303 |
| S4 | **No licence gate.** Ultralytics is AGPL-3.0 by decision, but nothing stops an unknown or non-redistributable licence arriving tomorrow; a public launch needs the list. | Legal exposure discovered at launch | T-1303 |
| S5 | **Cross-workspace IDOR is tested file by file**, not as one matrix over every resource kind. New routes inherit no test. | One missed `workspace_id` filter is a tenant data leak | T-1304 |
| S6 | **No auth-bypass matrix**: expired/tampered/missing token, wrong-scope key, publishable key on a non-`infer` route, revoked key, refresh-token replay, cross-workspace file URL. | Silent regressions in the most attacked paths | T-1304 |
| S7 | **No injection / traversal / SSRF adversarial suite in one place.** `safefetch` has unit tests; route-level paths (search `q`, class names, export names, `?path=`-shaped params, `files/{rel}`) are covered incidentally. | SQLi/XSS/traversal regressions are found by users | T-1305 |
| S8 | **No written threat model.** The inference-hub and MCP notes carry local threat tables; nothing covers auth, uploads, connectors, OT, workers or supply chain as one document. | Reviews re-derive the same reasoning, and new surfaces are assessed ad hoc | T-1306 |
| S9 | **No ASVS L2 / OWASP API Top 10 mapping.** "Are we secure?" has no answer that cites a standard. | Owner cannot judge posture; auditors cannot be answered | T-1307 |
| S10 | **Header gaps.** No `Permissions-Policy` or `Cross-Origin-Opener-Policy` on API responses; no CSP violation report endpoint; HSTS exists only where Caddy or Vercel terminates TLS (a bare `nginx.conf` deployment has none). | Clickjacking/side-channel hardening left half done | T-1308 |
| S11 | **No protection for the new metrics surface.** `/metrics` will be internet-adjacent by default once monitoring lands. | Metrics leak route names, volumes and tenant activity | T-1308 |
| S12 | **Rate limits cover auth, keys, comments and one VLM call only.** Uploads, `/predict`, exports, version creation, search and MCP tool calls have no per-caller ceiling; there is no global per-IP ceiling. | One authenticated client can exhaust disk, GPU or credits | T-1309 |
| S13 | **Audit-log coverage holes.** Login/logout/failed login live in `LoginEvent` (per user, not per workspace), annotation save/delete, image delete, job cancel and key refusals write no `Audit` row. | "Who deleted the batch?" is unanswerable; PDPA export misses the auth history | T-1310 |
| S14 | **Custom-role divergence** (`need(role)` vs `perm(perm)`) 403s a legitimate grant on three endpoints. Security-adjacent, flagged by the code audit. | A grant that shows in the UI does not work | Owner decision (Q3) |

Deliberately out of scope here: WAF in front of the stack (Caddy + rate limits + payload caps cover the
realistic threats on one VM), third-party pentest (the in-repo suite is the repeatable part), and
malware scanning of uploads (images only, decoded by Pillow, never executed; AV adds a daemon and an
outbound call the product does not need yet).

## 3. Options, with size

Measured as production lines that stay in the repo. Test lines are quoted separately because they are
the safety net, not the design.

### 3.1 Static analysis

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **ruff `S` (flake8-bandit) added to the existing `ruff.toml`** | none — ruff 0.17.3 is already pinned and already gates `apps/backend` | ~15 config + ~30 targeted `# noqa` | **Chosen.** Zero new tool, same pinned version, same output format, one extra select. |
| 2 | `bandit -r apps/backend` | bandit | ~10 config + a baseline file with ~40 ignores | Rejected: a second scanner over the same rules, its own false-positive baseline to maintain. |
| 3 | Semgrep with a community ruleset | semgrep (~50 MB, needs network) | ~40 + triage | Rejected for now: better dataflow, too heavy for a single machine CI; revisit if the owner buys a hosted scanner. |

### 3.2 Dependency and secret gates

| # | Option | New dependency | Prod LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **`pip-audit -r requirements.txt` + `npm audit --omit=dev` + `gitleaks dir` + one 60-line licence script** | pip-audit, gitleaks binary | ~90 (script) + ~25 YAML | **Chosen.** Each tool is single-purpose, offline-capable (pip-audit has `--no-deps` cache; gitleaks is a binary), and the licence script reads installed metadata instead of adding a fifth tool. |
| 2 | `safety` + `retire.js` + `detect-secrets` | three tools | ~90 | Rejected: `safety` now needs an account for its database; `detect-secrets` needs a committed baseline that rots. |
| 3 | OSV-Scanner + Dependabot PRs | osv-scanner binary; Dependabot config | ~40 | Rejected as the gate (Dependabot opens PRs, it does not block a merge), kept as an owner question (Q5). |

### 3.3 Threat model and standards mapping

| # | Option | Prod LOC | Verdict |
| --- | --- | --- | --- |
| 1 | **Markdown STRIDE table + data-flow list in `docs/ops/THREAT-MODEL.md`** | 0 code, ~220 doc lines | **Chosen.** Lives next to the plans, reviewed like code, no tool to keep alive. |
| 2 | Threat Dragon / pytm models | ~150 model lines + a renderer | Rejected: a diagram tool nobody opens beats no tool only if it is maintained; the table is the artefact reviewers use. |
| 3 | Nothing; rely on the per-wave tables | 0 | Rejected: the owner asked for one app-wide model, and waves I and M each cover one surface. |

ASVS/API-Top-10 mapping: **one table** (`docs/ops/ASVS-GAPS.md`), every gap row citing a card or a
one-line accepted risk. The alternative (a spreadsheet per release) costs the same and rots faster.

### 3.4 Adversarial suites

| # | Option | Prod LOC | Test LOC | Verdict |
| --- | --- | --- | --- | --- |
| 1 | **pytest files over the real app with the existing fixtures** | 0 | ~420 total (T-1304 + T-1305) | **Chosen.** Runs in the existing 15-minute gate with the seeded database, and it can assert workspace isolation because it owns the fixture. |
| 2 | OWASP ZAP baseline scan in CI | 0 | ~50 workflow + triage per run | Rejected: a live scan of a seeded app is flaky, slow and blind to the cross-workspace checks that matter here. |
| 3 | Schemathesis over `openapi.json` | schemathesis | 0 | ~60 + triage | Deferred: a good addition later for 500-hunting; it cannot see IDOR. |

### 3.5 Headers, limits, audit

| Area | Options | Prod LOC | Chosen |
| --- | --- | --- | --- |
| Headers | (a) extend the existing middleware with `Permissions-Policy`, `COOP`, `CORP` and a CSP report endpoint; (b) add headers only in Caddy/nginx; (c) a third-party middleware package | (a) ~35 | **(a)** — one place, works for the API origin and any proxy; the SPA CSP already exists in two files and stays there |
| `/metrics` exposure | (a) bearer `LD_METRICS_TOKEN` when set, never routed by Caddy; (b) bind a second port on `127.0.0.1`; (c) leave it open on the internal network | (a) ~20 | **(a)** — one env var, works for both Prometheus (compose network) and the in-product checker |
| Rate limits | (a) a route-class middleware over the existing `limit()` kernel; (b) `slowapi` decorators on ~30 routes; (c) limits inside each router | (a) ~55 | **(a)** — one map, one middleware, no new dependency, no decorator on every route |
| Audit coverage | (a) add `audit()` calls at the 6 missing sites; (b) an event bus with subscribers; (c) derive audit from application logs | (a) ~15 | **(a)** — the existing `audit()` is already the seam and the export already reads it |

## 4. Chosen design

### 4.1 The gate (what blocks and what warns)

Ordered by cost. Everything runs in the existing `api`/`web`/`tools` jobs; the only new job is
`security` (target ≤ 3 min, so the gate stays inside its current wall time).

| Check | Command | Blocks? | Ignore list |
| --- | --- | --- | --- |
| SAST | `ruff check apps/backend tools` with `select = ["F","S"]` | **blocks** | inline `# noqa: S101` etc., max ~30, each with a reason |
| Python CVEs | `pip-audit -r apps/backend/requirements.txt --strict` | **blocks** on high/critical | `security/audit-ignore.txt` with a comment and an expiry date per entry |
| Node CVEs | `npm audit --omit=dev --audit-level=high` | **blocks** | `npm audit` overrides in `package.json` |
| Node CVEs (dev) | `npm audit --audit-level=high` | warns | — |
| Secrets | `gitleaks dir . --redact` | **blocks** | `.gitleaks.toml` for test fixtures that look like keys |
| Licences | `python tools/check_licenses.py` over installed metadata + `package-lock.json` | warns; **blocks** on "no licence" or a licence outside the allowlist | `security/licences-allow.txt`; AGPL-3.0 is listed and annotated "Ultralytics, deliberate" |

Why this split: a CVE or a committed key must stop a merge (fix is one line), a licence is a legal
judgement the owner makes (must not block a hotfix), and dev-only npm advisories are noisy.

### 4.2 Threat model shape

`docs/ops/THREAT-MODEL.md` is a STRIDE table per trust boundary — eleven boundaries, five columns
(threat, impact, existing control, residual risk, card). Boundaries: auth/session, RBAC and workspace
isolation, API keys, uploads, safefetch/SSRF, webhooks and connectors, PLC/OT, MCP, workers and
installers, secrets, dependency supply chain. Each row's limits are in
[`THREAT-MODEL.md`](THREAT-MODEL.md). The inference hub's §5 table is folded in as the
installer boundary rather than duplicated.

### 4.3 Adversarial suites

Two files, one theme each, driven by a parameter table so a new resource kind is one row:

- `tests/test_sec_idor.py` — for every resource kind (project, image, annotation, version, model,
  job, stream, connector, webhook, alert channel, workflow, API key, audit export, file URL): workspace
  A's session and workspace A's API key against workspace B's id → **404**, never 403-with-data and
  never 200. Plus the auth-bypass matrix: no header, `Bearer garbage`, expired access, tampered
  signature, revoked key, publishable key on a write route, refresh replay after rotation.
- `tests/test_sec_injection.py` — SQL metacharacters in `q`/class name/tags/slug (assert no error text
  leaks and no row escapes the workspace), stored-XSS payloads in names and comments (assert the API
  returns them escaped where it renders HTML, and the SPA never `dangerouslySetInnerHTML`s them —
  a grep guard), path traversal in `files/{rel}`, export file names, upload filenames and MCP
  `project` slugs, and SSRF payloads through every route that accepts a URL (upload-by-URL, stream
  source, webhook, connector, MCP `upload_image_url`) including `169.254.169.254`, `127.0.0.1`,
  `[::1]`, `0.0.0.0`, `metadata.google.internal`, decimal-IP and redirect-to-private forms.

Test budget: both files must finish in under 40 s together on the seeded SQLite database; they are
part of the API job, not a new job.

### 4.4 Rate limits (one map)

| Class | Limit | Key |
| --- | --- | --- |
| Anonymous, per IP | 120 / 60 s | IP |
| Authenticated, per user | 600 / 60 s | user id |
| API key, per key | 600 / 60 s (existing) | key id |
| Upload | 30 / 60 s, `MAX_UPLOAD_MB` unchanged | user |
| Inference / predict | 120 / 60 s | user or key |
| Export / version create | 10 / 60 s | user |
| MCP tool calls | 120 / 60 s | key |

Implemented as `ROUTE_LIMITS = ((prefix, limit, window, who), …)` walked by one middleware; the
existing `limit()` kernel does the counting, so `LD_RATE_LIMIT=0` still disables everything.

### 4.5 Audit coverage to add

`auth.login`, `auth.login_failed` (both also keep writing `LoginEvent`), `auth.logout`,
`image.annotate` (per save, with a count, not per box), `image.delete`, `job.cancel`, and
`apikey.refused` (wrong scope or publishable key on a non-infer route). Six calls, all through the
existing `audit()`.

## 5. Phases

| Phase | Cards | Ships | Depends on | Gate |
| --- | --- | --- | --- | --- |
| **S0 Quick wins** | T-1303, T-1304 | scanners in the gate; the IDOR/auth-bypass matrix | none | the gate turns red once, then clean with a documented ignore list |
| **S1 Written posture** | T-1306, T-1307 | threat model; ASVS L2 + API Top 10 gap map | S0 evidence (scanner output feeds the gap list) | docs reviewed by R7 |
| **S2 Adversarial depth** | T-1305 | injection/traversal/SSRF suite | T-1304 (shared fixture helpers) | 40 s test budget met |
| **S3 Hardening** | T-1308, T-1309, T-1310 | headers + metrics token; rate-limit map; audit holes | T-1303 (the `S` rules must already pass) | no route changes its documented behaviour except 429s beyond the limits |

S3 is last on purpose: each of its cards changes runtime behaviour, and the owner should see the
scanner and suite output before a rate limit starts refusing a legitimate script.

## 6. Test strategy

| Layer | Proves | Where |
| --- | --- | --- |
| Scanner self-test | the gate fails when it should: a fixture file with a hard-coded password and a fake key makes the security job exit non-zero in a scratch clone | `tools/tests/test_gate_security.py` |
| Licence script | allowlist parsing, AGPL annotated, unknown licence blocks, npm side reads the lockfile | `tools/tests/test_check_licenses.py` |
| IDOR matrix | 404 across 14 resource kinds × 2 principal types | `apps/backend/tests/test_sec_idor.py` |
| Auth bypass | 401/403 for every malformed credential; no data in the body | same file |
| Injection / traversal / SSRF | payloads are inert; no internal address is contacted (socket guard) | `apps/backend/tests/test_sec_injection.py` |
| Headers | `Permissions-Policy`, `COOP`, `nosniff`, API CSP on every JSON route, no `Server` header | `apps/backend/tests/test_sec_headers.py` |
| Rate limits | each class returns 429 past its budget, `Retry-After` present, `LD_RATE_LIMIT=0` disables | `apps/backend/tests/test_sec_ratelimit.py` |
| Audit coverage | one row per listed action, no secret in `meta` | `apps/backend/tests/test_audit_coverage.py` |
| Docs guard | every ASVS gap row cites an existing card id; every card id in the gap map exists | `tools/tests/test_docs_ops.py` (created by T-1306, extended by T-1307) |

Full gate cost added by this wave: scanners ≈ 90 s, two test files ≈ 40 s. Both fit the existing jobs.

## 7. Owner questions

1. **`LD_` key lifetime.** Workspace API keys have no expiry. Should the plan add an optional
   `expires` per key (about 40 lines, one column, one UI field), or is revocation enough?
2. **AGPL exposure.** Ultralytics stays, with the badge. Do you want the licence gate to *warn* on
   AGPL (as planned) or *block* once a hosted public service exists?
3. **Custom-role divergence** (`need` vs `perm`, three endpoints): fix so a grant works, or remove the
   grant from the UI? It is a product decision, one card either way.
4. **Upload scanning.** Do customers upload arbitrary images only, or may a `.zip` dataset arrive?
   If zips are ever accepted, an archive-bomb guard and a scanning story are needed before that card.
5. **Dependabot.** Automatic PRs for CVE bumps (owner may prefer a nightly report instead)?
6. **Public `/metrics`?** Confirm it stays internal with `LD_METRICS_TOKEN` and is never routed by
   Caddy, even though that means a hosted Grafana cannot scrape it directly.

## 8. Definition of done

- [ ] `ruff check` (F + S), `pip-audit`, `npm audit`, `gitleaks` and the licence script run in CI and
      the security job is part of the `gate` aggregator.
- [ ] `docs/ops/THREAT-MODEL.md` covers all eleven boundaries with a card or an accepted risk per row.
- [ ] `docs/ops/ASVS-GAPS.md` maps every L2/API-Top-10 row to a card, a guard, or an accepted risk.
- [ ] The IDOR and injection suites are in the 15-minute gate and green.
- [ ] No response leaves the API without `nosniff`, `Permissions-Policy` and the API CSP; `/metrics`
      answers 401 without the token.
- [ ] Every rate-limit class has a 429 test; `LD_RATE_LIMIT=0` still disables all of them.
- [ ] The six audit actions are written and asserted; the audit export still passes its tests.
- [ ] R7 has signed off on T-1303, T-1304, T-1305, T-1308, T-1309, T-1310.
