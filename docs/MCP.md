# Connect an agent: LabelDesk MCP

LabelDesk's MCP server turns the labeling API into sixteen tools an AI agent can call: look at a
project, upload by URL, write labels, run auto-label, freeze a version, train, predict. Three
resources (`labeldesk://workspace`, `labeldesk://projects/{project}`,
`labeldesk://projects/{project}/classes`) and two prompts (`review_low_confidence_labels`,
`audit_unannotated_batch`) sit beside them, so an agent reads before it writes.

Every tool is one call to `/api/v1` under the workspace API key the caller presents. The server has no
database, no second permission model and no secret of its own: a tool cannot be more permissive than
the route behind it.

## Two switches, both independent

| Switch | What it decides | Where |
| --- | --- | --- |
| The compose profile | Whether this **deployment** runs the endpoint at all. Off, no container exists and `/mcp` is the SPA's 404. | `docker compose --profile mcp up -d` |
| `task_992` | Whether one **workspace** may use the endpoint. Off, every tool refuses before the API, and `/mcp` answers 404. | Settings → Features |

Turning one on never turns the other on. A deployment that runs the endpoint still refuses a
workspace where `task_992` is off, and a workspace that enables it still reaches nothing when the
profile was not started.

## Local agent (stdio)

Install once, then point the host at the command. Nothing but MCP frames reaches stdout; logs go to
stderr; the key is never logged.

```bash
pip install ./packages/sdk
pip install ./apps/mcp
```

```json
{
  "mcpServers": {
    "labeldesk": {
      "command": "labeldesk-mcp",
      "env": {
        "LABELDESK_API_KEY": "<workspace API key>",
        "LABELDESK_URL": "https://<your-labeldesk-host>"
      }
    }
  }
}
```

A missing key exits 2 with one line on stderr: `LABELDESK_API_KEY is not set`.

## Hosted runner (Streamable HTTP)

`docker compose --profile mcp up -d` starts the `mcp` service beside `api`, and the existing Caddy
serves it on the API's own origin — same TLS, same key:

```json
{
  "mcpServers": {
    "labeldesk": {
      "type": "http",
      "url": "https://<your-labeldesk-host>/mcp",
      "headers": { "Authorization": "Bearer <workspace API key>" }
    }
  }
}
```

`docker compose ps` shows one `mcp` line; its log carries the bind address and never a key. The
endpoint accepts the key as `Authorization: Bearer` or `x-api-key` on every POST, and reads no key
from the query string.

## Environment variables

| Variable | Transport | Meaning |
| --- | --- | --- |
| `LABELDESK_URL` | both | The LabelDesk origin the tools call. Defaults to the SDK's local URL. |
| `LABELDESK_API_KEY` | stdio | The workspace key; the HTTP transport takes each request's own key instead. |
| `LD_MCP_ALLOWED_HOSTS` | HTTP | Comma-separated `Host` allow-list. The compose service sets it to `LD_DOMAIN`. |
| `LD_MCP_ALLOWED_ORIGINS` | HTTP | Comma-separated `Origin` allow-list. The compose service sets it to `https://LD_DOMAIN`. |

Three settings cover a connection — the URL, the key, and the host allow-list (host plus origin).
With both allow-lists empty the SDK keeps its localhost-only default, which is the right answer for a
laptop.

## First call

`whoami` answers the workspace, its plan, the key's scopes and whether `task_992` is on:

```json
{ "workspace": "acme", "name": "Acme", "plan": "team",
  "scopes": ["read", "upload", "write", "train", "infer"],
  "mcp": true, "publishable": false }
```

`tools/list` is filtered by those scopes: a `read`-only key never sees `start_training`, and a key
without `write` never sees `write_annotations`. The filter is a courtesy — the API still answers 403
when a tool exceeds its scope.

An agent that needs class ids reads `labeldesk://projects/<slug>/classes` first; `write_annotations`
takes exactly those ids.

**Empty and loading.** An empty workspace answers `[]` from `list_projects`, `whoami` still names it,
and the classes resource renders `No classes yet.` Nothing in the protocol has a loading state: a tool
call answers or errors, and the jobs that take time report progress through `get_job`.

## What a client can meet

