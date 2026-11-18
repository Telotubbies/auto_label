# ASVS L2 and API Top 10 gap map — LabelDesk

The answer to "are we secure?" that cites a standard instead of an opinion. Two maps, one per standard:
**OWASP ASVS 4.0.3 Level 2** grouped by chapter, and the **OWASP API Security Top 10 (2023)**, all ten
rows. This file is a map, not a manual: it names what exists, what proves it, and who closes what does
not exist.

A row is a *requirement group*, not a requirement. ASVS L2 has 286 items; one row per item is a
document nobody maintains, so each row is the smallest group that shares one control, one card or one
accepted risk. Requirements are paraphrased in one line, never copied: the standard is CC-BY-SA and a
copy of it here would age badly. Chapters with no non-obvious gap are absent, and two chapters do not
apply at all — V13.3 (SOAP) and V13.4 (GraphQL), because the product exposes neither.

The mapping is deliberately narrow and honest. **A row is `satisfied` only when a shipped control and
its proof exist today**: a `path:line`, a test that fails when the control goes away, or both. "It is a
standard-library feature" is not evidence. If a control is half there it is a card, not a satisfied row.
Read this with [`THREAT-MODEL.md`](THREAT-MODEL.md) (what can go wrong at each boundary) and
[`SECURITY-PLAN.md`](SECURITY-PLAN.md) (why the cards are ordered as they are).

## 1. How a row is counted

| State | Means | The last cell must carry |
| --- | --- | --- |
| satisfied | a shipped control, with a test or a `path:line` proving it | the cite, in backticks |
| card | the gap is planned and not built | exactly one card id whose file exists |
| accepted | the owner keeps this risk knowingly, for a stated reason | the reason, and the decision it waits on |

There is no "partial". A half-built control is a card id, and a risk nobody is planning to remove is
`accepted` with the reason and the decision it waits on.

## 2. ASVS 4.0.3 Level 2 — gaps by chapter

