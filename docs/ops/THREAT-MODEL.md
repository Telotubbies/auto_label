# Application threat model — LabelDesk

One page per trust boundary, written for the person reviewing the next diff. Every control cites the
code that implements it; when a control does not exist, the residual column says so and the
disposition names the card that will build it. `accepted — reason` is a risk the owner keeps on
purpose, re-signed by R7 at each review of this file.

Scope: the API, the browser, the job worker, remote GPU workers, the MCP server, the future inference
hub, and the supply chain that reaches all of them. The inference hub's own table
([`PLAN.md`](../research/inference-hub/PLAN.md) §5) is referenced by number, never copied.

## 1. Assets and actors

| Asset or actor | What it is | Why it matters |
| --- | --- | --- |
| Tenant data | Images, labels, versions, trained weights, exports | Loss or cross-tenant read is the product's worst failure |
| Workspace credentials | Password hashes, sessions, MFA seeds, recovery codes | Taken over, they act as a member or an owner |
| API keys | `ld_` workspace keys and browser-public `ld_pub_` keys | A leaked workspace key is `/api/v1` access |
| Connector and PLC credentials | S3/Azure secrets, webhook signing secret, OT endpoints | They reach customer storage and factory hardware |
| GPU time | Training, auto-label, inference jobs | Spent by anyone who can enqueue |
| The operator's host | Data directory, `LD_SECRET`, `.secret`, model cache | Root on it is game over, and is out of scope below |
| Availability | API, queue, worker, outbound deliveries | A flood stops labelling and can stop a line |
| Anonymous internet | Anyone who can reach a public route | Sees login, signup, public project pages, signed URLs |
| Member of another workspace | Authenticated, guesses ids | The IDOR case every route must answer with 404 |
| Malicious member of the same workspace | Legitimate low-privilege account | Tries to read more, delete more, spend more |
| Compromised API key | Stolen `ld_` or `ld_pub_` key | Tries to widen its scope or drive an agent |
| Hostile image or URL | Uploaded bytes, a stream source, a webhook target | Tries to execute, traverse or reach the LAN |
| Supply-chain attacker | A dependency, wheel, container tag or installer | Runs with the API's or the worker's privileges |
| Operator error | A rotated secret, a dropped allowlist, a stale worker | The most likely cause of a real outage |

## 2. Data flow

1. Browser → API over HTTPS: session JWT or API key on every call; signed file URLs carry no session.
2. API → database and data directory: tenant rows filtered by `workspace_id`, files under `DATA_DIR`.
3. API → worker: a `Job` row, claimed compare-and-set by the local executor.
4. API → remote GPU worker: outbound-only HTTPS claim, progress and completion, `X-Worker-Token`.
5. API → outbound: `safefetch` downloads, SMTP mail, signed webhooks, connectors, PLC/OT writes.
6. MCP client → MCP server → API: a per-request bearer key, scope-filtered tools, `confirm` on writes.
7. API → future inference hub: install/download jobs on an operator-chosen worker host (PLAN §5).

## 3. STRIDE per boundary

Each table is one boundary. S/T/R/I/D/E are spoofing, tampering, repudiation, information disclosure,
denial of service and elevation. Every row cites a control, or says `none`, and ends with a
disposition: a card id, or `accepted — why`.

