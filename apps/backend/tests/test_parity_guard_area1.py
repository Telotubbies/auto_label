"""Parity guard, area 1: workspace, projects and first run.

Pins the shipped behaviour behind the HAVE rows of `docs/research/roboflow-parity/backlog/T-001.md`:
1-F2.1 (type-first creation lands on upload), 1-F3.2 (the sidebar is the lifecycle), 1-F3.3 (four-column
board), 1-F3.4 (counters where the decision is made), 1-F6.1 / 1-F6.2 (folders then projects, designed
empty state). 1-F1.5 (a key's one-time reveal) lives in `test_api_keys_scopes.py`, which owns the key
matrix. Every assertion names the row it protects, so a regression reads as the feature that broke.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    Image,
    LabelClass,
    Member,
    Project,
    User,
    Workspace,
    set_annotations,
)
from app.security import issue_access
from app.services import health

WS = "parity-guard-area1"
FRESH_WS = "parity-guard-area1-fresh"
LIST_WS = "parity-guard-area1-list"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _user(db, email: str) -> User:
    u = User(email=email, name=email.split("@")[0], pw_hash="")
    db.add(u)
    return u


def _project(ws_slug: str, slug: str, name: str, classes: tuple[str, ...] = (),
             images: tuple[tuple[str, str, tuple[str, ...]], ...] = ()) -> None:
    """Seed rows directly: this guard reads what the UI reads, it does not re-test the upload pipeline."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
        p = Project(workspace_id=ws.id, slug=slug, name=name, settings={})
        db.add(p)
        db.flush()
        class_ids = {}
        for i, name_ in enumerate(classes):
            cid = f"{slug}-{i}"
            db.add(LabelClass(id=cid, project_id=p.id, name=name_, color=f"#8b5cf{i}"))
            class_ids[name_] = cid
            db.flush()
        for img_name, status, labels in images:
            # a 10x10 heatmap and class counts need real geometry, so every seed label is a small box
            img = Image(project_id=p.id, name=img_name, sha256=hashlib.sha256(
                f"{slug}/{img_name}".encode()).hexdigest(), width=64, height=48, path=img_name, thumb=img_name,
                status=status)
            db.add(img)
            db.flush()
            if labels:
                set_annotations(db, img, [{"classId": class_ids[label],
                                           "shape": {"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.2, "h": 0.2}}
                                          for label in labels])
        db.commit()


@pytest.fixture(scope="module")
def data(c):
    with SessionLocal() as db:
        admin = _user(db, "area1-admin@test.local")
        outsider = _user(db, "area1-outsider@test.local")
        fresh = _user(db, "area1-fresh@test.local")
        lister = _user(db, "area1-list@test.local")
        db.flush()
        ws = Workspace(slug=WS, name="Area 1 Guard", owner_id=admin.id)
        fresh_ws = Workspace(slug=FRESH_WS, name="Area 1 Fresh", owner_id=fresh.id)
        list_ws = Workspace(slug=LIST_WS, name="Area 1 List", owner_id=lister.id)
        db.add_all([ws, fresh_ws, list_ws])
        db.flush()
        db.add_all([
            Member(workspace_id=ws.id, user_id=admin.id, role="admin"),
            Member(workspace_id=fresh_ws.id, user_id=fresh.id, role="admin"),
            Member(workspace_id=list_ws.id, user_id=lister.id, role="admin"),
        ])
        db.commit()
        ids = {"admin": admin.id, "outsider": outsider.id, "fresh": fresh.id, "list": lister.id}
    # The list project first, so creating the second is the newer row and the touch below is the only
    # thing that can put it back on top.
    _project(LIST_WS, "first-one", "First One", images=(("x.jpg", "unassigned", ()),))
    _project(LIST_WS, "second-one", "Second One")
    return ids


def _headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {issue_access(uid)}"}


def test_project_create_stores_type_group_and_classes_and_lands_a_slug(c, data):
    """1-F2.1: the create modal's answers are stored, the slug is derived, and its classes exist."""
    r = c.post(f"/api/ws/{WS}/projects", headers=_headers(data["admin"]), json={
        "name": "Guard Vehicles", "type": "instance-segmentation",
        "annotation_group": "vehicles", "classes": ["car", "van"]})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["slug"] == "guard-vehicles", "1-F2.1: the project slug is slugified from its name"
    assert p["type"] == "instance-segmentation", "1-F2.1: the chosen type is stored"
    assert p["annotationGroup"] == "vehicles", "1-F2.1: the annotation group is stored"

    classes = c.get(f"/api/ws/{WS}/projects/{p['slug']}/classes", headers=_headers(data["admin"]))
    assert classes.status_code == 200, classes.text
    rows = classes.json()
    assert [x["name"] for x in rows] == ["car", "van"], "1-F2.1: the initial classes are created in order"
    assert all(str(x["color"]).startswith("#") for x in rows), "1-F2.1: every class gets a palette colour"
    assert all(x["count"] == 0 for x in rows), "1-F2.1: a new class counts no annotations"


def test_project_detail_and_analytics_carry_the_counters(c, data, monkeypatch):
    """1-F3.4: the project header counts images, models and statuses; analytics counts the labels."""
    # GET /analytics auto-queues a health scan; the guard runs on a machine with no GPU and no
    # network, so it must not leave that job (or its weight download) for the worker to pick up.
    monkeypatch.setattr(health, "enqueue", lambda *a, **k: None)
    _project(WS, "guard-counters", "Guard Counters", classes=("car", "van"),
             images=(("c1.jpg", "annotating", ("car", "car", "van")),))

    detail = c.get(f"/api/ws/{WS}/projects/guard-counters", headers=_headers(data["admin"]))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["images"] == 1 and body["models"] == 0, "1-F3.4: the header counts this project's rows"
    assert body["statusCounts"] == {"annotating": 1}, "1-F3.4: the status counters come from the image rows"

    a = c.get(f"/api/ws/{WS}/projects/guard-counters/analytics", headers=_headers(data["admin"]))
    assert a.status_code == 200, a.text
    body = a.json()
    assert (body["images"], body["annotations"]) == (1, 3), "1-F3.4: analytics counts images and labels"
    assert len(body["heatmap"]) == 10 and all(len(row) == 10 for row in body["heatmap"]), \
        "1-F3.4: the label heatmap is a 10x10 grid"
    counts = [x["count"] for x in body["classes"]]
    assert counts == sorted(counts, reverse=True), "1-F3.4: classes are ordered by count"
    assert [x["name"] for x in body["classes"]] == ["car", "van"], "1-F3.4: the busiest class leads"


def test_board_has_the_four_statuses_and_a_move_approves(c, data):
    """1-F3.3: Unassigned / Annotating / Review / Dataset, and dropping into Dataset approves."""
    _project(WS, "guard-board", "Guard Board", images=(("b1.jpg", "review", ()),))

    board = c.get(f"/api/ws/{WS}/projects/guard-board/board", headers=_headers(data["admin"]))
    assert board.status_code == 200, board.text
    assert list(board.json()["columns"]) == ["unassigned", "annotating", "review", "done"], \
        "1-F3.3: the board has exactly the four pipeline columns, in pipeline order"

    move = c.post(f"/api/ws/{WS}/projects/guard-board/board/move", headers=_headers(data["admin"]),
                  json={"from_status": "review", "to_status": "done"})
    assert move.status_code == 200, move.text
    assert move.json()["moved"] >= 1, "1-F3.3: the review card moves to Dataset"

    done = c.get(f"/api/ws/{WS}/projects/guard-board/images", params={"status": "done"},
                 headers=_headers(data["admin"]))
    assert done.status_code == 200, done.text
    items = done.json()["items"]
    assert [i["name"] for i in items] == ["b1.jpg"], "1-F3.3: the moved image is now in the done column"
    assert items[0]["review"] == "approved", "1-F3.3: Dataset means approved"


def test_home_is_zeroed_for_a_new_workspace_and_counts_for_a_seeded_one(c, data):
    """1-F6.2 / 1-F6.1: a brand-new workspace answers zeros instead of 404, then counts what it owns."""
    h = c.get(f"/api/ws/{FRESH_WS}/home", headers=_headers(data["fresh"]))
    assert h.status_code == 200, h.text
    body = h.json()
    assert body["stats"] == {"projects": 0, "images": 0, "annotations": 0, "models": 0, "deployments": 0}, \
        "1-F6.2: a workspace with no work answers zeros, not an error"
    assert body["waiting"] == [], "1-F6.2: an empty workspace has nothing waiting"

    _project(FRESH_WS, "fresh-first", "Fresh First", images=(("f1.jpg", "unassigned", ()),))
    body = c.get(f"/api/ws/{FRESH_WS}/home", headers=_headers(data["fresh"])).json()
    assert body["stats"]["projects"] == 1, "1-F6.1: the home counter follows the first project"
    assert body["stats"]["images"] == 1, "1-F6.1: the home counter follows the first image"


def test_projects_list_is_newest_first_and_carries_counts(c, data):
    """1-F6.1: Home lists projects newest-edited first, each with its image/model counts and cover."""
    patch = c.patch(f"/api/ws/{LIST_WS}/projects/first-one", headers=_headers(data["list"]),
                    json={"name": "First One touched"})
    assert patch.status_code == 200, patch.text

    rows = c.get(f"/api/ws/{LIST_WS}/projects", headers=_headers(data["list"])).json()
    assert [r["slug"] for r in rows] == ["first-one", "second-one"], \
        "1-F6.1: the most recently edited project leads the grid"
    assert all({"images", "models", "thumbnail"} <= set(r) for r in rows), \
        "1-F6.1: every card carries its counts and a cover slot"
    assert [r["images"] for r in rows] == [1, 0], "1-F6.1: the image counts are per project"


def test_a_foreign_project_slug_is_404_not_403(c, data):
    """1-F3.2 isolation: a slug from another workspace is not found, never merely refused."""
    r = c.get(f"/api/ws/{WS}/projects/first-one", headers=_headers(data["admin"]))
    assert r.status_code == 404, "1-F3.2: another workspace's slug is not readable through this workspace"

    # and a non-member is refused before any slug is resolved, so the two answers stay distinguishable
    r = c.get(f"/api/ws/{WS}/projects/first-one", headers=_headers(data["outsider"]))
    assert r.status_code == 403, "1-F3.2: a workspace non-member is refused"
