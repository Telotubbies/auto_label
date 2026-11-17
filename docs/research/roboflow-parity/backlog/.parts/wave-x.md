# Part X — Wave X MCP server for AI agents

Gap rows: 0 (0 PARTIAL, 0 MISSING) · Cards: 10 · Hours: 27.5

## Mapping
| Parity id | Status | Task ids | Wave | Size | Hours |
| --- | --- | --- | --- | --- | --- |
| — (owner request 2026-11-17: "make an MCP server so AI agents can connect to LabelDesk and use it") | — | T-990, T-991, T-992, T-993, T-994, T-995, T-996, T-997, T-998, T-999 | X | — | 27.5 |

No PARITY.md row and no BEYOND.md feature is closed by this wave; it is a new delivery surface over the 334
rows and the 101 BEYOND features that the other waves already plan. The design note is
[`../../mcp/MCP-PLAN.md`](../../mcp/MCP-PLAN.md).

## Shared-file users (suggested merge order)
| Shared file | Task ids, in merge order |
| --- | --- |
| `tools/gen_sdk.py` | T-990, T-991 |
| `apps/backend/tests/test_sdk_cli.py` | T-990, T-991 |
| `packages/sdk/labeldesk/_generated.py` | T-990, T-991 |
| `apps/backend/openapi.json` | T-990, T-991 |
| `apps/frontend/src/lib/api-types.gen.ts` | T-990, T-991 |
| `packages/sdk/README.md` | T-990 |
| `apps/backend/app/services/flags.py` | T-990 |
| `apps/backend/app/routers/__init__.py` | T-991 |
| `apps/backend/requirements.txt` | T-992 |
| `apps/mcp/labeldesk_mcp/server.py` | T-993, T-994, T-995 |
| `apps/mcp/labeldesk_mcp/__main__.py` | T-996 |
| `deploy/docker-compose.yml` | T-999 |
| `deploy/Caddyfile` | T-999 |

## Cards
| Task | Title | Wave | Hours | Role | R7 | Exclusive files |
| --- | --- | --- | --- | --- | --- | --- |
| T-990 | Key surface: read a project, search images, read and write labels | X | 3 | R3 | yes | `apps/backend/app/routers/devapi.py`, `apps/backend/app/models/common.py`, `apps/backend/tests/test_devapi_labels.py` |
| T-991 | Key surface: auto-label, create a version, list deployments, infer by image | X | 3 | R3 | yes | `apps/backend/app/routers/devapi_actions.py`, `apps/backend/app/routers/training.py`, `apps/backend/app/routers/versions.py`, `apps/backend/tests/test_devapi_actions.py` |
| T-992 | MCP app: skeleton, per-request key, scope-filtered tool list | X | 3 | R3 | yes | `apps/mcp/pyproject.toml`, `apps/mcp/labeldesk_mcp/{__init__,api,server,__main__}.py`, `packages/sdk/labeldesk/client.py`, `apps/backend/tests/test_mcp_server.py` |
| T-993 | The eight read tools, with paging caps | X | 3 | R3 | no | `apps/mcp/labeldesk_mcp/tools_read.py`, `apps/backend/tests/test_mcp_read_tools.py` |
| T-994 | Six write and spend tools behind one confirm gate | X | 3 | R3 | yes | `apps/mcp/labeldesk_mcp/tools_write.py`, `apps/backend/tests/test_mcp_write_tools.py` |
| T-995 | Resources and prompts: read before you write | X | 2 | R3 | no | `apps/mcp/labeldesk_mcp/meta.py`, `apps/backend/tests/test_mcp_resources.py` |
| T-996 | Streamable HTTP transport, per-request key, origin guard | X | 3 | R3 | yes | `apps/mcp/labeldesk_mcp/http.py`, `apps/backend/tests/test_mcp_http_transport.py` |
| T-997 | Audit every tool call, prove the limits | X | 2.5 | R3 | yes | `apps/backend/app/apikeys.py`, `apps/backend/tests/test_mcp_audit.py` |
| T-998 | Isolation and adversarial suite for the whole server | X | 2.5 | R3 | yes | `apps/backend/tests/test_mcp_isolation.py` |
| T-999 | Ship it: sidecar, Caddy route, client setup, R7 sign-off | X | 2.5 | R3 | yes | `apps/mcp/Dockerfile`, `.dockerignore`, `apps/mcp/README.md`, `docs/MCP.md`, `apps/backend/tests/test_mcp_deploy.py` |

## Judgment calls
- **No matrix row.** Wave X exists because the owner asked for it on 2026-11-17, not because a PARITY or
  BEYOND row is open. Its Mapping row is therefore `—`, and the wave closes nothing that waves A–F already
  own; it exposes what they build.
- **Placed right after E-frame.** The PM asked for it there. It is safe there because the server touches
  only `/api/v1` and the two cards that add routes are backend-only: X shares no file with G2, G3, A, B, C,
  D, E or F, and E-frame's `/p/` route move does not change a single URL a tool calls.
- **A sidecar, not an in-process mount.** The API image builds from `apps/backend` and copies only `app/`, so
  mounting the server inside it would mean moving the build context to the repo root, adding `mcp` +
  `httpx2` to a 1.9 GB image, and putting a protocol bug inside the process that holds the database. The
  endpoint still lives on the API's origin (`route /mcp*` in the existing Caddy) and still takes the same
  bearer key. Priced alternatives: `MCP-PLAN.md` §10, option 2.
- **A new `write` scope, not a reused one.** Annotations, versions and auto-label write project data.
  Reusing `upload` would let an image-upload key rewrite human labels; reusing `train` would hand GPU spend
  to a label-writing bot. One new value in `API_SCOPES`, and a key opts in.
- **Key-issued label writes are attributed to the key's issuer.** `label_events.user_id` is NOT NULL
  (`app/models/insights.py:123`), and the house convention for "no user" (`Audit.user_id = NULL`) is not
  available here without a Postgres `ALTER COLUMN`. Attribution to `api_keys.created_by`, falling back to
  the workspace owner, keeps the throughput and AI-acceptance dashboards correct and needs no migration.
- **Three read checks folded into one tool.** `list_images` covers "datasets and images, paged" and "search
  images" from the owner's list: one tool with the Dataset screen's filters beats two tools with a shared
  schema. `get_project` is not a new route either — it is `project_out(detail=True)` minus `settings`.
- **`predict_image` asks for `confirm` even though it costs 0.001 credits.** The owner's rule is "spend
  credits ⇒ confirm", and a per-tool exception is how the rule rots. The dry run states the cost, which is
  the whole point.
- **`upload_image_url` does not ask for `confirm`.** Additive, deduped on the image hash, and the fetch runs
  through `services/safefetch.py`; the worst case is one duplicate row.
- **No OAuth.** LabelDesk has no authorization server, consent screen or client registry, so publishing RFC
  9728 metadata would be a lie. Bearer API key is the documented deviation, and it is what Stripe,
  Cloudflare and Linear ship. `MCP-PLAN.md` §8.
