"""The one seam between MCP and LabelDesk: a key per request, one call, one error shape."""
from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

import httpx
from labeldesk.client import DEFAULT_URL, LabelDesk, LabelDeskError
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__

CLIENT_ID = f"labeldesk-mcp/{__version__}"
MAX_TEXT = 8192
SECRET_KEYS = {"settings", "hash", "sha256", "password", "token", "secret", "api_key", "credentials"}


def scrub(value: Any) -> Any:
    """Drop credentials and project settings from a tool result, and cap oversized strings."""
    if isinstance(value, dict):
        return {key: scrub(item) for key, item in value.items() if str(key).lower() not in SECRET_KEYS}
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT]
    return value


class Api:
    """One LabelDesk API seam: `use()` binds the key, `call()` spends it once, `scrub()` on the way out."""

    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url or os.environ.get("LABELDESK_URL") or DEFAULT_URL
        self.transport = transport
        self._key: ContextVar[str | None] = ContextVar("labeldesk_mcp_key", default=None)
        self._whoami_cache: ContextVar[dict | None] = ContextVar("labeldesk_mcp_whoami", default=None)

    def key(self) -> str | None:
        """The current request's key; the stdio adapter binds it once from `LABELDESK_API_KEY`."""
        return self._key.get() or os.environ.get("LABELDESK_API_KEY")

    def use(self, key: str) -> None:
        """Bind a key to this request; the `/whoami` answer is cached for that request only."""
        self._key.set(key)
        self._whoami_cache.set(None)

    def _whoami(self) -> dict:
        cached = self._whoami_cache.get()
        if cached is None:
            cached = self.call("whoami", "whoami")
            self._whoami_cache.set(cached)
        return cached

    def scopes(self) -> list[str]:
        return self._whoami().get("scopes") or []

    def enabled(self) -> bool:
        """The workspace's `task_992` switch, as the API reports it on `/whoami`."""
        return bool(self._whoami().get("mcp"))

    def me(self) -> dict:
        """This key's own `/whoami` payload, the one `scopes()` and `enabled()` already read."""
        return self._whoami()

    def call(self, tool: str, operation: str, path_params: dict | None = None, params: dict | None = None,
             json: Any = None, files: Any = None, data: dict | None = None) -> Any:
        """Run one API operation as one tool call, and answer in the tool's language."""
        with LabelDesk(api_key=self.key(), base_url=self.base_url, transport=self.transport) as client:
            try:
                return scrub(client.call(operation, path_params=path_params, params=params, json=json,
                                         files=files, data=data,
                                         headers={"x-mcp-tool": tool, "x-mcp-client": CLIENT_ID}))
            except LabelDeskError as exc:
                if not exc.status:
                    raise ToolError("cannot reach LabelDesk — check LABELDESK_URL") from exc
                raise ToolError(f"{exc.detail} (HTTP {exc.status})") from exc
