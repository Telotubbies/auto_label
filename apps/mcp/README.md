# LabelDesk MCP server

The agent-facing seam over LabelDesk's own API. Sixteen tools, three resources and two prompts, all
served under the caller's workspace API key, so permissions, metering and audit stay in exactly one
place. The server holds no database handle and no key of its own.

## Install and run

The SDK is not on PyPI, so it installs first:

```bash
pip install ./packages/sdk
pip install ./apps/mcp
```

**stdio** — a local agent host runs the command. Nothing but MCP frames reaches stdout, logs go to
stderr, and the key is never logged. A missing key exits 2 with one line on stderr.

```bash
LABELDESK_API_KEY="<workspace API key>" \
LABELDESK_URL="https://labeldesk.example.com" \
labeldesk-mcp
```

**Streamable HTTP** — one stateless endpoint on `/mcp`, one key per POST:

```bash
labeldesk-mcp --http --host 0.0.0.0 --port 8020
```

`LD_MCP_ALLOWED_HOSTS` and `LD_MCP_ALLOWED_ORIGINS` are its host and origin allow-lists. The compose
profile `mcp` runs this beside the API, and Caddy routes `/mcp` on the API's own origin. Agent and
operator setup, the status codes and the security sign-off are in [`docs/MCP.md`](../../docs/MCP.md).

## Tools

| Tool | Scope | Confirm | What it does |
| --- | --- | --- | --- |
| `whoami` | read | — | The workspace, plan, credits and this key's scopes |
| `list_projects` | read | — | Every project with its image count and classes |
| `get_project` | read | — | One project by slug: classes with ids and counts, status counts |
| `list_images` | read | — | One page of images with filters and `total`; a page is capped at 200 |
| `get_image` | read | — | One image plus its annotations: class id, shape, source, confidence |
| `list_versions` | read | — | A project's frozen versions |
| `get_job` | read | — | One job's status, progress, error and result |
| `list_models` | read | — | Every trained model with lean metrics |
| `get_model` | read | — | One model: variant, status, metrics, source version |
| `list_deployments` | read | — | Deployment aliases and the ready models each can point at |
| `upload_image_url` | upload | no | Add one image by public URL; the API fetches it, deduped on content hash |
| `write_annotations` | write | yes | Replace one image's whole annotation set |
| `run_auto_label` | write | yes | Queue auto-label over the images you choose; returns a job id |
| `create_version` | write | yes | Freeze the current data into a numbered version |
| `start_training` | train | yes | Queue a training run on a frozen version; returns a job id |
| `predict_image` | infer | yes | Run one ready model over one image id or public URL |

A tool with `confirm` answers a dry run first — what it would change and what it would cost — and acts
only when the call passes `confirm: true` as a JSON boolean (the string `"true"` is refused). No tool waits on a job: training, version generation and
auto-label return a job id, and `get_job` is how an agent follows it.

## What the server will not do

1. **Remove anything.** No image, project or version is deleted from here.
2. **Move a deployment.** Aliases and rollback are read-only; a model pointer is never switched.
3. **Manage keys, members or billing.** No key creation, no invitation, no charge beyond the API's own
   metering of a tool that already says what it costs.
4. **Reach another workspace.** Every id resolves inside the key's own workspace; a foreign id is the
   API's 404, never a second permission path.
