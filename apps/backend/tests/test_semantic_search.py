"""Task 27: semantic image search over Task 20a's CLIP features and saved collections."""

import hashlib
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-semantic-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Image, ImageClass, LabelClass, Project, User, Workspace
from app.security import issue_access
from app.services import collections as collection_service
from app.services import insights_embedding, semantic_search

WS = "labeldesk-demo"
SLUG = "semantic-qa"
OTHER = "semantic-other"
BASE = f"/api/ws/{WS}/projects/{SLUG}"
OTHER_BASE = f"/api/ws/{WS}/projects/{OTHER}"
FLAG = "task_27"


@pytest.fixture(scope="module")
def client():
    with TestClient(app):
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield c


@pytest.fixture(scope="module")
def labeler_client(client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
    yield c


@pytest.fixture(autouse=True)
def _flag_on(client):
    client.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    yield


def seed_image(pid: str, name: str, *, sha: str, split: str = "train", tags: list[str] | None = None,
               class_id: str | None = None, assigned: str | None = None, status: str = "done",
               review: str | None = None, created: float | None = None) -> str:
    shape = {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    anns = [{"id": f"{name}-a", "classId": class_id, "shape": shape}] if class_id else []
    with SessionLocal() as db:
        row = Image(project_id=pid, name=name, sha256=sha, width=640, height=480, path=f"semantic/{name}",
                    thumb=f"semantic/{name}", split=split, tags=tags or [], annotations=anns,
                    n_annotations=len(anns), assignee_id=assigned, status=status, review=review)
        if created is not None:
            row.created = created
        db.add(row)
        db.flush()
        if class_id:
            db.add(ImageClass(image_id=row.id, class_id=class_id, project_id=pid, n=1))
        db.commit()
        return row.id


@pytest.fixture(scope="module")
def data():
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        project = Project(workspace_id=ws.id, slug=SLUG, name="Semantic QA", settings={})
        other = Project(workspace_id=ws.id, slug=OTHER, name="Semantic Other", settings={})
        db.add_all([project, other])
        db.flush()
        person = LabelClass(project_id=project.id, name="person", color="#8b5cf6")
        car = LabelClass(project_id=project.id, name="car", color="#22c55e")
        db.add_all([person, car])
        db.commit()
        ids = {"project": project.id, "other": other.id, "person": person.id, "car": car.id,
               "labeler": labeler.id}
    ids["a"] = seed_image(ids["project"], "a-red-helmet.jpg", sha=hashlib.sha256(b"a").hexdigest(), tags=["ppe"],
                          class_id=ids["person"], review="approved", created=1_700_000_001)
    ids["b"] = seed_image(ids["project"], "b-blue-car.jpg", sha=hashlib.sha256(b"b").hexdigest(), split="valid",
                          tags=["vehicle"], class_id=ids["car"], created=1_700_000_002)
    ids["c"] = seed_image(ids["project"], "c-green-dog.jpg", sha=hashlib.sha256(b"c").hexdigest(), split="test",
                          class_id=None, created=1_700_000_003)
    ids["d"] = seed_image(ids["project"], "d-unindexed.jpg", sha=hashlib.sha256(b"d").hexdigest(), split="train",
                          created=1_700_000_004)
    ids["e"] = seed_image(ids["project"], "e-labeled.jpg", sha=hashlib.sha256(b"e").hexdigest(), split="train",
                          class_id=ids["car"], assigned=ids["labeler"], created=1_700_000_005)
    ids["other_img"] = seed_image(ids["other"], "z-other.jpg", sha=hashlib.sha256(b"z").hexdigest())

    vectors = {"a": [1.0, 0.0, 0.0], "b": [0.8, 0.6, 0.0], "e": [0.7, 0.7, 0.0], "c": [0.0, 1.0, 0.0],
               "other_img": [1.0, 0.0, 0.0]}
    shas = {"a": hashlib.sha256(b"a").hexdigest(), "b": hashlib.sha256(b"b").hexdigest(),
            "c": hashlib.sha256(b"c").hexdigest(), "e": hashlib.sha256(b"e").hexdigest(),
            "other_img": hashlib.sha256(b"z").hexdigest()}
    for key, vector in vectors.items():
        insights_embedding._store_feature("clip", shas[key], np.asarray(vector, dtype=np.float32))
    return ids


def text_vec(vector=(1.0, 0.0, 0.0)):
    def fake(_query: str):
        return np.asarray(vector, dtype=np.float32)

    return fake


def search(client: TestClient, query: str = "", **params) -> dict:
    r = client.get(f"{BASE}/search", params={"q": query, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_semantic_ranking_uses_task_20a_cached_features(client, data, monkeypatch):
    monkeypatch.setattr(semantic_search, "embed_text", text_vec())
    body = search(client, "red helmet")
    assert body["mode"] == "semantic"
    assert body["total"] == 5
    assert body["indexed"] == 4
    assert body["missing"] == 1
    names = [item["name"] for item in body["items"]]
    assert names[:3] == ["a-red-helmet.jpg", "b-blue-car.jpg", "e-labeled.jpg"]
    assert body["items"][0]["score"] == pytest.approx(1.0)
    assert body["items"][0]["thumbnail"]
    assert "d-unindexed.jpg" not in names
    assert [c["name"] for c in body["facets"]["classes"]] == ["person", "car"]
    assert set(body["facets"]["tags"]) == {"ppe", "vehicle"}


def test_metadata_filters_apply_before_ranking(client, data, monkeypatch):
    monkeypatch.setattr(semantic_search, "embed_text", text_vec())
    by_class = search(client, "red helmet", class_id=data["car"])
    assert [i["name"] for i in by_class["items"]] == ["b-blue-car.jpg", "e-labeled.jpg"]
    by_tag = search(client, "red helmet", tag="ppe")
    assert [i["name"] for i in by_tag["items"]] == ["a-red-helmet.jpg"]
    annotated = search(client, "red helmet", split="train", annotated="yes")
    assert [i["name"] for i in annotated["items"]] == ["a-red-helmet.jpg", "e-labeled.jpg"]


def test_search_degrades_to_filtered_browse_without_clip(client, data, monkeypatch):
    def unavailable(_query: str):
        raise RuntimeError("CLIP embeddings are not available")

    monkeypatch.setattr(semantic_search, "embed_text", unavailable)
    body = search(client, "red helmet", split="train")
    assert body["mode"] == "filter"
    assert "CLIP" in body["reason"]
    assert [i["name"] for i in body["items"]] == ["e-labeled.jpg", "a-red-helmet.jpg"]
    assert all(i["score"] is None for i in body["items"])


def test_blank_query_browses_the_filtered_dataset(client, data, monkeypatch):
    monkeypatch.setattr(semantic_search, "embed_text", text_vec())
    body = search(client)
    assert body["mode"] == "browse"
    assert body["total"] == 5
    assert [i["name"] for i in body["items"]][:2] == ["e-labeled.jpg", "d-unindexed.jpg"]
    assert body["items"][0]["score"] is None


def test_labeler_only_searches_assigned_images(labeler_client, data, monkeypatch):
    monkeypatch.setattr(semantic_search, "embed_text", text_vec())
    body = labeler_client.get(f"{BASE}/search", params={"q": "car"}).json()
    assert [i["name"] for i in body["items"]] == ["e-labeled.jpg"]


def test_collections_are_reviewer_only(labeler_client, data):
    assert labeler_client.get(f"{BASE}/collections").status_code == 403
    assert labeler_client.post(f"{BASE}/collections", json={"name": "nope"}).status_code == 403


def test_new_routes_are_404_while_the_flag_is_off(client):
    client.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})
    try:
        assert client.get(f"{BASE}/search").status_code == 404
        assert client.post(f"{BASE}/collections", json={"name": "nope"}).status_code == 404
    finally:
        client.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})