### 1. Auth/session

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: stolen access or refresh token replayed | Act as the user | Access TTL 15 min `app/security.py:15`; refresh stored hashed and rotated on use `app/routers/auth.py:278-286` | Theft is visible only when the rotated token fails; no device binding | accepted — short TTL and rotation bound the window; T-1310 adds the audit rows |
| T: password guessing or credential stuffing | Account takeover | PBKDF2-SHA256 260k rounds `app/security.py:19-32`; per-IP and per-IP+email limits `app/routers/auth.py:236-237` | Distributed attempts across many IPs have no global ceiling | T-1309 |
| R: sign-in or sign-out denied | No proof of who was in the account | `LoginEvent` per attempt `app/routers/auth.py:242,247` | No `auth.logout` audit row yet | T-1310 |
| I: email enumeration | Learn which addresses have accounts | Generic 401 and one PBKDF2 always run `app/routers/auth.py:239-243`; signup limited `app/routers/auth.py:199` | Signup still answers differently from login | accepted — the login timing and body are equalised and signup is capped |
| D: TOTP replay or MFA bypass | Session without the second factor | Spent-step guard `app/routers/auth.py:155-159`; MFA ticket scope `app/security.py:51-62`; workspace policy `app/deps.py:138-139` | Recovery codes and seeds depend on `LD_SECRET` hygiene | accepted — codes are hashed `app/security.py:76-89`, seeds encrypted `app/routers/auth.py:378-379` |
| E: forged session token | Full impersonation | HS256 with `LD_SECRET` and scope claim check `app/security.py:37-48` | A leaked `LD_SECRET` forges any session | accepted — the secret is host-only and gitleaks gates commits (T-1303) |

### 2. RBAC and workspace isolation

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: cross-tenant IDOR on a guessed id | Read or change another workspace's data | `project_ctx` resolves the project inside the workspace `app/deps.py:151-158`; routes filter too, e.g. `app/routers/images.py:197` | Coverage is per route file, not one matrix | T-1304 |
| T: role escalation through a stale or custom role | Elevated rights | Owners/admins stay project managers `app/deps.py:118-122`; custom grants filtered to their level `app/rbac.py:137-144` | `need()` vs `perm()` divergence denies a legitimate grant on three endpoints | accepted — it can deny, not grant (SECURITY-PLAN §7 Q3) |
| R: annotation save or deletion unattributed | Cannot answer who changed data | `audit()` is the single seam `app/deps.py:182` | Annotation save/delete and image delete write no row | T-1310 |
| I: labeler sees unassigned images or honeypots | Answer-key leak | Visible filter `app/routers/images.py:67-69`; honeypot counts blanked `app/routers/images.py:205-210` | Direct object routes rely on the same helper, tested per route | T-1304 |
| D: member deletes or exports without permission | Data loss | `Ctx.perm` and `need` raise 403 `app/deps.py:84-98`; destructive routes require `project.settings` `app/routers/ot.py:85-87` | Admins can still delete by design; the UI confirm is not a control | accepted — the role model intends it and T-1310 records it |
| E: last admin locked out by a stale project row | Workspace unmanageable | Owners/admins keep manager rights `app/deps.py:118-122`; last-admin guard T-007 | No test of a custom role that shadows admin; T-1304 extends the matrix | T-1304 |

### 3. API keys

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: key stolen from a log or a repository | Workspace takeover | Only the SHA-256 hash is stored `app/security.py:129-136`; the key is shown once `app/routers/workspaces.py:283-290` | Keys have no expiry (owner decision) | accepted — revocation exists, `apikey.use` is audited `app/apikeys.py:27-36`; expiry is SECURITY-PLAN §7 Q1 |
| T: a read-only key performs a write | Unintended mutation | Scope check `app/apikeys.py:53-56`; publishable keys forced to `infer` `app/routers/workspaces.py:269-276` | Every write route's scope is not asserted in one place | T-1304 |
| R: key use or refusal unattributed | Cannot trace abuse | Throttled `apikey.use` row `app/apikeys.py:27-36`; one `mcp.tool` row per call `app/apikeys.py:90-92` | Refusals such as a wrong scope write nothing | T-1310 |
| I: key leaks through a URL or referrer | Key in history and proxy logs | Query-string keys refused unless `ld_pub_` `app/apikeys.py:83-84`; publishable keys are infer-only | A publishable key is public in the browser by design | accepted — it can only infer, never read or write |
| D: key spraying exhausts the API | Service degradation | 600 lookups per minute per IP `app/apikeys.py:79-81` | No per-key ceiling for authenticated traffic | T-1309 |
| E: publishable key drives an agent or admin route | Privilege escalation | Infer-only scope `app/routers/workspaces.py:269-276`; MCP refuses publishable keys `apps/mcp/labeldesk_mcp/http.py:53-58` | Route-level enforcement is asserted per route | T-1304 |

