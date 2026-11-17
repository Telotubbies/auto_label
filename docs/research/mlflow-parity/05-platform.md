# MLflow parity — Area 5: Platform

Baseline `feat/labeldesk-v2` @ `f6feb09`. MLflow docs read 2026-11-17 (site version 3.18.0,
released 2026-11-04). Release notes window 2025-11-17 → 2026-11-17 checked at
<https://github.com/mlflow/mlflow/releases> (v3.7.0 … v3.18.0, plus `ts/v0.2.0`).

**Doc pages covered (full navigation walk).** The sidebar was re-cut since the brief was
written: the docs now split into `ml/` (product) and `self-hosting/` (server, security,
workspaces). `/docs/latest/auth/` and `/docs/latest/projects.html` are redirects;
`/docs/latest/recipes.html` no longer exists (see Judgment call 1). Walked via
<https://mlflow.org/docs/latest/sitemap.xml> plus the live sidebar on each page below.

ml/ (product)
- <https://mlflow.org/docs/latest/ml/projects/> — project format, entry points, params, environments, local/remote run
- <https://mlflow.org/docs/latest/ml/tracking/> — runs/models/experiments concepts, Tracking UI, store components, model URIs
- <https://mlflow.org/docs/latest/ml/tracking/quickstart/> — UI walk (home → experiment → run list → run detail → model → artifacts)

self-hosting/ (server)
- <https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/> — `mlflow server` flags, proxies, artifacts-only, `/version`, server jobs
- <https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/> — SQLite default, Postgres/MySQL, file store legacy, `mlflow gc`, `mlflow db upgrade`
- <https://mlflow.org/docs/latest/self-hosting/workspaces/> — workspace scoping, artifact isolation, resolution order, "not a hard isolation boundary"
- <https://mlflow.org/docs/latest/self-hosting/workspaces/permissions/> — `(workspace, *, USE|MANAGE)` floor, seeded roles, `list_workspaces()` visibility
- <https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/> — `--app-name basic-auth`, permission levels, `/signup`, credentials file, admin user
- <https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/> — roles, sub-resource tiers, resolution order, admin UI
- <https://mlflow.org/docs/latest/self-hosting/security/network/> — allowed hosts, CORS, X-Frame-Options, middleware off-switch
- <https://mlflow.org/docs/latest/self-hosting/security/sso/> — community OIDC plugin, group → admin/plain, reverse-proxy identity headers

API reference
- <https://mlflow.org/docs/latest/rest-api.html> — every endpoint family, request/response structure (3.18.0 build)
- <https://mlflow.org/docs/latest/api_reference/cli.html> — linked from every page's API-reference sidebar (not fetched; the CLI commands cited below come from the pages that document them)
- <https://mlflow.org/docs/latest/api_reference/python_api/index.html>, `R-api.html`, `java_api/index.html`, `typescript_api/index.html` — linked from the API-reference sidebar
- <https://pypi.org/project/mlflow-skinny/> — what the skinny distribution is and does not contain

Pages that produced no row
- `/docs/latest/self-hosting/kubernetes-helm/`, `/deploy-to-cloud/*`, `/job-containers/`, `/webhooks/`,
  `/migration/`, `/migrate-from-file-store/` — deployment recipes for their own server; we do not
  ship a second server, so nothing to copy (Helm/cloud = our own deploy lane, area 6).
- `/docs/latest/self-hosting/security/custom/`, `/security/kubernetes/`, `/security/secure-installs/`
  — plugin surfaces that only exist because their server is embeddable. Ours is not.

## Area count

24 rows: 2 HAVE · 13 PARTIAL · 9 MISSING.

