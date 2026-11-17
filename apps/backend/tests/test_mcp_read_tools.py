"""The eight read tools: one page at a time, in the shapes the app's screens already use.

Two layers, because they prove different things. The in-memory layer pins the argument shape, the
paging cap, the sort allow-list and the error mapping; the live layer proves each operation really
exists on the API, resolves ids inside the key's own workspace, and ranks AI work the way the
Dataset screen does.
"""
import asyncio
import json
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

from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, LabelClass, Member, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access
from app.services.flags import set_flag
from labeldesk_mcp import server as mcp_server
from labeldesk_mcp.api import Api

KEY = "ld_live_s3cret_key_do_not_leak"
READ_TOOLS = {"get_project", "list_images", "get_image", "list_versions", "list_models", "get_model",
              "get_job", "list_deployments"}
PAGE = {"total": 1, "items": [{"id": "img_1", "name": "IMG_0001.jpg"}]}


# --- the in-memory layer: arguments, caps, error mapping ------------------------------------

def api_with(handler=None, *, mcp=True):
    """An Api over a MockTransport whose `/whoami` answers this key's scopes and the workspace switch."""
    seen = []

    def transport(request):
        seen.append(request)
        if request.url.path == "/api/v1/whoami":
            return httpx.Response(200, json={"workspace": "demo", "scopes": ["read"], "mcp": mcp})
        return (handler or (lambda r: httpx.Response(200, json=PAGE)))(request)

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use(KEY)
    return api, seen


def call(api, name, args=None):
    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return await client.call_tool(name, args or {})

    return asyncio.run(run())


def tools(api):
    async def run():
        async with Client(mcp_server.build_server(api)) as client:
            return list((await client.list_tools()).tools)

    return asyncio.run(run())


def payload(result):
    return json.loads(result.content[0].text)


def text_of(result):
    return " ".join(block.text for block in result.content)


def test_the_tool_list_is_the_documented_sixteen():
    """T-994 adds the six write/spend tools; this card adds the eight reads, all read-scoped."""
    api, _ = api_with(lambda request: httpx.Response(200, json=[]))

    names = {tool.name for tool in tools(api)}

    assert READ_TOOLS <= names
    for name in READ_TOOLS:
        assert mcp_server.TOOL_SCOPES[name] == "read", name


def test_list_images_passes_every_filter_and_caps_the_page():
    api, seen = api_with()

    result = call(api, "list_images", {
        "project": "parcels", "q": "dent", "split": "train", "status": "review", "class_id": "cls_1",
        "tag": "night", "batch_id": "batch-7", "annotated": "no", "sort": "nonsense", "offset": 40,
        "limit": 1000})

    assert result.is_error is False
    assert payload(result) == PAGE
    request = [r for r in seen if r.url.path == "/api/v1/projects/parcels/images"][-1]
    assert dict(request.url.params) == {
        "q": "dent", "split": "train", "status": "review", "class_id": "cls_1", "tag": "night",
        "batch_id": "batch-7", "annotated": "no", "sort": "newest", "offset": "40", "limit": "200"}
    assert request.headers["x-mcp-tool"] == "list_images"


def test_empty_answers_stay_empty():
    def empty(request):
        return httpx.Response(200, json={"total": 0, "items": []} if request.url.path.endswith("/images") else [])

    api, _ = api_with(empty)

    assert payload(call(api, "list_images", {"project": "fresh"})) == {"total": 0, "items": []}
    assert call(api, "list_versions", {"project": "fresh"}).content == []
    assert call(api, "list_models").content == []


def test_an_unknown_slug_is_a_tool_error():
    api, _ = api_with(lambda request: httpx.Response(404, json={"detail": "project not found"}))

    result = call(api, "get_project", {"project": "no-such-project"})

    assert result.is_error is True
    assert "project not found (HTTP 404)" in text_of(result)