### 4. Uploads

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: malicious or polyglot file executes | Host compromise | Pillow decode only `app/routers/images.py:124-128`; filenames reduced to display names `app/routers/images.py:39-43` | No antivirus scan; images are decoded, never executed | accepted — documented in SECURITY-PLAN §2 until archives are accepted |
| T: path traversal through a filename | Read or write outside the data directory | `safe_name` strips separators `app/routers/images.py:39-43`; files keyed by id; containment `app/main.py:102-104` | Export filenames are covered incidentally, not as a matrix | T-1305 |
| R: personal data uploaded with no trace | PDPA exposure | Audit row per batch `app/routers/images.py:159`; face blur before storage `app/routers/images.py:88-90,129-130` | Erasure and export live in the privacy workflow, not this path | accepted — T-751/T-752 own DSAR; plate redaction is T-728 |
| I: oversized or decompression-bomb image | Memory and disk exhaustion | Per-request budget `app/routers/images.py:169-177`; `MAX_UPLOAD_MB` `app/config.py:147`; storage quota `app/routers/images.py:100-101` | Pixel count is not capped before decode; the upload rate class is T-1309 | T-1305 |
| D: upload flood fills the disk | API and database outage | 2,000-file cap `app/routers/images.py:169-170`; storage quota `app/routers/images.py:100-101` | No upload-specific rate class yet | T-1309 |
| E: face blur silently skipped | Privacy promise broken | Fail closed when the detector is absent `app/routers/images.py:88-90`; blur runs before save `app/routers/images.py:129-130` | A detector failure mid-batch is not separately exercised | accepted — the request refuses at start, before any bytes are stored |

### 5. safefetch/SSRF

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: SSRF to loopback, RFC1918 or metadata | Internal service access | Every resolved address must be global unicast `app/services/safefetch.py:29-38`; NAT64 blocked `app/services/safefetch.py:26` | Each URL-accepting route must call the guard | T-1305 |
| T: DNS rebinding or a redirect to a private address | Bypass of the first check | Connection pinned to the vetted IP `app/services/safefetch.py:110-118`; every hop re-checked `app/services/safefetch.py:146-180` | DNS is not interruptible and spends the total budget `app/services/safefetch.py:130` | accepted — pinning and one deadline leave a narrow race |
| R: outbound request with no record | Cannot explain egress | Webhook deliveries keep a row `app/services/webhooks.py:69-77`; connector and stream writes are audited | Plain `safefetch.fetch` calls write no row | accepted — egress is operator-owned and the set is small (SECURITY-PLAN §4.2) |
| I: response body injected or echoed | Data injection | 20 MB cap `app/services/safefetch.py:14`; webhook bodies are never read `app/services/webhooks.py:64-66` | Image downloads are decoded, not trusted | accepted — decoded bytes are re-encoded by Pillow |
| D: a slow endpoint holds a worker | Queue starvation | One total deadline for connect, redirects and reads `app/services/safefetch.py:146-180` | No per-host concurrency cap | T-1309 |
| E: non-HTTP scheme or redirect smuggling | Protocol abuse | http(s) only `app/services/safefetch.py:41-47`; webhook POST never follows redirects `app/services/safefetch.py:121-140` | accepted — no other scheme reaches a socket | accepted — the scheme check precedes every connection |

