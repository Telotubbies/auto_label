"""Natural-language event search (Task 38): sampled footage/stream frames, ranked candidates, human confirm."""

import os
import random
import tempfile
import time
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-event-search-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ.setdefault("LD_CLIP", "0")

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete, event, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import EventSearchFrame, Image, Project, Stream, StreamEvent, User, Video, Workspace
from app.services import event_search

WS = "labeldesk-demo"
PROJECT = "event-search-qa"
OTHER_PROJECT = "event-search-other"
BASE = f"/api/ws/{WS}/projects/{PROJECT}"
OTHER = f"/api/ws/{WS}/projects/{OTHER_PROJECT}"
FLAG = "task_38"
PW = "demo1234"
DAY = 24 * 3600


def _login(email: str = "demo@labeldesk.dev") -> TestClient:
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return client


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin(client):
    yield _login()


@pytest.fixture(scope="module")
def labeler(client):
    yield _login("labeler@labeldesk.dev")


def _project(slug: str = PROJECT) -> Project:
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == slug))
        if p is None:
            p = Project(workspace_id=ws.id, slug=slug, name=slug.replace("-", " ").title(),
                        type="object-detection", annotation_group="ppe", settings={})
            db.add(p)
            db.commit()
        return p


def _write_frame(name: str) -> str:
    """A small noisy JPEG on disk; returns the DATA_DIR-relative path."""
    rng = random.Random(name)
    im = PImage.frombytes("RGB", (32, 32), bytes(rng.getrandbits(8) for _ in range(32 * 32 * 3)))
    rel = f"event-search/{name}"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / rel, "JPEG", quality=85)
    return rel


def _frame(name: str, created: float) -> str:
    """A frame stored like a real extracted video frame."""
    rel = _write_frame(name)
    with SessionLocal() as db:
        p = _project()
        video = db.scalar(select(Video).where(Video.project_id == p.id, Video.name == "plant-walk.mp4"))
        if video is None:
            video = Video(project_id=p.id, workspace_id=p.workspace_id, name="plant-walk.mp4", path="",
                          status="ready")
            db.add(video)
            db.flush()
        row = Image(project_id=p.id, video_id=video.id, frame_index=0, name=name,
                    sha256=f"{abs(hash(name)):064d}"[:64], width=32, height=32, path=rel, thumb=rel,
                    split="train", status="unassigned", created=created)
        db.add(row)
        db.commit()
        return row.id


