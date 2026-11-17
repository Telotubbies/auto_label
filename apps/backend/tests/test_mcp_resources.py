"""The three resources and two prompts: facts an agent reads before it writes anything.

Two layers, because they prove different things. The in-memory layer pins the rendering, the argument
shapes and the error mapping; the live layer proves a foreign project slug is a 404 through a real
key, which is the isolation claim.
"""
import asyncio
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from app.db import SessionLocal
from app.main import app
from app.models import Member, Project, User, Workspace
from app.security import issue_access
from app.services.flags import set_flag
from labeldesk_mcp import server as mcp_server
from labeldesk_mcp.api import Api

KEY = "ld_live_s3cret_key_do_not_leak"
WORKSPACE_URI = "labeldesk://workspace"
PROJECT_URI = "labeldesk://projects/parcels"
CLASSES_URI = "labeldesk://projects/parcels/classes"
BOX = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}

PROJECT = {
    "id": "prj_1", "slug": "parcels", "name": "Parcels", "type": "object-detection",
    "images": 2, "models": 1, "statusCounts": {"annotating": 1, "review": 1},
    "classes": [{"id": "cls_box", "name": "box", "color": "#ef4444", "count": 3},
                {"id": "cls_dent", "name": "dent", "color": "#22c55e", "count": 1}],
    "settings": {"webhook_secret": "s3cr3t"}, "thumbnail": "/files/projects/prj_1/cover.jpg?exp=1&sig=abc",
}
REVIEW_PAGE = {"total": 2, "items": [
    {"id": "img_low", "name": "low-confidence.jpg", "classIds": ["cls_box"], "annotationCount": 1},
    {"id": "img_high", "name": "reviewed.jpg", "classIds": ["cls_dent"], "annotationCount": 1},
]}
ANNOTATIONS = {
    "img_low": [{"id": "a1", "classId": "cls_box", "shape": BOX, "source": "model", "confidence": 0.1}],
    "img_high": [{"id": "a2", "classId": "cls_dent", "shape": BOX, "source": "model", "confidence": 0.9}],
}
AUDIT_PAGE = {"total": 3, "items": [{"id": "img_u1", "name": "unlabelled-1.jpg", "classIds": [],
                                    "annotationCount": 0}]}


# --- the in-memory layer: rendering, arguments, error mapping -------------------------------

def default(request):
    """The API a healthy workspace answers: one project, two images, three unlabelled in a batch."""
    path = request.url.path
    if path == "/api/v1/projects":
        return httpx.Response(200, json=[PROJECT])
    if path == "/api/v1/projects/parcels":
        return httpx.Response(200, json=PROJECT)
    if path == "/api/v1/projects/parcels/images":
        if request.url.params.get("annotated") == "no":
            return httpx.Response(200, json=AUDIT_PAGE)
        return httpx.Response(200, json=REVIEW_PAGE)
    if path.startswith("/api/v1/images/"):
        image_id = path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"id": image_id, "annotations": ANNOTATIONS[image_id]})
    return httpx.Response(404, json={"detail": "not found"})


def api_with(handler=None, *, mcp=True, plan="pro", scopes=("read", "write")):
    """An Api over a MockTransport whose `/whoami` answers this key's scopes and the workspace switch."""
    seen = []

    def transport(request):
        seen.append(request)
        if request.url.path == "/api/v1/whoami":
            return httpx.Response(200, json={"workspace": "demo", "name": "Demo Lab", "plan": plan,
                                             "scopes": list(scopes), "mcp": mcp})
        return (handler or default)(request)

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use(KEY)
    return api, seen


def run(api, fn):
    async def go():
        async with Client(mcp_server.build_server(api)) as client:
            return await fn(client)

    return asyncio.run(go())


def read(api, uri):
    return run(api, lambda client: client.read_resource(uri))


def text_of(api, uri):
    result = read(api, uri)
    assert result.contents, f"{uri} returned no contents"
    return result.contents[0].text


def listing(api):
    async def go(client):
        return (await client.list_resources()).resources, (await client.list_resource_templates()).resource_templates

    return run(api, go)


def message_of(prompt):
    return " ".join(block.content.text for block in prompt.messages if getattr(block.content, "text", None))


def failure(api, fn):
    """The MCP error a call raises, caught inside the session so the SDK does not wrap it in a group."""
    async def go():
        async with Client(mcp_server.build_server(api)) as client:
            try:
                await fn(client)
            except MCPError as exc:
                return exc
        return None

    return asyncio.run(go())


# --- the three resources -------------------------------------------------------------------

def test_the_three_resources_are_listed_with_templates():
    api, _ = api_with()

    resources, templates = listing(api)

    assert [str(r.uri) for r in resources] == [WORKSPACE_URI]
    assert {str(t.uri_template) for t in templates} == {"labeldesk://projects/{project}",
                                                        "labeldesk://projects/{project}/classes"}


def test_workspace_resource_names_plan_and_scopes():
    api, _ = api_with()

    body = text_of(api, WORKSPACE_URI)

    assert "demo" in body
    assert "Pro" in body
    assert "read" in body and "write" in body
    assert "Projects: 1" in body


def test_project_resource_carries_class_ids():
    api, _ = api_with()

    body = text_of(api, PROJECT_URI)

    row = next(line for line in body.splitlines() if "cls_box" in line)
    assert "box" in row
    assert "Parcels" in body and "object-detection" in body and "review 1" in body
    assert "s3cr3t" not in body and "settings" not in body and "sha256" not in body and "sig=" not in body