def test_collections_crud(client, data):
    created = client.post(f"{BASE}/collections", json={"name": "PPE set", "image_ids": [data["a"], data["b"]],
                                                       "query": "red helmet"})
    assert created.status_code == 200, created.text
    collection = created.json()
    assert collection["count"] == 2 and collection["query"] == "red helmet"

    listing = client.get(f"{BASE}/collections").json()
    assert [c["id"] for c in listing["collections"]] == [collection["id"]]
    assert listing["collections"][0]["count"] == 2

    page = client.get(f"{BASE}/collections/{collection['id']}", params={"limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["name"] == "a-red-helmet.jpg"

    added = client.post(f"{BASE}/collections/{collection['id']}/items", json={"image_ids": [data["c"]]})
    assert added.json()["count"] == 3
    removed = client.request("DELETE", f"{BASE}/collections/{collection['id']}/items",
                             json={"image_ids": [data["b"]]})
    assert removed.json()["count"] == 2
    renamed = client.patch(f"{BASE}/collections/{collection['id']}", json={"name": "PPE picks"})
    assert renamed.json()["name"] == "PPE picks"

    assert client.delete(f"{BASE}/collections/{collection['id']}").status_code == 200
    assert client.get(f"{BASE}/collections/{collection['id']}").status_code == 404


def test_collection_rejects_images_from_another_project(client, data):
    r = client.post(f"{BASE}/collections", json={"name": "mixed", "image_ids": [data["a"], data["other_img"]]})
    assert r.status_code == 400
    # the refusal must not read the other project's row: the id is simply not in this project
    assert "not found" in r.json()["detail"]


def test_collection_rejects_a_deleted_image(client, data):
    ghost = seed_image(data["project"], "ghost.jpg", sha=hashlib.sha256(b"ghost").hexdigest())
    with SessionLocal() as db:
        db.get(Image, ghost).deleted_at = 1.0
        db.commit()
    r = client.post(f"{BASE}/collections", json={"name": "ghosts", "image_ids": [data["a"], ghost]})
    assert r.status_code == 400
    assert "deleted" in r.json()["detail"]


def test_collection_name_is_validated(client, data):
    assert client.post(f"{BASE}/collections", json={"name": "   "}).status_code == 400
    long_name = client.post(f"{BASE}/collections", json={"name": "x" * 256})
    assert long_name.status_code == 400 and "too long" in long_name.json()["detail"]


def test_collection_item_cap_is_enforced(client, data, monkeypatch):
    monkeypatch.setattr(collection_service, "MAX_ITEMS", 3)
    over = client.post(f"{BASE}/collections",
                       json={"name": "cap", "image_ids": [data["a"], data["b"], data["c"], data["d"]]})
    assert over.status_code == 400 and "3 images" in over.json()["detail"]

    made = client.post(f"{BASE}/collections", json={"name": "cap ok",
                                                    "image_ids": [data["a"], data["b"], data["c"]]})
    assert made.status_code == 200, made.text
    cid = made.json()["id"]
    assert client.post(f"{BASE}/collections/{cid}/items",
                       json={"image_ids": [data["d"]]}).status_code == 400
    # an id already in the set costs no room, so re-adding it is not an error
    same = client.post(f"{BASE}/collections/{cid}/items", json={"image_ids": [data["a"]]})
    assert same.status_code == 200 and same.json()["count"] == 3


def test_over_long_query_is_rejected(client, data):
    assert client.get(f"{BASE}/search", params={"q": "x" * 500}).status_code == 200
    r = client.get(f"{BASE}/search", params={"q": "x" * 501})
    assert r.status_code == 400 and "500" in r.json()["detail"]


def test_collections_are_project_scoped(client, data):
    cid = client.post(f"{BASE}/collections", json={"name": "scope", "image_ids": [data["a"]]}).json()["id"]
    assert client.get(f"{OTHER_BASE}/collections/{cid}").status_code == 404
    assert client.delete(f"{OTHER_BASE}/collections/{cid}").status_code == 404


def test_duplicate_collection_name_is_refused(client, data):
    client.post(f"{BASE}/collections", json={"name": "dupe"})
    r = client.post(f"{BASE}/collections", json={"name": "dupe"})
    assert r.status_code == 409