@pytest.fixture(scope="module", autouse=True)
def _own_project_headroom():
    """The demo workspace's Free plan cannot fit this module's two projects plus whatever earlier
    modules leak, and the projects would push later modules past the limit, so raise the plan for
    this module and drop what it created before restoring it."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        ws_id, before = ws.id, ws.plan
        ws.plan = "pro"
        db.commit()
    yield
    with SessionLocal() as db:              # children (images, video, stream, index rows) cascade
        db.execute(delete(Project).where(Project.workspace_id == ws_id,
                                         Project.slug.in_((PROJECT, OTHER_PROJECT))))
        db.get(Workspace, ws_id).plan = before
        db.commit()


@pytest.fixture(scope="module", autouse=True)
def footage(client):
    """Four frames in one window; names carry the metadata the lexical fallback can match."""
    now = time.time()
    with SessionLocal() as db:
        db.execute(delete(EventSearchFrame))
        db.commit()
    ids = {
        "helmet": _frame("helmet-frame-a.jpg", now - 600),
        "corridor": _frame("corridor-frame-b.jpg", now - 540),
        "forklift": _frame("forklift-frame-c.jpg", now - 480),
        "helmet2": _frame("helmet-frame-d.jpg", now - 420),
    }
    _project(OTHER_PROJECT)
    return {"ids": ids, "now": now}


@pytest.fixture(autouse=True)
def fresh_index(client):
    """Each test starts with an empty index; the reuse test builds it twice inside one test."""
    with SessionLocal() as db:
        db.execute(delete(EventSearchFrame))
        db.commit()
    yield


@pytest.fixture(autouse=True)
def flag_on(admin):
    """Every test except the explicit off test runs with task_38 enabled."""
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    yield


def _run(client: TestClient, payload: dict, base: str = BASE, timeout: float = 20.0) -> dict:
    r = client.post(f"{base}/event-search", json=payload)
    assert r.status_code == 200, r.text
    jid = r.json()["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"{base}/jobs/{jid}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            assert job["status"] == "done", job.get("error")
            return job
        time.sleep(0.1)
    raise AssertionError("event search job did not finish in time")


def test_flag_off_hides_the_feature(admin):
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})
    assert admin.post(f"{BASE}/event-search", json={"query": "helmet"}).status_code == 404

    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})
    # reachable again (the empty query is rejected by validation, not hidden by the flag)
    assert admin.post(f"{BASE}/event-search", json={"query": ""}).status_code == 400


def test_rank_candidates_scores_sum_to_one_and_match_first():
    now = time.time()

    def row(rid: str, label: str, ts: float) -> SimpleNamespace:
        return SimpleNamespace(id=rid, source="footage", source_id=rid, stream_id=None, video_id=None,
                               ts=ts, label=label, embedding=[], confirmed=False, confirmed_by=None,
                               path=rid)

    rows = [row("a", "helmet frame", now), row("b", "empty corridor", now - 10),
            row("c", "forklift passing", now - 20)]
    ranked, ranking = event_search.rank_candidates("worker wearing a helmet", rows, None, limit=10)

    assert ranking == "lexical"
    assert [r["id"] for r in ranked] == ["a"]
    assert 0 < ranked[0]["score"] <= 1
    other, _ = event_search.rank_candidates("helmet or forklift", rows, None, limit=10)
    assert [r["id"] for r in other] == ["a", "c"]
    assert sum(r["score"] for r in other) <= 1.0
    assert all(0 <= r["score"] <= 1 for r in other)


def test_rank_candidates_blends_clip_similarity_with_text():
    def row(rid: str, label: str, ts: float, embedding: list[float]) -> SimpleNamespace:
        return SimpleNamespace(id=rid, source="footage", source_id=rid, stream_id=None, video_id=None,
                               ts=ts, label=label, embedding=embedding, confirmed=False, confirmed_by=None,
                               path=rid)

    rows = [row("visual", "frame without words", 1, [1.0, 0.0]), row("text", "helmet on a hook", 2, [0.0, 1.0])]
    ranked, ranking = event_search.rank_candidates("helmet frame", rows, [1.0, 0.0], limit=10)

    assert ranking == "clip+lexical"
    assert [r["id"] for r in ranked] == ["visual", "text"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_sample_is_bounded_and_spread_over_the_window():
    candidates = [{"source_id": str(i), "ts": 1000 - i} for i in range(100)]
    sampled = event_search.sample_candidates(candidates, 10)

    assert len(sampled) == 10
    assert sampled[0]["source_id"] == "0" and sampled[-1]["source_id"] == "90"  # stride, newest first


def test_job_indexes_footage_and_ranks_candidates(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search.embeddings, "available", lambda: True)
    monkeypatch.setattr(event_search, "_image_vector", lambda im, sha: [1.0, 0.0])
    monkeypatch.setattr(event_search, "_text_vector", lambda text: [1.0, 0.0])

    now = footage["now"]
    job = _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now, "limit": 5})
    result = job["result"]

    assert result["ranking"] == "clip+lexical"
    assert result["candidates"] == 4 and result["embeddings"] == 4
    # every frame gets the same fake CLIP vector, so the stored words rank the two helmets first
    assert {r["source_id"] for r in result["results"][:2]} == {
        footage["ids"]["helmet"], footage["ids"]["helmet2"],
    }
    assert len(result["results"]) == 4
    assert all(r["image"].startswith(f"/api/ws/{WS}/projects/{PROJECT}/event-search/frames/")
               for r in result["results"])
    with SessionLocal() as db:
        rows = db.scalars(select(EventSearchFrame).where(EventSearchFrame.project_id == _project().id)).all()
        assert len(rows) == 4
        assert all(row.embedding == [1.0, 0.0] for row in rows)


def test_stream_events_join_the_index(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search, "_text_vector", lambda text: None)
    now = footage["now"]
    with SessionLocal() as db:
        p = _project()
        stream = Stream(workspace_id=p.workspace_id, project_id=p.id, name="Gate camera",
                        source="file:x.mp4", model_ref="ultralytics:yolo", zones=[], rules=[])
        db.add(stream)
        db.flush()
        db.add(StreamEvent(stream_id=stream.id, ts=now - 300, summary="worker without helmet",
                           snapshot_path=_write_frame("stream-event.jpg"), rule_label="no-helmet",
                           classes="|person|"))
        db.commit()
    job = _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})
    stream_hits = [r for r in job["result"]["results"] if r["source"] == "stream"]
    assert len(stream_hits) == 1 and stream_hits[0]["source_name"] == "Gate camera"


def test_results_are_scoped_to_the_project_and_window(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search, "_text_vector", lambda text: None)
    now = footage["now"]
    narrow = _run(admin, {"query": "helmet", "from_ts": now - 610, "to_ts": now - 570})
    assert narrow["result"]["candidates"] == 1
    assert [r["source_id"] for r in narrow["result"]["results"]] == [footage["ids"]["helmet"]]

    other = _run(_login(), {"query": "helmet", "from_ts": now - 900, "to_ts": now}, base=OTHER)
    assert other["result"]["candidates"] == 0 and other["result"]["results"] == []


def test_confirm_records_the_person_and_is_project_scoped(admin, labeler, monkeypatch, footage):
    monkeypatch.setattr(event_search, "_text_vector", lambda text: None)
    now = footage["now"]
    job = _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})
    frame_id = job["result"]["results"][0]["id"]

    r = admin.post(f"{BASE}/event-search/frames/{frame_id}/confirm", json={"confirmed": True})
    assert r.status_code == 200, r.text
    assert r.json()["confirmed"] is True and r.json()["confirmed_by"]
    assert labeler.post(f"{BASE}/event-search/frames/{frame_id}/confirm",
                        json={"confirmed": True}).status_code == 403
    assert admin.post(f"{OTHER}/event-search/frames/{frame_id}/confirm",
                      json={"confirmed": True}).status_code == 404

    with SessionLocal() as db:
        row = db.get(EventSearchFrame, frame_id)
        admin_user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        assert row.confirmed is True and row.confirmed_by == admin_user.id


def test_index_is_reused_without_duplicate_rows(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search.embeddings, "available", lambda: True)
    monkeypatch.setattr(event_search, "_image_vector", lambda im, sha: [1.0, 0.0])
    monkeypatch.setattr(event_search, "_text_vector", lambda text: [1.0, 0.0])
    now = footage["now"]
    _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})
    _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})

    with SessionLocal() as db:
        rows = db.scalars(select(EventSearchFrame).where(EventSearchFrame.project_id == _project().id)).all()
    # the two runs upsert, so each frame appears once (the earlier stream event is still indexed)
    assert len({(row.source, row.source_id) for row in rows}) == len(rows)
    assert len([row for row in rows if row.source == "footage"]) == 4


def test_frame_image_url_is_signed_and_still_requires_the_flag(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search, "_text_vector", lambda text: None)
    now = footage["now"]
    job = _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})
    url = job["result"]["results"][0]["image"]

    r = admin.get(url)
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    tampered = url.replace("sig=", "sig=0")
    assert admin.get(tampered).status_code == 403

    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})
    assert admin.get(url).status_code == 404
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True})


def test_request_validation(admin):
    assert admin.post(f"{BASE}/event-search", json={"query": "  "}).status_code == 400
    now = time.time()
    assert admin.post(f"{BASE}/event-search",
                      json={"query": "x", "from_ts": now, "to_ts": now - 10}).status_code == 400
    assert admin.post(f"{BASE}/event-search", json={"query": "x", "limit": 0}).status_code == 400


def test_window_is_limited_to_31_days(admin):
    now = time.time()
    r = admin.post(f"{BASE}/event-search",
                   json={"query": "helmet", "from_ts": now - 31 * DAY - 60, "to_ts": now})
    assert r.status_code == 400 and "31 days" in r.json()["detail"]


def test_labeler_cannot_start_an_event_search(labeler):
    """Stream footage is project.streams data and the result needs project.models; a labeler gets neither."""
    assert labeler.post(f"{BASE}/event-search", json={"query": "helmet"}).status_code == 403


def test_data_path_refuses_paths_outside_the_data_dir():
    assert event_search.data_path("event-search/frame.jpg") == (DATA_DIR / "event-search/frame.jpg").resolve()
    assert event_search.data_path("") is None
    assert event_search.data_path("../escape.jpg") is None
    assert event_search.data_path(str(DATA_DIR.parent / "escape.jpg")) is None


def test_unreadable_frame_file_does_not_fail_the_search(admin, monkeypatch, footage):
    """A purged or half-extracted frame costs its own vector, not the whole job."""
    monkeypatch.setattr(event_search.embeddings, "available", lambda: True)
    monkeypatch.setattr(event_search.embeddings, "embed_image", lambda im, sha: [1.0, 0.0])
    monkeypatch.setattr(event_search, "_text_vector", lambda text: [1.0, 0.0])
    now = footage["now"]
    gone = _frame("helmet-gone-frame.jpg", now - 570)
    (DATA_DIR / "event-search" / "helmet-gone-frame.jpg").unlink()

    job = _run(admin, {"query": "helmet", "from_ts": now - 900, "to_ts": now})
    result = job["result"]
    assert result["ranking"] == "clip+lexical"
    assert result["embeddings"] == result["candidates"] - 1   # only the unreadable frame is skipped
    # it still ranks on its stored words instead of taking the job down with it
    assert {*footage["ids"].values(), gone} <= {r["source_id"] for r in result["results"]}

    with SessionLocal() as db:                             # leave the module window at four live frames
        db.get(Image, gone).deleted_at = time.time()
        db.commit()


def test_concurrent_index_of_the_same_window_keeps_one_row_per_frame(footage):
    """Coalescing windows must not duplicate rows: confirm is per row, so a frame needs one identity."""
    now = footage["now"]
    with SessionLocal() as db:
        project = _project()
        candidates = event_search.collect_candidates(db, project, now - 900, now)
        assert len(candidates) >= 4
        raced: list[str] = []

        @event.listens_for(db, "before_flush")
        def _competing_index(_session, _ctx, _instances):
            if raced:                                      # only the first flush loses the race
                return
            raced.append("raced")
            first = candidates[0]
            with SessionLocal() as other:                  # a second search commits the same frame first
                other.add(EventSearchFrame(
                    id="racedframe", workspace_id=project.workspace_id, project_id=project.id,
                    source=first["source"], source_id=first["source_id"], ts=first["ts"],
                    path=first["path"], label=first["label"], embedding=[]))
                other.commit()

        event_search.index_candidates(db, project, candidates)
        assert raced
    with SessionLocal() as db:
        rows = db.scalars(select(EventSearchFrame).where(EventSearchFrame.project_id == _project().id)).all()
    keys = [(row.source, row.source_id) for row in rows]
    assert len(keys) == len(set(keys)) == len(candidates)


def test_frame_of_a_deleted_image_is_not_served_and_not_reindexed(admin, monkeypatch, footage):
    """An erased dataset image must not stay openable inside an old result, nor keep its vector."""
    monkeypatch.setattr(event_search, "_text_vector", lambda text: None)
    now = footage["now"]
    erased = _frame("erased-frame.jpg", now - 570)
    job = _run(admin, {"query": "erased", "from_ts": now - 900, "to_ts": now})
    hit = next(r for r in job["result"]["results"] if r["source_id"] == erased)
    assert admin.get(hit["image"]).status_code == 200
    with SessionLocal() as db:
        assert db.get(EventSearchFrame, hit["id"]) is not None

    with SessionLocal() as db:
        db.get(Image, erased).deleted_at = time.time()
        db.commit()
    assert admin.get(hit["image"]).status_code == 404      # already-handed-out signed URL

    _run(admin, {"query": "erased", "from_ts": now - 900, "to_ts": now})
    with SessionLocal() as db:
        kept = {row.source_id for row in db.scalars(
            select(EventSearchFrame).where(EventSearchFrame.project_id == _project().id)).all()}
    assert erased not in kept and footage["ids"]["helmet"] in kept


def test_indexing_stops_after_a_cancellation(admin, monkeypatch, footage):
    monkeypatch.setattr(event_search.embeddings, "available", lambda: True)
    embedded: list[str] = []

    def vector(_im, sha):
        embedded.append(sha)
        return [1.0, 0.0]

    monkeypatch.setattr(event_search, "_image_vector", vector)
    now = footage["now"]
    with SessionLocal() as db:
        project = _project()
        candidates = event_search.collect_candidates(db, project, now - 900, now)
        rows, stats = event_search.index_candidates(
            db, project, candidates, should_stop=lambda: len(embedded) >= 1)
    assert stats["embeddings"] == 1
    assert len(embedded) == 1
    assert sum(1 for row in rows if row.embedding) == 1