def test_class_resource_matches_the_project_resource_table():
    api, _ = api_with()

    project = text_of(api, PROJECT_URI)
    classes = text_of(api, CLASSES_URI)

    rows = [line for line in project.splitlines() if line.startswith("| `cls_")]
    assert rows, "the project resource rendered no class rows"
    assert rows == [line for line in classes.splitlines() if line.startswith("| `cls_")]


def test_a_big_class_table_keeps_the_most_used_fifty():
    classes = [{"id": f"cls_{i}", "name": f"class-{i}", "color": "#ef4444", "count": i} for i in range(200)]
    api, _ = api_with(lambda request: httpx.Response(200, json={**PROJECT, "classes": classes}))

    body = text_of(api, CLASSES_URI)

    rows = [line for line in body.splitlines() if line.startswith("| `cls_")]
    assert len(rows) == 50
    assert "cls_199" in rows[0] and "cls_150" in rows[-1]
    assert "(+150 more)" in body


# --- the two prompts -----------------------------------------------------------------------

def test_review_prompt_lists_the_low_confidence_images():
    api, _ = api_with()

    prompt = run(api, lambda client: client.get_prompt("review_low_confidence_labels", {"project": "parcels"}))
    message = message_of(prompt)

    assert "low-confidence.jpg" in message
    assert "box" in message and "0.10" in message
    assert "reviewed.jpg" not in message


def test_audit_prompt_counts_the_batch_and_ends_with_the_confirm_step():
    api, seen = api_with()

    prompt = run(api, lambda client: client.get_prompt(
        "audit_unannotated_batch", {"project": "parcels", "batch_id": "batch-7"}))
    message = message_of(prompt).rstrip()

    assert "3" in message
    assert "run `run_auto_label`" in message.lower()
    assert message.endswith("only after the operator confirms the cost.")
    assert {request.method for request in seen} == {"GET"}, "a prompt wrote something"
    asked = [request for request in seen if request.url.path == "/api/v1/projects/parcels/images"]
    assert dict(asked[-1].url.params)["annotated"] == "no"
    assert dict(asked[-1].url.params)["batch_id"] == "batch-7"


def test_prompt_arguments_are_declared():
    api, _ = api_with()

    prompts = {p.name: p for p in run(api, lambda client: client.list_prompts()).prompts}

    review = {arg.name: arg for arg in prompts["review_low_confidence_labels"].arguments}
    assert review["project"].required is True
    assert review["threshold"].required is False and review["limit"].required is False
    assert "0.4" in prompts["review_low_confidence_labels"].description
    assert "20" in prompts["review_low_confidence_labels"].description
    audit = {arg.name: arg for arg in prompts["audit_unannotated_batch"].arguments}
    assert audit["project"].required is True and audit["batch_id"].required is True

    # the SDK refuses before the prompt body runs; its wire message is generic, so the proof is the error itself
    error = failure(api, lambda client: client.get_prompt("review_low_confidence_labels", {}))
    assert error is not None, "a prompt ran without its required argument"


# --- the live layer: a foreign project slug is a 404, not an empty resource ------------------

WS, FOREIGN = "mcp-meta-ws", "mcp-meta-foreign"
FOREIGN_SLUG = "meta-foreign-project"


@pytest.fixture(scope="module")
def live():
    """Workspace A with its own key and one project; workspace B holds the project A must not read."""
    with TestClient(app) as c:
        with SessionLocal() as db:
            owner = User(email="mcp-meta-owner@test.local", name="mcp meta", pw_hash="", email_verified=time.time())
            other = User(email="mcp-meta-other@test.local", name="mcp other", pw_hash="", email_verified=time.time())
            db.add_all([owner, other])
            db.flush()
            ws = Workspace(slug=WS, name="MCP meta", owner_id=owner.id)
            foreign = Workspace(slug=FOREIGN, name="MCP foreign", owner_id=other.id)
            db.add_all([ws, foreign])
            db.flush()
            db.add_all([Member(workspace_id=ws.id, user_id=owner.id, role="admin"),
                        Member(workspace_id=foreign.id, user_id=other.id, role="admin"),
                        Project(workspace_id=foreign.id, slug=FOREIGN_SLUG, name="Foreign", settings={})])
            db.flush()
            set_flag(db, ws.id, "task_992", True)
            db.commit()

        headers = {"Authorization": f"Bearer {issue_access(owner.id)}"}
        key = c.post(f"/api/ws/{WS}/keys", headers=headers, json={"name": "agent", "scopes": ["read"]})
        assert key.status_code == 200, key.text

    # The SDK speaks httpx and starlette's TestClient speaks httpx2, so the live layer drives the
    # same app over a real loopback socket instead of borrowing a transport it cannot share.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "the live layer's server did not start"
    port = server.servers[0].sockets[0].getsockname()[1]
    api = Api(base_url=f"http://127.0.0.1:{port}")
    api.use(key.json()["key"])
    yield api, FOREIGN_SLUG
    server.should_exit = True
    thread.join(10)


def test_a_foreign_project_uri_is_an_error_not_empty(live):
    api, slug = live

    error = failure(api, lambda client: client.read_resource(f"labeldesk://projects/{slug}"))

    assert error is not None, "a foreign project read returned instead of failing"
    assert "project not found" in str(error)
    assert f"labeldesk://projects/{slug}" in str(error)
