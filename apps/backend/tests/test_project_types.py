"""T-017 — eight project types with outcome wording, plus "ask for another".

The eight ids are the contract the New project grid sends. The words on the cards live in
`apps/frontend/src/features/project/projectTypes.ts` and are pinned by
`apps/frontend/tests/project-types.test.mjs`; this module pins the server half: which ids create,
what `multi-label-classification` sets, and the wish-list route that writes one audit row.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, Project, Workspace, WorkspaceFlag
from app.services import flags
from conftest import login

WS = "labeldesk-demo"
EIGHT = (
    "object-detection", "instance-segmentation", "semantic-segmentation", "classification",
    "multi-label-classification", "keypoint-detection", "action-recognition", "anomaly-detection",
)
# The five that existed before this card: four original types plus the anomaly station.
ORIGINAL = ("object-detection", "instance-segmentation", "classification", "keypoint-detection",
            "anomaly-detection")
NEW = ("semantic-segmentation", "multi-label-classification", "action-recognition")


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _set_flag(key: str, enabled: bool) -> None:
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), key, enabled)
        db.commit()


def _type_request_rows(workspace_id: str | None = None) -> list[Audit]:
    with SessionLocal() as db:
        return list(db.scalars(select(Audit).where(
            Audit.workspace_id == (workspace_id or _ws_id()),
            Audit.action == "project.type_request").order_by(Audit.created)))


def _create(c: TestClient, type_id: str):
    """One project per type; the unique suffix keeps two runs of this module from colliding."""
    return c.post(f"/api/ws/{WS}/projects",
                  json={"name": f"T017 {type_id} {uuid.uuid4().hex[:8]}", "type": type_id})


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture(scope="module", autouse=True)
def _headroom_and_flags():
    """The Free plan holds three projects, and anomaly needs its own station flag on."""
    with SessionLocal() as db:
        ws = db.get(Workspace, _ws_id())
        before = ws.plan
        ws.plan = "pro"
        db.commit()
    _set_flag("task_a1_types", True)
    _set_flag("task_29", True)
    yield
    with SessionLocal() as db:
        db.get(Workspace, _ws_id()).plan = before
        for p in db.scalars(select(Project).where(Project.workspace_id == _ws_id(),
                                                  Project.slug.like("t017-%"),
                                                  Project.deleted_at.is_(None))):
            p.deleted_at = time.time()
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key.in_(
            ("task_a1_types", "task_29")), WorkspaceFlag.workspace_id == _ws_id()))
        db.commit()


def test_eight_types_are_accepted(c):
    for type_id in EIGHT:
        r = _create(c, type_id)
        assert r.status_code == 200, f"{type_id}: {r.status_code} {r.text}"
        assert r.json()["type"] == type_id


def test_multi_label_type_sets_the_flag(c):
    multi = _create(c, "multi-label-classification")
    assert multi.status_code == 200, multi.text
    assert multi.json()["multilabel"] is True

    single = _create(c, "classification")
    assert single.status_code == 200, single.text
    assert single.json()["multilabel"] is False


def test_unknown_type_is_refused_with_the_list(c):
    r = c.post(f"/api/ws/{WS}/projects",
               json={"name": f"T017 obb {uuid.uuid4().hex[:8]}", "type": "obb"})

    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "obb" not in detail.split("one of")[-1]
    for type_id in EIGHT:
        assert type_id in detail, f"the refusal must name {type_id}"


def test_type_request_writes_one_audit_row(c):
    before = _type_request_rows()
    r = c.post(f"/api/ws/{WS}/type-requests",
               json={"wanted": "Count fish in a pond", "example": "night camera on the north bank"})

    assert r.status_code == 201, r.text
    rows = _type_request_rows()
    assert len(rows) == len(before) + 1, rows
    row = rows[-1]
    assert row.action == "project.type_request"
    assert row.target == "Count fish in a pond"
    assert row.meta["example"] == "night camera on the north bank"


def test_blank_type_request_is_422(c):
    before = len(_type_request_rows())
    for body in ({"wanted": ""}, {"wanted": "   "}, {}):
        assert c.post(f"/api/ws/{WS}/type-requests", json=body).status_code == 422, body
    assert len(_type_request_rows()) == before


def test_type_request_is_cross_workspace_404(c):
    # A slug that is not a workspace answers 404 and never says whether one exists.
    assert c.post("/api/ws/t017-no-such-workspace/type-requests",
                  json={"wanted": "seals"}).status_code == 404

    # A real other tenant stays unreachable (the platform rule, T-1304) and gets no audit row.
    other = TestClient(app)
    signup = other.post("/api/auth/signup", json={
        "name": "Type Outsider", "email": f"t017-{uuid.uuid4().hex[:8]}@x.io", "password": "longenough1",
    }).json()
    headers = {"Authorization": f"Bearer {signup['token']}"}
    other_slug = other.get("/api/me", headers=headers).json()["workspaces"][0]["slug"]
    with SessionLocal() as db:
        other_id = db.scalar(select(Workspace.id).where(Workspace.slug == other_slug))

    refused = c.post(f"/api/ws/{other_slug}/type-requests", json={"wanted": "seals"})
    assert refused.status_code in (403, 404), refused.text
    assert _type_request_rows(other_id) == []


def test_flag_off_keeps_five_types(c):
    _set_flag("task_a1_types", False)
    try:
        for type_id in ORIGINAL:
            r = _create(c, type_id)
            assert r.status_code == 200, f"{type_id} must still create: {r.status_code} {r.text}"
        for type_id in NEW:
            r = _create(c, type_id)
            assert r.status_code == 400, f"{type_id} must be refused: {r.status_code} {r.text}"
            assert type_id not in r.json()["detail"].split("one of")[-1]
    finally:
        _set_flag("task_a1_types", True)