def test_results_are_scrubbed():
    row = {"id": "prj_1", "slug": "parcels", "classes": [], "settings": {"webhook_secret": "s3cr3t"}}
    api, _ = api_with(lambda request: httpx.Response(200, json=row))

    result = call(api, "get_project", {"project": "parcels"})

    dumped = json.dumps([block.text for block in result.content])
    assert "s3cr3t" not in dumped
    assert "settings" not in dumped
    assert json.loads(result.content[0].text)["slug"] == "parcels"


def test_every_read_tool_is_read_only():
    api, _ = api_with(lambda request: httpx.Response(200, json={}))

    listed = {tool.name: tool for tool in tools(api)}

    for name in READ_TOOLS:
        tool = listed[name]
        wire = tool.model_dump(by_alias=True)
        assert wire["annotations"]["readOnlyHint"] is True, name
        assert "confirm" not in (wire["inputSchema"].get("properties") or {}), name


def test_the_workspace_switch_refuses_before_the_api():
    api, seen = api_with(mcp=False)

    result = call(api, "get_project", {"project": "parcels"})

    assert result.is_error is True
    assert "the MCP endpoint is not enabled for this workspace" in text_of(result)
    assert [r.url.path for r in seen] == ["/api/v1/whoami"]


# --- the live layer: the operations exist and stay inside the key's workspace ---------------