| Answer | The sentence it prints | What to do |
| --- | --- | --- |
| `401` | `authentication required`, with `WWW-Authenticate: Bearer` | Send the workspace key on the POST. A key the API rejects is also 401, never a 500. |
| `403` | `a publishable key cannot drive an agent` | Use a normal workspace key. A browser-embedded publishable key is `infer`-only and never drives an agent loop. |
| `404` | `Not Found` | The endpoint is off for this workspace (`task_992`), or the deployment never started the profile. Check Settings → Features first, then `docker compose ps`. |
| `413` | the server logs `request body over the 4 MiB cap` | A tool call is small. Image bytes travel by URL — `upload_image_url` hands the fetch to the API, never to this process. |
| `429` | `too many attempts — try again shortly`, with `Retry-After` | One IP resolves 600 keys per 60 s. Wait the number of seconds the header gives. |

Inside a tool result, the API's own message arrives as `isError: true` — for example a 402 naming the
plan when credits are spent, or a 404 for an id outside the key's workspace. The sentences above are
the transport's, before a tool runs.

## Limits

| Bound | Value |
| --- | --- |
| Tool results | Strings capped at 8 KiB; keys named `settings`, `hash`, `sha256`, `password`, `token`, `secret`, `api_key`, `credentials` are dropped |
| Images per page | `list_images` caps a page at 200 (the route's own maximum is 1000) |
| Annotations per image | 5000 (the route's cap) |
| Request body | 4 MiB, then 413 before parsing |
| Key resolution | 600 per 60 s per client IP, then 429 |
| Credits | train 3, version 0.5, auto-label 0.01 per image, inference 0.001; 402 at the plan ceiling |
| Image upload by URL | 20 MB, 10 s, public addresses only, through the API's safefetch |
| Jobs | No tool waits. Training, version generation and auto-label return a job id; poll `get_job`. |

## Workspace isolation

Every id resolves inside the workspace of the key that presented it. A project, image, version, job
or model from another workspace answers **404** — not 403, because a 403 would confirm the id exists.
Nothing is read and nothing changes. No tool takes a workspace argument: the key is the only identity,
so there is no second path to get wrong. `apps/backend/tests/test_mcp_isolation.py` (T-998)
parametrises the cross-workspace cases.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `/mcp` answers the SPA's 404 | The `mcp` profile was not started, or Caddy was not reloaded | `docker compose --profile mcp up -d`, then `docker compose ps` |
| `401` with a key that works in `/api/v1` | The header is missing on the POST, or the key was revoked | Send `Authorization: Bearer <key>` on every request |
| `403` for a publishable key | Publishable keys are `infer`-only and refused here | Use a workspace key from Settings → API keys |
| `404` although the container runs | `task_992` is off for this workspace | Settings → Features → MCP |
| `421` or `403` before any tool | `Origin` or `Host` is not in the allow-list | Set `LD_MCP_ALLOWED_HOSTS` and `LD_MCP_ALLOWED_ORIGINS` to the public origin |
| A tool returns a dry run | The call omitted `confirm: true` | Read the estimate, then confirm deliberately |

## R7 security sign-off

The endpoint is the deployment change that exposes the tools; this is what a reviewer needs in one
place. Every route is the existing key-authenticated developer surface.

| Tool | Scope | Route | Proved by |
| --- | --- | --- | --- |
| `whoami` | read | `GET /api/v1/whoami` | `test_mcp_server.py::test_whoami_names_the_workspace_this_key_belongs_to` |
| `list_projects` | read | `GET /api/v1/projects` | `test_mcp_server.py::test_list_projects_round_trips_through_the_api` |
| `get_project` | read | `GET /api/v1/projects/{project}` | `test_mcp_read_tools.py::test_get_project_returns_classes_with_ids_and_counts` |
| `list_images` | read | `GET /api/v1/projects/{project}/images` | `test_mcp_read_tools.py::test_list_images_passes_every_filter_and_caps_the_page` |
| `get_image` | read | `GET /api/v1/images/{image_id}` | `test_mcp_read_tools.py::test_get_image_returns_annotations_with_class_ids` |
| `list_versions` | read | `GET /api/v1/projects/{project}/versions` | `test_mcp_read_tools.py::test_list_versions_and_models_answer_on_the_live_api` |
| `get_job` | read | `GET /api/v1/jobs/{job_id}` | `test_mcp_read_tools.py::test_a_foreign_model_id_is_a_404_tool_error` |
| `list_models` | read | `GET /api/v1/models` | `test_mcp_read_tools.py::test_list_versions_and_models_answer_on_the_live_api` |
| `get_model` | read | `GET /api/v1/models/{model_id}` | `test_mcp_read_tools.py::test_a_foreign_model_id_is_a_404_tool_error` |
| `list_deployments` | read | `GET /api/v1/deployments` | `test_mcp_read_tools.py::test_list_deployments_returns_aliases` |
| `upload_image_url` | upload | `POST /api/v1/{ws_slug}/{project}/upload` | `test_mcp_write_tools.py::test_upload_image_url_sends_the_url_not_the_bytes` |
| `write_annotations` | write | `PUT /api/v1/images/{image_id}/annotations` | `test_mcp_write_tools.py::test_write_annotations_with_confirm_replaces_the_set` |
| `run_auto_label` | write | `POST /api/v1/projects/{project}/autolabel` | `test_mcp_write_tools.py::test_run_auto_label_dry_run_estimates_the_bill` |
| `create_version` | write | `POST /api/v1/projects/{project}/versions` | `test_mcp_write_tools.py::test_create_version_dry_run_then_the_real_charge_and_the_402` |
| `start_training` | train | `POST /api/v1/projects/{project}/train` | `test_mcp_write_tools.py::test_no_spend_tool_acts_without_confirm` |
| `predict_image` | infer | `POST /api/v1/models/{model_id}/predict` | `test_mcp_write_tools.py::test_predict_image_refuses_two_sources` |

**The confirm rule.** Five tools can spend credits or overwrite labels: `write_annotations`,
`run_auto_label`, `create_version`, `start_training`, `predict_image`. Each one takes
`confirm: bool = false`; without it the call returns `{dryRun: true, ...what would change,
estimatedCredits, next: "call again with confirm: true"}` and reaches no write route. The gate is
strict: the JSON boolean `true` opens it, and the string `"true"` is refused as a host bug.
`upload_image_url` also takes `confirm` but is additive and deduped on the image hash.
Proved by `test_mcp_write_tools.py::test_no_spend_tool_acts_without_confirm` and
`test_mcp_write_tools.py::test_write_annotations_dry_run_counts_the_replacement`.

**The audit row.** Every admitted call carries `x-mcp-tool`; `resolve_key` writes one `mcp.tool` audit
row naming the tool (capped at 64 characters) and the method, scoped to the key's workspace, with no
key, token or secret in the row or the log. A call refused before the API leaves nothing to audit
because nothing happened. Proved by `test_mcp_audit.py::test_an_mcp_call_writes_one_mcp_tool_row`,
`test_mcp_audit.py::test_the_row_is_scoped_to_the_keys_workspace` and
`test_mcp_audit.py::test_no_log_line_carries_the_key`.

**The four non-goals, and the test that proves each.**

1. Nothing destructive: no image, project or version is removed — `test_mcp_write_tools.py::test_no_tool_can_delete_anything`.
2. No deployment-alias switching and no rollback: aliases are read, never moved — `test_mcp_read_tools.py::test_the_tool_list_is_the_documented_sixteen`.
3. No key, member or billing management — `test_mcp_read_tools.py::test_the_tool_list_is_the_documented_sixteen`.
4. No cross-workspace reach: a foreign id is the API's 404 — `test_mcp_read_tools.py::test_a_foreign_model_id_is_a_404_tool_error`.

The tool list itself is pinned to exactly these sixteen by
`test_mcp_read_tools.py::test_the_tool_list_is_the_documented_sixteen`, so no later card can add a
seventeenth tool quietly.

**Secrets.** The image, the compose file and the Caddyfile hold no secret: keys arrive per request.
The tool scrubber drops project `settings` (where webhook and connector values live) before a result
reaches the transcript — proved by `test_mcp_server.py::test_project_settings_and_secrets_are_scrubbed`.
A publishable key is refused at the transport before any tool runs —
`test_mcp_http_transport.py::test_a_publishable_key_is_refused` — and a foreign `Origin` is refused by
the SDK's DNS-rebinding guard — `test_mcp_http_transport.py::test_an_unknown_origin_is_403`.
