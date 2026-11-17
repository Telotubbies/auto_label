"""The MCP surface: the tool registry, the scope filter, and today's two tools."""
from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import INVALID_REQUEST, MCPError
from mcp.types import CallToolResult, TextContent, Tool, ToolAnnotations

from .api import Api

INSTRUCTIONS = (
    "LabelDesk is a visual labeling product: images are labeled, then a model is trained and deployed. "
    "Every id in a result is LabelDesk's own API id — pass it back unchanged. "
    "A `project` argument is a project slug, not a display name. "
    "A tool that spends credits refuses to run unless the call passes confirm: true."
)

# Every toolset appends its tools here; a tool missing from this map is never listed.
TOOL_SCOPES: dict[str, str] = {"whoami": "read", "list_projects": "read"}

# The hint sets a host reads before it asks a person. `idempotentHint` is the tool's real behaviour:
# a hash-deduped upload and a whole-set replace land the same on a second call, a job does not.
READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, idempotent_hint=False, open_world_hint=False)
IDEMPOTENT_WRITE = ToolAnnotations(read_only_hint=False, idempotent_hint=True, open_world_hint=False)
DESTRUCTIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True,
                              open_world_hint=False)


def summarised(data: Any, line: str) -> CallToolResult:
    """One record: the JSON a text-only host reads, its typed copy, and one line for a person.

    A tool's return annotation is the published outputSchema, so it stays the record's type while the
    tool hands back this wrapper.
    """
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, indent=2)),
                                   TextContent(type="text", text=line)],
                          structured_content=data)


class _ScopedServer(MCPServer):
    """An MCPServer that shows each key only the tools its own scopes allow."""

    def __init__(self, api: Api):
        super().__init__(name="LabelDesk", instructions=INSTRUCTIONS)
        self.api = api

    async def list_tools(self) -> list[Tool]:
        try:
            scopes = self.api.scopes()
        except ToolError as exc:
            # A revoked key must read as one sentence, not as an internal server error.
            raise MCPError(INVALID_REQUEST, str(exc)) from exc
        return [tool for tool in await super().list_tools() if TOOL_SCOPES.get(tool.name) in scopes]


def _enabled(api: Api) -> None:
    """Refuse at the workspace switch before any API call the tool would make."""
    if not api.enabled():
        raise ToolError("the MCP endpoint is not enabled for this workspace")


def build_server(api: Api) -> MCPServer:
    """Both transports build this server; the key differs per request, the tools do not."""
    from . import meta
    from .tools_read import register
    from .tools_write import register as register_write

    server = _ScopedServer(api)

    @server.tool(annotations=READ)
    def whoami() -> dict[str, Any]:
        """This key's workspace, plan and scopes.

        Use it first, to learn what the key may do; do not use it to read a project's data — call get_project.
        """
        _enabled(api)
        me = api.me()
        # the annotation is the published outputSchema; the wrapper adds the one-line summary
        return summarised(me, f"Key for workspace {me.get('workspace')} with "
                              f"{len(me.get('scopes') or [])} scopes.")

    @server.tool(annotations=READ)
    def list_projects() -> list[dict]:
        """Every project in this workspace with its image count and class names.

        Use it to find a project's slug; do not use it for one project's detail — call get_project.
        """
        _enabled(api)
        return api.call("list_projects", "list_projects")

    register(server, api)
    register_write(server, api)
    meta.register(server, api)
    return server
