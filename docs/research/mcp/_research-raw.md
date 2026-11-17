# MCP research — raw primary-source findings

Collected 2026-11-17. Every claim is followed by the primary URL it came from.
Two protocol eras exist and the difference matters for every design decision below:

- **Modern**: revision `2026-07-28` — stateless, per-request `_meta`, no `initialize`, no `Mcp-Session-Id`. This is what `https://modelcontextprotocol.io/specification/latest` serves.
- **Legacy**: `2025-11-25` and earlier — `initialize` handshake, optional `MCP-Session-Id`, GET SSE stream, `Last-Event-ID` resumability bootstrap.

Most deployed clients/servers in the wild still speak legacy; the SDKs are "dual-era".

---

## 1. Model Context Protocol specification

### 1.0 Which revision is newest

- The "latest" entry point serves revision **2026-07-28**: its own links point at `https://modelcontextprotocol.io/specification/2026-07-28/...` and it cites `schema/2026-07-28/schema.ts` (https://modelcontextprotocol.io/specification/latest).
- Revision identifiers are dates; the changelog states the previous revision is `2025-11-25` (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md). The site also publishes `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05` and a `draft` (https://modelcontextprotocol.io/llms.txt).
- Revision `2026-07-28` is a large breaking change, described by its own changelog as: removing protocol-level sessions and `Mcp-Session-Id`, making MCP stateless (no `initialize`/`notifications/initialized`), adding `server/discover`, replacing the HTTP GET stream and `resources/subscribe`/`unsubscribe` with `subscriptions/listen`, removing `ping`/`logging/setLevel`, moving tasks to an extension, adding Multi Round-Trip Requests (MRTR), requiring `resultType` on all results, and removing SSE resumability/redelivery (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).

### 1.a Base protocol and lifecycle / version negotiation

Modern (`2026-07-28`):

- JSON-RPC 2.0; base-protocol characteristics listed as "Stateless, self-contained requests" and "Per-request capability negotiation" (https://modelcontextprotocol.io/specification/latest).
- "There is no negotiation handshake. Every request carries its protocol version, and the server accepts or rejects each request independently" (https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md).
- Version, client identity and client capabilities travel in `_meta`: `io.modelcontextprotocol/protocolVersion`, `io.modelcontextprotocol/clientCapabilities`, and SHOULD `io.modelcontextprotocol/clientInfo`; servers SHOULD report `io.modelcontextprotocol/serverInfo` in each result's `_meta` (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- Unsupported version → `UnsupportedProtocolVersionError`, code `-32022`, with `data.supported` listing accepted versions; client SHOULD retry with a mutually supported version (https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md).
- Servers **MUST** implement `server/discover`; it returns `supportedVersions`, `capabilities`, `_meta['io.modelcontextprotocol/serverInfo']`, optional `instructions`, plus `ttlMs`/`cacheScope` (https://modelcontextprotocol.io/specification/2026-07-28/server/discover.md).
- Era detection: stdio probes with `server/discover` and falls back to `initialize` on any unrecognized error/timeout; Streamable HTTP attempts a modern request and inspects the body of a `400` before falling back (https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md).
- Compatibility matrix is spelled out for modern/dual-era/legacy client × server combinations, including "Legacy client + Modern server: fails" (https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md).

Legacy (`2025-11-25`):

- `initialize` request, client sends a protocol version it supports; if the server supports it, it MUST respond with the same version, else MUST respond with another version it supports (latest it supports); if the client does not support that, it SHOULD disconnect (https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle.md).
- Capability negotiation happens in `initialize` (`roots`, `sampling`, `elicitation`, `tasks`, `experimental` for clients; `prompts`, `resources`, `tools`, etc. for servers) (https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle.md).
- On HTTP the client MUST send `MCP-Protocol-Version: <version>` on all subsequent requests (https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle.md).

### 1.b Tools

Methods, schemas and result shape (`2026-07-28`):

- Servers supporting tools MUST declare the `tools` capability, with optional `listChanged` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- `tools/list` supports pagination and caching; the result carries `tools`, `nextCursor`, and `ttlMs`/`cacheScope` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- `tools/call` params: `name`, `arguments`; result: `content` array, optional `structuredContent`, `isError` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Tool fields: `name`, `title`, `description`, `icons`, `inputSchema`, `outputSchema`, `annotations` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- `inputSchema`: JSON Schema, defaults to 2020-12 when no `$schema`; MUST be a valid schema object (not `null`); for no-parameter tools prefer `{"type":"object","additionalProperties":false}` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md). The revision loosened both schemas to allow any JSON Schema 2020-12 keywords, and `structuredContent` to allow **any JSON value** (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- `outputSchema`: optional; if present, servers MUST return structured results conforming to it and clients SHOULD validate (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- `structuredContent`: "server-produced result data and is unrelated to LLM 'structured outputs'"; for backwards compatibility a tool returning structured content SHOULD also serialize the JSON into a `TextContent` block (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- `isError: true` marks **tool execution errors** (API failures, input validation, business logic) which clients SHOULD feed back to the model; **protocol errors** (unknown tool, malformed request) are JSON-RPC errors, e.g. `-32602 "Unknown tool"` (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Tool names SHOULD be 1–128 chars, case-sensitive, limited to `A-Za-z0-9_.-`, unique within a server; uniqueness is per-server only, so aggregators SHOULD prefix by server (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Servers SHOULD return a deterministic tool order to enable caching and prompt-cache hits (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Listing MUST NOT vary per-connection, but **MAY vary by the authorization presented on the request** — "since credentials are per-request input, not connection state" (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).

Annotations (`readOnlyHint` etc.) — the prose page only says "Optional properties describing tool behavior"; the authoritative definitions are in the schema:

- `ToolAnnotations { title?, readOnlyHint?, destructiveHint?, idempotentHint?, openWorldHint? }`; all are **hints**, "Clients should never make tool use decisions based on ToolAnnotations received from untrusted servers" (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- `readOnlyHint` — "If true, the tool does not modify its environment. Default: false" (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- `destructiveHint` — "If true, the tool may perform destructive updates… If false, the tool performs only additive updates. (meaningful only when `readOnlyHint == false`) Default: true" (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- `idempotentHint` — "If true, calling the tool repeatedly with the same arguments will have no additional effect… Default: false" (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- `openWorldHint` — "If true, this tool may interact with an 'open world' of external entities… Default: true" (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- Clients MUST treat annotations as untrusted unless they come from trusted servers (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).

Also in `2026-07-28`:

- `x-mcp-header` in a property schema mirrors that argument into an HTTP header `Mcp-Param-{name}`; only `string`/`integer`/`boolean`, statically reachable via `properties` keys only; clients MUST reject invalid annotations by dropping the tool (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- A tool call MAY return `InputRequiredResult` (`resultType: "input_required"`, `inputRequests`, `requestState`) and the client retries with `inputResponses`; "the JSON-RPC `id` MUST be different between the initial request and the retry" (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Non-normative "Stateful Tools" section: the protocol has no state handle; servers should mint an explicit handle, accept it as an argument, treat it as a name not a capability, validate authorization against it on every call, keep it opaque, state its lifetime, and return a tool execution error when it is expired (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).

### 1.c Resources

- Servers MUST declare `resources`; capability flags `listChanged` and `subscribe` (subscriptions are now delivered through `subscriptions/listen` with a `resourceSubscriptions` filter) (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- `resources/list` (pagination + caching, result has `resources`, `nextCursor`, `ttlMs`, `cacheScope`) (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- `resources/read` takes `uri`, returns `contents` (multiple allowed); text or base64 `blob`; supports caching (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- `resources/templates/list` returns `resourceTemplates` with RFC 6570 `uriTemplate`; may be completed through the completion API (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- Resource not found is now `-32602` (was `-32002`; clients SHOULD still accept `-32002`); servers MUST NOT return an empty `contents` array for a nonexistent resource (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- Subscriptions: client sends `subscriptions/listen` with `notifications.resourceSubscriptions`; server emits `notifications/resources/updated` tagged with `_meta["io.modelcontextprotocol/subscriptionId"]` (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md). `resources/subscribe`/`resources/unsubscribe` were removed in this revision (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- Annotations on resources/content: `audience` (`user`/`assistant`), `priority` 0.0–1.0, `lastModified` ISO 8601 (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).
- Security: servers MUST validate URIs, MUST sanitize `file://` paths against traversal (https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md).

### 1.d Prompts

- Servers MUST declare `prompts`; `prompts/list` (pagination + caching) returns `prompts` with `name`, `title`, `description`, `icons`, `arguments[{name, description, required}]` (https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).
- `prompts/get` takes `name` + `arguments` and returns `description` + `messages[{role, content}]`; content types text / image / audio / resource_link / embedded resource (https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).
- Errors: invalid name `-32602`, missing required args `-32602`, internal `-32603` (https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).
- Prompts are "user-controlled" (surfaced for explicit user selection, e.g. slash commands) (https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).
- `prompts/get` may also answer with `InputRequiredResult` and be retried with `inputResponses` (https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).

### 1.e Transports

stdio (`2026-07-28`):

- Client launches the server as a subprocess; newline-delimited JSON-RPC on stdin/stdout, no embedded newlines; server MAY log UTF-8 to `stderr`; server MUST NOT write non-MCP data to stdout (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md).
- No header layer: all metadata is inline in `_meta` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md).
- Server MUST NOT write JSON-RPC *requests* to stdout; server→client interactions are `InputRequiredResult` replies (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md).
- Cancellation is `notifications/cancelled`; shutdown by closing the child's stdin and waiting (SIGTERM→SIGKILL on POSIX, TerminateProcess/Job Objects on Windows) (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio.md).

Streamable HTTP (`2026-07-28`) — current shape:

- One endpoint that supports **POST** (e.g. `https://example.com/mcp`); the GET stream endpoint is removed (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Every JSON-RPC message is its own POST; client MUST include `Accept` with **both** `application/json` and `text/event-stream`; client MUST NOT POST JSON-RPC responses (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Notification POST → `202 Accepted` with no body; request POST → either `application/json` or `text/event-stream` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- SSE responses carry only request-related notifications then the final response; servers MUST NOT send independent JSON-RPC requests on the stream (that is now MRTR/`InputRequiredResult`) (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Closing the SSE stream **is** the cancellation signal on HTTP; `notifications/cancelled` is stdio-only (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Servers SHOULD send `X-Accel-Buffering: no` when opening an SSE stream, and are encouraged to emit `:` comment lines as keep-alive on long-lived streams (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- **Resumability is gone**: "Resumable SSE streams via `Last-Event-ID` are not supported"; a broken stream loses the in-flight request and clients MUST re-issue it as a new request with a new request ID (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md, https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- Required headers per POST: `MCP-Protocol-Version` (must match `_meta` version, else `400` + `HeaderMismatch` `-32020`), `Mcp-Method` (all requests), `Mcp-Name` (for `tools/call`, `resources/read`, `prompts/get`); unsafe values are Base64-wrapped as `=?base64?...?=` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Unknown method → `404` + JSON-RPC `-32601`; unsupported version → `400` + `UnsupportedProtocolVersionError` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Backwards-compat handling for a modern-only server: GET/DELETE → `405`; ignore `Mcp-Session-Id`; ignore `Last-Event-ID` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).

Streamable HTTP (`2025-11-25`) — the shape most existing deployments still use:

- Endpoint MUST support both POST and GET (https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md).
- Client MUST send `Accept` listing both `application/json` and `text/event-stream` (https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md).
- Sessions: server MAY assign a session at initialization by returning `MCP-Session-Id` on the response carrying `InitializeResult`; the ID SHOULD be globally unique and cryptographically secure and MUST be visible ASCII (0x21–0x7E); clients MUST echo it on all subsequent requests; servers requiring it SHOULD return `400` when it is missing; the server MAY terminate a session and then MUST answer `404`, on which the client MUST start a new session; clients SHOULD `DELETE` with the header to end a session, and the server MAY answer `405` (https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md).
- Resumability: servers MAY attach SSE event `id`s (globally unique per session, or per client when sessionless), clients resume with HTTP GET + `Last-Event-ID`, and the server MAY close a connection while keeping the stream alive, sending a `retry` field the client MUST respect (https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md).
- Note on casing: the 2025-11-25 transport text writes `MCP-Session-Id`, the 2026-07-28 changelog writes `Mcp-Session-Id`; HTTP field names are case-insensitive (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).

Security requirements for the HTTP transport (identical wording in both revisions):

- Servers MUST validate the `Origin` header on all incoming connections to prevent DNS rebinding; if `Origin` is present and invalid, MUST respond `403 Forbidden` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md, https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md).
- When running locally, servers SHOULD bind only to `127.0.0.1`, not `0.0.0.0` (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Servers SHOULD implement proper authentication for all connections (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).

### 1.f Authorization (HTTP transports)

- Authorization is OPTIONAL; HTTP transports SHOULD conform; **stdio SHOULD NOT follow this spec and instead retrieve credentials from the environment** (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Built on: OAuth 2.1 draft-13, RFC 6750 (bearer), RFC 8414 (AS metadata), RFC 7591 (DCR — now deprecated), RFC 8707 (resource indicators), RFC 9728 (protected resource metadata), RFC 9207 (`iss`), Client ID Metadata Documents, OIDC discovery/registration (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Roles: MCP server = OAuth 2.1 **resource server**; MCP client = OAuth 2.1 client; authorization server is separate (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Servers **MUST** implement RFC 9728 Protected Resource Metadata and clients **MUST** use it for AS discovery; ASes MUST provide RFC 8414 or OIDC discovery and clients MUST support both (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- `WWW-Authenticate` on `401` carries `resource_metadata="…/.well-known/oauth-protected-resource"` and SHOULD carry `scope="…"`; clients treat challenged scopes as authoritative (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Insufficient scope → `403` with `WWW-Authenticate: Bearer error="insufficient_scope", scope="…", resource_metadata="…"`, then step-up authorization (re-authorize with the union of previously requested scopes) (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Resource indicators (RFC 8707): the `resource` parameter MUST be sent in both authorization and token requests, identifying the MCP server's canonical URI; clients MUST send it whether or not the AS supports it; canonical URI examples include `https://mcp.example.com/mcp` (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Bearer tokens: `Authorization: Bearer <token>` MUST be on **every** HTTP request; tokens MUST NOT go in the query string; servers MUST validate audience and MUST only accept tokens issued for them; invalid/expired → `401` (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Token passthrough is explicitly forbidden: "MCP servers MUST NOT accept or transit any other tokens" (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Client registration: Client ID Metadata Documents are the SHOULD; DCR (RFC 7591) is **deprecated** in `2026-07-28` and retained only for older ASes (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- `iss` handling: ASes SHOULD include `iss` (RFC 9207); clients MUST validate a present `iss` against the recorded issuer before redeeming the code, with a 4-row action matrix and no scheme/host case folding or trailing-slash normalization (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).

### 1.g Security best practices page (the three items asked about)

- **Confused deputy**: an MCP proxy server that uses a static client ID with a third-party AS, allows dynamic client registration, and the third party sets a consent cookie, lets an attacker obtain an authorization code without consent. Mitigations: per-client consent registry keyed by `client_id` checked before the third-party flow; consent UI naming the client, scopes and redirect URI; CSRF protection; `frame-ancestors`/`X-Frame-Options`; exact-match `redirect_uri` validation; single-use `state` stored only after consent approval (https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).
- **Token passthrough**: accepting tokens not issued to the MCP server and forwarding them downstream — audience-validation failure plus trust-boundary breakage; "MCP servers MUST NOT accept any tokens that were not explicitly issued for the MCP server" (https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).
- **Session hijacking → "State Handle Hijacking"** in the modern revision, because "MCP is stateless and has no protocol-level sessions": servers mint explicit handles; servers MUST NOT treat possession of a handle as authentication, SHOULD use non-deterministic handles, SHOULD bind them server-side as `<user_id>:<handle>` where the user ID comes from the verified token (https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).
- The legacy session-hijacking attack (prompt injection via a guessed session ID, and impersonation) is documented on the 2025-11-25 page and is explicitly cross-referenced for servers still using server-assigned session IDs (https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices.md).
- Other vectors on the same page: SSRF during OAuth metadata discovery (block private ranges, enforce HTTPS, validate redirects, use an egress proxy), local MCP server compromise (consent before running commands, sandboxing), OAuth authorization URL validation (`javascript:`/shell injection), stdio proxy privilege escalation, mix-up attacks, localhost redirect URI impersonation, scope minimization (https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).

---

## 2. Official MCP Python SDK (`modelcontextprotocol/python-sdk`)

### 2.1 Package, version, floor, dependencies

- Package name `mcp`, current release **2.3.0**, released **Oct 2, 2026**; `Requires: Python >=3.10`; extras `cli`, `rich` (https://pypi.org/project/mcp/).
- Runtime dependencies of 2.3.0: `anyio`, `httpx2>=2.10.0`, `jsonschema`, `mcp-types==2.3.0`, `opentelemetry-api`, `pydantic>=2.12.0`, `pyjwt[crypto]`, `python-multipart`, `pywin32` (Windows only), `sse-starlette`, `starlette`, `typing-extensions`, `typing-inspection`, `uvicorn` (https://pypi.org/pypi/mcp/json).
- Extras: `mcp[cli]` adds the `mcp` command (`mcp dev`, `mcp run`, `mcp install`); plain `mcp` has no CLI (https://pypi.org/project/mcp/).
- **Breaking v2 change**: `httpx` + `httpx-sse` were replaced by `httpx2` (https://py.sdk.modelcontextprotocol.io/migration/index.md).
- v1.x is still maintained for critical fixes and is documented at `/v1/`; projects on `mcp` v1 should pin `<2` (https://py.sdk.modelcontextprotocol.io/migration/index.md).

### 2.2 v2 server API — the names the task assumed are v1 names

- v2 entry point is `from mcp.server import MCPServer`; `FastMCP` was **renamed** to `MCPServer` and `mcp.server.fastmcp` no longer exists ("`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`") (https://py.sdk.modelcontextprotocol.io/migration/index.md, https://pypi.org/project/mcp/).
- Decorators are unchanged in shape: `@mcp.tool()`, `@mcp.resource("greeting://{name}")`, `@mcp.prompt()`; type hints + docstring are the schema (https://pypi.org/project/mcp/).
- `mcp.run()` with no argument = `stdio`; `mcp.run(transport="streamable-http", port=3001)` serves via uvicorn; `sse` still exists but is superseded (https://py.sdk.modelcontextprotocol.io/run/index.md).
- Transport options are arguments to `run()`, **not** the constructor: `host` (default `127.0.0.1`), `port` (default `8000`), `streamable_http_path` (default `/mcp`), `json_response`, `stateless_http`, `max_request_body_size` (default 4 MiB, larger → `413` before parsing), `session_idle_timeout` (default 1800, legacy only), `max_sessions` (default 10000, legacy only), `event_store`, `retry_interval`, `transport_security` (https://py.sdk.modelcontextprotocol.io/run/index.md).
- Constructor args are `log_level` (default `INFO`) and `debug`, both landing on `mcp.settings` (https://py.sdk.modelcontextprotocol.io/run/index.md).
- `json_response=True` answers each POST with one JSON body; that path has no back-channel, so `ctx.elicit()`/sampling raise `NoBackChannelError` and in-flight progress/per-call logs are dropped (https://py.sdk.modelcontextprotocol.io/run/index.md).

### 2.3 `streamable_http_app()` and ASGI mounting — supported, with two gotchas

- `mcp.streamable_http_app()` returns a **Starlette** application (hence any ASGI host: uvicorn, Hypercorn, Starlette, FastAPI) with one route `/mcp` plus a lifespan that starts `mcp.session_manager` (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Mounting in an existing Starlette/FastAPI app is explicitly documented via `Mount("/", app=mcp.streamable_http_app())`, and **the host app's lifespan must enter `mcp.session_manager.run()`** because "a mounted sub-application's lifespan never runs"; forgetting it fails the first request with `RuntimeError: Task group is not initialized. Make sure to use run().` (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- `mcp.session_manager` only exists after `streamable_http_app()` has been called, so build routes at module level and touch the manager inside the lifespan (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Path handling: `Mount("/notes", app=mcp.streamable_http_app())` → `/notes/mcp`; `streamable_http_path="/"` makes the mount prefix the whole public path (`/notes/`) (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Route order: `Mount("/")` matches everything, so your own routes go **before** it (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Multiple servers in one app: one mount per server, one lifespan entering every `session_manager.run()` (via `AsyncExitStack`) (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- `@mcp.custom_route("/health", methods=["GET"])` adds plain Starlette routes; they are **never authenticated**, even when the rest of the server is (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Browser clients need CORS: `allow_headers` must include the `Mcp-*` request headers, and `expose_headers=["Mcp-Session-Id"]` because browsers hide response headers otherwise (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- `streamable_http_app()` takes the same kwargs as `run("streamable-http", ...)` minus `port` (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).

### 2.4 Per-request auth / token access on HTTP

- The server is an OAuth 2.1 **resource server**: implement `TokenVerifier` (one async method `verify_token(token) -> AccessToken | None`) and pass it with `AuthSettings(issuer_url=..., resource_server_url=..., required_scopes=[...], validate_token_resource=...)`; passing one without the other raises `ValueError` (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- With `auth=`, the app publishes RFC 9728 metadata at `/.well-known/oauth-protected-resource/mcp` and answers unauthenticated requests with `401` + `WWW-Authenticate: Bearer error="invalid_token", resource_metadata="…"` (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- Per-request identity inside any tool/resource/prompt handler: `from mcp.server.auth.middleware.auth_context import get_access_token` → returns the `AccessToken` (`client_id`, `scopes`, `subject`, `expires_at`, extra `claims`) for the current request, from a context variable set by middleware; `None` over stdio and in-memory (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- `token_verifier` is never consulted on stdio, and the in-memory `Client(mcp)` skips the HTTP layer including auth (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- There is also an `auth_server_provider=` constructor arg that embeds a full authorization server; the docs say it predates the AS/RS split and new servers should not use it (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- **`get_http_request()` does not appear in either the v1 or v2 docs** — see "uncertain" list.

### 2.5 Client side

- v2: `from mcp import Client`; passing a URL string selects Streamable HTTP; `async with Client("http://localhost:8000/mcp") as client: await client.list_tools()` / `call_tool("add", {...})`; `client.session` is the underlying `ClientSession`, described as "the low-level escape hatch" (https://py.sdk.modelcontextprotocol.io/client/index.md, https://pypi.org/project/mcp/).
- Explicit transport: `from mcp.client.streamable_http import streamable_http_client`; its params are `url`, `http_client`, `terminate_on_close`, `max_sse_event_size` — `headers=`/`timeout=` were **removed** and live on the `httpx2.AsyncClient` you pass in (https://py.sdk.modelcontextprotocol.io/client/transports/index.md).
- Default timeouts the SDK sets on its own client: 30 s connect/write/pool and **300 s read** because the server may hold a response stream open; an `httpx2` client built without a timeout gets 5 s and long tool calls fail (https://py.sdk.modelcontextprotocol.io/client/transports/index.md).
- v1 name `streamablehttp_client` was **removed** in v2 (`ImportError: cannot import name 'streamablehttp_client'`) (https://py.sdk.modelcontextprotocol.io/migration/index.md).
- Redirects: same-origin `307`/`308` and `http→https` on the same host are followed; any other redirect fails with `MCPError: Redirect to … not followed` (https://py.sdk.modelcontextprotocol.io/client/transports/index.md).
- The v2 client defaults to `mode='auto'`, probing with `server/discover` and falling back to the legacy handshake (https://py.sdk.modelcontextprotocol.io/migration/index.md, https://py.sdk.modelcontextprotocol.io/client/index.md).

### 2.6 `mcp dev` / Inspector

- `uv run mcp dev server.py` launches the server under the MCP Inspector, which behaves like a real host: it spawns the file as a subprocess and talks stdio; `--with pkg` / `--with-editable .` extend the environment; it needs `npx` on PATH because the Inspector is a Node app (https://py.sdk.modelcontextprotocol.io/run/index.md).
- `mcp run server.py[:object]` imports the file and calls `run()` on module-level `mcp`/`server`/`app`; `mcp install` writes a Claude Desktop entry; `mcp version` prints the SDK version (https://py.sdk.modelcontextprotocol.io/run/index.md).

### 2.7 v1 API (what the task's assumptions map to)

- `from mcp.server.fastmcp import FastMCP` (https://py.sdk.modelcontextprotocol.io/v1/authorization/index.md).
- v1 kept transport settings on the constructor; `Settings` fields include `host`, `port`, `mount_path`, `sse_path`, `message_path`, `streamable_http_path`, `json_response`, `stateless_http`, `max_request_body_size`, `session_idle_timeout`, `max_sessions`, `transport_security`, all overridable via `FASTMCP_`-prefixed env vars (https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/v1.30.0/src/mcp/server/fastmcp/server.py).
- v1 `FastMCP.streamable_http_app() -> Starlette` builds a `StreamableHTTPSessionManager` with `json_response`, `stateless`, `security_settings`, `max_request_body_size`, `session_idle_timeout`, `max_sessions` (source above).
- v2 moved those transport kwargs to `run()` / `streamable_http_app()` and raises `TypeError: MCPServer.__init__() got an unexpected keyword argument 'port'` if you use the v1 habit (https://py.sdk.modelcontextprotocol.io/migration/index.md).

---

## 3. How data/ML products expose MCP servers

| Product | Docs URL | Transport | Auth | Verbatim tool names |
|---|---|---|---|---|
| GitHub | https://github.com/github/github-mcp-server | Remote Streamable HTTP at `https://api.githubcopilot.com/mcp/` | OAuth, or GitHub PAT as `Authorization: Bearer …` | `get_me`, `list_code_scanning_alerts`, `get_code_scanning_alert`, `assign_copilot_to_issue`, `ui_get` |
| Cloudflare | https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/ | Streamable HTTP at `https://mcp.cloudflare.com/mcp`; "servers support the MCP 2026-07-28 specification and stateless requests from 2025 Streamable HTTP clients" | OAuth (dashboard consent) or a Cloudflare API token as `Authorization: Bearer` | `search()`, `execute()`, `docs()` |
| Sentry | https://docs.sentry.io/product/sentry-mcp/ | Streamable HTTP at `https://mcp.sentry.dev/mcp` (optionally `/{org}` or `/{org}/{project}`); local stdio via `sentry mcp` | OAuth only for remote ("All connections use OAuth"); local uses CLI login | not enumerated on that page |
| Linear | https://linear.app/docs/mcp | Streamable HTTP at `https://mcp.linear.app/mcp`; `/mcp/readonly` for read-only; `/sse` deprecated | OAuth 2.1 with dynamic client registration, or bearer token / Linear API key in `Authorization` | not enumerated on that page |
| Stripe | https://docs.stripe.com/mcp | Streamable HTTP at `https://mcp.stripe.com` | OAuth, or **agent API key** as `Authorization: Bearer` (legacy secret/restricted keys stop working Dec 2026) | `stripe_api_search`, `stripe_api_details`, `stripe_api_read`, `stripe_api_write`, `get_stripe_account_info`, `search_stripe_documentation` |
| Hugging Face | https://huggingface.co/docs/hub/en/hf-mcp-server | Remote endpoint `https://huggingface.co/mcp`; configured from https://huggingface.co/settings/mcp | HF account auth via settings page (OAuth-style client config generated for you) | `hf_fs` (built-in); optional Contribute Repos / Sandboxes / Jobs tool groups |
| Roboflow (vision + data labeling) | https://docs.roboflow.com/agents/mcp-server | Streamable HTTP at `https://mcp.roboflow.com/mcp` | OAuth with DCR; pre-registered client_id/secret for gateways (Azure AI Foundry, Copilot Studio, TrueFoundry) | `agent_chat`, `agent_chat_result`, `projects_list`, `projects_get`, `agent_workflow_publish` |

Details worth copying:

- GitHub: server is toolset-scoped; omitting toolsets uses defaults; insiders mode is a URL path (`/mcp/insiders`) or header `X-MCP-Insiders: true`; per-tool "OAuth Challenge Scopes" are published next to each tool (https://github.com/github/github-mcp-server).
- Cloudflare: the whole 2,500-endpoint API is exposed as **two** tools via a search-and-execute "Code Mode" pattern (~1,000 tokens vs ~1.17M for native per-endpoint tools); the generated code runs in an isolated Dynamic Worker (https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/).
- Linear: read-write is the default and read-only is a separate path *or* a `read`-only OAuth scope; "the underlying token can't reach write APIs" (https://linear.app/docs/mcp).
- Stripe: several actions require Dashboard "Human confirmation" and expire after 24 h; confirmation is keyed to the action, not the tool name (`stripe_api_write` covers both confirmed and unconfirmed actions) (https://docs.stripe.com/mcp).
- Sentry: scoping to an org/project hides unnecessary discovery tools and defaults tools to that scope (https://docs.sentry.io/product/sentry-mcp/).
- Roboflow: tools declare the OAuth scopes they need; clients namespace them, e.g. `projects_list` appears as `mcp__roboflow__projects_list` (https://docs.roboflow.com/agents/mcp-server).
- Not found / not checked: Comet, Weights & Biases, Label Studio, Ultralytics, Encord — no official MCP server page was verified in this pass (Ultralytics' guessed `/integrations/mcp/` URL returned 404). Treat as "no verified entry", not "no server exists".

---

## 4. Running an MCP server inside an existing authenticated REST API

### 4.1 Mounting at `/mcp` behind existing API-key auth

- The MCP endpoint path is a normal route on your app: default `/mcp`, configurable with `streamable_http_path`, and with `Mount("/prefix", ...)` the public path becomes `/prefix/mcp` (or just `/prefix/` with `streamable_http_path="/"`) (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Put your existing API routes **before** the `Mount("/")`, because `Mount("/")` matches every path (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).
- Authentication can stay your existing middleware: the MCP app is an ordinary Starlette app, so any ASGI middleware in front of it sees the request first — the SDK's own auth is opt-in (`token_verifier=` + `auth=`) (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md, https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- If you adopt MCP-native auth instead, the SDK gives you the resource-server half only: it verifies tokens and publishes RFC 9728 metadata; it never issues tokens and gives you no login/consent UI (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).
- The spec makes OAuth-style HTTP auth a SHOULD, not a MUST ("Authorization is OPTIONAL… Implementations using an HTTP-based transport SHOULD conform"), so an API-key scheme is a deliberate deviation you should document (https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/index.md).
- Bearer-style API keys in `Authorization` are what real products do, so the header shape is at least interoperable: Stripe (agent API key as bearer), Cloudflare (API token as bearer), Linear (API key as bearer) (https://docs.stripe.com/mcp, https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/, https://linear.app/docs/mcp).

### 4.2 Why one shared endpoint needs per-request credential resolution

- There is no session on `2026-07-28`: "MCP is stateless and has no protocol-level sessions", and every request carries its own version/capabilities in `_meta` (https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning.md, https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).
- The spec expects list results to depend on the *request's* credentials: `tools/list`, `resources/list`, `prompts/list` MUST NOT vary per-connection, but MAY vary by "the authorization presented on the request — since credentials are per-request input, not connection state" (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md, https://modelcontextprotocol.io/specification/2026-07-28/server/resources.md, https://modelcontextprotocol.io/specification/2026-07-28/server/prompts.md).
- Consequence: one shared `/mcp` endpoint serving many tenants must resolve the caller on every POST and (a) filter `tools/list`, (b) authorize inside every `tools/call`/`resources/read`, and (c) scope any hired state by the resolved principal — a state handle "is a name, not a capability" (https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md, https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices.md).
- In the SDK the resolved principal is available anywhere in the handler via `get_access_token()`, which reads a per-request context variable set by auth middleware (https://py.sdk.modelcontextprotocol.io/run/authorization/index.md).

### 4.3 Known pitfalls

**Session state vs stateless**

- Modern clients: nothing to be sticky on — "A modern request is one self-contained POST: no `initialize` handshake before it, no `Mcp-Session-Id` on the response" (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Legacy clients: sessions live in one worker's memory; a follow-up hitting another worker returns `404 "Session not found"`, so either pin sticky sessions or set `stateless_http=True` — which costs the server→client back-channel and resumability (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- `stateless_http=True` is a **legacy-only** knob: on the `2026-07-28` path the transport routes on `MCP-Protocol-Version` and returns before that flag is read (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Multi-worker MRTR: `requestState` is sealed with a per-process `os.urandom(32)` key by default, so a retry on another worker fails with `-32602 "Invalid or expired requestState"`; fix is `RequestStateSecurity(keys=[...])` plus the same server name on every instance (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Cross-replica change notifications need a shared `SubscriptionBus`; the SDK's only implementation is in-process (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).

**DNS rebinding / Origin**

- Spec: MUST validate `Origin`, `403` on an invalid one; SHOULD bind `127.0.0.1` locally (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- SDK default is localhost-only and bites in production: every request behind a real hostname gets `421 Misdirected Request` (bad `Host`) or `403 Forbidden` (bad `Origin`) until you pass `transport_security=TransportSecuritySettings(allowed_hosts=[...], allowed_origins=[...])`; the client only sees a generic transport error, the reason appears in the server log (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- `TransportSecuritySettings(enable_dns_rebinding_protection=False)` is the honest setting only when a reverse proxy already controls `Host` (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Passing a non-localhost `host=` does **not** allowlist that hostname — it only stops the localhost default from arming protection (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Browser clients must have the same origins in CORS and in `allowed_origins`; CORS lets the browser send the request, the transport checks `Origin` itself (https://py.sdk.modelcontextprotocol.io/run/asgi/index.md).

**Request body size**

- SDK default `max_request_body_size` is 4 MiB, and larger requests get `413` before parsing or session creation; raise it only when legitimate MCP messages exceed that (https://py.sdk.modelcontextprotocol.io/run/index.md).
- Client side has a matching ceiling: `max_sse_event_size`, default 1 MiB per event, `None` disables it (https://py.sdk.modelcontextprotocol.io/client/transports/index.md).

**Long-running tool calls timing out**

- Protocol: closing the SSE response stream MUST be treated as cancellation of that request (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Proxies: servers SHOULD send `X-Accel-Buffering: no` so nginx-class proxies don't hold events, and are encouraged to emit `:` keep-alive comment lines on long-lived streams (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Client: the SDK's default read timeout is 300 s and the docs warn that a tool call longer than an `httpx2` default 5 s timeout fails — keep the timeout on your own client (https://py.sdk.modelcontextprotocol.io/client/transports/index.md).
- Server: the SDK exposes no production timeout/TLS/connection-limit settings; "they belong to your ASGI server" (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).
- Recovery: on `2026-07-28` a broken stream loses the in-flight request and the client MUST re-issue it as a new request with a new request ID — there is no `Last-Event-ID` replay (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).
- For work that legitimately outlives a request, the spec's answer is the Tasks extension (polling via `tasks/get`, `tasks/update`), not a held-open HTTP stream (https://modelcontextprotocol.io/specification/2026-07-28/changelog.md).

**Idempotency for retried tool calls**

- There is no idempotency key in the protocol. The only related primitive is the `idempotentHint` annotation, which is a **hint** that clients must not trust from untrusted servers (https://modelcontextprotocol.io/specification/2026-07-28/schema.md).
- Because a lost stream forces a re-issue with a new JSON-RPC `id`, the server can see the same logical operation twice; and MRTR retries must use a different `id` from the initial request (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md, https://modelcontextprotocol.io/specification/2026-07-28/server/tools.md).
- Therefore retry-safety has to be designed into the tool: make mutating tools idempotent or accept a caller-supplied idempotency key as an ordinary argument and dedupe on it. *This is a design consequence of the cited rules, not a spec requirement.*
- Two adjacent spec rules that reduce the blast radius: destructive tools should be annotated (`destructiveHint` defaults to `true`), and a held-open opaque `requestState` lets a confirmed action be completed on retry (https://modelcontextprotocol.io/specification/2026-07-28/schema.md, https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).

**Headers a proxy in front of `/mcp` must not break**

- `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` (and `Mcp-Param-*`) are required on `2026-07-28` POSTs; a mismatch between header and body is `400` + `-32020`, and intermediaries that route on those headers SHOULD refuse requests whose version header says they are unvalidated (https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md).
- Behind TLS termination, run uvicorn with `--proxy-headers --forwarded-allow-ips=…`, or its `/mcp` → `/mcp/` redirect points at `http://` and the client refuses the downgrade (https://py.sdk.modelcontextprotocol.io/run/deploy/index.md).

---

## 5. Uncertain / could not verify

- **Release date of the `2026-07-28` revision** beyond the identifier itself: not stated on the pages fetched. (SDK 2.0.0 shipped Jul 28, 2026 per https://pypi.org/project/mcp/ — suggestive, not proof.)
- **`get_http_request()`**: not found in v1 docs, v2 docs, or the v1 source I read. The documented per-request auth accessor is `get_access_token()`; the raw Starlette request is reachable via `Context`/`request_context` in v1 source but I did not verify the v2 equivalent.
- **`mcp.server.fastmcp` shim**: the migration guide says the module is gone (`ModuleNotFoundError`); I did not read the v2 package source to confirm there is no re-export.
- **Hugging Face transport type**: the docs page gives the endpoint (`https://huggingface.co/mcp`) and config generation but does not name the transport; assumed Streamable HTTP, unverified.
- **Sentry and Linear tool names**: neither cited page enumerates them, so the table says "not enumerated" rather than guessing.
- **Resources subscribe method names in `2025-11-25`**: I read the `2026-07-28` resources page and the changelog statement that `resources/subscribe`/`unsubscribe` were replaced; I did not fetch the 2025-11-25 resources page itself.
- **OAuth client-credentials / identity-assertion**: v2 docs describe both (https://py.sdk.modelcontextprotocol.io/client/identity-assertion/, https://modelcontextprotocol.io/extensions/auth/oauth-client-credentials.md) but I did not read them in detail.
- **Tasks extension**: semantics summarized from the changelog only; the extension page (https://modelcontextprotocol.io/extensions/tasks/overview.md) was not read.
- **Vendor pages behind JS** (Sentry, Linear, Roboflow): content was obtained through the markdown-rendering fetch, so exact wording of tool descriptions may differ slightly from the live HTML.
