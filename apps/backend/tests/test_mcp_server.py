"""The MCP app's contract: one seam to the API, a scope filter, and no key on the wire out.

The card's UX flow is the test list: a tool the key may not use is absent from `tools/list`, an
API failure comes back as a tool result error the model can act on, and the key never reaches a
log, a result or stdout. The MCP SDK is the client under test.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from mcp.client import Client                                    # noqa: E402
from mcp.server.mcpserver import MCPServer                       # noqa: E402
from mcp.shared.exceptions import MCPError                        # noqa: E402

from labeldesk_mcp import __version__, server as mcp_server      # noqa: E402
from labeldesk_mcp.__main__ import main                          # noqa: E402
from labeldesk_mcp.api import Api                                # noqa: E402

KEY = "ld_live_s3cret_key_do_not_leak"
ROWS = [
    {"id": "prj_1", "slug": "defects", "name": "Defects", "type": "object-detection", "images": 12,
     "classes": ["scratch", "dent"]},
    {"id": "prj_2", "slug": "pallet", "name": "Pallet corners", "type": "object-detection", "images": 0,
     "classes": []},
]


def api_with(handler=lambda request: httpx.Response(200, json=ROWS), *, scopes=("read",), mcp=True, whoami=None):
    """An Api over a MockTransport whose `/whoami` answers this key's scopes and the workspace switch."""
    seen = []

    def transport(request):
        seen.append(request)
        if request.url.path == "/api/v1/whoami":
            if whoami is not None:
                return whoami(request)
            return httpx.Response(200, json={"workspace": "demo", "scopes": list(scopes), "mcp": mcp})
        return handler(request)

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use(KEY)
    return api, seen


def tools_of(api, register=None):
    async def run():
        server = mcp_server.build_server(api)
        if register is not None:
            register(server)
        async with Client(server) as client:
            return (await client.list_tools()).tools

    return asyncio.run(run())


def tool_names(api, register=None):
    return [tool.name for tool in tools_of(api, register)]


def call(api, name):
    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return await client.call_tool(name, {})

    return asyncio.run(run())


def text_of(result):
    return " ".join(block.text for block in result.content)


def test_the_pinned_sdk_is_the_one_we_target():
    from importlib.metadata import version

    major, minor = (int(part) for part in version("mcp").split(".")[:2])
    assert (major, minor) >= (2, 3)
    assert major < 3
    # the v2 class name the server is built on, not the v1 FastMCP every snippet on the web shows
    assert MCPServer.__name__ == "MCPServer"


def test_tools_list_is_filtered_by_the_keys_scopes(monkeypatch):
    def probe(server):
        @server.tool()
        def train_probe() -> str:
            """A tool that needs the train scope."""
            return "ok"

    monkeypatch.setitem(mcp_server.TOOL_SCOPES, "train_probe", "train")
    read_key, _ = api_with()
    train_key, _ = api_with(scopes=("read", "train"))

    read_tools = tool_names(read_key, probe)
    train_tools = tool_names(train_key, probe)

    assert "train_probe" not in read_tools
    assert "train_probe" in train_tools
    assert {"whoami", "list_projects"} <= set(read_tools)
    assert {"whoami", "list_projects"} <= set(train_tools)


def test_list_projects_round_trips_through_the_api():
    api, seen = api_with(lambda request: httpx.Response(200, json=ROWS))

    result = call(api, "list_projects")

    assert result.is_error is False
    assert [json.loads(block.text) for block in result.content] == ROWS
    request = [r for r in seen if r.url.path == "/api/v1/projects"][-1]
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["x-mcp-tool"] == "list_projects"
    assert request.headers["x-mcp-client"] == f"labeldesk-mcp/{__version__}"


def test_scopes_and_enabled_share_one_whoami_call_and_cache_it():
    api, seen = api_with()

    assert api.scopes() == ["read"]
    assert api.enabled() is True
    assert [request.url.path for request in seen] == ["/api/v1/whoami"]


def test_whoami_names_the_workspace_this_key_belongs_to():
    api, _ = api_with()

    result = call(api, "whoami")

    assert json.loads(result.content[0].text)["workspace"] == "demo"


def test_a_workspace_with_no_project_answers_no_rows():
    api, _ = api_with(lambda request: httpx.Response(200, json=[]))

    result = call(api, "list_projects")

    assert result.is_error is False
    assert result.content == []


def test_no_tool_takes_a_workspace_so_the_key_is_the_only_identity():
    tools = tools_of(api_with()[0])

    params = {tool.name: set(tool.input_schema.get("properties", {})) for tool in tools}
    assert {"whoami", "list_projects"} <= set(params)
    assert params["whoami"] == set() and params["list_projects"] == set()
    for name, props in params.items():
        assert not props & {"workspace", "ws", "workspace_id"}, f"{name} takes a workspace"


def test_an_api_error_becomes_a_tool_result_error():
    api, _ = api_with(lambda request: httpx.Response(403, json={"detail": "api_key lacks the 'write' scope"}))

    result = call(api, "list_projects")

    assert result.is_error is True
    assert "api_key lacks the 'write' scope" in text_of(result)
    assert "HTTP 403" in text_of(result)


def test_a_transport_failure_names_the_url_check():
    def dead(request):
        raise httpx.ConnectError("name resolution failed", request=request)

    api, _ = api_with(dead)

    result = call(api, "list_projects")

    assert result.is_error is True
    assert "cannot reach LabelDesk" in text_of(result)


def test_project_settings_and_secrets_are_scrubbed():
    row = {**ROWS[0], "settings": {"webhook_secret": "s3cr3t"}, "hash": "h4shy"}
    api, _ = api_with(lambda request: httpx.Response(200, json=[row]))

    result = call(api, "list_projects")

    dumped = json.dumps([block.text for block in result.content])
    assert "s3cr3t" not in dumped
    assert "h4shy" not in dumped
    assert "settings" not in dumped
    assert json.loads(result.content[0].text)["slug"] == "defects"


def test_the_key_is_never_logged(caplog):
    state = {"fail": False}

    def handler(request):
        if state["fail"]:
            return httpx.Response(503, json={"detail": "service unavailable"})
        return httpx.Response(200, json=ROWS)

    api, _ = api_with(handler)
    caplog.set_level(logging.DEBUG)

    assert call(api, "list_projects").is_error is False
    state["fail"] = True
    assert call(api, "list_projects").is_error is True

    assert KEY not in caplog.text
    assert KEY[:12] not in caplog.text


def test_main_exits_two_without_a_key(monkeypatch, capsys):
    monkeypatch.delenv("LABELDESK_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        main([])

    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().splitlines() == ["LABELDESK_API_KEY is not set"]


def test_a_workspace_with_the_mcp_flag_off_is_refused():
    api, seen = api_with(mcp=False)

    for name in ("whoami", "list_projects"):
        result = call(api, name)
        assert result.is_error is True
        assert "the MCP endpoint is not enabled for this workspace" in text_of(result)

    assert {request.url.path for request in seen} == {"/api/v1/whoami"}


def test_a_revoked_key_fails_the_list_with_one_readable_line():
    api, _ = api_with(whoami=lambda request: httpx.Response(401, json={"detail": "invalid api_key"}))

    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            with pytest.raises(MCPError) as error:
                await client.list_tools()
        return error.value

    assert "invalid api_key (HTTP 401)" in str(asyncio.run(run()))
