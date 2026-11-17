# MCP server for LabelDesk — design note

Baseline: `feat/labeldesk-v2`, read 2026-11-17 (planning lane, read-only; no application code touched).
Sources read the same day: the MCP specification and the official Python SDK docs (URLs in §1 and §2),
and the LabelDesk API itself — `apps/backend/app/routers/`, `apps/backend/app/apikeys.py`,
`apps/backend/app/services/`, `packages/sdk/`. Raw evidence with every URL:
[`_research-raw.md`](_research-raw.md).

Owner request this note answers (2026-11-17): *"make an MCP server so AI agents can connect to LabelDesk
and use it."*

**What it contains.** One server, 16 tools, 3 resources and 2 prompts, over two transports (stdio for a
local agent, Streamable HTTP on the API's origin for a hosted agent). Every tool is a thin call to the
existing `/api/v1` developer surface under the caller's own API key: no second permission model, no second
database, no new store. **10 cards, 27.5 agent-hours**, `T-990`–`T-999`.

---

## 1. The specification, summarised

Two protocol eras are live today, and the difference decides most of the design:

| Era | Revision | Shape |
| --- | --- | --- |
| Modern | **`2026-07-28`** (served as "latest") | Stateless. Every request is self-contained, carries its own version in `_meta`, and there is no `initialize` handshake, no `Mcp-Session-Id`, no HTTP GET stream and no SSE resumability. |
| Legacy | `2025-11-25` and earlier | `initialize` handshake, optional `Mcp-Session-Id`, GET SSE stream, `Last-Event-ID` resumability. What most deployed clients still speak. |

Sources: <https://modelcontextprotocol.io/specification/latest>,
<https://modelcontextprotocol.io/specification/2026-07-28/changelog.md>.

**Primitives.** `tools` (JSON-Schema `inputSchema`, optional `outputSchema`, `structuredContent`,
`isError` for execution errors, JSON-RPC errors for protocol errors), `resources` (`resources/list`,
`resources/read`, RFC 6570 templates), `prompts` (`prompts/list`, `prompts/get`, arguments, messages).
Tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) are hints a client
must not trust from an untrusted server. Tool-name rules: 1–128 chars of `A-Za-z0-9_.-`.
Sources: <https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md>,
[resources.md](https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md),
[prompts.md](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md),
[schema.md](https://modelcontextprotocol.io/specification/2026-07-28/schema.md).

**One rule that shapes everything here:** list results MUST NOT vary per connection but **MAY vary by the
authorization presented on the request** — "credentials are per-request input, not connection state"
(<https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md>). A shared `/mcp` endpoint is
therefore *expected* to answer `tools/list` differently per key, which is exactly what §6 does.

**Transports.**
- *stdio*: newline-delimited JSON-RPC on stdin/stdout; logs on stderr only; credentials come from the
  environment, not from the protocol (<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md>).
- *Streamable HTTP*: one endpoint, POST per message, `Accept` must allow `application/json` and
  `text/event-stream`. Servers **MUST** validate `Origin` (403 when invalid, DNS-rebinding defence) and
  **SHOULD** bind `127.0.0.1` when local
  (<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md>).

**Authorization** is OPTIONAL and, where used, an OAuth 2.1 resource-server model: RFC 9728 protected
resource metadata, `WWW-Authenticate` on 401, RFC 8707 resource indicators, bearer token on every request,
no tokens in the query string, and token passthrough explicitly forbidden
(<https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md>). LabelDesk has no
OAuth authorization server, so §8 documents a deliberate, smaller deviation: the workspace API key, sent as
`Authorization: Bearer`, which is what Stripe, Cloudflare and Linear do
(<https://docs.stripe.com/mcp>,
<https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/>,
<https://linear.app/docs/mcp>).

**Security practice** worth carrying into the tests: confused deputy, token passthrough, and state-handle
hijacking ("a handle is a name, not a capability") on the server side; scope minimisation and SSRF on
metadata discovery
(<https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md>).

## 2. The official Python SDK, summarised

`mcp` **2.3.0** (2026-10-02), Python **≥ 3.10**; runtime deps include `httpx2` (not `httpx`), `starlette`,
`uvicorn`, `pydantic>=2.12`, `jsonschema`
(<https://pypi.org/pypi/mcp/json> — verified 2026-11-17).

v2 renamed the server class, so the v1 snippets found in most blog posts do not import:

```python
from mcp.server.mcpserver import MCPServer, Context          # v1: from mcp.server.fastmcp import FastMCP
from mcp.server.mcpserver.exceptions import ToolError        # → isError: true, message fed to the model
```

- Decorators are unchanged: `@mcp.tool()`, `@mcp.resource("labeldesk://projects/{project}")`, `@mcp.prompt()`.
- Transport settings moved off the constructor onto `run()` / `streamable_http_app()`: `host`, `port`,
  `streamable_http_path`, `json_response`, `stateless_http`, `max_request_body_size` (4 MiB default),
  `transport_security`.
- `streamable_http_app()` returns a Starlette app (one route, default `/mcp`) and mounting is supported —
  but a mounted sub-app's lifespan never runs, so the host must enter `mcp.session_manager.run()`.
- `token_verifier=` + `auth=AuthSettings(...)` gives the OAuth resource-server half (RFC 9728 metadata,
  401 + `WWW-Authenticate`); `get_access_token()` reads the verified principal inside a handler.
- DNS-rebinding protection auto-arms for `127.0.0.1`/`localhost`/`::1`; a real hostname needs
  `TransportSecuritySettings(allowed_hosts=[...], allowed_origins=[...])` from `mcp.server.transport_security`.
- Client side: `from mcp.client import Client`; `async with Client(server)` is the in-memory test path,
  `Client("https://host/mcp")` speaks Streamable HTTP, and the SDK's default read timeout is 300 s.
Sources: <https://py.sdk.modelcontextprotocol.io/migration/index.md>,
<https://py.sdk.modelcontextprotocol.io/run/index.md>,
<https://py.sdk.modelcontextprotocol.io/run/asgi/index.md>,
<https://py.sdk.modelcontextprotocol.io/run/authorization/index.md>,
<https://py.sdk.modelcontextprotocol.io/client/transports/index.md>.

**What other products do, in one line each** (details and URLs in `_research-raw.md` §3): GitHub —
Streamable HTTP + PAT-or-OAuth, per-tool OAuth scopes; Cloudflare — two tools (`search`, `execute`) instead
of 2,500 endpoints; Sentry — remote HTTP + local stdio, scoped per org/project; Linear — separate read-only
path plus a read-only scope; Stripe — a bearer "agent key" and human confirmation on write actions; Roboflow
— Streamable HTTP, OAuth with DCR, tools named `projects_list` / `projects_get` / `agent_workflow_publish`.
Two lessons carried in: **fewer, task-shaped tools beat an endpoint mirror**, and **write actions need a
confirmation step that is keyed to the action, not the tool name**.

## 3. What LabelDesk already has

The developer surface is the seam this server uses. Every operation is key-authenticated, scope-checked and
already audited at the key boundary.

| Operation (`operationId`) | Method + path | Scope | Notes |
| --- | --- | --- | --- |
| `whoami` | `GET /api/v1/whoami` | read | returns workspace, plan and the key's scopes |
| `list_projects` | `GET /api/v1/projects` | read | id, slug, name, type, image count, class names |
| `list_images` | `GET /api/v1/projects/{project}/images` | read | `offset`/`limit`, currently no filters |
| `upload_images` | `POST /api/v1/projects/{project}/upload` | upload | multipart files |
| `upload_images_v1` | `POST /api/v1/{ws_slug}/{project}/upload` | upload | accepts `image=<url>` through `services/safefetch.py` |
| `list_versions` | `GET /api/v1/projects/{project}/versions` | read | |
| `export_version` | `POST /api/v1/projects/{project}/versions/{vid}/export` | read | |
| `start_training` | `POST /api/v1/projects/{project}/train` | train | 3 credits |
| `get_job` | `GET /api/v1/jobs/{job_id}` | read | |
| `list_models`, `get_model` | `GET /api/v1/models[/{id}]` | read | includes lean metrics |
| `predict` | `POST /api/v1/models/{model_id}/predict` | infer | `file`, `image=<url\|base64>`, 0.001 credits |

Evidence: `apps/backend/app/routers/devapi.py`, `apps/backend/app/routers/training.py:662-689`,
`packages/sdk/labeldesk/_generated.py`, `tools/gen_sdk.py`.

Everything else an agent needs — annotations, auto-label, creating a version, deployment aliases, filtered
image search, project detail — exists **only in the session-authenticated app routers**
(`images.py`, `training.py`, `versions.py`, `deployments.py`) and has no key-authenticated twin. Those
missing twins — six new routes, plus two existing key routes extended in place — are the only backend work
in this wave (§5, cards `T-990` and `T-991`).

Facts that constrain the design, all read from the code:

- Scopes are `read | upload | train | infer` (`app/models/common.py:14`); a NULL scope list means all
  (`app/apikeys.py:39-41`); publishable keys are forced to `infer` (`app/routers/workspaces.py:255-256`).
- A key is accepted as `Authorization: Bearer`, `x-api-key`, or `?api_key=` **only for publishable keys**
  (`app/apikeys.py:21-23,67-84`).
- Key resolution rate-limits at **600 per 60 s per client IP** (`app/apikeys.py:81`), and every use writes
  one throttled `apikey.use` audit row (`app/apikeys.py:27-36`).
- Credits: train 3, auto-label 0.01 per image, inference 0.001, version 0.5; over the plan's allowance the
  API answers **402** (`app/config.py:115`, `app/deps.py:191-197`).
- Developer calls run with `Ctx(user=None, role="admin")` (`app/routers/devapi.py:22-24`), so any code path
  that touches `c.user.id` breaks under a key. Two such paths exist today and are fixed in `T-991`:
  `training.autolabel` (`routers/training.py:524`) and `versions.create_version` (`routers/versions.py:66`).
- `label_events.user_id` is NOT NULL (`app/models/insights.py:123`), so a key-driven annotation save must be
  attributed to a real user. It is attributed to **the key's issuer** (`api_keys.created_by`), falling back
  to the workspace owner — no schema change, and "who did this" stays answerable.

## 4. Design

**A thin adapter over `/api/v1`, not a second backend.** The server holds no database handle, no model
cache and no state beyond the key of the current request. Delete it and LabelDesk still works, minus the
agent-facing protocol — the deletion test passes because the complexity it hides (16 tool schemas, two
transports, the confirm gate, the scrub, error shaping) would otherwise reappear in every agent that wanted
to call the REST API by hand.

Decisions, each with the reason that made it win:

1. **Tools call the public API with the caller's key.** Permission, workspace isolation, metering, audit and
   rate limiting stay in exactly one place. A tool cannot be more permissive than the route behind it, and a
   cross-workspace id returns the route's 404, not a new refusal path to get wrong.
2. **Per-request key.** stdio: `LABELDESK_API_KEY` from the environment. HTTP: the `Authorization` header of
   each POST, put in a context variable by one middleware. One seam, two adapters; the in-memory test path
   sets the same variable directly.
3. **`tools/list` is filtered by the key's scopes.** `whoami` is called once per request to learn the scopes
   (a 5 ms local call, cached for the request). A `read`-only key never sees `start_training`; a key without
   `write` never sees `write_annotations`. The API still enforces every scope — the filter is courtesy, the
   403 is the contract.
4. **Every spend or overwrite takes `confirm: bool = false`.** Without it the tool performs a dry run and
   returns what would happen and what it would cost. This is Stripe's pattern (confirmation keyed to the
   action) and it also blunts prompt-injection: an agent that reads a hostile caption cannot quietly start a
   3-credit training run.
5. **No tool blocks on a job.** Training, version generation and auto-label return the `Job` and the agent
   polls `get_job`. Long-held SSE streams are the first thing a proxy breaks
   (<https://py.sdk.modelcontextprotocol.io/run/deploy/index.md>).
6. **Scrub on the way out.** Every result passes one recursive scrubber that drops keys named
   `settings`, `hash`, `sha256`, `password`, `token`, `secret`, `api_key`, `credentials`, and truncates
   strings over 8 KiB. Project `settings` can hold webhook and connector values; an agent transcript is a
   place they must never reach.
7. **Audit at the key boundary.** The server stamps `x-mcp-tool` on every API call; `resolve_key` writes one
   `mcp.tool` audit row when that header is present. One hook, every tool, including the ones added later.
8. **`write` is a new scope.** Annotations, versions and auto-label write project data. Reusing `upload`
   would let an image-upload key rewrite human labels; reusing `train` would grant GPU spend to a
   label-writing bot. One new value in `models/common.py` and a key that opts in.
9. **Destructive account actions are out of scope.** No delete, no deploy-alias switch, no key management, no
   billing. A leaked agent key must not be able to destroy a dataset, and `destructiveHint` is a hint, not a
   gate.
10. **One workspace switch, one deployment switch.** `task_992` in `services/flags.py`, reported as
   `whoami().mcp`, is the per-workspace kill switch: off, every tool refuses before touching the API, on
   either transport. The compose `profiles: ["mcp"]` decides whether a deployment runs the endpoint at all.
   Neither is a substitute for the other, and neither needs a new endpoint.

**Where the HTTP transport runs.** The API's image builds from `apps/backend` (1.9 GB with CPU torch) and
copies only `app/`; the MCP server needs `mcp` + the SDK, and it must also be `pip install`-able for a local
agent. Rather than grow the API image and teach it a second lifecycle, the server is its own small app
(`apps/mcp`, a ~90 MB image) served on the API's own origin by the existing Caddy: `route /mcp* { reverse_proxy
mcp:8020 }` before the SPA's `reverse_proxy web:80` (`route` keeps the written order; a `handle` block would
mean re-wrapping the existing proxy). Same URL space, same TLS, same bearer key — and an MCP bug cannot take
the API down or reach the database. The in-process alternative is priced in §10 and left as the upgrade path
if the owner wants `/mcp` to disappear behind the API's own middleware.

## 5. Tool catalogue

Common conventions: every tool returns a JSON object or array (`structuredContent` plus a text block);
expected failures raise `ToolError`, which the client sees as `isError: true` with the API's own message;
`project` is the project **slug**; ids are the API's ids. `limit` is capped by the server below the route's
own maximum so one call cannot return a megabyte.

### Read tools (scope `read`)

| Tool | Input | Output | Backing operation |
| --- | --- | --- | --- |
| `whoami` | — | `{workspace, name, plan, scopes, mcp, publishable}` | `whoami` |
| `list_projects` | — | `[{id, slug, name, type, images, classes}]` | `list_projects` |
| `get_project` | `project` | `{id, slug, name, type, visibility, images, models, statusCounts, classes:[{id,name,color,count}]}` | `get_project` (new, T-990) |
| `list_images` | `project`, `q=""`, `split=""`, `status=""`, `class_id=""`, `tag=""`, `batch_id=""`, `annotated=""`, `sort="newest"`, `offset=0`, `limit=50` | `{total, items:[{id,name,width,height,split,status,review,tags,batchId,annotated,annotationCount,created,url,thumbnail,classIds}]}` | `list_images` (filters added, T-990) |
| `get_image` | `project`, `image_id` | image as above plus `annotations:[{id,classId,shape,source,confidence?}]` | `get_image` (new, T-990) |
| `list_versions` | `project` | `[{id, number, name, status, created}]` (`settings` is stripped: tiling config is not something an agent acts on) | `list_versions` |
| `get_job` | `job_id` | `{id, kind, status, progress, error, result, url}` | `get_job` |
| `list_models` | — | `[{id, name, variant, status, metrics, versionId, created}]` | `list_models` |
| `get_model` | `model_id` | same, one row | `get_model` |
| `list_deployments` | — | `{projects:[{project, aliases:[{alias, model, updated}], models:[...]}]}` | `list_deployments` (new, T-991) |

### Write and spend tools

| Tool | Scope | `confirm` | Input | Output |
| --- | --- | --- | --- | --- |
| `upload_image_url` | `upload` | no (additive, deduped by sha256) | `project`, `url`, `batch="MCP upload"`, `split="auto"`, `tags=""` | `{success, duplicate, id}` |
| `write_annotations` | `write` | **yes** | `project`, `image_id`, `annotations[]`, `confirm=false` | `{saved, status}` — dry run: `{wouldReplace: n, wouldSave: m, credits: 0}` |
| `run_auto_label` | `write` | **yes** | `project`, `model_ref=""`, `model_id=""`, `prompt=""`, `class_ids=[]`, `image_ids=[]`, `batch_id=""`, `confidence=null`, `only_unannotated=true`, `send_to_review=true`, `confirm=false` | `Job` — dry run: `{estimatedImages, estimatedCredits}` |
| `create_version` | `write` | **yes** | `project`, `name=""`, `settings={}`, `confirm=false` | `Version` — dry run: `{credits: 0.5, images}` |
| `start_training` | `train` | **yes** | `project`, `version_id`, `variant="yolo26n"`, `epochs=30`, `imgsz=640`, `batch=8`, `name=""`, `confirm=false` | `Job` — dry run: `{credits: 3, gpuLease: true}` |
| `predict_image` | `infer` | **yes** | `model_id`, `image_id=""`, `image_url=""`, `confidence=null`, `confirm=false` | `{predictions:[{class, confidence, x, y, width, height}], image:{width,height}}` — dry run: `{credits: 0.001}` |

`upload_image_url` deliberately has no `confirm`: it is additive, it dedupes on the image sha256, and the
URL is fetched by `services/safefetch.py` (public addresses only, 20 MB cap, 10 s budget, redirects
re-checked), so the worst case is one duplicate row.

### Resources

| URI | Returns |
| --- | --- |
| `labeldesk://workspace` | Markdown: workspace name, plan, credits left, project count, the key's scopes |
| `labeldesk://projects/{project}` | Markdown: project summary, status counts, class table with ids |
| `labeldesk://projects/{project}/classes` | Markdown table: class id, name, colour, image count |

Resources are the "read it before you write it" surface: an agent that has read `…/classes` knows the
`classId` values `write_annotations` needs.

### Prompts

| Prompt | Arguments | Message |
| --- | --- | --- |
| `review_low_confidence_labels` | `project`, `threshold=0.5`, `limit=20` | One user message: the low-confidence annotations found by `sort=review`, the class names, and the instruction to inspect each with `get_image` and correct only real errors |
| `audit_unannotated_batch` | `project`, `batch_id=""` | One user message: the unannotated image count, the batch name, and a step list: sample 10 images, propose classes, then `run_auto_label` **after** the operator confirms |

## 6. Permissions, per tool

| Tool | Key scope | Route check | Cross-workspace id | Notes |
| --- | --- | --- | --- | --- |
| `whoami` | read | `k.need("read")` | n/a | also returns the scope list the client filters on |
| `list_projects`, `list_models`, `list_deployments` | read | `k.need("read")` | n/a | filtered by `workspace_id` in the route |
| `get_project`, `list_images`, `get_image`, `list_versions` | read | `k.need("read")` | **404** | project resolved by `(workspace_id, slug)`; image by project |
| `get_job`, `get_model` | read | `k.need("read")` | **404** | route returns 404 when the row's workspace differs |
| `upload_image_url` | upload | `k.need("upload")` | **404** | `ws_slug` must equal the key's workspace (403 otherwise) |
| `write_annotations` | write | `k.need("write")` | **404** | classes must belong to the project (400), 5000-annotation cap |
| `run_auto_label` | write | `k.need("write")` | **404** | `metering.check` reserves one AI call per target image |
| `create_version` | write | `k.need("write")` | **404** | 0.5 credits, 402 when exhausted |
| `start_training` | train | `k.need("train")` | **404** | 3 credits, GPU lease, 402 when exhausted |
| `predict_image` | infer | `k.need("infer")` | **404** | 0.001 credits, `metering.check` first |

Publishable keys (`ld_pub_*`) can never reach this server's non-`infer` tools: they are `infer`-only and the
MCP HTTP middleware refuses a publishable key outright, because a browser-embedded key must not be able to
drive an agent loop.

## 7. Transports and deployment

**stdio (local).** `pip install ./packages/sdk` then `pip install ./apps/mcp` (the SDK is not on PyPI, so it
goes first), then the agent host runs `labeldesk-mcp` with

```json
{ "command": "labeldesk-mcp",
  "env": { "LABELDESK_API_KEY": "ld_...", "LABELDESK_URL": "https://labeldesk.example.com" } }
```

Nothing is written to stdout except MCP frames; the key is never logged; a missing key exits 2 with one line
on stderr.

**Streamable HTTP (hosted).** `labeldesk-mcp --http --host 0.0.0.0 --port 8020` serves a Starlette app whose
only route is `/mcp` (path configurable). One middleware resolves `Authorization: Bearer ld_…` per POST into
the context variable, refuses `ld_pub_*`, and validates `Origin`/`Host` against
`TransportSecuritySettings(allowed_hosts=[LD_MCP_ALLOWED_HOSTS])`. Deployed as a compose service on the API's
network and routed by the existing Caddy (`handle /mcp* { reverse_proxy mcp:8020 }`), so the public URL is
`https://<LD_DOMAIN>/mcp` — same origin, same TLS, same key as `/api/v1`.

`max_request_body_size` stays at the SDK's 4 MiB: a tool call is small; image bytes travel by URL, and
`upload_image_url` hands the fetch to the API's `safefetch`, never to the MCP process.

## 8. Authentication, and the part of the spec we do not implement

| Item | Decision |
| --- | --- |
| Credential | Workspace API key (`ld_…`), `Authorization: Bearer` on every HTTP request |
| stdio | `LABELDESK_API_KEY` from the environment, per the spec's stdio rule |
| Query-string keys | Refused. The API only allows `?api_key` for publishable keys, and this server refuses publishable keys |
| OAuth 2.1 / RFC 9728 metadata | **Not implemented.** LabelDesk has no authorization server, no consent screen and no client registry. Publishing RFC 9728 metadata that points at nothing would be worse than not publishing it. |
| Token passthrough | Structurally impossible: the incoming key is the outgoing key, to the same product. No second token is ever minted or forwarded. |
| Scope of a key | The key is workspace-wide and acts as workspace admin (`routers/devapi.py:22-24`). Project-role granularity is not available to keys today; the card for `write` states this limit. |

This is a documented deviation, not an oversight: the spec makes HTTP authorization a SHOULD
(<https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md>), and a bearer
API key is what Stripe, Cloudflare and Linear ship. If LabelDesk later grows OIDC-based MCP auth, the SDK
already provides the resource-server half (`token_verifier=` + `AuthSettings`), so the change is one
verifier plus metadata publishing, not a rewrite.

## 9. Rate limits, quotas and failure modes

| Bound | Value | Where |
| --- | --- | --- |
| Key resolution | 600 per 60 s per client IP | `app/apikeys.py:81` |
| Credits | train 3, version 0.5, auto-label 0.01/image, inference 0.001; 402 when the plan's allowance is spent | `app/config.py:115`, `app/deps.py:191-197` |
| AI calls | reserved before the job runs (`metering.check`) | `app/services/metering.py` |
| Uploaded image | 20 MB, 10 s, public addresses only | `app/services/safefetch.py:13-14` |
| Annotations per image | 5000 (route), 500 for a consensus draft | `routers/images.py:536` |
| Images per page | route max 1000, tool cap 200 | `routers/images.py:252`, `T-993` |
| HTTP body | 4 MiB, then 413 before parsing | SDK default |
| Client read timeout | 300 s default; no tool is allowed to approach it | <https://py.sdk.modelcontextprotocol.io/client/transports/index.md> |
| Retry safety | No idempotency key in the protocol; `upload_image_url` dedupes on sha256, the job tools return a job id that a retry would duplicate — an agent that retries `start_training` starts a second run and pays for it | <https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md> |

`429` and `402` are surfaced as `ToolError` with the API's message and `Retry-After`/credit wording intact,
because the model has to be able to tell "wait" from "ask the owner for credits".

## 10. Options considered

| # | Option | New code (LOC) | Verdict |
| --- | --- | --- | --- |
| **1** | **Thin MCP app over `/api/v1` + 6 new key-authenticated routes and 2 extended ones** — stdio and Streamable HTTP in `apps/mcp`, sidecar on the API's origin | ~180 backend, ~380 app, ~40 deploy/config, ~450 tests → **~1,050** | **Chosen.** One permission model, one audit path, a key that cannot exceed its scopes, and an image small enough to `pip install` on a laptop. |
| 2 | Mount the same server inside the API process (`app/mcp/`, `Mount("/", …)`, `session_manager.run()` in the lifespan) | ~40 more (lifespan + mount), ~120 more (build context change, Dockerfile, `.dockerignore`), and `mcp`+`httpx2` in the API image | Rejected **for now**: the API image builds from `apps/backend` and copies only `app/`, so sharing the server needs the build context moved to the repo root; and a protocol bug would then sit inside the process that holds a DB session. Kept as the upgrade path. |
| 3 | A second backend that talks to the database — re-implement RBAC, tenancy, metering, audit inside the MCP server | ~1,500+, plus every future permission change in two places | Rejected outright. Two permission models is how cross-tenant bugs ship. |
| 4 | Full OAuth 2.1 resource server — RFC 9728 metadata, token verifier, client registration, consent | ~400 more, and a product decision (who is the authorization server?) the owner has not made | Rejected for v1. The SDK's `token_verifier` makes it additive later. |
| 5 | No server; document the SDK/CLI and let agents write Python | 0 | Rejected: the owner asked for MCP, and a code-execution agent is a larger trust jump than 16 typed tools. |
| 6 | Mirror every REST endpoint as a tool (Roboflow-style breadth) | ~1,800 | Rejected: 60+ tools overflow an agent's tool budget and expose surfaces (keys, billing, members) no agent should touch. 16 tools cover the whole core loop. |

## 11. Risks

| # | Risk | Mitigation (and the card that proves it) |
| --- | --- | --- |
| 1 | **A leaked agent key is a workspace-wide admin key.** Scopes bound it to read/upload/write/train/infer; destructive account actions are not exposed at all. | Documented limit; `T-998` asserts every destructive tool is absent; key revocation is one click (`DELETE /api/ws/{ws}/keys/{id}`). |
| 2 | **Credit burn.** An agent can loop `run_auto_label` at 0.01 credits per image, up to 600 requests a minute. | `confirm` on every spend tool, `metering.check` reservations, 402 at the plan ceiling, and one audit row per call so the cause is visible (`T-994`, `T-997`). |
| 3 | **Prompt injection through image names, tags or annotations** — the model reads attacker-controlled text and then calls a write tool. | `confirm` on writes, no delete/deploy tools, image names sanitised at ingest (`routers/images.py:39-43`), and tool descriptions that never instruct the model to trust file content (`T-994`). |
| 4 | **Cross-workspace access through a guessed id.** | Every tool resolves through the key's workspace; the route's 404 is the only answer; `T-998` parametrises 10 cross-workspace cases. |
| 5 | **Secret leakage into the transcript.** Project `settings` can hold webhook/connector config. | One scrubber on every result (`T-992`), asserted by a test that seeds a secret into `settings` and greps the tool output. |
| 6 | **Audit blind spot.** A tool call that never reaches the API (a refused confirm) is not audited. | Accepted: nothing happened. Every admitted call is audited at `resolve_key` (`T-997`). |
| 7 | **The HTTP endpoint is a new internet-facing surface.** | Bearer key required, publishable keys refused, `Origin`/`Host` allowlist, 4 MiB body cap, no server→client channel used (`stateless`-safe), R7 review on `T-997`/`T-998`. |
| 8 | **Retry duplicates a paid job.** | The protocol has no idempotency key; tool descriptions say so, job tools return the job id, and `upload_image_url` dedupes on sha256. |
| 9 | **Two protocol eras.** Most deployed clients still handshake `2025-11-25`. | Both eras are the SDK's job, not ours: no session state is kept, so `stateless` is the honest default, and `T-996` proves the modern path while `T-999` documents the legacy clients the SDK supports. |
| 10 | **Version drift.** Pinning `mcp` wrong breaks imports (`FastMCP` is gone in v2). | `mcp>=2.3,<3` in `apps/mcp/pyproject.toml` and a test that asserts `MCPServer` is importable (`T-992`). |

## 12. Deliberately not planned

Delete (image/project/version), deploy-alias switching, rollback, key or member management, billing, webhook
configuration, stream/OT control, workflow execution, batch inference over a bucket, semantic search
(`task_27` is off by default), resource subscriptions, sampling/elicitation, and a prompt library beyond the
two prompts in §5. Each is a separate decision with its own blast radius; none is needed for the core loop
"look at the data, label it, train, evaluate, deploy, infer".

## 13. The cards

`T-990`–`T-999`, 10 cards, 27.5 agent-hours, every card 1–3 h, tests first.

| Task | Title | Hours | Role | R7 | Depends on | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-990 | Key surface for reading and writing labels | 3 | R3 | yes | none | `apps/backend/app/routers/devapi.py`, `apps/backend/app/models/common.py`, `apps/backend/tests/test_devapi_labels.py` |
| T-991 | Key surface for jobs, versions and deployments | 3 | R3 | yes | T-990 (`write` scope) | `apps/backend/app/routers/devapi_actions.py` (new), `apps/backend/app/routers/training.py`, `apps/backend/app/routers/versions.py`, `apps/backend/tests/test_devapi_actions.py` |
| T-992 | MCP app skeleton, per-request key, scope filter | 3 | R3 | yes | T-990 (tool 1 needs the new surface) | `apps/mcp/pyproject.toml`, `apps/mcp/labeldesk_mcp/{__init__,api,server,__main__}.py`, `packages/sdk/labeldesk/client.py`, `apps/backend/tests/test_mcp_server.py` |
| T-993 | The eight read tools, with paging caps | 3 | R3 | no | T-992, T-991 (`list_deployments`) | `apps/mcp/labeldesk_mcp/tools_read.py`, `apps/backend/tests/test_mcp_read_tools.py` |
| T-994 | Six write and spend tools with a confirm gate | 3 | R3 | yes | T-992, T-991 (auto-label, version, predict-by-image) | `apps/mcp/labeldesk_mcp/tools_write.py`, `apps/backend/tests/test_mcp_write_tools.py` |
| T-995 | Resources and prompts | 2 | R3 | no | T-993 (the read helpers) | `apps/mcp/labeldesk_mcp/meta.py`, `apps/backend/tests/test_mcp_resources.py` |
| T-996 | Streamable HTTP transport and its guards | 3 | R3 | yes | T-992 | `apps/mcp/labeldesk_mcp/http.py`, `apps/backend/tests/test_mcp_http_transport.py` |
| T-997 | Audit every tool call, prove the limits | 2.5 | R3 | yes | T-992, T-996 | `apps/backend/app/apikeys.py`, `apps/backend/tests/test_mcp_audit.py` |
| T-998 | Isolation and adversarial suite | 2.5 | R3 | yes | T-993, T-994, T-996 | `apps/backend/tests/test_mcp_isolation.py` |
| T-999 | Ship it: sidecar, Caddy, client setup, R7 sign-off | 2.5 | R3 | yes | T-996, T-997 | `apps/mcp/Dockerfile`, `apps/mcp/README.md`, `.dockerignore` (root, new), `docs/MCP.md` (new), `apps/backend/tests/test_mcp_deploy.py` |

Merge order is the id order; the file sets are disjoint except the shared registries, which each card
appends to with one line: `tools/gen_sdk.py`, `apps/backend/tests/test_sdk_cli.py`, `routers/__init__.py`,
`services/flags.py` (`task_992`, added by T-990 because it owns `devapi.py`'s `whoami`),
`apps/mcp/labeldesk_mcp/{server,__main__}.py`, `deploy/docker-compose.yml`, `deploy/Caddyfile`,
`openapi.json` + `api-types.gen.ts` (generated).

## 14. Definition of done

- [ ] `pip install ./packages/sdk` then `pip install ./apps/mcp`, then `labeldesk-mcp` answers `tools/list` over stdio, and one
      `tools/call` round-trips against a running API (in-memory and real transport tests).
- [ ] `POST /mcp` on the compose stack answers with a bearer key and 401 without one.
- [ ] 16 tools, 3 resources, 2 prompts; `tools/list` hides every tool the key's scopes do not allow.
- [ ] Every spend/overwrite tool refuses without `confirm: true` and reports the cost it would have incurred.
- [ ] Workspace A's key gets 404 for workspace B's project, image, job, version and model ids.
- [ ] One `mcp.tool` audit row per admitted call, with the tool name; no key, token or secret in any output.
- [ ] `ruff check apps/backend` clean, the full serial API suite green, `openapi.json` and `api-types.gen.ts`
      regenerated, `npm run build` green.
- [ ] R7 review signed off on `T-990`, `T-991`, `T-992`, `T-994`, `T-996`, `T-997`, `T-998`, `T-999`.