| Id | Requirement (one line) | Current state | State | Evidence or card |
| --- | --- | --- | --- | --- |
| V1.2 | The threat model is written, current, and reviewed when a boundary changes | Eleven STRIDE boundaries, a control and a disposition on every row, and a guard that fails when a boundary, a row or a cited card disappears | satisfied | `docs/ops/THREAT-MODEL.md`, `tools/tests/test_docs_ops.py` |
| V1.5 | Components are split into the fewest trust boundaries, each one written down | One API process with an embedded worker on one operator host; GPU workers, the MCP server and the future inference hub are separate processes | accepted | one operator-controlled host is the deployment, and a second process becomes a new boundary (THREAT-MODEL §4) |
| V1.10 | Secrets live in a managed store, with rotation and least access | `LD_SECRET` is env-only, must be 32+ characters, and rotates through `LD_SECRET_OLD`; there is no KMS or vault | accepted | self-hosted single host, env-only secret, rotation documented in `docs/DEPLOY.md:141` |
| V2.1 | Password policy: length over composition, and a breached-password check | Signup and reset require 8 characters and nothing else; no breach list, no length ladder | accepted | an 8-character floor is the shipped rule and raising it is an owner decision, Q1 |
| V2.2 | Credential anti-automation, and no account enumeration | Login capped per IP and per IP+email, signup capped, one generic 401 after a constant-time check | satisfied | `apps/backend/tests/test_security.py`, `apps/backend/app/routers/auth.py:258-259` |
| V2.4 | Passwords are stored with an approved, salted, slow KDF | PBKDF2-SHA256, 260 000 rounds, 16-byte random salt, constant-time compare | satisfied | `apps/backend/app/security.py:19-32` |
| V2.5 | Recovery links and one-time codes are single-use, expiring, and reveal nothing | Reset and verify links are hashed, single-use and expiring; TOTP codes cannot be replayed; recovery codes are HMAC-hashed; seeds are encrypted at rest | satisfied | `apps/backend/tests/test_account.py` |
| V3.2 | Session tokens are unguessable, integrity-protected, and stored hashed server-side | 256-bit refresh tokens stored as SHA-256, rotated on use; HS256 access tokens carry a scope claim | satisfied | `apps/backend/tests/test_security.py`, `apps/backend/app/security.py:66` |
| V3.3 | Logout and timeouts end a session, and a token can be revoked | Logout deletes the refresh token and refresh rotates, but an issued access token stays valid for its full 15-minute life and no deny list exists | accepted | the access TTL bounds the window, and a server-side deny list is an owner decision, Q2 |
| V4.1 | Access control is central, deny-by-default and least-privilege | One context object gates every route over the role matrix; custom grants add rights only at their own level; the known `need()`/`perm()` divergence can deny a grant, never grant | satisfied | `apps/backend/tests/test_rbac.py` |
| V4.2 | Object-level authorisation on every resource kind | A foreign id answers 404 for every resource kind, including API keys and signed file URLs | satisfied | `apps/backend/tests/test_sec_idor.py` |
| V5.1 | Every input is validated server-side and every output is encoded at its sink | Pydantic bodies; SQL payloads never 500 or leak; HTML payloads round-trip as text and no frontend sink renders an API field as HTML | satisfied | `apps/backend/tests/test_sec_injection.py` |
| V5.3 | Query construction is parameterised | The query compiler emits SQLAlchemy expressions, never string SQL, and no payload escapes the workspace | satisfied | `apps/backend/tests/test_dataset_query.py`, `apps/backend/tests/test_sec_injection.py` |
| V6.2 | Only approved algorithms, with keys derived and never in code | PBKDF2-SHA256, HMAC-SHA256, SHA-256, HS256 and Fernet for stored secrets; every key derives from `LD_SECRET` | satisfied | `apps/backend/app/security.py:19-32`, `apps/backend/app/services/secretbox.py:19-49` |
| V6.3 | Randomness comes from a CSPRNG | `secrets.token_urlsafe` and `token_hex` produce tokens, salts, TOTP seeds and the fallback secret | satisfied | `apps/backend/app/security.py:93`, `apps/backend/app/config.py:137` |
| V7.3 | Security events are logged with enough identity to investigate them | One JSON request line with a request id for every API call and worker step, and 99 `audit()` call sites — but login, failed login, logout, annotation save, image delete and job cancel write no audit row | card | T-1310 |
| V7.4 | Errors leak no internals and carry a traceable id | `safe_error`/`safe_text` strip paths and URLs, keep our own validation text, and never store a raw exception | satisfied | `apps/backend/tests/test_r1_error_hygiene.py`, `apps/backend/tests/test_logging_request_id.py` |
| V8.3 | Sensitive data is not kept in client storage an XSS could read | Access and refresh tokens sit in `localStorage`; the SPA ships a CSP with `script-src 'self'` | accepted | bearer tokens, no cookie, cleared on logout (`apps/frontend/src/lib/api/client.ts:16-21`); httpOnly cookies are an owner decision, Q3 |
| V9.1 | Every hop uses TLS, and a plain-HTTP deployment cannot happen silently | HSTS comes from Caddy and Vercel; a bare `nginx.conf` deployment sends none and has no redirect-to-HTTPS rule | card | T-1308 |
| V10.1 | Uploaded bytes are treated as untrusted data and never executed | Pillow decode only, display-name filenames, face blur fails closed, no malware scan | accepted | images are decoded and never executed, and archives are not accepted (SECURITY-PLAN §2) |
| V10.3 | Dependencies are pinned, scanned for known CVEs, and licence-checked | pip-audit with `--strict` blocks any advisory not waived in `security/audit-ignore.txt`, npm audit blocks a high CVE in a production dependency, and gitleaks, the licence allowlist and ruff `F`+`S` over app code all run in the gate | satisfied | `.github/workflows/ci.yml`, `tools/tests/test_gate_security.py` |
| V11.1 | Business flows have anti-automation and resource ceilings | Auth, keys, comments and one VLM route are limited; uploads, `/predict`, exports, version creation, search and MCP tool calls have no per-caller ceiling | card | T-1309 |
| V12.1 | Upload size and archive bombs are bounded before anything is stored | A per-request byte budget, a 2 000-file cap, and a refused zip bomb | satisfied | `apps/backend/tests/test_security.py`, `apps/backend/app/routers/images.py:169-177` |
| V12.2 | Uploaded and requested filenames cannot leave the data directory | `safe_name` strips separators, signed paths stay contained, and traversal, NUL bytes and Windows device names are refused | satisfied | `apps/backend/tests/test_sec_injection.py` |
| V13.1 | The API validates request shape and standardises its error body | Pydantic models on every route, annotation payload validation asserted, FastAPI's error envelope | satisfied | `apps/backend/tests/test_security.py` |
| V14.3 | The default configuration discloses nothing and is safe out of the box | `LD_CORS_ORIGINS` defaults to `*` with credentials off, and `/docs` plus `/openapi.json` are served in every environment | accepted | bearer auth means a wildcard origin reads nothing without the token (`apps/backend/app/main.py:63-64`); tightening is an owner decision, Q4 |
| V14.4 | Response headers deny the classic browser attacks | nosniff, `Referrer-Policy`, `X-Frame-Options`, `no-store` and a deny-all API CSP are set; `Permissions-Policy`, COOP/CORP and HSTS under nginx are missing | card | T-1308 |
| V14.5 | Server-side requests cannot be aimed at the internal network | `safefetch` allows http(s) only, requires every resolved address to be global, pins the vetted IP, re-checks each hop, and caps 20 MB under one deadline | satisfied | `apps/backend/tests/test_sec_injection.py`, `apps/backend/tests/test_r1_connector_ssrf.py` |