WS, OTHER = "mcp-read-ws", "mcp-read-other"
BOX = {"id": "ann-1", "classId": None, "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}}


@pytest.fixture(scope="module")
def live():
    """One workspace with two annotated images, a ready model and a live alias; a second to be foreign."""
    with TestClient(app) as c:
        with SessionLocal() as db:
            owner = User(email="mcp-read-owner@test.local", name="mcp read", pw_hash="", email_verified=time.time())
            outsider = User(email="mcp-read-outsider@test.local", name="outsider", pw_hash="", email_verified=time.time())
            db.add_all([owner, outsider])
            db.flush()
            ws = Workspace(slug=WS, name="MCP read", owner_id=owner.id)
            other = Workspace(slug=OTHER, name="MCP foreign", owner_id=outsider.id)
            db.add_all([ws, other])
            db.flush()
            db.add_all([Member(workspace_id=ws.id, user_id=owner.id, role="admin"),
                        Member(workspace_id=other.id, user_id=outsider.id, role="admin")])
            parcels = Project(workspace_id=ws.id, slug="parcels", name="Parcels", settings={})
            foreign = Project(workspace_id=other.id, slug="foreign", name="Foreign", settings={})
            db.add_all([parcels, foreign])
            db.flush()
            box = LabelClass(project_id=parcels.id, name="box", color="#ef4444")
            dent = LabelClass(project_id=parcels.id, name="dent", color="#22c55e")
            theirs = LabelClass(project_id=foreign.id, name="other", color="#3b82f6")
            db.add_all([box, dent, theirs])
            db.flush()
            # the low-confidence AI image is the OLDER one: `review` must outrank `newest` for it to come first
            low = Image(project_id=parcels.id, name="low-confidence.jpg", sha256="a" * 64, width=64, height=64,
                        path="low.jpg", thumb="low.jpg", status="annotating", created=time.time() - 60)
            high = Image(project_id=parcels.id, name="reviewed.jpg", sha256="b" * 64, width=64, height=64,
                         path="high.jpg", thumb="high.jpg", status="review", created=time.time())
            db.add_all([low, high])
            db.flush()
            v1 = Version(project_id=parcels.id, number=1, name="parcels v1", status="ready")
            v2 = Version(project_id=foreign.id, number=1, name="foreign v1", status="ready")
            db.add_all([v1, v2])
            db.flush()
            model = TrainedModel(workspace_id=ws.id, project_id=parcels.id, version_id=v1.id, name="parcels-ready",
                                 arch="yolo26n", task="detect", status="ready")
            foreign_model = TrainedModel(workspace_id=other.id, project_id=foreign.id, version_id=v2.id,
                                         name="foreign-ready", arch="yolo26n", task="detect", status="ready")
            job = Job(workspace_id=ws.id, project_id=parcels.id, kind="export", status="done")
            foreign_job = Job(workspace_id=other.id, project_id=foreign.id, kind="export", status="done")
            db.add_all([model, foreign_model, job, foreign_job])
            db.flush()
            set_flag(db, ws.id, "task_992", True)
            ids = {"low": low.id, "high": high.id, "box": box.id, "dent": dent.id, "version": v1.id,
                   "model": model.id, "foreign_model": foreign_model.id, "job": job.id,
                   "foreign_job": foreign_job.id}
            db.commit()

        headers = {"Authorization": f"Bearer {issue_access(owner.id)}"}
        for image_id, annotations in (
            (ids["high"], [
                {**BOX, "classId": ids["box"]},
                {**BOX, "id": "ann-2", "classId": ids["dent"], "shape": {"kind": "bbox", "x": 0.5, "y": 0.5,
                                                                        "w": 0.2, "h": 0.2}},
            ]),
            (ids["low"], [
                {**BOX, "id": "ann-3", "classId": ids["box"], "source": "model", "confidence": 0.1},
            ]),
        ):
            r = c.put(f"/api/images/{image_id}/annotations", headers=headers, json={"annotations": annotations})
            assert r.status_code == 200, r.text

        r = c.put(f"/api/ws/{WS}/projects/parcels/deployments/production", headers=headers,
                  json={"model_id": ids["model"]})
        assert r.status_code == 200, r.text

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
    yield api, ids
    server.should_exit = True
    thread.join(10)


def test_get_project_returns_classes_with_ids_and_counts(live):
    api, ids = live

    result = call(api, "get_project", {"project": "parcels"})

    assert result.is_error is False
    project = payload(result)
    assert {c["id"] for c in project["classes"]} >= {ids["box"], ids["dent"]}
    assert project["statusCounts"] == {"annotating": 1, "review": 1}
    assert project["images"] == 2 and project["models"] == 1


def test_get_image_returns_annotations_with_class_ids(live):
    api, ids = live

    result = call(api, "get_image", {"image_id": ids["high"]})

    assert result.is_error is False
    image = payload(result)
    assert image["id"] == ids["high"]
    assert {a["classId"] for a in image["annotations"]} == {ids["box"], ids["dent"]}
    assert {a["shape"]["kind"] for a in image["annotations"]} == {"bbox"}
    assert {a["source"] for a in image["annotations"]} == {"human"}


def test_search_by_review_sort_reaches_the_ranking(live):
    api, ids = live

    review = payload(call(api, "list_images", {"project": "parcels", "sort": "review"}))
    newest = payload(call(api, "list_images", {"project": "parcels", "sort": "newest"}))

    assert review["total"] == 2
    assert [item["id"] for item in review["items"]][0] == ids["low"]
    assert [item["id"] for item in newest["items"]][0] == ids["high"]


def test_list_versions_and_models_answer_on_the_live_api(live):
    api, ids = live

    versions = call(api, "list_versions", {"project": "parcels"})
    models = call(api, "list_models")

    assert versions.is_error is False
    assert [json.loads(block.text)["id"] for block in versions.content] == [ids["version"]]
    assert "settings" not in json.dumps([block.text for block in versions.content])
    assert models.is_error is False
    assert [json.loads(block.text)["id"] for block in models.content] == [ids["model"]]


def test_a_foreign_model_id_is_a_404_tool_error(live):
    api, ids = live

    model = call(api, "get_model", {"model_id": ids["foreign_model"]})
    job = call(api, "get_job", {"job_id": ids["foreign_job"]})

    assert model.is_error is True
    assert "model not found (HTTP 404)" in text_of(model)
    assert job.is_error is True
    assert "job not found (HTTP 404)" in text_of(job)


def test_list_deployments_returns_aliases(live):
    api, ids = live

    result = call(api, "list_deployments")

    assert result.is_error is False
    projects = payload(result)["projects"]
    assert {p["slug"] for p in projects} == {"parcels"}
    alias = next(a for a in projects[0]["aliases"] if a["alias"] == "production")
    assert alias["model_id"] == ids["model"]
    assert alias["model_name"] == "parcels-ready"
