"""T-997: every admitted MCP call leaves one audit row, and the API's limits are the agent's limits.

Settings -> Audit log already renders `action` + `target` + `meta`, so the whole surface is one row:
`mcp.tool`, the request path as the target and the tool name in the detail. A call refused before the
key is resolved (rate limit, revoked key) leaves nothing. The `apikey.use` throttle stays
one-per-minute; `mcp.tool` is one per call on purpose, because an MCP call is a conversation turn,
not a poll. No row, log line or tool result may carry the key, its prefix or the Authorization value.
"""
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import ratelimit
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Member, User, Workspace
from app.security import issue_access
from conftest import login as shared_login

WS = "labeldesk-demo"
TOOL_HEADER = "x-mcp-tool"
PLAN_SENTENCE = "monthly credit limit reached on the Free plan"
THROTTLE_SENTENCE = "too many attempts — try again shortly"

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from labeldesk_mcp import server as mcp_server      # noqa: E402
from labeldesk_mcp.api import Api                  # noqa: E402
from mcp.client import Client                      # noqa: E402


def anon() -> TestClient:
    return TestClient(app)


def rows_since(t0: float, ws_id: str | None = None) -> list[Audit]:
    """`mcp.tool` rows written after `t0`; the demo workspace already holds audit rows from other modules."""
    with SessionLocal() as db:
        q = select(Audit).where(Audit.action == "mcp.tool", Audit.created >= t0)
        if ws_id is not None:
            q = q.where(Audit.workspace_id == ws_id)
        return list(db.scalars(q))


def workspace_id(slug: str) -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == slug))


def mcp_tool_result(response):
    """Drive one real MCP tool whose API answers `response`; answer (is_error, text)."""
    def transport(request):
        if request.url.path == "/api/v1/whoami":
            return httpx.Response(200, json={"workspace": WS, "scopes": ["read"], "mcp": True})
        return response

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use("ld_test_key_not_a_real_one")

    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return await client.call_tool("list_projects", {})

    result = asyncio.run(run())
    return result.is_error, " ".join(block.text for block in result.content)


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(shared_login(client))
        yield client


@pytest.fixture(scope="module")
def key(c) -> dict:
    r = c.post(f"/api/ws/{WS}/keys", json={"name": "t997-mcp", "scopes": ["read"]})
    assert r.status_code == 200, r.text
    created = r.json()
    yield {"headers": {"Authorization": f"Bearer {created['key']}"},
           "key": created["key"], "prefix": created["prefix"]}
    c.delete(f"/api/ws/{WS}/keys/{created['id']}")