## 3. OWASP API Security Top 10 (2023)

| Id | Route family here | Guard today | State | Evidence or card |
| --- | --- | --- | --- | --- |
| API1 | Broken object level authorisation — `/api/ws/{ws}/…` for projects, images, annotations, versions, models, jobs, streams, connectors, webhooks and keys | A foreign id resolves inside the caller's workspace or answers 404, for every resource kind | satisfied | `apps/backend/tests/test_sec_idor.py` |
| API2 | Broken authentication — `/api/auth/*`, `/api/v1/*`, `/api/worker/*`, `/mcp` | Short-lived HS256 access, rotated hashed refresh, scoped keys, infer-only publishable keys, a constant-time worker token, and rejected expired, tampered and deleted-user tokens | satisfied | `apps/backend/tests/test_sec_idor.py`, `apps/backend/tests/test_api_keys_scopes.py` |
| API3 | Broken object property level authorisation — every JSON response model | Explicit `*_out` serialisers, a blanked honeypot count for labelers, and a key list that shows a prefix and never the secret | accepted | the serialisers are allowlists, but no per-role field matrix is planned; that is an owner decision, Q5 |
| API4 | Unrestricted resource consumption — upload, `/predict`, export, version create, search, `/mcp` | A per-request upload budget and a 2 000-file cap; no per-caller rate class on these routes | card | T-1309 |
| API5 | Broken function level authorisation — every mutating route | One `need()`/`perm()` gate per route over the role matrix; custom grants add rights only at their own level | satisfied | `apps/backend/tests/test_rbac.py` |
| API6 | Unrestricted access to sensitive business flows — login, signup, password reset, export, train, auto-label | Auth flows are capped; spend and export flows are not | card | T-1309 |
| API7 | Server-side request forgery — upload-by-URL, stream source, webhook, connector, MCP `upload_image_url` | `safefetch` only: public-address resolution, a pinned connection, per-hop re-checks, and no redirects on a webhook POST | satisfied | `apps/backend/tests/test_sec_injection.py` |
| API8 | Security misconfiguration — every `/api/*` response and `/api/metrics` | nosniff, `Referrer-Policy`, `X-Frame-Options`, an API CSP and a token-gated `/api/metrics`; `Permissions-Policy`, COOP and HSTS under nginx are missing | card | T-1308 |
| API9 | Improper inventory management — `/api/*`, `/api/v1/*`, `/api/dev/*`, `/mcp` | `openapi.json` is generated, a test asserts it matches the app and is host-free, and the developer API has its own prefix and scope | satisfied | `apps/backend/tests/test_openapi_contract.py` |
| API10 | Unsafe consumption of third-party APIs — connector downloads, webhook deliveries, stream sources | `safefetch` with a 20 MB cap and one deadline; a webhook POST never follows redirects; a bad signature is refused | satisfied | `apps/backend/tests/test_r1_connector_ssrf.py`, `apps/backend/tests/test_webhooks.py` |

