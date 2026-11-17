"""The six write and spend tools: one confirm gate, the API's own validation, no fetch in this process.

Two layers, because they prove different things. The in-memory layer pins the gate, the argument
shapes, the scope filter and the multipart body; the live layer proves the real charges, the 402 that
names the plan, and that ids resolve inside the key's own workspace.
"""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs

REPO_ROOT = Path(__file__).resolve().parents[3]
for _path in (REPO_ROOT / "apps" / "mcp", REPO_ROOT / "packages" / "sdk"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from mcp.client import Client

from app.config import PLANS
from app.db import SessionLocal
from app.main import app
from app.models import Image, LabelClass, Member, Project, User, Workspace
from app.security import issue_access
from app.services.flags import set_flag
from labeldesk_mcp import server as mcp_server
from labeldesk_mcp.api import Api

KEY = "ld_live_write_s3cret_key_do_not_leak"
WRITE_TOOLS = ("upload_image_url", "write_annotations", "run_auto_label", "create_version",
               "start_training", "predict_image")
ALL_SCOPES = ("read", "upload", "write", "train", "infer")
NEXT = "call again with confirm: true"
URL = "https://images.example.test/parts/dent-01.jpg"


def box(x: float, class_id: str, ident: str) -> dict:
    return {"id": ident, "classId": class_id,
            "shape": {"kind": "bbox", "x": x, "y": 0.1, "w": 0.2, "h": 0.2}}


# --- the in-memory layer: the gate, the arguments, the scope filter -------------------------

def api_with(handler=None, *, scopes=ALL_SCOPES, mcp=True):
    """An Api over a MockTransport whose `/whoami` answers this key's scopes and the workspace switch."""
    seen = []

    def transport(request):
        seen.append(request)
        if request.url.path == "/api/v1/whoami":
            return httpx.Response(200, json={"workspace": "demo", "scopes": list(scopes), "mcp": mcp})
        return (handler or read_only)(request)

    api = Api(base_url="http://labeldesk.test", transport=httpx.MockTransport(transport))
    api.use(KEY)
    return api, seen


def read_only(request):
    """The cheap reads a dry run makes: one annotated image and a counted image page."""
    if request.url.path.startswith("/api/v1/images/"):
        return httpx.Response(200, json={"id": "img_1", "annotations": [box(0.1, "cls_1", "a1"),
                                                                       box(0.4, "cls_1", "a2")]})
    if request.url.path.endswith("/images"):
        return httpx.Response(200, json={"total": 4, "items": []})
    return httpx.Response(200, json={})


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


def dry_calls(api):
    """One realistic call per tool, none of them confirmed."""
    return {
        "upload_image_url": {"project": "parcels", "url": URL},
        "write_annotations": {"image_id": "img_1", "annotations": [box(0.1, "cls_1", "n1"),
                                                                  box(0.2, "cls_1", "n2"),
                                                                  box(0.3, "cls_1", "n3")]},
        "run_auto_label": {"project": "parcels", "model_id": "mdl_1"},
        "create_version": {"project": "parcels", "name": "parcels v2"},
        "start_training": {"project": "parcels", "version_id": "ver_1"},
        "predict_image": {"model_id": "mdl_1", "image_id": "img_1"},
    }


def test_no_spend_tool_acts_without_confirm():
    api, seen = api_with()

    for name, args in dry_calls(api).items():
        result = call(api, name, args)

        assert result.is_error is False, name
        body = payload(result)
        assert body["dryRun"] is True, name
        assert body["tool"] == name, name
        assert isinstance(body["estimatedCredits"], (int, float)), name
        assert body["next"] == NEXT, name

    assert [r.method for r in seen if r.method in ("POST", "PUT", "PATCH")] == []


def test_write_annotations_with_confirm_sends_the_put():
    def handler(request):
        if request.method == "PUT":
            return httpx.Response(200, json={"saved": 3, "status": "annotating"})
        return read_only(request)

    api, seen = api_with(handler)

    result = call(api, "write_annotations", {
        "image_id": "img_1", "confirm": True,
        "annotations": [box(0.1, "cls_1", "n1"), box(0.2, "cls_1", "n2"), box(0.3, "cls_1", "n3")]})

    assert result.is_error is False
    assert payload(result) == {"saved": 3, "status": "annotating"}
    put = [r for r in seen if r.method == "PUT"][-1]
    assert put.url.path == "/api/v1/images/img_1/annotations"
    assert [a["id"] for a in json.loads(put.content)["annotations"]] == ["n1", "n2", "n3"]


def test_a_spend_tool_the_key_cannot_use_is_absent():
    api, _ = api_with(scopes=("read", "upload"))

    names = {tool.name for tool in tools(api)}

    assert "upload_image_url" in names
    assert "start_training" not in names
    assert "write_annotations" not in names


def test_upload_image_url_sends_the_url_not_the_bytes():
    api, seen = api_with()
    api.me()                       # the scope filter's own whoami, cached for this request
    seen.clear()

    result = call(api, "upload_image_url", {"project": "parcels", "url": URL, "confirm": True})

    assert result.is_error is False
    assert len(seen) == 1, [r.url.path for r in seen]
    request = seen[0]
    assert request.url.path == "/api/v1/demo/parcels/upload"
    body = request.content.decode()
    assert parse_qs(body)["image"] == [URL]
    assert "filename=" not in body


def test_predict_image_refuses_two_sources():
    api, seen = api_with()

    result = call(api, "predict_image", {"model_id": "mdl_1", "image_id": "img_1", "image_url": URL})

    assert result.is_error is True
    text = text_of(result)
    assert "image_id" in text and "image_url" in text
    assert [r.method for r in seen if r.method in ("POST", "PUT", "PATCH")] == []


def test_no_tool_can_delete_anything():
    api, _ = api_with()

    names = {tool.name for tool in tools(api)}

    assert set(WRITE_TOOLS) <= names
    assert not [name for name in names if any(word in name for word in ("delete", "remove", "destroy", "drop"))]


def test_write_tools_carry_the_right_annotations():
    api, _ = api_with()

    listed = {tool.name: tool.model_dump(by_alias=True) for tool in tools(api)}

    for name in WRITE_TOOLS:
        assert listed[name]["annotations"]["readOnlyHint"] is False, name
        assert "confirm" in (listed[name]["inputSchema"].get("properties") or {}), name
    destructive = [name for name in WRITE_TOOLS if listed[name]["annotations"].get("destructiveHint") is True]
    assert destructive == ["write_annotations"]


def test_a_write_key_gets_the_routes_403():
    def handler(request):
        if request.url.path.endswith("/train"):
            return httpx.Response(403, json={"detail": "api_key lacks the 'train' scope"})
        return read_only(request)

    api, _ = api_with(handler, scopes=("read", "write"))

    result = call(api, "start_training", {"project": "parcels", "version_id": "ver_1", "confirm": True})

    assert result.is_error is True
    assert "api_key lacks the 'train' scope (HTTP 403)" in text_of(result)


# --- the live layer: the real writes, the real charges, the workspace boundary --------------

WS, OTHER = "mcp-write-ws", "mcp-write-other"


@pytest.fixture(scope="module")
def live():
    """One workspace with four unannotated images, a two-box image and a foreign one; a second workspace."""
    with TestClient(app) as c:
        with SessionLocal() as db:
            owner = User(email="mcp-write-owner@test.local", name="mcp write", pw_hash="", email_verified=time.time())
            outsider = User(email="mcp-write-outsider@test.local", name="outsider", pw_hash="",
                            email_verified=time.time())
            db.add_all([owner, outsider])
            db.flush()
            ws = Workspace(slug=WS, name="MCP write", owner_id=owner.id)
            other = Workspace(slug=OTHER, name="MCP foreign", owner_id=outsider.id)
            db.add_all([ws, other])
            db.flush()
            db.add_all([Member(workspace_id=ws.id, user_id=owner.id, role="admin"),
                        Member(workspace_id=other.id, user_id=outsider.id, role="admin")])
            parcels = Project(workspace_id=ws.id, slug="parcels", name="Parcels", settings={})
            foreign = Project(workspace_id=other.id, slug="foreign", name="Foreign", settings={})
            db.add_all([parcels, foreign])
            db.flush()
            box_cls = LabelClass(project_id=parcels.id, name="box", color="#ef4444")
            dent_cls = LabelClass(project_id=parcels.id, name="dent", color="#22c55e")
            their_cls = LabelClass(project_id=foreign.id, name="other", color="#3b82f6")
            db.add_all([box_cls, dent_cls, their_cls])
            db.flush()
            blanks = [Image(project_id=parcels.id, name=f"blank-{i}.jpg", sha256=f"{i}" * 64, width=64, height=64,
                            path=f"blank-{i}.jpg", thumb=f"blank-{i}.jpg", status="unassigned", created=time.time() + i)
                      for i in range(4)]
            two = Image(project_id=parcels.id, name="two-boxes.jpg", sha256="c" * 64, width=64, height=64,
                        path="two.jpg", thumb="two.jpg", status="annotating", created=time.time())
            theirs = Image(project_id=foreign.id, name="theirs.jpg", sha256="d" * 64, width=64, height=64,
                           path="theirs.jpg", thumb="theirs.jpg", status="unassigned")
            db.add_all([*blanks, two, theirs])
            db.flush()
            set_flag(db, ws.id, "task_992", True)
            ids = {"two": two.id, "foreign": theirs.id, "box": box_cls.id, "dent": dent_cls.id,
                   "their_class": their_cls.id, "blanks": [b.id for b in blanks]}
            db.commit()

        headers = {"Authorization": f"Bearer {issue_access(owner.id)}"}
        r = c.put(f"/api/images/{ids['two']}/annotations", headers=headers,
                  json={"annotations": [box(0.1, ids["box"], "old-1"), box(0.5, ids["dent"], "old-2")]})
        assert r.status_code == 200, r.text
        keys = {}
        for name, scopes in (("agent", ALL_SCOPES), ("writer", ["read", "write"])):
            made = c.post(f"/api/ws/{WS}/keys", headers=headers, json={"name": name, "scopes": scopes})
            assert made.status_code == 200, made.text
            keys[name] = made.json()["key"]

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

    def api_for(name="agent"):
        made = Api(base_url=f"http://127.0.0.1:{port}")
        made.use(keys[name])
        return made

    yield api_for, ids
    server.should_exit = True
    thread.join(10)


def image_of(api, image_id):
    return api.call("get_image", "get_image", path_params={"image_id": image_id})


def test_write_annotations_dry_run_counts_the_replacement(live):
    api_for, ids = live
    api = api_for()

    result = call(api, "write_annotations", {
        "image_id": ids["two"], "annotations": [box(0.1, ids["box"], "n1"), box(0.2, ids["dent"], "n2"),
                                                box(0.3, ids["box"], "n3")]})

    assert result.is_error is False
    dry = payload(result)
    assert dry["wouldReplace"] == 2
    assert dry["wouldSave"] == 3
    assert len(image_of(api, ids["two"])["annotations"]) == 2


def test_write_annotations_with_confirm_replaces_the_set(live):
    api_for, ids = live
    api = api_for()

    first = call(api, "write_annotations", {
        "image_id": ids["two"], "confirm": True,
        "annotations": [box(0.1, ids["box"], "n1"), box(0.2, ids["dent"], "n2"), box(0.3, ids["box"], "n3")]})
    second = call(api, "write_annotations", {
        "image_id": ids["two"], "confirm": True, "annotations": [box(0.4, ids["dent"], "n4")]})

    assert first.is_error is False, text_of(first)
    assert payload(first)["saved"] == 3
    assert second.is_error is False, text_of(second)
    assert payload(second)["saved"] == 1
    assert [a["id"] for a in image_of(api, ids["two"])["annotations"]] == ["n4"]


def test_an_annotation_with_a_foreign_class_is_the_apis_400(live):
    api_for, ids = live

    result = call(api_for(), "write_annotations", {
        "image_id": ids["two"], "confirm": True, "annotations": [box(0.1, ids["their_class"], "x1")]})

    assert result.is_error is True
    assert "annotation class does not belong to this project (HTTP 400)" in text_of(result)


def test_a_foreign_image_id_is_a_404(live):
    api_for, ids = live

    result = call(api_for(), "write_annotations", {
        "image_id": ids["foreign"], "confirm": True, "annotations": [box(0.1, ids["box"], "x1")]})

    assert result.is_error is True
    assert "image not found (HTTP 404)" in text_of(result)


def test_run_auto_label_dry_run_estimates_the_bill(live):
    api_for, ids = live

    result = call(api_for(), "run_auto_label", {"project": "parcels", "model_id": "mdl_1"})

    assert result.is_error is False
    dry = payload(result)
    assert dry["estimatedImages"] == 4
    assert dry["estimatedCredits"] == 0.04


def test_create_version_dry_run_then_the_real_charge_and_the_402(live):
    api_for, ids = live
    api = api_for()

    dry = payload(call(api, "create_version", {"project": "parcels", "name": "parcels v1"}))
    assert dry["estimatedCredits"] == 0.5
    assert dry["estimatedImages"] == 5

    made = call(api, "create_version", {"project": "parcels", "name": "parcels v1", "confirm": True})
    assert made.is_error is False, text_of(made)
    assert payload(made)["number"] == 1

    with SessionLocal() as db:
        ws = db.query(Workspace).filter(Workspace.slug == WS).one()
        saved, period = ws.credits_used, ws.credits_period
        ws.credits_used, ws.credits_period = PLANS["free"]["credits"], time.strftime("%Y-%m")
        db.commit()
    try:
        broke = call(api, "create_version", {"project": "parcels", "name": "parcels v2", "confirm": True})
        assert broke.is_error is True
        assert "monthly credit limit reached on the Free plan (HTTP 402)" in text_of(broke)
    finally:
        with SessionLocal() as db:
            ws = db.query(Workspace).filter(Workspace.slug == WS).one()
            ws.credits_used, ws.credits_period = saved, period
            db.commit()


def test_a_bad_shape_is_the_apis_field_message(live):
    api_for, ids = live

    result = call(api_for(), "write_annotations", {
        "image_id": ids["two"], "confirm": True,
        "annotations": [{"id": "bad-1", "classId": ids["box"], "shape": {"kind": "bbox", "x": 0.1}}]})

    assert result.is_error is True
    assert "bbox needs normalised numeric x,y,w,h (HTTP 400)" in text_of(result)


def test_auto_label_without_a_model_names_the_fix(live):
    api_for, ids = live

    result = call(api_for(), "run_auto_label", {"project": "parcels", "confirm": True})

    assert result.is_error is True
    assert "choose a trained model (HTTP 400)" in text_of(result)


def test_auto_label_with_no_ai_call_allowance_is_the_apis_402(live):
    from app.models import TrainedModel, Version

    api_for, ids = live
    with SessionLocal() as db:
        ws = db.query(Workspace).filter(Workspace.slug == WS).one()
        v = Version(project_id=db.query(Project).filter(Project.slug == "parcels").one().id, number=99, name="v99")
        db.add(v)
        db.flush()
        model = TrainedModel(workspace_id=ws.id, project_id=v.project_id, version_id=v.id, name="ready",
                             arch="yolo26n", task="detect", status="ready")
        db.add(model)
        saved, ws.quotas = ws.quotas, {"ai_calls": 0}
        db.commit()
        model_id = model.id
    try:
        result = call(api_for(), "run_auto_label", {"project": "parcels", "model_id": model_id, "confirm": True})
        assert result.is_error is True
        assert "AI calls quota reached on the Free plan (HTTP 402)" in text_of(result)
    finally:
        with SessionLocal() as db:
            ws = db.query(Workspace).filter(Workspace.slug == WS).one()
            ws.quotas = saved
            db.commit()