### 6. Webhooks and connectors

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: a forged webhook reaches a customer | False event, wrong action | Timestamp-bound HMAC `app/services/webhooks.py:36-56`; signing secret encrypted `app/routers/webhooks.py:75-76` | Receivers must dedupe on the delivery id, stated in code `app/services/webhooks.py:44` | accepted — the contract is signed and documented |
| T: webhook or connector URL reaches the LAN | SSRF | URL validated on save `app/routers/webhooks.py:24-31`; every connector endpoint validated `app/services/connectors.py:37-41` | A hostname re-pointed after save is re-checked only on the download path | T-1305 |
| R: subscription change or failed delivery unrecorded | No incident trail | Audit on create, update, delete and test `app/routers/webhooks.py:79,101,112,135`; delivery rows keep attempts `app/services/webhooks.py:69-77` | Delivery rows are not exported | accepted — retries are capped at three `app/services/webhooks.py:26-27` |
| I: connector credential echoed in a response | Credential leak | Secrets encrypted `app/services/secretbox.py:65-70`; `public_config` masks every secret field `app/services/connectors.py:120-123`; webhooks show a prefix `app/routers/webhooks.py:36-41` | A new secret field must be added to the mask list | accepted — the list is one tuple `app/services/connectors.py:25`, reviewed with the connector |
| D: retry storm or duplicate deliveries | Customer endpoint flooded | Three attempts with backoff `app/services/webhooks.py:26-27`; 5 s timeout `app/services/webhooks.py:28` | Many subscriptions can multiply one event | accepted — bounded by the event volume the workspace creates |
| E: `LD_SECRET` rotation breaks deliveries | Silent delivery failure | MultiFernet decrypts old ciphertext `app/services/secretbox.py:26-29`; startup re-encrypts `app/services/secretbox.py:74-113` | Dropping the old key early makes rows unreadable | accepted — documented at the top of `app/services/secretbox.py:6-9` |

### 7. PLC/OT

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: an OT target used as a blind SSRF oracle | LAN scanning through status | Allowlist checked at save `app/services/ot.py:177-205`; empty by default `app/config.py:161-164` | The check is at save time; a re-pointed hostname is not re-checked | accepted — the target is admin-supplied on an operator-controlled host |
| T: a member actuates the line | Physical or safety impact | `project.settings` permission `app/routers/ot.py:85-87`; audit on create and update `app/routers/ot.py:92,117` | No second-person approval | accepted — T-688/T-689 own the fail-safe policy |
| R: an actuation with no record | Cannot investigate a missed part | `OtDelivery` rows `app/routers/ot.py:48-51`; config changes audited `app/routers/ot.py:92,117` | Delivery rows are not exportable | accepted — the station screen reads the same rows |
| I: GPIO path traversal writes outside the root | Host file write | Path confined to `LD_GPIO_ROOT`, never caller-supplied `app/ot/drivers.py:11-12`; line bounded `app/ot/drivers.py:26` | No caller-controlled path exists | accepted — `drivers.py:12` states the confinement |
| D: driver failure leaves the output asserted | Missed reject | One-bit signal, released on failure `app/ot/drivers.py:1-13`; 2 s timeout `app/ot/drivers.py:24` | A blackholed network can delay release up to the timeout | accepted — the fail-safe is de-energised by design |
| E: optional OPC-UA package absent | Silent no-op | The driver fails safe with a clear reason `app/ot/drivers.py:9-12` | Absence is the safe state | accepted — the output reports driver error |

### 8. MCP

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: the agent's key has more scope than the task | Unintended reads or writes | Tool list filtered by the key's scopes `apps/mcp/labeldesk_mcp/server.py:45-57`; publishable keys refused `apps/mcp/labeldesk_mcp/http.py:53-58` | No matrix over every tool's downstream route | T-1304 |
| T: spend or destructive write without consent | Credits lost, data replaced | `confirm: true` gate `apps/mcp/labeldesk_mcp/tools_write.py:30-32`; a string "true" is refused `apps/mcp/labeldesk_mcp/tools_write.py:23` | A host can still set `confirm` programmatically | accepted — the host runs the operator's agent |
| R: a tool call unattributed | Cannot trace an agent | One `mcp.tool` audit row per call `app/apikeys.py:90-92` | No per-tool duration or outcome | T-1300 |
| I: secret or storage path returned to the model | Leak into a transcript | Recursive scrubber `apps/mcp/labeldesk_mcp/api.py:19-24`; every value passes through it `apps/mcp/labeldesk_mcp/meta.py:4` | A new unwrapped field can pass the deny list | accepted — tool payloads reuse the routes' already-redacted output |
| D: hostile Origin or Host drives a local server | DNS rebinding | Allowlists or the SDK's localhost default `apps/mcp/labeldesk_mcp/http.py:88-96` | An empty allowlist trusts any localhost port | accepted — the default binds the operator's machine only |
| E: a publishable key drives an agent | Route escalation | 403 on publishable keys `apps/mcp/labeldesk_mcp/http.py:53-58`; scope filter `apps/mcp/labeldesk_mcp/server.py:53-57` | The API side is covered by T-1304 | accepted — two independent refusals |