## 4. Coverage summary

Counted by `test_summary_counts_match_the_tables`, from the state cell of every row above, so the
numbers cannot drift from the tables.

| Scope | satisfied | guarded by a test | card | accepted |
| --- | --- | --- | --- | --- |
| V1 | 1 | 1 | 0 | 2 |
| V2 | 3 | 2 | 0 | 1 |
| V3 | 1 | 1 | 0 | 1 |
| V4 | 2 | 2 | 0 | 0 |
| V5 | 2 | 2 | 0 | 0 |
| V6 | 2 | 0 | 0 | 0 |
| V7 | 1 | 1 | 1 | 0 |
| V8 | 0 | 0 | 0 | 1 |
| V9 | 0 | 0 | 1 | 0 |
| V10 | 1 | 1 | 0 | 1 |
| V11 | 0 | 0 | 1 | 0 |
| V12 | 2 | 2 | 0 | 0 |
| V13 | 1 | 1 | 0 | 0 |
| V14 | 1 | 1 | 1 | 1 |
| API | 6 | 6 | 3 | 1 |
| Total | 23 | 20 | 7 | 8 |

Three cards close the seven card rows: T-1308 (headers, HSTS, `/api/metrics`), T-1309 (rate classes)
and T-1310 (audit rows). The eight accepted rows name their reason and, for five of them, the owner
decision they wait on (§6). Every other row is proven above. "Guarded by a test" is the subset of
satisfied rows whose cite is a test, not a separate count.

## 5. How to re-check

Run from the repository root; the versions are the ones CI pins, because a newer scanner sees new rules.

| Check | Command |
| --- | --- |
| Static analysis (`S` rules, CI-pinned 0.17.3) | `ruff check apps/backend tools` |
| Python CVEs (CI-pinned 2.10.1; a waiver needs a reason and an expiry) | `pip-audit -r apps/backend/requirements.txt --strict` |
| This map's guards | `python -m pytest tools/tests/test_docs_ops.py -q` |
| Tenancy and the adversarial surface | `python -m pytest apps/backend/tests/test_sec_idor.py apps/backend/tests/test_sec_injection.py -q` |

Then read two documents: [`THREAT-MODEL.md`](THREAT-MODEL.md) for what can go wrong at each boundary,
and [`SECURITY-PLAN.md`](SECURITY-PLAN.md) for the gap list this map is counted from and the gate's
block/warn split. A reviewer who finds a row this map calls satisfied but no longer proves is holding a
finding against the card that removed the proof, not against this file.

## 6. Questions for the owner

Five of the eight `accepted` rows are accepted because the answer is a product decision, not a code
change. They belong in SECURITY-PLAN §7, which the T-1307 card does not own; move them there when that
file is next opened. The other three rest on deployment facts (one operator host, images never executed).

| # | Decision | Cost of each answer |
| --- | --- | --- |
| Q1 | Password policy: keep 8 characters as shipped, or raise the floor to 12 and add a k-anonymity breach check? | A floor change is one field plus one screen hint; a breach check is an outbound call on signup, so it needs a timeout and a fail-open rule |
| Q2 | Access-token revocation: accept the 15-minute window, or add a server-side deny list? | A deny list is one column, one middleware lookup per request, and one test; the window stays as the fallback |
| Q3 | Tokens in `localStorage`: keep bearer tokens, or move to httpOnly cookies? | Cookies change the refresh flow, need a CSRF token and credentialed CORS, and touch every client at once |
| Q4 | Default `*` CORS and public `/docs`: keep them as the developer contract, or require an explicit origin list and hide the docs in production? | One env default and one FastAPI flag; a self-hoster who forgets the variable loses the browser client |
| Q5 | Response properties: are the explicit serialisers the answer, or is a per-role field matrix wanted? | A matrix is one test per resource kind and a review rule for every new field |