## 5.1 A runnable spec committed next to the code
**What it does.** A directory becomes runnable when it carries an `MLproject` file (or just
`.py`/`.sh` files). The file names the project, lists entry points with typed parameters and
names one environment; `mlflow run <dir>` then resolves that file and executes an entry point.
Without the file, every `.py`/`.sh` is an entry point and parameters arrive as `--key value`.
`(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Project → Train** — the trainer screen offers "Use a spec from my repo" next to the form. [empty: no spec found in the connected repo — "we'll copy this form into `labeldesk.yaml`" with a download button] [loading: reading the repo tree, one skeleton row per candidate file] [error: repo unreachable — "can't read your repo; the form still works"].
2. **Spec preview** — the parsed spec renders as the same fields the form uses: entry points as rows, parameters with type and default, dataset and model as references. [empty: spec has no entry points — "add one"] [loading: parsing] [error: line/column with the reason, never a stack trace].
3. **Run** — "Run this entry point" starts a job; the resolved values are frozen onto the run so editing the file later cannot rewrite history.
**LabelDesk:** MISSING — `apps/backend/app/routers/training.py` (training is a form POST, `TrainIn` fields only), `apps/frontend/src/features/project/Train.tsx`, no `MLproject`/`labeldesk.yaml` anywhere (`grep MLproject` → docs-only hits). The nearest artefact is the workflow definition in `apps/backend/app/services/workflows.py:1-22` (ordered blocks, versioned), which describes an inference chain, not a training run.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — the file is a spec for *our* trainer, parsed into our schema; nothing to integrate.
**Roboflow overlap:** `5-F5.7`/`5-F5.9` (recipe editor, speed preset, T-2xx) cover a GUI recipe; a committed file is the CI/agent half they do not deliver → **T-968**.
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.2 Entry points and typed parameters
**What it does.** Each entry point declares parameters typed `string | float | int | path | uri`,
validated on the way in; `path` downloads a remote URI to a local file first while `uri` is passed
through. Defaults are declared inline (`{type: float, default: 0.1}`), so an unset parameter is
never a silent null. `(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Project → Train → Advanced** — parameters appear as typed inputs (number stepper, path picker, text) already carrying the spec default. [empty: spec declares none — the form shows only our own fields] [loading: values from the last run are fetched to prefill] [error: a value fails its type — the field is red with "must be a whole number", the Run button disabled].
2. **CLI parity** — `labeldesk train --spec labeldesk.yaml --set epochs=60 --set lr=0.01` rejects `--set epochs=sixty` with the same sentence, not a 422 dump.
3. **Resolved plan** — before spending, the screen/CLI prints what will run: entry point, every parameter with its resolved value and where it came from (default, flag, run), dataset version, model family.
**LabelDesk:** MISSING — `packages/sdk/labeldesk/cli.py:95-103` has fixed argparse flags (`--epochs`, `--imgsz`, `--batch`) and no types beyond `int`; `apps/backend/app/routers/training.py` `TrainIn` (`devapi.py:95-101`) validates with pydantic but exposes no typed-parameter contract to a user.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a thin schema over fields we already have; the CLI is the same object.
**Roboflow overlap:** none (their recipe editor has no typed parameter contract) → **T-969**.
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.3 The environment a run happened in
**What it does.** Three environment kinds, declared by the project: `python_env.yaml` (pip only,
recommended), `conda.yaml` (native libraries, CUDA), `docker_env` (image, volumes, environment
vars). `--env-manager virtualenv|conda|local` chooses which one is honoured, so the same entry
point can run isolated or in the current shell. `(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Model detail → Environment** — a run shows python version, key package versions, CUDA/driver, GPU model, container image digest, and the worker that executed it. [empty: legacy run recorded before this shipped — "environment not recorded"] [loading: skeleton lines] [error: worker never reported — "the worker did not report its environment", with no fabricated versions].
2. **Compare** — two runs of the same project show a one-line diff ("torch 2.6.0 → 2.7.0, CUDA 12.4 → 12.8") so a metric jump has a suspect.
3. **Copy** — "copy as requirements" yields a pinned file for the next run.
**LabelDesk:** MISSING — `apps/backend/app/models/training.py:34-54` (`TrainedModel`) carries metrics/history/weights/family/variant/license/runtime_refs and no environment blob; `Job.params` (`models/training.py:24-25`) holds the request only. Workers exist (`apps/backend/app/routers/remote.py:85-112`) and could report it.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — replaying a conda/docker resolve is not the value; *recording* what ran is, and it is one JSON column from data the worker already has.
**Roboflow overlap:** none — `5-F5.9` records hyper-parameters, not the interpreter → **T-971**.
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.4 Running locally, and a dry run that costs nothing
**What it does.** `mlflow run .` executes in the current checkout with the chosen env manager;
`--env-manager local` skips isolation. The point is that the same declaration can be tried
before anything is submitted to a cluster. `(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Project → Train → "Check before you spend"** — validates the spec, the dataset version, the class list and the parameter types, and prints the plan; no job row is created and no credits are charged. [empty: nothing to check — the button is disabled with the reason next to it] [loading: a 2-second spinner with "checking dataset …"] [error: a list of blocking problems, each linking to the screen that fixes it].
2. **CLI** — `labeldesk train --dry-run` prints the same plan and exits 0/1, so CI can gate a recipe.
**LabelDesk:** PARTIAL — `apps/backend/app/routers/training.py` train endpoint writes a `Job` and `apps/backend/app/deps.py:195-200` (`charge`) meters credits at submit; there is no validate-only path. Job creation is visible in `apps/frontend/src/components/shell/JobTray.tsx:19`.
**Priority:** Must · **Size:** S
**Decision:** Build (our store/UI) — a validate-only branch in the existing train handler; the checks already exist inside it.
**Roboflow overlap:** `5-F5.11`/`7-F7.18` (training quote, T-252/T-254) estimate cost; they do not validate a spec without submitting → **T-970** (depends on T-252 for the quote text).
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.5 Choosing where a run executes
**What it does.** `--backend local|databricks|kubernetes` with a `--backend-config` file decides the
executor, and a custom backend is a plugin (`mlflow.project_backend`). A Kubernetes run is a job
template with image, resources and the tracking URI injected; `--build-image` builds the project
image first. `(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Project → Train → Where** — a select: "this server", or a named worker from the worker list, showing each worker's GPU, last heartbeat and current job. [empty: no workers registered — "train on this server" preselected, with a link to the worker setup] [loading: worker list skeleton] [error: chosen worker went offline between selection and submit — the run is refused with "worker `x` is offline" and nothing is charged].
2. **Job tray → run row** — shows which executor claimed the job and when, and whether the reaper has flagged it.
**LabelDesk:** PARTIAL — remote workers are real: `apps/backend/app/routers/remote.py:1` ("HTTP protocol for remote GPU workers"), claim sets `executor="remote"` (`remote.py:90`), progress/complete/fail endpoints, and `apps/backend/app/services/remote_reaper.py` reaps stale claims; `apps/backend/app/models/training.py:23` stores `executor`. There is no UI to choose an executor and no worker registry with heartbeat visible to a user.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — the queue and the lease already exist; this is visibility plus a pin, not a scheduler.
**Roboflow overlap:** none (they have no user-facing executor choice) → **T-972**.
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.6 Pointing a client at a server, once
**What it does.** A client learns its server from `MLFLOW_TRACKING_URI` or `set_tracking_uri()`,
credentials from `MLFLOW_TRACKING_USERNAME`/`PASSWORD`, `MLFLOW_TRACKING_TOKEN`, or an INI file
`~/.mlflow/credentials` (plaintext on disk, "protected only by filesystem permissions"); env vars
win over the file. `(MLF: https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/)`
**UX flow, click by click.**
1. **Settings → Integrations → Command line** — a copy-paste block prefilled with this workspace's URL and a key *prefix*, never the key itself. [empty: no key yet — the block says "create a key first" and links to the keys tab] [loading: none, it is static text] [error: key was revoked — the copy block swaps to "this key no longer works" on the next `whoami`].
2. **`labeldesk login`** — writes `~/.config/labeldesk/config.toml` (0600) and verifies with `whoami`; `labeldesk config` prints the effective base URL and key source (env, file, flag) with the key masked.
**LabelDesk:** PARTIAL — `packages/sdk/labeldesk/client.py:51-56` reads `LABELDESK_API_KEY`/`LABELDESK_URL` only; `packages/sdk/labeldesk/cli.py:68-70` adds `--base-url`/`--api-key`. No config file and no key-source reporting.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a config file is ten lines and the existing `whoami` operation (`routers/devapi.py:31-35`) already proves the credential.
**Roboflow overlap:** `7-F7.37` → **T-441** (area 7) owns the CLI/SDK auth handshake and the default workspace; this row adds nothing it does not already plan. **No new card.**
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/>

## 5.7 Pipelines as a file: steps, graph, caching, profiles
**What it does.** A multi-step pipeline is composed by calling one project from another and passing
the previous run's params as the next one's inputs — the docs show it as a Python function that
waits on `SubmittedRun` objects, fans out with a thread pool and picks the best run by metric.
There is no declarative pipeline file in 3.18; `mlflow run` is the unit of composition.
`(MLF: https://mlflow.org/docs/latest/ml/projects/)`
**UX flow, click by click.**
1. **Project → Studio → Pipelines → "Import from repo"** — a `pipelines/*.yaml` is parsed into the existing block graph (model → filter → crop → ocr → rule → sink) and shown on the canvas; an unknown block or a port mismatch is a line-numbered error, not a stack trace. [empty: no pipeline file found — offer the canvas] [loading: "reading the repo"] [error: two blocks claim the same output — "step 3 writes `detections` which step 2 also writes"].
2. **Profiles** — the file may declare named profiles (`dev`, `ci`, `full`); the run panel shows a profile picker with the diff each profile applies ("ci: 20 images, model yolo26n") and refuses a profile that changes the graph shape.
3. **Cache** — a step whose inputs hash matches the last run is reused and badged "cached"; an explicit "recompute" clears it for that step only.
4. **CLI** — `labeldesk pipeline run <file> --profile ci` and `labeldesk pipeline status <run>`.
**LabelDesk:** PARTIAL — a graph and a runner exist for inference: `apps/backend/app/services/workflows.py:17-22` (≤12 blocks, six block types, canonical configs, versioned saves), `apps/backend/app/services/workflow_runner.py`, UI at `apps/frontend/src/features/project/Workflows.tsx`, flag `task_31` in `apps/backend/app/services/flags.py:30`. There is no YAML import, no profile, no per-step cache and no pipeline CLI.
**Priority:** Should · **Size:** M
**Decision:** Build (our store/UI) — one parser in front of a graph and runner we already own; importing a file is cheaper than asking a user to draw one.
**Roboflow overlap:** `6-F6.21`–`6-F6.30` are the canvas, run panel, cache (T-325) and version history (T-330) — **cite T-320, T-324, T-325, T-330; do not duplicate**. The file/profile/CLI half is not theirs → **T-973, T-974, T-975**.
**Sources:** <https://mlflow.org/docs/latest/ml/projects/>

## 5.8 Recipe CLI
**What it does.** With no declarative pipeline, the documented CLI surface for a multi-step run is
`mlflow run` per project plus `mlflow gc`, `mlflow db upgrade`, `mlflow server`. There is no
`mlflow recipe` command in 3.18. `(MLF: https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/)`
**UX flow, click by click.**
1. **Terminal** — `labeldesk pipeline run pipelines/qa.yaml --profile ci --wait` prints a step table that updates in place, exits non-zero on the first failed step, and prints the run URL. [empty: the file has no steps — "nothing to run", exit 2] [loading: a step line per step, `queued/running/done`] [error: the failing step, its sanitised message, and the local log path].
2. **`labeldesk pipeline status <run>`** — same table for a run started elsewhere.
**LabelDesk:** MISSING — `packages/sdk/labeldesk/cli.py:71-110` has six commands (`whoami`, `models`, `upload`, `export`, `train`, `predict`); nothing pipeline-shaped.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — a formatter over the run/job API the runner already exposes.
**Roboflow overlap:** none of `6-F6.2x` is CLI → **T-975** (same card as 5.7's CLI bullet; one card, two rows).
**Sources:** <https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/>

## 5.9 Accounts, default access and the role model
**What it does.** `mlflow server --app-name basic-auth` turns on a login wall in front of every
resource; users are created by an admin or at `/signup`; `READ` is the default permission and is
configurable; the first start creates an admin from `MLFLOW_AUTH_ADMIN_PASSWORD` (no shipped
default since 3.16.1). From 3.13 every grant goes through a **role** — `(resource_type,
resource_pattern, permission)` — assigned to users; permissions ladder `READ < USE < EDIT <
MANAGE` with `DENY` from 3.17, and a `(workspace, *, USE|MANAGE)` grant acts as a floor.
`(MLF: https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/)`
**UX flow, click by click.**
1. **Sign in** — email + password, TOTP when the account has it, or the workspace SSO button. [empty: n/a, a login form is never empty] [loading: button spinner, form disabled] [error: "email or password is wrong" — identical text for unknown email and wrong password].
2. **Settings → Members** — the roster shows each member's workspace role and effective project role; **Settings → Roles** builds a bundle from grouped permission checkboxes. [empty: "only you so far" with an invite button] [loading: roster skeleton] [error: role name taken — 409 surfaced as "a role with this name already exists"].
3. **Assign** — a role is attached at workspace or project level and the roster shows the union.
**LabelDesk:** HAVE — login/refresh/MFA/OIDC/invites: `apps/backend/app/routers/auth.py:144-482`; sessions and history `auth.py:420-448`; two-level roles and custom bundles `apps/backend/app/rbac.py:14-42`, `rbac.py:132-165`; resolver `apps/backend/app/deps.py:88-102`; role CRUD API `apps/backend/app/routers/rbac.py:96-141`; roster UI `apps/frontend/src/features/settings/Settings.tsx:738-807`; role editor `apps/frontend/src/features/governance/Roles.tsx:9-70`. Absent vs their model: a grant cannot name one object; there is no `DENY`; a bundle is grant-only (`rbac.py:45-46`, `CUSTOM_DENIED`).
**Priority:** Must · **Size:** — (shipped)
**Decision:** Build (our store/UI) and keep it — mapping to `rbac.py` is the whole point; importing a second auth store in front of customer data is the thing we are avoiding.
**Roboflow overlap:** `7-F7.6`, `7-F7.9`, `7-F7.10` → T-381, T-382, T-383 (area 7) refine this screen. **No new card.** No guard exists yet for this row (area-5 guard `T-005` pins model/train/eval rows only).
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/>, <https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/>

## 5.10 A permission on one object
**What it does.** Beyond the workspace floor, a grant can name a single experiment
(`experiment:42`), every experiment (`experiment:*`), or a sub-resource tier (`run`, `trace`,
`registered_model_version` — wildcard-grain only from 3.17). Resolution: platform admin → workspace
MANAGE → container READ → max over same-tier grants with `DENY` winning → server default.
`(MLF: https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/)`
**UX flow, click by click.**
1. **Project → Settings → Access** — the permission matrix for this project, with an "inherited from workspace" badge on every row that is not set here. [empty: no explicit rows — "everyone inherits their workspace role"] [loading: skeleton] [error: 403 with "requires project.roles" rendered as a banner, not a dead page].
2. **Grant** — pick a member, pick a project role, save; the response shows the effective permission set immediately.
**LabelDesk:** MISSING (per-object) / HAVE (per-project) — our unit is the project: `rbac.py:28-42` project permissions, `rbac.py:91-98` effective role, `apps/backend/app/routers/rbac.py:163-175` returns each member's effective set and `inherited`. There is no per-image, per-version or per-run grant.
**Priority:** Could · **Size:** L
**Decision:** Build (our store/UI), and **decline the per-object part** — a labeler working set is already per-project plus folder scope; per-run ACLs would add a resolver branch to every query for a need no buyer has stated. The analogue that matters is folder-scoped access.
**Roboflow overlap:** `7-F7.11` → **T-384, T-385, T-386, T-387** (area 7) deliver folder-scoped access; that *is* our per-object tier. **No new card.**
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/>, <https://mlflow.org/docs/latest/self-hosting/workspaces/permissions/>

## 5.11 An admin screen that explains access
**What it does.** `/admin` (platform admins) and `/admin/ws?workspace=…` (workspace managers) share
a Users tab and a Roles tab: click a user → **Edit access** → role assignments and *direct
permissions*, previewed in a **Review** step before applying. Role create/edit is one page with
three sections (details, permissions, assigned users). `(MLF: https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/)`
**UX flow, click by click.**
1. **Settings → Members → row → "Why can they do this?"** — a drawer lists every effective permission with the source: workspace role, project role, custom bundle, or "not granted". [empty: a member with no project row — "inherits workspace role `member` → labeler"] [loading: one fetch, skeleton rows] [error: the resolver disagrees with the roster — "reload; the values changed while you were looking" instead of a stale answer].
2. **Change with a preview** — a role change shows the before/after permission set and needs an explicit Apply.
**LabelDesk:** PARTIAL — the roster with effective permissions exists (`apps/backend/app/routers/rbac.py:163-175`, `apps/frontend/src/features/settings/Settings.tsx:738-807`), custom bundles and their grants exist (`governance/Roles.tsx`), but there is no per-member explanation, no before/after preview, and no direct grant that bypasses a role.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — the resolver already returns the answer; the gap is a screen.
**Roboflow overlap:** `7-F7.9`, `7-F7.10` → T-382, T-383 (area 7) rebuild the matrix and bundle editor. This row adds the *explanation for one person* they do not plan → **T-976**.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/>

## 5.12 What sits in front of the server
**What it does.** From 3.5 the server ships middleware: `--allowed-hosts` (DNS-rebinding defence,
default localhost + private IPs), `--cors-allowed-origins`, `--x-frame-options`
(`SAMEORIGIN` default), and `--disable-security-middleware` for operators who terminate at a proxy.
`(MLF: https://mlflow.org/docs/latest/self-hosting/security/network/)`
**UX flow, click by click.**
1. **Deploy** — an operator sets the public host and the proxy's forwarded headers; a request whose Host header is not on the list is refused with a plain 400. [empty: no allowed hosts configured — start in localhost-only mode, not open] [loading: n/a] [error: "this host is not allowed to talk to this server" in the response body and the server log].
2. **Settings → Workspace → Security** — the admin sees the effective host list and whether TLS is terminated in front ("behind a proxy at `x`"), read-only.
**LabelDesk:** PARTIAL — `apps/backend/app/main.py:66-77` already sets nosniff, referrer policy, `X-Frame-Options: DENY`, `no-store` and a strict CSP for `/api/*`; CORS from `LD_CORS_ORIGINS` (`config.py:39`, default `*`). No Host-header validation, no forwarded-proto handling, no way to see the effective settings.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — `TrustedHostMiddleware` is one line of Starlette once the list comes from config; the rest exists.
**Roboflow overlap:** none → **T-977**.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/network/>

## 5.13 Single sign-on
**What it does.** SSO is a community plugin (`mlflow-oidc-auth`, `--app-name oidc-auth`): the IdP
authenticates the browser, groups map to an admin group and a plain group, and the client still
authenticates with the basic-auth protocol using a generated access token (only the newest token is
valid). The alternative is a reverse proxy (oauth2-proxy) that injects `X-Forwarded-User` and does
the enforcement itself. `(MLF: https://mlflow.org/docs/latest/self-hosting/security/sso/)`
**UX flow, click by click.**
1. **Sign in → "Continue with <provider>"** — browser leaves for the IdP and returns to the workspace. [empty: no IdP configured — the button is absent, not dead] [loading: "checking with your identity provider"] [error: token rejected — "your organisation's sign-in did not confirm this account", plus a support code in the log only].
2. **First sign-in** — the account is created with the workspace's default role, and an admin sees it in the roster flagged "joined via SSO".
**LabelDesk:** PARTIAL — bearer-token OIDC exists: `apps/backend/app/oidc.py:1-91` (RS256 only, issuer/audience checks, JWKS cached 10 min, auto-provision `oidc:<sub>`), surfaced in `apps/backend/app/deps.py:50-60`; config exposed at `routers/auth.py:146`. Absent: a browser redirect flow, group → role mapping, SAML, and a deprovisioning path.
**Priority:** Should · **Size:** L
**Decision:** Build (our store/UI) — identity stays ours; the token can be verified, but *sessions and roles* must be minted by us.
**Roboflow overlap:** `7-F7.35` → T-423–T-426 and `7-F7.41` → T-430–T-432 (area 7) own SSO and directory sync. **No new card.**
**Sources:** <https://mlflow.org/docs/latest/self-hosting/security/sso/>, <https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/>

## 5.14 API families and version negotiation
**What it does.** The wire surface is versioned by path family: `/api/2.0/mlflow/*` (tracking,
registry, webhooks), `/api/3.0/mlflow/*` (traces, scorers, gateway, MCP, jobs), `/api/2.1` and
`/ajax-api/…` variants used by the UI. `GET /version` returns the server version so a client can
refuse to talk to a mismatched server. `(MLF: https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)`
**UX flow, click by click.**
1. **`labeldesk doctor`** — prints the API version this SDK speaks and the one the server announces, and warns when they differ. [empty: unreachable server — "cannot reach <url>" with the DNS/TLS reason] [loading: one request, fast] [error: version mismatch — a warning line, not a hard stop, unless the major differs].
2. **Docs / Settings → Integrations** — the supported API versions are listed with the deprecation policy sentence.
**LabelDesk:** PARTIAL — one public family, `/api/v1` (`apps/backend/app/routers/devapi.py:19`), plus the internal `/api` tree; no version endpoint (only `/api/health`, `apps/backend/app/main.py:84-86`) and no written compatibility rule.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — our families are ours to name; the cheap part is announcing one and promising it.
**Roboflow overlap:** `7-F7.37` → T-441 covers the handshake; the version endpoint is not theirs → **T-981**.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/>, <https://mlflow.org/docs/latest/rest-api.html>

## 5.15 Paging and the error contract
**What it does.** Every list endpoint takes `max_results` plus an opaque `page_token` and returns
`next_page_token`; a missing token means no more pages. Errors carry a machine code
(`RESOURCE_DOES_NOT_EXIST`, `INVALID_PARAMETER_VALUE`) alongside the message, so a client can branch
without parsing prose. `(MLF: https://mlflow.org/docs/latest/rest-api.html)`
**UX flow, click by click.**
1. **Any list screen** — "load more" appends a page; the URL carries the cursor so a refresh returns to the same page, and a stale cursor says "this list changed; showing the first page" instead of silently repeating. [empty: `{items: [], next: null}` → the screen's empty state] [loading: footer skeleton while the next page arrives] [error: a malformed cursor is a 400 with "bad cursor", never a silent first page].
2. **SDK** — `LabelDeskError.status`/`detail` stay, and a `code` field is added so a caller can check `code == "not_found"`.
**LabelDesk:** PARTIAL — offset/limit everywhere with a total: `routers/devapi.py:56-62` (`{total, items}`), `routers/workspaces.py:286-311` (clamped `limit`, `offset`). Error bodies are FastAPI `{"detail": …}` — no code (`apps/backend/app/errors.py:29-43` sanitises *text*, not shape), and `packages/sdk/labeldesk/client.py:28-39` already has to flatten both shapes.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — one helper plus one envelope on `/api/v1`; the internal API keeps offset paging so nothing else moves.
**Roboflow overlap:** `7-F7.38` → **T-399** adds cursor paging to the *audit* endpoint; the public v1 contract is separate → **T-982**.
**Sources:** <https://mlflow.org/docs/latest/rest-api.html>

## 5.16 Speaking enough of their wire format that their client works
**What it does.** The tracking API is a small, stable set of JSON POSTs: `experiments/create|get|
get-by-name|search`, `runs/create|get|update|delete|restore|search`, `runs/log-metric|
log-parameter|log-batch|set-tag|delete-tag`, `metrics/get-history`, `artifacts/list`. Requests carry
`experiment_id`/`run_id`; responses wrap an `experiment`/`run` object with `info`, `data.metrics`,
`data.params`, `data.tags`. `(MLF: https://mlflow.org/docs/latest/rest-api.html)`
**UX flow, click by click.**
1. **Settings → Integrations → "Log from Python"** — the page shows `MLFLOW_TRACKING_URI=<our base>/api/mlflow`, `MLFLOW_TRACKING_USERNAME=<workspace slug>`, `MLFLOW_TRACKING_PASSWORD=<key>` and a four-line snippet. [empty: no key — "create a key first"] [loading: n/a] [error: a key from another workspace — the first call returns 404 for the experiment, and the page's "Test" button says "this key belongs to a different workspace"].
2. **Notebook** — `mlflow.set_experiment("qa-sweep")` then `mlflow.start_run()`; the run appears in the workspace's runs list within a second, attributed to the key's owner and the key prefix.
3. **Wrong shape** — an unknown `run_id` returns a 404 whose body is shaped like their error envelope, so their client raises `MlflowException` instead of a parse error.
**LabelDesk:** MISSING — no `/api/2.0/mlflow/*` surface: `grep -i mlflow apps/` returns nothing; the public API is `/api/v1` (`routers/devapi.py`), authenticated by workspace keys with scopes `read|upload|train|infer` (`apps/backend/app/apikeys.py:1-6`).
**Priority:** Must · **Size:** M
**Decision:** **Wire-compatible (MLflow REST subset)** — their client, our tenancy: a router mounted in our app behind our key auth, translating into our tables. Never their server, never a second auth boundary.
**Roboflow overlap:** none — no card plans an external-wire surface → **T-983, T-984**.
**Sources:** <https://mlflow.org/docs/latest/rest-api.html>, <https://mlflow.org/docs/latest/api_reference/python_api/index.html>

## 5.17 The Python client, and what "skinny" means for us
**What it does.** `mlflow-skinny` is the same client API without SQL storage, server, UI or data
science dependencies ("set the tracking URI to your remote server"); `mlflow` adds the rest. So a
team can log from a notebook with a ~4 MB wheel. `(MLF: https://pypi.org/project/mlflow-skinny/)`
**UX flow, click by click.**
1. **Notebook** — `pip install mlflow-skinny`, set the three env vars from the Integrations page, `mlflow.log_param`/`log_metric`; no LabelDesk package needed. [empty: no runs yet — the workspace runs screen shows its own empty state, the notebook is unaffected] [loading: each log call is one HTTP round-trip] [error: a revoked key → their client raises with our 401 body, and the Integrations page's own test says the key is revoked].
2. **Our own SDK stays thinner** — `packages/sdk/labeldesk` keeps one dependency (`httpx`, `client.py:1-14`).
**LabelDesk:** PARTIAL — our SDK exists and is deliberately thin (`packages/sdk/labeldesk/client.py`, `cli.py`, generated operation map `_generated.py`), but it only speaks `/api/v1`; nothing speaks the wire format of 5.16, so a notebook cannot log without our package.
**Priority:** Should · **Size:** S
**Decision:** Integrate (mlflow-skinny, optional extra) + Build the server half — the client is thousands of lines and Apache-2.0; we install it in a dev/test extra only, never in the app image. `THIRD_PARTY_LICENSES.md` gets the entry when the test extra lands.
**Roboflow overlap:** `7-F7.37` → T-441 is our *own* client's handshake; a third-party client is a different contract → **T-985**.
**Sources:** <https://pypi.org/project/mlflow-skinny/>, <https://mlflow.org/docs/latest/rest-api.html>

## 5.18 Other language SDKs
**What it does.** Four first-party clients are documented: Python, R, Java, TypeScript (the TS SDK
shipped as `ts/v0.2.0` in this window). All four are thin over the same REST surface.
`(MLF: https://mlflow.org/docs/latest/rest-api.html)`
**UX flow, click by click.**
1. **Settings → Integrations → JavaScript** — `npm i @labeldesk/client`, a snippet using a publishable key for browser inference and a workspace key for server calls. [empty: no publishable key — the browser tab is greyed with "publishable keys are needed for the browser"] [loading: n/a] [error: a workspace key used in the browser — the server refuses with "publishable keys only" and the snippet annotates why].
**LabelDesk:** MISSING — Python only: `packages/sdk/labeldesk/{client.py,cli.py,_generated.py}`; the frontend has generated types (`apps/frontend/src/lib/api-types.gen.ts`, `npm run gen:api-types`) but no published JS client.
**Priority:** Could · **Size:** S
**Decision:** Build (our store/UI) — generate from the OpenAPI file we already export; R and Java are declined (no buyer asks, and a half-maintained client is worse than none).
**Roboflow overlap:** `7-F7.34` → T-007 guards the publishable key this would use; no client card exists → **T-987**.
**Sources:** <https://mlflow.org/docs/latest/rest-api.html>

## 5.19 The command line
**What it does.** One CLI covers the whole platform: `mlflow run` (projects), `mlflow server`,
`mlflow gc` (purge deleted runs), `mlflow db upgrade|downgrade|move-resources`, `mlflow doctor`-style
diagnostics under `db`/`traces` subcommands, plus newer `mlflow datasets list`, `mlflow skills`.
`(MLF: https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/)`
**UX flow, click by click.**
1. **`labeldesk doctor`** — checks: base URL reachable, key valid and its scopes, API version match, server disk free, GPU/worker health, credits left; prints a tick/cross table and exits non-zero on a cross. [empty: n/a] [loading: one line per check as it completes] [error: each failed check prints one sentence and the fix, never a traceback].
2. **`labeldesk jobs`** — the workspace job list with status, kind and elapsed, matching the tray.
**LabelDesk:** PARTIAL — `packages/sdk/labeldesk/cli.py:71-110`: `whoami`, `models`, `upload`, `export`, `train`, `predict`, with `--json` and `--wait`. No doctor, no job list, no dataset dump.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a read-only reporter over routes that exist (`/api/health`, `/api/v1/whoami`, `/api/ws/{ws}/jobs`).
**Roboflow overlap:** `7-F7.37` → T-441 owns auth setup inside the CLI; diagnostics are new → **T-986**.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/>, <https://mlflow.org/docs/latest/api_reference/cli.html>

## 5.20 Where the model surfaces live in the sidebar
**What it does.** The UI is one navigation tree: home lists experiments → an experiment lists runs
→ a run detail shows overview, metrics, params, tags, a Model section and an Artifacts section →
runs can be selected for comparison → a logged model has its own page with artifacts and
environment. 3.6 moved the experiment tab bar to the left rail; 3.10 added a workspace landing
page. `(MLF: https://mlflow.org/docs/latest/ml/tracking/quickstart/)`
**UX flow, click by click.**
1. **Sidebar → project → "Experiments"** — the new group sits under MODELS with one entry, and the workspace breadcrumb gains the experiment name. [empty: "no experiments yet — every training run lands in `default`" with a link to Train] [loading: nav renders immediately; the page shows its own skeleton] [error: the page fails to load — the nav entry stays, the page shows retry, never a blank shell].
2. **Reserved segments** — `experiments` is added to the reserved workspace-segment set so `/:ws/experiments` is never mistaken for a project slug (`apps/frontend/src/lib/nav/registry.ts:38-40`).
**LabelDesk:** PARTIAL — the IA exists and is testable (`apps/frontend/src/lib/nav/registry.ts:21-25`, groups in `lib/nav/workspace/*.ts` and `lib/nav/project/*.ts`, guarded by `apps/frontend/tests/nav.test.mjs`), but there is no experiments/runs branch at all; workspace pages are `models|deployments|activity|playground|settings|audit|admin` (`routes/workspace.routes.tsx:15-28`).
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — one nav entry and one route shell so area 1's screens have a home; no screen content here.
**Roboflow overlap:** `5-F5.1`/`5-F5.16` (model table, live graphs, T-005 guard) sit in the existing MODEL group; the experiments slot is new → **T-980**.
**Sources:** <https://mlflow.org/docs/latest/ml/tracking/quickstart/>, <https://mlflow.org/docs/latest/ml/tracking/>

## 5.21 An experiment as a thing you can name, tag and delete
**What it does.** An experiment groups runs. It can be created (UI/API/CLI), renamed, tagged
(`set-experiment-tag`, 20 000-char values from 3.16), deleted and **restored**
(`mlflow.restore_experiment()` landed in 3.17), and searched by name/tag. Its artifact location is
recorded at creation. `(MLF: https://mlflow.org/docs/latest/ml/tracking/)`
**UX flow, click by click.**
1. **Project → Experiments** — a table: name, owner, run count, last activity, tags. Row menu: rename, edit tags, archive. [empty: "no experiments yet" with "create one" and "every run needs an experiment — use `default`"] [loading: skeleton rows] [error: duplicate name — "an experiment called `qa-sweep` already exists here" with a link to it].
2. **Archive** — archived experiments leave the list behind a "show archived" toggle and can be restored with one click; a delete is permanent only after typed confirmation.
3. **Notes** — a free-text note on the experiment, rendered on its page.
**LabelDesk:** MISSING — no experiment entity: `grep -i experiment apps/` returns nothing; the closest containers are `Project` (`apps/backend/app/models/project.py`) and the workspace trash (`routers/workspaces.py:399-418`).
**Priority:** Must · **Size:** M
**Decision:** Build (our store/UI) — experiments are tenancy-adjacent (they scope runs and permissions), so they are ours; no library is involved.
**Roboflow overlap:** `4-F4.45`/`5-F5.27` compare *versions*, not runs; `7-F7.43` → T-405–T-407 own trash semantics to reuse → **T-978, T-979**.
**Sources:** <https://mlflow.org/docs/latest/ml/tracking/>, <https://mlflow.org/docs/latest/rest-api.html>

## 5.22 Workspaces: many teams, one deployment
**What it does.** An optional scoping layer: experiments, registered models, prompts, gateway
resources and artifacts each belong to exactly one workspace; child resources inherit the parent's;
artifacts are isolated by URI prefix (`<root>/workspaces/<name>/<id>`); the active workspace is
chosen by `set_workspace()` → `MLFLOW_WORKSPACE` → provider default; `list_workspaces()` returns
only workspaces where you hold a workspace-level grant; the reserved `default` workspace cannot be
deleted. The docs are explicit that this is logical separation, **not** a compliance boundary.
`(MLF: https://mlflow.org/docs/latest/self-hosting/workspaces/)`
**UX flow, click by click.**
1. **Sidebar → workspace switcher** — the current workspace's name and plan, a list of the ones you belong to with your role, and "New workspace". [empty: you belong to none — the switcher offers "create your first workspace"] [loading: the list comes with `/me`, so the shell renders a placeholder rather than an empty menu] [error: a workspace you were removed from — the URL redirects to your first workspace instead of a 403 page].
2. **Switch** — every list, key, member and job is scoped to the new workspace; the URL changes to `/:ws`.
**LabelDesk:** HAVE, and stricter — `apps/frontend/src/components/shell/AppSidebar.tsx:68,120` builds the switcher from `me.workspaces`; membership per workspace `apps/backend/app/deps.py:135-144` (404/403 split), roles/custom bundles are workspace rows (`rbac.py`), keys are workspace rows (`apikeys.py`), and every query is rooted at `ctx.ws.id`. Workspace creation: `routers/auth.py:482-…`, UI `features/settings/Settings.tsx:1112`. Isolation is real (a foreign id is a 404), which is the opposite of their documented caution.
**Priority:** Must · **Size:** — (shipped)
**Decision:** Build (our store/UI) and keep it — this is the boundary their own docs say their server does not provide.
**Roboflow overlap:** `7-F7.1` → T-380 (roster/seats), `7-F7.57` → T-007 (first-run creation), `7-F7.61` → T-447–T-449 (cross-workspace rollup). **No new card.** No guard exists yet for this row.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/workspaces/>, <https://mlflow.org/docs/latest/self-hosting/workspaces/permissions/>

## 5.23 One server, one store, and a way to see both
**What it does.** `mlflow server` serves UI + REST from one process; the backend store is SQLite by
default (since 3.7), or Postgres/MySQL/MSSQL, or the legacy file store (maintenance mode);
artifacts go local (`./mlartifacts`), to a proxied object store (`--artifacts-destination`), or
direct (`--no-serve-artifacts` + `--default-artifact-root`); `--artifacts-only` splits artifact
serving onto its own process; deleted runs keep their rows until `mlflow gc`; a schema mismatch
stops the server until `mlflow db upgrade`. `(MLF: https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/)`
**UX flow, click by click.**
1. **`labeldesk doctor` → Stores** — prints the DB dialect and path, the artifact root, free disk, and the row counts that matter (jobs queued, oldest job). [empty: fresh install — all zeros, no error] [loading: one line per check] [error: DB file unreadable or disk < 10% — a cross with the exact path].
2. **Superadmin → Admin console → Server** — the same facts, read-only, for a support call.
**LabelDesk:** PARTIAL — one process, one store, chosen by env: `apps/backend/app/config.py:36-39` (`LD_DATA_DIR`, `DATABASE_URL`, default `sqlite:///<DATA_DIR>/labeldesk.db`), schema without a revision table but idempotent `ADD COLUMN` steps (`apps/backend/app/schema/__init__.py:10-34`), signed file serving (`main.py:89-98`). No diagnostics surface, no artifact-root choice, no gc command.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — a read-only reporter. We deliberately do **not** offer a second store backend or an artifacts-only split: one deployment shape is a feature.
**Roboflow overlap:** `6-F6.45`/`6-F6.5` (deploy hub, self-host install) own the deployment story; diagnostics are new → **T-986** (same card as 5.19).
**Sources:** <https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/>, <https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/>

## 5.24 Job status, ownership and cancellation
**What it does.** Long work runs as a server job: `/jobs/search` returns the caller's jobs (scoped
per-job under basic auth since 3.16's fail-closed work), the queue is a local Huey store or Redis
(`MLFLOW_SERVER_JOB_HUEY_REDIS_URL`), periodic tasks run on exactly one replica, and the executor
engine is documented as single-replica only. `(MLF: https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)`
**UX flow, click by click.**
1. **Job tray** — every queued/running/done/failed job for the workspace, with kind, progress and a cancel button; the tray survives navigation and announces changes politely. [empty: "nothing running" with the last three finished jobs] [loading: a queued row appears immediately, before the worker claims it] [error: cancel a running job — it flips to "cancelling" and says the worker must acknowledge; a reaped job says "the worker stopped reporting" not "failed"].
2. **Drill-in** — a job row opens its params, result, sanitised error and the retry action.
**LabelDesk:** PARTIAL — jobs are first class: `apps/backend/app/models/training.py:9-31` (status/executor/progress/params/result/error/times), list `apps/backend/app/routers/workspaces.py:314-331`, cancel `routers/projects.py:523-…` (queued → cancelled, running → cancelling), UI `apps/frontend/src/components/shell/JobTray.tsx:19`. Absent: a per-job detail with retry, and a log tail.
**Priority:** Should · **Size:** S
**Decision:** Build (our store/UI) — extend the tray we have; a Huey/Redis queue is exactly the complexity ponytail refuses.
**Roboflow overlap:** `5-F5.16` live graphs and `7-F7.43`; the tray rewrite is **T-481** (wave E, job panel with per-row cancel/dismiss) and **T-016** already maps finished kinds to destinations. **No new card** — retry stays a note on T-481 rather than a second card on the same file.
**Sources:** <https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/>

## Judgment calls

- **5.7 recipes** — the brief asks for `recipe.yaml`, profiles, steps and caching; the current docs
  have no recipes page at all (`/docs/latest/recipes.html` redirects to a 403 stub, and the sitemap
  has no `recipe` entry). I planned the *behaviour* (declarative multi-step pipeline, profiles,
  per-step cache) against the composition story that does replace it, and reused our block graph.
  Anything labelled "recipes" as if it were current docs would be citing a page that does not exist.
- **5.16 wire compatibility vs "integrate the library"** — the brief's rule is their client, our
  tenancy. The subset is a router inside `app.main` mounted on our own key auth; no process, no
  second session store, no `basic_auth.db`. Every card that touches it says so.
- **5.10 per-object permissions** — declined, not deferred silently: `rbac.py` is two-level plus
  grant-only bundles, and `7-F7.11`'s folder scope is the tier our users actually need. Adding
  `experiment:42`-style grants would put a new branch in every query for no buyer.
- **5.22 workspaces** — their docs say workspaces are "not a hard isolation boundary"; ours are.
  I did **not** copy their workspace semantics (a shared `default` workspace, URI-prefixed
  artifacts, a floor that per-resource grants can only raise), because our boundary is the
  security property customers buy.
- **5.13 SSO** — counted PARTIAL, not MISSING, because token verification and just-in-time
  provisioning already ship (`oidc.py`); what is missing is the browser flow and group mapping,
  which `7-F7.35`/`7-F7.41` already own. No card, to avoid two plans for one IdP integration.
- **5.24 job surface** — counted PARTIAL with no card: `T-481` rewrites the exact file
  (`components/shell/JobTray.tsx`) and `T-016` already maps job kinds to destinations. Adding a
  card here would put two agents on one file.
- **5.3 / 5.23 stores** — I did not plan a pluggable artifact store or a schema-revision table.
  The first is `L` work with a new dependency (an S3 client) for a need no buyer has stated; the
  second is unnecessary while `schema.apply` is idempotent. Both are recorded as gaps, not cards.
