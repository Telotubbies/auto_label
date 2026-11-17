"""The MCP surface: the tool registry, the scope filter, and today's two tools."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import INVALID_REQUEST, MCPError
from mcp.types import Tool

from .api import Api

INSTRUCTIONS = (
    "LabelDesk is a visual labeling product: images are labeled, then a model is trained and deployed. "
    "Every id in a result is LabelDesk's own API id — pass it back unchanged. "
    "A `project` argument is a project slug, not a display name. "
    "A tool that spends credits refuses to run unless the call passes confirm: true."
)

# Every toolset appends its tools here; a tool missing from this map is never listed.
TOOL_SCOPES: dict[str, str] = {"whoami": "read", "list_projects": "read"}


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
    from .tools_read import register

    server = _ScopedServer(api)

    @server.tool()
    def whoami() -> dict:
        """Which workspace this key belongs to, its plan, and the scopes it carries."""
        _enabled(api)
        return api.call("whoami", "whoami")

    @server.tool()
    def list_projects() -> list:
        """The workspace's projects, with their image counts and classes."""
        _enabled(api)
        return api.call("list_projects", "list_projects")

    register(server, api)
    return server
