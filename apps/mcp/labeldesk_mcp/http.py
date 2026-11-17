"""The MCP endpoint on LabelDesk's own origin: one key per POST, no session to keep.

The SDK app is wrapped, not mounted: a Starlette ``Mount`` never enters the sub-app's lifespan,
so its session manager would answer the first request with "Task group is not initialized".
A raw ASGI wrapper forwards ``lifespan`` untouched and needs no second app.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
from collections.abc import Sequence

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .api import Api

logger = logging.getLogger(__name__)

PUBLISHABLE_PREFIX = "ld_pub_"
MAX_BODY_BYTES = 4 * 1024 * 1024


def _presented_key(scope: Scope) -> str:
    """The key this one request carries: `Authorization: Bearer`, else `x-api-key`."""
    headers = {name.decode("latin-1"): value.decode("latin-1") for name, value in scope["headers"]}
    authorization = headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return headers.get("x-api-key", "").strip()


async def _answer(scope: Scope, receive: Receive, send: Send, status: int, body: str,
                  headers: dict[str, str] | None = None) -> None:
    await Response(body, status_code=status, headers=headers)(scope, receive, send)


class KeyMiddleware:
    """Bind the request's key for that request only, and refuse what can never work."""

    def __init__(self, app: ASGIApp, api: Api):
        self.app = app
        self.api = api

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)  # lifespan: the SDK's session manager starts here
            return
        key = _presented_key(scope)
        if not key:
            await _answer(scope, receive, send, 401, "authentication required", {"www-authenticate": "Bearer"})
            return
        if key.startswith(PUBLISHABLE_PREFIX):
            await _answer(scope, receive, send, 403, "a publishable key cannot drive an agent")
            return
        # A fresh context per request: the credential dies with the request, never with the connection.
        await asyncio.create_task(self._as_key(scope, receive, send, key), context=contextvars.copy_context())

    async def _as_key(self, scope: Scope, receive: Receive, send: Send, key: str) -> None:
        self.api.use(key)
        try:
            enabled = self.api.enabled()
        except ToolError:
            # A key the API will not accept is an authentication answer, never a 500.
            await _answer(scope, receive, send, 401, "authentication required", {"www-authenticate": "Bearer"})
            return
        if not enabled:
            await _answer(scope, receive, send, 404, "Not Found")  # "off" looks missing, not forbidden
            return
        await self.app(scope, receive, self._naming_the_cap(send))

    @staticmethod
    def _naming_the_cap(send: Send) -> Send:
        """Pass the response through, naming the body cap when it is the reason for a refusal."""

        async def watched(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 413:
                logger.warning("request body over the %d MiB cap", MAX_BODY_BYTES // (1024 * 1024))
            await send(message)

        return watched


def build_app(server: MCPServer, api: Api, *, allowed_hosts: Sequence[str] = (),
              allowed_origins: Sequence[str] = (), path: str = "/mcp") -> ASGIApp:
    """One stateless POST endpoint: no session id, no server-side state between requests."""
    security = None
    if allowed_hosts or allowed_origins:
        security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                             allowed_hosts=list(allowed_hosts),
                                             allowed_origins=list(allowed_origins))
    # Empty allow-lists keep the SDK's localhost-only default, the safe answer for a laptop.
    app = server.streamable_http_app(streamable_http_path=path, stateless_http=True,
                                     max_request_body_size=MAX_BODY_BYTES, transport_security=security)
    return KeyMiddleware(app, api)