@pytest.fixture(scope="module")
def workspace_b():
    """A second workspace with its own read key: its rows must never appear under the demo workspace."""
    tag = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(email=f"t997-b-{tag}@test.local", name="B", pw_hash="", email_verified=time.time())
        db.add(u)
        db.flush()
        ws = Workspace(slug=f"t997-b-{tag}", name="B", owner_id=u.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        db.commit()
        ws_id, ws_slug, uid = ws.id, ws.slug, u.id
    r = anon().post(f"/api/ws/{ws_slug}/keys", headers={"Authorization": f"Bearer {issue_access(uid)}"},
                    json={"name": "t997-b-read", "scopes": ["read"]})
    assert r.status_code == 200, r.text
    yield {"id": ws_id, "headers": {"Authorization": f"Bearer {r.json()['key']}"}}
    with SessionLocal() as db:
        db.query(Audit).filter(Audit.workspace_id == ws_id).delete()
        db.query(Member).filter(Member.workspace_id == ws_id).delete()
        db.query(Workspace).filter(Workspace.id == ws_id).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()


# --- the audit row ---------------------------------------------------------------------------

def test_an_mcp_call_writes_one_mcp_tool_row(key):
    demo_ws = workspace_id(WS)

    t0 = time.time()
    r = anon().get("/api/v1/projects", headers={**key["headers"], TOOL_HEADER: "list_projects"})

    assert r.status_code == 200, r.text
    rows = rows_since(t0, demo_ws)
    assert len(rows) == 1, "one admitted MCP call leaves exactly one mcp.tool row"
    row = rows[0]
    assert row.action == "mcp.tool"
    assert row.target == "/api/v1/projects"
    assert row.meta["tool"] == "list_projects"
    assert row.meta["method"] == "GET"
    assert row.user_id is None, "a key-scoped action has no user"


def test_a_plain_api_call_writes_none(key):
    t0 = time.time()
    r = anon().get("/api/v1/projects", headers=key["headers"])

    assert r.status_code == 200, r.text
    assert rows_since(t0) == [], "the SDK, CLI and browser paths are unchanged"


def test_the_row_is_scoped_to_the_keys_workspace(key, workspace_b):
    t0 = time.time()
    r = anon().get("/api/v1/projects", headers={**workspace_b["headers"], TOOL_HEADER: "list_projects"})

    assert r.status_code == 200, r.text
    assert len(rows_since(t0, workspace_b["id"])) == 1
    assert rows_since(t0, workspace_id(WS)) == [], "workspace A never sees workspace B's tool calls"


def test_the_tool_name_is_truncated_and_never_the_key(key):
    t0 = time.time()
    r = anon().get("/api/v1/projects", headers={**key["headers"], TOOL_HEADER: "x" * 500})

    assert r.status_code == 200, r.text
    rows = rows_since(t0, workspace_id(WS))
    assert len(rows) == 1
    row = rows[0]
    assert len(row.meta["tool"]) == 64, "the client-asserted header is capped at 64 chars"
    dumped = f"{row.target} {json.dumps(row.meta)}"
    assert key["key"] not in dumped
    assert key["prefix"] not in dumped
    assert "uthorization" not in dumped
    assert set(row.meta) == {"tool", "method"}


# --- the limits the agent meets --------------------------------------------------------------

def test_the_rate_limit_still_answers_429(key):
    """The 601st resolution in a minute is refused at the limiter, before the key is resolved.

    Two real calls prove `resolve_key` spends one shared per-IP budget; the other 598 slots are
    filled through `limit` itself rather than 601 real requests (which cost a minute of suite time).
    """
    ratelimit.ENABLED = True
    ratelimit._hits.clear()
    headers = {**key["headers"], TOOL_HEADER: "list_projects"}
    client = anon()

    for _ in range(2):
        assert client.get("/api/v1/projects", headers=headers).status_code == 200
    assert len(ratelimit._hits) == 1
    (budget,) = ratelimit._hits
    assert len(ratelimit._hits[budget]) == 2
    for _ in range(598):
        ratelimit.limit(budget, 600, 60)

    t0 = time.time()
    refused = client.get("/api/v1/projects", headers=headers)

    assert refused.status_code == 429
    assert refused.headers.get("Retry-After", "").isdigit()
    assert THROTTLE_SENTENCE in refused.text
    assert rows_since(t0) == [], "a refusal before key resolution leaves no audit row"

    replay = httpx.Response(refused.status_code, json=refused.json(),
                            headers={"Retry-After": refused.headers["Retry-After"]})
    is_error, text = mcp_tool_result(replay)
    assert is_error is True
    assert THROTTLE_SENTENCE in text


def test_a_402_is_a_tool_error_with_the_plan_name():
    is_error, text = mcp_tool_result(httpx.Response(402, json={"detail": PLAN_SENTENCE}))

    assert is_error is True
    assert PLAN_SENTENCE in text


# --- nothing hidden --------------------------------------------------------------------------

def test_no_log_line_carries_the_key(key, caplog):
    caplog.set_level(logging.DEBUG)

    t0 = time.time()
    r = anon().get("/api/v1/projects", headers={**key["headers"], TOOL_HEADER: "list_projects"})

    assert r.status_code == 200, r.text
    assert len(rows_since(t0)) == 1
    assert key["key"] not in caplog.text
    assert key["prefix"] not in caplog.text
    assert "Authorization: Bearer" not in caplog.text