### 9. Workers and installers

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: a forged worker claims a job and its dataset | Tenant data leak | Shared token compared in constant time `app/routers/remote.py:35-37`; min 24 chars `app/config.py:165-166`; compare-and-set claim `app/worker.py:132-145` | One shared token for every worker, no per-worker identity | accepted — one operator-controlled GPU host is the deployment |
| T: installer or weight substitution | Malicious code on the GPU host | Exact pins, digest-pinned containers, no user index, post-install freeze (`docs/research/inference-hub/PLAN.md` §5 #2) | The hash-locked wheelhouse is not built yet | T-1008 |
| R: job claim or outcome unlogged | Cannot attribute a run | Claim log line `app/worker.py:142-144`; job rows keep executor and times | No structured claim/complete audit row | T-1300 |
| I: dataset or weights leak through a signed URL | Model or data theft | HMAC-signed, TTL-bounded URLs `app/security.py:98-124`; 24 h remote dataset and weights `app/routers/remote.py:60,82-84` | A leaked URL works for up to 24 h | accepted — scoped to one job and short-lived by policy |
| D: a stale worker keeps a job forever | Queue wedge | Progress timeout `app/config.py:151-155`; reaper fails stale rows `app/services/remote_reaper.py:57-90` | A worker that reports progress forever still holds the job | accepted — the lease budget is enforced by the reaper |
| E: malicious weights exploit the runtime | Host compromise | No sandbox; `safetensors` preferred, `trust_remote_code=False` (`docs/research/inference-hub/PLAN.md` §5 #9) | Not made safe; the runtime is not hardened against hostile weights | accepted — out of scope §5, operator-run host |

### 10. Secrets

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: `LD_SECRET` committed or leaked | Forge sessions, decrypt stored secrets | Env-only, 32-char minimum `app/config.py:128-142`; gitleaks gate `.github/workflows/ci.yml:143-151` | A leaked secret must still be rotated | accepted — rotation is documented and tested `app/services/secretbox.py:6-9` |
| T: plaintext secret in the database | Credential theft from a dump | `enc:v1:` Fernet/MultiFernet `app/services/secretbox.py:19-49`; startup re-encrypts legacy rows `app/services/secretbox.py:74-113` | Rows written before the migration stay plaintext until it runs | accepted — the migration runs at every startup |
| R: secret use with no trace | Cannot explain a connector action | Connector and webhook writes are audited `app/routers/webhooks.py:79`; secret material never enters `meta` | Reading a secret is not audited | accepted — use is attributed by the action, not the key |
| I: secret in an error or a log line | Leak into logs | `safe_error`/`safe_text` collapse internals `app/errors.py:29-53`; MCP scrubber `apps/mcp/labeldesk_mcp/api.py:19-24` | An unhandled traceback can still carry locals | T-1300 |
| D: rotation makes stored rows unreadable | Connector and webhook outage | MultiFernet with `LD_SECRET_OLD` `app/services/secretbox.py:26-29`; named decryption error `app/services/secretbox.py:42-49` | Dropping the old key early is operator error | accepted — `app/services/secretbox.py:6-9` spells out the order |
| E: recovery codes or TOTP seeds stolen | Account takeover | Recovery codes hashed `app/security.py:76-89`; TOTP seed encrypted `app/routers/auth.py:378-379` | A database dump alone cannot sign in | accepted — both factors need the secret |

### 11. Dependency supply chain

| Threat | Impact | Existing control | Residual risk | Disposition |
| --- | --- | --- | --- | --- |
| S: typosquatted or malicious package | Code execution in API or worker | Pinned scanners and no user index `.github/workflows/ci.yml:112-151` | `requirements.txt` uses `>=` ranges with no lock or hashes; the lock/hash follow-up is SECURITY-PLAN §2 S2 | T-1303 |
| T: known CVE in a dependency | Remote compromise | pip-audit blocks high/critical `.github/workflows/ci.yml:125-136`; npm audit `.github/workflows/ci.yml:101-102` | Dev-only npm advisories warn; a waiver needs an expiry `security/audit-ignore.txt:1-3` | accepted — the block/warn split is the owner's choice (SECURITY-PLAN §4.1) |
| R: licence violation in a dependency | Legal exposure | Licence gate and allowlist `.github/workflows/ci.yml:139-142`; AGPL annotated deliberate `security/licences-allow.txt` | Warn vs block on AGPL is an owner decision | accepted — owner decides at public launch (SECURITY-PLAN §7 Q2) |
| I: secret committed with code | Workspace takeover | gitleaks `.github/workflows/ci.yml:143-151` | A secret already pushed must still be rotated | accepted — the gate stops the next one, rotation is the remedy |
| D: a compromised npm package breaks the build | Release blocked | Lockfile plus `npm ci` in CI `.github/workflows/ci.yml:93-96` | Dev-dependency advisories do not block | accepted — a build compromise is not a production compromise |
| E: a postinstall script runs on the developer host | Developer-machine compromise | CI installs from the lockfile with `npm ci` | Install scripts are not disabled (`--ignore-scripts`) | accepted — the developer host is outside the deployment boundary (§5) |

## 4. Trust assumptions

If one of these is false, the risk belongs to whoever changed the deployment, not to this table.

| Assumption | Consequence if false |
| --- | --- |
| This deployment is one API process with one embedded worker; scaling out adds no new trust boundary | A second process or a shared queue changes the audit and rate-limit assumptions |
| The GPU worker host is operator-controlled, on a network the operator names | A tenant-controlled host turns the worker token into tenant access |
| `LD_SECRET` is not in the repository and is rotated through `LD_SECRET_OLD` | Every session and every stored secret is forgeable or unreadable |
| The browser is not trusted: it holds a publishable key at most | A session token in browser storage becomes a cross-site-scripting prize |
| A tenant may be hostile to another tenant, but not to the operator | A tenant with host access is out of scope, not a missing control |
| Public routes are reachable from the internet; everything else is not | A route accidentally public inherits the anonymous actor |

## 5. Out of scope

| Out of scope | Why |
| --- | --- |
| Root compromise of the operator's host | Whoever has root reads `LD_SECRET`, the database and the data directory; no in-app control survives |
| Malicious weights exploiting the inference runtime | The runtime is not sandboxed; the hub prefers `safetensors` and refuses remote code, which reduces but does not remove the risk |
| Side-channel attacks on a shared CPU | The deployment is one operator host, not a co-tenanted cloud VM; cache timing is outside the product's control |
| Physical access to the host or the PLC cabinet | An attacker at the cabinet can wire around any software control; the OT allowlist is not a physical lock |
| A compromised PyPI or npm mirror | The gate checks resolved packages, not the mirror; a mirror that serves matching hashes is indistinguishable |

## 6. Review triggers

Update this file in the same branch when any of these four events happens:

1. **A new route family** or a new public route: add it to the boundary it belongs to and check T-1304.
2. **A new outbound client** (another fetch, mailer, webhook or connector): check safefetch and audit.
3. **A new credential store** or secret field: add it to `secretbox` and to the connector mask list.
4. **A new process or third-party binary** (worker, installer, MCP server, scanner): add its boundary
   or extend the workers/installers table.

R7 also re-reads this file whenever a diff touches auth, RBAC, secrets, uploads, outbound URLs,
webhooks, connectors, PLC/OT, MCP, workers, installers or monitoring
([`OPENCODE_TEAM_FLOW.md`](../OPENCODE_TEAM_FLOW.md) §1).

## 7. R7 sign-off

Every `accepted — reason` row above was signed by the T-1306 R7 lane on 2026-11-18. A later R7 review
may revoke any of them; a revoked row becomes a card id in the same edit, never a silent deletion.
