"""The MCP endpoint's contract over HTTP: one authenticated POST, no session to keep.

The card's UX flow is the test list. Guard tests drive the ASGI app in process and assert the
answer each refusal deserves — 401 with a challenge, 403 for a browser key, 404 when the
workspace switch is off, 403/421 for a foreign Origin/Host, 413 over 4 MiB, all before any tool
runs. The round trip starts a real server and talks to it with the SDK's own client, because an
endpoint only MCP clients can reach is the feature.
"""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import httpx2                                                    # noqa: E402
from mcp.client import Client                                    # noqa: E402
from mcp.client.streamable_http import streamable_http_client     # noqa: E402

from labeldesk_mcp import server as mcp_server                    # noqa: E402
from labeldesk_mcp.api import Api                                # noqa: E402
from labeldesk_mcp.http import build_app                         # noqa: E402

READ_KEY = "ld_live_read_key_do_not_leak"
TRAIN_KEY = "ld_live_train_key_do_not_leak"
SCOPES = {READ_KEY: ["read"], TRAIN_KEY: ["read", "train"]}
WORKSPACE = "demo"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2026-07-28", "capabilities": {},
               "clientInfo": {"name": "test", "version": "0"}},
}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def api_with(*, mcp=True):
    """An Api whose `/whoami` answers per key, so two keys in one process can differ."""

    def transport(request):
        if request.url.path == "/api/v1/whoami":
            key = request.headers.get("authorization", "").removeprefix("Bearer ")
            return httpx.Response(200, json={"workspace": WORKSPACE, "scopes": SCOPES.get(key, ["read"]),
                                              "mcp": mcp})
        return httpx.Response(200, json=[])

    return Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))


def app_for(api, *, hosts=("testserver",), origins=("http://testserver",)):
    return build_app(mcp_server.build_server(api), api, allowed_hosts=hosts, allowed_origins=origins)


def bearer(key):
    return {**HEADERS, "authorization": f"Bearer {key}"}


def test_a_request_without_a_key_is_401_with_a_bearer_challenge():
    with TestClient(app_for(api_with())) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=HEADERS)

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert WORKSPACE not in response.text


def test_a_publishable_key_is_refused():
    with TestClient(app_for(api_with())) as client:
        response = client.post("/mcp", json=INITIALIZE, headers=bearer("ld_pub_browser_key"))

    assert response.status_code == 403
    assert WORKSPACE not in response.text


def test_a_workspace_with_mcp_off_is_404():
    with TestClient(app_for(api_with(mcp=False))) as client:
        for method in ("post", "get", "delete"):
            response = getattr(client, method)("/mcp", headers=bearer(READ_KEY))
            assert response.status_code == 404
            # "off" must look missing: the answer an unknown path gets, not a forbidden one.
            assert response.text == client.get("/not-mcp", headers=bearer(READ_KEY)).text


def test_an_unknown_origin_is_403():
    with TestClient(app_for(api_with())) as client:
        response = client.post("/mcp", json=INITIALIZE,
                               headers={**bearer(READ_KEY), "origin": "https://evil.example"})

    assert response.status_code == 403


def test_an_unknown_host_is_421_or_403():
    with TestClient(app_for(api_with())) as client:
        response = client.post("/mcp", json=INITIALIZE,
                               headers={**bearer(READ_KEY), "host": "evil.example"})

    assert response.status_code in (403, 421)


def test_the_body_cap_is_four_mib():
    with TestClient(app_for(api_with())) as client:
        response = client.post("/mcp", content=b"x" * (5 * 1024 * 1024), headers=bearer(READ_KEY))

    assert response.status_code == 413


@pytest.fixture(scope="module")
def live_url():
    """One real server for the two round-trip tests: a client must be able to reach this."""
    api = api_with()
    server = mcp_server.build_server(api)

    @server.tool()
    def train_probe() -> str:
        """A tool that needs the train scope."""
        return "ok"

    mcp_server.TOOL_SCOPES["train_probe"] = "train"
    app = build_app(server, api, allowed_hosts=["127.0.0.1:*"], allowed_origins=["http://127.0.0.1:*"])
    running = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not running.started and time.time() < deadline:
        time.sleep(0.02)
    assert running.started, "the MCP HTTP server did not start"
    port = running.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    running.should_exit = True
    thread.join(timeout=20)
    mcp_server.TOOL_SCOPES.pop("train_probe", None)


def with_client(url, key, work):
    async def run():
        async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {key}"}) as http_client:
            transport = streamable_http_client(f"{url}/mcp", http_client=http_client)
            async with Client(transport) as client:
                return await work(client)

    return asyncio.run(run())


def tool_names(url, key):
    return with_client(url, key, lambda client: client.list_tools()).tools


def test_a_real_client_round_trips_over_http(live_url):
    async def work(client):
        names = [tool.name for tool in (await client.list_tools()).tools]
        result = await client.call_tool("whoami", {})
        return names, result

    names, result = with_client(live_url, READ_KEY, work)

    assert "whoami" in names
    assert json.loads(result.content[0].text)["workspace"] == WORKSPACE


def test_two_keys_in_one_process_see_their_own_scopes(live_url):
    train_names = [tool.name for tool in tool_names(live_url, TRAIN_KEY)]
    read_names = [tool.name for tool in tool_names(live_url, READ_KEY)]

    assert "train_probe" in train_names
    assert "train_probe" not in read_names


def test_http_mode_binds_the_allow_lists_from_the_environment(monkeypatch):
    from labeldesk_mcp.__main__ import _comma_list, main

    started = {}
    monkeypatch.delenv("LABELDESK_API_KEY", raising=False)
    monkeypatch.setenv("LD_MCP_ALLOWED_HOSTS", "mcp.labeldesk.test, 127.0.0.1:*")
    monkeypatch.setenv("LD_MCP_ALLOWED_ORIGINS", "https://mcp.labeldesk.test")
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port: started.update(app=app, host=host, port=port))

    assert _comma_list("LD_MCP_ALLOWED_HOSTS") == ["mcp.labeldesk.test", "127.0.0.1:*"]
    assert main(["--http", "--port", "8123"]) == 0  # no key at startup: the key arrives per request

    assert (started["host"], started["port"]) == ("127.0.0.1", 8123)
    assert type(started["app"]).__name__ == "KeyMiddleware"
