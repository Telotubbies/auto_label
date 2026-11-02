"""Insights Studio 20a: dataset analytics, scan jobs, version diff, labeling ops, isolation."""

import hashlib
import json
import os
import random
import tempfile
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Image, LabelClass, LabelEvent, Project, User, Version, Workspace
from app.security import issue_access
from app.services import insights, insights_dataset, insights_embedding

WS = "labeldesk-demo"
SLUG = "insights-qa"
BASE = f"/api/ws/{WS}/projects/{SLUG}"
INS = f"{BASE}/insights"
JOBS = f"{BASE}/jobs"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


def noise(w: int, h: int, seed: str) -> PImage.Image:
    """Distinct pixels per seed so pHash only groups the copy we make on purpose."""
    rng = random.Random(seed)
    return PImage.frombytes("RGB", (w, h), bytes(rng.getrandbits(8) for _ in range(w * h * 3)))


def seed_image(
    pid: str,
    name: str,
    w: int,
    h: int,
    anns: list[dict],
    split: str = "train",
    assignee: str | None = None,
    status: str = "done",
    review: str | None = None,
    updated: float | None = None,
    im: PImage.Image | None = None,
) -> str:
    im = im or noise(w, h, name)
    rel = f"insights/{name}.jpg"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / rel, "JPEG", quality=90)
    with SessionLocal() as db:
        row = Image(
            project_id=pid,
            name=name,
            sha256=hashlib.sha256(name.encode()).hexdigest(),
            width=w,
            height=h,
            path=rel,
            thumb=rel,
            split=split,
            status=status,
            review=review,
            assignee_id=assignee,
            annotations=anns,
            n_annotations=len(anns),
            updated=updated if updated is not None else time.time(),
        )
        db.add(row)
        db.commit()
        return row.id


def box(
    aid: str,
    x: float,
    y: float,
    w: float,
    h: float,
    cid: str,
    source: str | None = None,
) -> dict:
    out = {
        "id": aid,
        "classId": cid,
        "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h},
    }
    if source:
        out["source"] = source
    return out


@pytest.fixture(scope="module")
def data(c):
    # Seed directly: the demo workspace's project quota is shared with other modules.
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        project = Project(workspace_id=ws.id, slug=SLUG, name=SLUG, type="object-detection", settings={})
        db.add(project)
        db.flush()
        for name, color in (("person", "#8b5cf6"), ("car", "#22c55e"), ("dog", "#3b82f6")):
            db.add(LabelClass(project_id=project.id, name=name, color=color))
        db.commit()
        pid = project.id
    cls = {x["name"]: x["id"] for x in c.get(f"{BASE}/classes").json()}
    with SessionLocal() as db:
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    t0 = time.time() - 3600
    ids = {}
    ids["both"] = seed_image(
        pid,
        "both-train",
        640,
        480,
        [
            box("a1", 0.1, 0.1, 0.1, 0.1, cls["person"]),
            box("a2", 0.5, 0.5, 0.2, 0.1, cls["car"]),
        ],
        split="train",
        assignee=labeler.id,
        updated=t0,
    )
    ids["person"] = seed_image(
        pid,
        "person-valid",
        320,
        320,
        [box("b1", 0.5, 0.5, 0.01, 0.01, cls["person"])],
        split="valid",
        assignee=labeler.id,
        updated=t0,
    )
    ids["null"] = seed_image(pid, "null-test", 200, 100, [], split="test", status="unassigned")
    ids["car_ai"] = seed_image(
        pid,
        "car-ai-train",
        640,
        640,
        [box("c1", 0.2, 0.2, 0.5, 0.5, cls["car"], source="sam3")],
        split="train",
    )
    shared = noise(64, 64, "duplicate-pixels")
    ids["dup_train"] = seed_image(
        pid,
        "dup-train",
        64,
        64,
        [box("d1", 0.2, 0.2, 0.2, 0.2, cls["person"])],
        split="train",
        assignee=labeler.id,
        updated=t0,
        im=shared,
    )
    ids["dup_valid"] = seed_image(
        pid,
        "dup-valid",
        64,
        64,
        [box("d2", 0.2, 0.2, 0.2, 0.2, cls["person"])],
        split="valid",
        im=shared,
    )
    ids["rejected"] = seed_image(
        pid,
        "rejected-valid",
        128,
        128,
        [box("e1", 0.1, 0.1, 0.2, 0.2, cls["car"], source="vlm+sam3")],
        split="valid",
        status="review",
        review="rejected",
    )
    return {"project": {"id": pid, "slug": SLUG, "name": SLUG}, "classes": cls, "ids": ids, "labeler": labeler.id}


def wait_job(c, jid: str, timeout: float = 40) -> dict:
    deadline = time.time() + timeout
    j = {}
    while time.time() < deadline:
        j = c.get(f"{JOBS}/{jid}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            assert j["status"] == "done", j
            return j
        time.sleep(0.05)
    with SessionLocal() as db:
        from app.models import Job as JobRow
        rows = db.scalars(select(JobRow).where(JobRow.status.in_(("queued", "running")))).all()
        blockers = [(r.kind, r.id, r.status, r.created) for r in rows]
    raise TimeoutError(f"{jid} last={j} jobs={blockers}")


def test_summary_counts_splits_sources_and_annotator_read(c, data):
    r = c.get(f"{INS}/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project"] == {
        "id": data["project"]["id"],
        "name": SLUG,
        "type": "object-detection",
    }
    assert body["version"] is None
    assert body["images"] == 7
    assert body["annotations"] == 7
    assert body["null_images"] == 1
    assert body["splits"] == {"train": 3, "valid": 3, "test": 1}
    classes = {x["name"]: x for x in body["classes"]}
    assert classes["person"]["count"] == 4 and classes["person"]["images"] == 4
    assert classes["car"]["count"] == 3 and classes["car"]["images"] == 3
    assert classes["dog"]["count"] == 0 and classes["dog"]["images"] == 0
    assert classes["person"]["color"]
    sources = {x["source"]: x for x in body["sources"]}
    assert sources["human"]["annotations"] == 5
    assert sources["sam3"]["annotations"] == 1
    assert sources["vlm+sam3"]["annotations"] == 1
    assert sources["human"]["share"] == pytest.approx(5 / 7, abs=1e-4)

    with SessionLocal() as db:
        lab = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    r = c.get(f"{INS}/summary", headers={"Authorization": f"Bearer {issue_access(lab.id)}"})
    assert r.status_code == 200, r.text


def test_distribution_split_classes_instances_cooccurrence_and_buckets(c, data):
    body = c.get(f"{INS}/distribution").json()
    split = {x["class"]: x for x in body["split_classes"]}
    assert split["person"] == {"class": "person", "train": 2, "valid": 2, "test": 0}
    assert split["car"] == {"class": "car", "train": 2, "valid": 1, "test": 0}
    inst = {x["class"]: x for x in body["instances_vs_images"]}
    assert inst["person"]["instances"] == 4 and inst["person"]["images"] == 4
    assert inst["car"]["instances"] == 3 and inst["car"]["images"] == 3

    co = body["cooccurrence"]
    i, j = co["classes"].index("person"), co["classes"].index("car")
    assert co["matrix"][i][j] == 1 and co["matrix"][j][i] == 1
    assert co["matrix"][i][i] == 4 and co["matrix"][j][j] == 3

    buckets = {x["bucket"]: x["images"] for x in body["annotations_per_image"]}
    assert buckets["0"] == 1 and buckets["1"] == 5 and buckets["2"] == 1
    assert sum(buckets.values()) == 7 and "20+" in buckets


def test_geometry_area_aspect_centres(c, data):
    body = c.get(f"{INS}/geometry").json()
    assert body["imgsz"] == 640
    assert body["area_buckets"] == {"small": 1, "medium": 2, "large": 4}
    aspect = {x["bucket"]: x["count"] for x in body["aspect"]}
    assert aspect == {"<0.5": 0, "0.5–1": 0, "1–2": 6, "2–4": 1, "≥4": 0}
    assert len(body["box_scatter"]) == 7
    assert body["sampled"] is False
    assert all(0 <= p["w"] <= 1.5 and 0 <= p["h"] <= 1.5 and p["class"] and p["split"] for p in body["box_scatter"])
    centres = {x["class"]: x["cells"] for x in body["centres"]}
    assert len(centres["person"]) == 100 and sum(centres["person"]) == 4
    assert len(centres["car"]) == 100 and sum(centres["car"]) == 3


def test_image_stats_scan_job_results_and_role_gate(c, data):
    r = c.post(f"{INS}/image-stats/scan")
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "insights_images" and job["status"] in ("queued", "running")
    done = wait_job(c, job["id"])
    assert done["result"]["scanned"] == 7

    body = c.get(f"{INS}/image-stats").json()
    assert body["imgsz"] == 640
    assert body["scanned"] == 7
    assert len(body["resolution"]) == 7
    assert sum(x["count"] for x in body["brightness"]) == 7
    assert sum(x["count"] for x in body["blur"]) == 7
    assert [x["bin"] for x in body["brightness"]] == list(range(16))
    assert [x["bin"] for x in body["blur"]] == [
        "0–10",
        "10–30",
        "30–100",
        "100–300",
        "300–1000",
        "≥1000",
    ]
    assert body["stale"] is False
    assert body["job"]["id"] == job["id"]

    with SessionLocal() as db:
        lab = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    r = c.post(
        f"{INS}/image-stats/scan",
        headers={"Authorization": f"Bearer {issue_access(lab.id)}"},
    )
    assert r.status_code == 403


def test_leakage_scan_finds_cross_split_duplicate_and_signs_gallery(c, data):
    r = c.post(f"{INS}/leakage/scan")
    assert r.status_code == 200, r.text
    wait_job(c, r.json()["id"])

    body = c.get(f"{INS}/leakage").json()
    pair = next(
        p
        for p in body["pairs"]
        if {p["a"]["image_id"], p["b"]["image_id"]} == {data["ids"]["dup_train"], data["ids"]["dup_valid"]}
    )
    assert pair["distance"] == 0
    assert {pair["a"]["split"], pair["b"]["split"]} == {"train", "valid"}
    assert body["total_pairs"] >= 1
    assert any({x["a"], x["b"]} == {"train", "valid"} and x["count"] >= 1 for x in body["split_pairs"])
    assert pair["a"]["thumb"].startswith("/api/files/") and pair["b"]["thumb"].startswith("/api/files/")
    assert body["stale"] is False
    assert body["leakage_moved"] is None


def test_embedding_scan_returns_finite_projection(c, data, monkeypatch):
    # Force the CV path: the scan must never download CLIP or touch a GPU from a test.
    monkeypatch.setattr(insights_embedding, "_CLIP", False)
    r = c.post(f"{INS}/embedding/scan")
    assert r.status_code == 200, r.text
    wait_job(c, r.json()["id"])

    body = c.get(f"{INS}/embedding").json()
    assert body["projection"] in ("umap", "pca")
    points = {p["image_id"]: p for p in body["points"]}
    assert set(points) == set(data["ids"].values())
    for p in points.values():
        assert isinstance(p["x"], float) and isinstance(p["y"], float)
        assert p["x"] == p["x"] and p["y"] == p["y"]  # finite
        assert p["split"] in ("train", "valid", "test")
        assert p["source"] in ("human", "ai")
        assert p["thumb"].startswith("/api/files/")
    assert points[data["ids"]["car_ai"]]["source"] == "ai"
    assert points[data["ids"]["both"]]["source"] == "human"
    assert points[data["ids"]["rejected"]]["error"] is True
    assert points[data["ids"]["both"]]["error"] is False
    assert body["features"] == "cv"          # transformers is not installed: the CV fallback runs
    assert body["total"] >= body["used"]
    assert body["used"] == len(body["points"])
    assert body["sampled"] is (body["total"] > body["used"])
    assert body["stale"] is False


def test_embedding_clip_branch_uses_mocked_vectors(c, data, monkeypatch, tmp_path):
    """The CLIP branch (batching, per-row cache) runs on fake vectors: no network, no GPU, no download."""
    calls: list[int] = []

    def fake_vectors(_state, rows):
        calls.append(len(rows))
        out = []
        for row in rows:
            vec = np.asarray([float(len(row.name)), float(sum(row.name.encode()) % 97), 1.0], dtype=np.float32)
            out.append((row, vec / np.linalg.norm(vec)))
        return out

    monkeypatch.setattr(insights_embedding, "_clip_backend", lambda: (None, None, None, "cpu"))
    monkeypatch.setattr(insights_embedding, "_clip_vectors", fake_vectors)
    monkeypatch.setattr(insights_embedding, "FEATURE_DIR", tmp_path / "features")
    with SessionLocal() as db:
        body = insights_embedding.scan_embedding(db, db.get(Project, data["project"]["id"]))

    assert body["features"] == "clip"
    assert body["used"] == len(body["points"]) == len(data["ids"])
    assert calls and all(1 <= size <= insights_embedding.EMBED_BATCH for size in calls)
    assert {p["image_id"] for p in body["points"]} == set(data["ids"].values())
    assert all(np.isfinite([p["x"], p["y"]]).all() for p in body["points"])


def _make_version(
    pid: str,
    number: int,
    name: str,
    splits: dict,
    class_stats: dict,
    sources: list[str],
) -> str:
    with SessionLocal() as db:
        v = Version(
            project_id=pid,
            number=number,
            name=name,
            status="ready",
            stats={
                "splits": dict(Counter(splits.values())),
                "classes": class_stats,
                "leakage_moved": 0,
                "version_hash": f"hash-{number}",
            },
        )
        db.add(v)
        db.commit()
        vid = v.id
    d = DATA_DIR / "versions" / vid
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "classes": list(class_stats),
        "type": "object-detection",
        "version_hash": f"hash-{number}",
        "config": {},
        "items": [
            {
                "file": f"{split}/{sid}.jpg",
                "split": split,
                "source": sid,
                "width": 100,
                "height": 100,
            }
            for sid, split in splits.items()
        ],
        "sources": [{"id": i, "sha256": i} for i in sources],
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    return vid


def test_version_diff_added_removed_moves_and_class_delta(c, data):
    pid = data["project"]["id"]
    ids = data["ids"]
    base = _make_version(
        pid,
        1,
        "base",
        {ids["both"]: "train", ids["person"]: "valid", ids["car_ai"]: "train"},
        {"person": 3, "car": 1},
        [ids["both"], ids["person"], ids["car_ai"]],
    )
    target = _make_version(
        pid,
        2,
        "target",
        {ids["both"]: "valid", ids["dup_train"]: "train", ids["rejected"]: "valid"},
        {"person": 4, "car": 2},
        [ids["both"], ids["dup_train"], ids["rejected"]],
    )
    body = c.get(f"{INS}/version-diff", params={"base": base, "target": target}).json()
    assert body["base"]["version_hash"] == "hash-1" and body["target"]["version_hash"] == "hash-2"
    assert {x["image_id"] for x in body["added"]} == {ids["dup_train"], ids["rejected"]}
    assert {x["image_id"] for x in body["removed"]} == {ids["person"], ids["car_ai"]}
    assert body["added"][0]["thumb"].startswith("/api/files/")
    assert body["split_moves"] == [{"image_id": ids["both"], "name": "both-train", "from": "train", "to": "valid"}]
    delta = {x["class"]: x for x in body["class_delta"]}
    assert delta["person"] == {"class": "person", "base": 3, "target": 4, "delta": 1}
    assert delta["car"] == {"class": "car", "base": 1, "target": 2, "delta": 1}
    assert body["summary"] == {"added": 2, "removed": 2, "moved": 1}

    scoped = c.get(f"{INS}/summary", params={"version": target}).json()
    assert scoped["version"]["id"] == target and scoped["version"]["version_hash"] == "hash-2"
    assert scoped["images"] == 3 and scoped["annotations"] == 4
    assert scoped["splits"] == {"train": 1, "valid": 2, "test": 0}

    # version scope must use the manifest's splits, not the images' current split column
    scoped_dist = c.get(f"{INS}/distribution", params={"version": target}).json()
    split = {x["class"]: x for x in scoped_dist["split_classes"]}
    assert split["person"] == {"class": "person", "train": 1, "valid": 1, "test": 0}
    assert split["car"] == {"class": "car", "train": 0, "valid": 2, "test": 0}
    scoped_geo = c.get(f"{INS}/geometry", params={"version": target}).json()
    assert {p["split"] for p in scoped_geo["box_scatter"]} == {"train", "valid"}

    with SessionLocal() as db:
        empty = Version(project_id=pid, number=3, name="empty", status="ready", stats={})
        db.add(empty)
        db.commit()
        empty_id = empty.id
    r = c.get(f"{INS}/version-diff", params={"base": base, "target": empty_id})
    assert r.status_code == 400 and "manifest" in r.json()["detail"]


def test_leakage_scan_uses_the_versions_frozen_splits(c, data):
    """Selecting a version means its manifest splits decide what counts as cross-split leakage."""
    pid = data["project"]["id"]
    ids = data["ids"]
    dups = {ids["dup_train"]: "train", ids["dup_valid"]: "train"}
    same = _make_version(pid, 91, "leak-same", dups, {"person": 2}, list(dups))
    split = _make_version(pid, 92, "leak-split", {**dups, ids["dup_valid"]: "valid"}, {"person": 2}, list(dups))

    body = c.get(f"{INS}/leakage", params={"version": same}).json()
    assert body["job"]["params"]["version"] == same
    wait_job(c, body["job"]["id"])
    body = c.get(f"{INS}/leakage", params={"version": same}).json()
    assert body["stale"] is False
    # both copies are train in this version, so the pair is not leakage
    assert body["total_pairs"] == 0 and body["pairs"] == []

    body = c.get(f"{INS}/leakage", params={"version": split}).json()
    wait_job(c, body["job"]["id"])
    body = c.get(f"{INS}/leakage", params={"version": split}).json()
    assert body["stale"] is False
    pair = next(
        p
        for p in body["pairs"]
        if {p["a"]["image_id"], p["b"]["image_id"]} == {ids["dup_train"], ids["dup_valid"]}
    )
    # the gallery reports the frozen splits, not the images' current split column
    assert {pair["a"]["split"], pair["b"]["split"]} == {"train", "valid"}
    assert any({x["a"], x["b"]} == {"train", "valid"} and x["count"] == 1 for x in body["split_pairs"])

    r = c.post(f"{INS}/leakage/scan", params={"version": split})
    assert r.status_code == 200, r.text
    assert r.json()["params"]["version"] == split
    wait_job(c, r.json()["id"])


def test_labeling_throughput_review_and_ai_acceptance(c, data):
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        now = time.time()
        db.add_all(
            [
                Audit(
                    workspace_id=ws.id,
                    action="image.review",
                    target="both-train",
                    meta={"approved": True},
                    created=now,
                ),
                Audit(
                    workspace_id=ws.id,
                    action="image.review",
                    target="person-valid",
                    meta={"approved": True},
                    created=now,
                ),
                Audit(
                    workspace_id=ws.id,
                    action="image.review",
                    target="dup-train",
                    meta={"approved": False},
                    created=now,
                ),
                Audit(
                    workspace_id=ws.id,
                    action="project.update",
                    target="both-train",
                    meta={},
                    created=now,
                ),
                # Saves are what the workforce definition reads: one row per save, with the AI ids
                # that save exposed. Acceptance is those ids surviving on an accepted image.
                LabelEvent(
                    workspace_id=ws.id,
                    project_id=data["project"]["id"],
                    image_id=data["ids"]["both"],
                    user_id=data["labeler"],
                    annotations=2,
                    ai_ids=["a1", "gone"],
                    created=now,
                ),
                LabelEvent(
                    workspace_id=ws.id,
                    project_id=data["project"]["id"],
                    image_id=data["ids"]["car_ai"],
                    user_id=data["labeler"],
                    annotations=1,
                    ai_ids=["c1"],
                    created=now,
                ),
            ]
        )
        db.commit()

    body = c.get(f"{INS}/labeling").json()
    today = datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime("%Y-%m-%d")
    rows = [x for x in body["throughput"] if x["labeler_id"] == data["labeler"] and x["date"] == today]
    assert len(rows) == 1
    assert rows[0]["labeler"] == "Lee Labeler"
    assert rows[0]["images"] == 2 and rows[0]["annotations"] == 3

    review = next(x for x in body["review"] if x["date"] == today)
    assert review["approved"] >= 2 and review["rejected"] >= 1
    assert review["rate"] == pytest.approx(review["rejected"] / (review["approved"] + review["rejected"]), abs=1e-3)
    assert body["throughput_basis"] == "label_event"
    # 3 distinct (image, AI id) pairs seen; a1 and c1 are still on accepted images, "gone" is not
    assert body["ai"] == {
        "human": 5,
        "ai": 3,
        "accepted_ai": 2,
        "acceptance_rate": pytest.approx(2 / 3, abs=1e-4),
        "by_source": [
            {"source": "sam3", "count": 1},
            {"source": "vlm+sam3", "count": 1},
        ],
    }


def test_insights_and_qa_dashboard_report_the_same_labeler_stats(c, data):
    """I4: both pages delegate to `labeler_stats`, so the same data yields the same numbers."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        db.add(
            LabelEvent(
                workspace_id=ws.id,
                project_id=data["project"]["id"],
                image_id=data["ids"]["dup_valid"],
                user_id=data["labeler"],
                annotations=1,
                ai_ids=["d2"],
                created=time.time(),
            )
        )
        db.commit()

    ins = c.get(f"{INS}/labeling").json()
    qa = c.get(f"{BASE}/labeling/dashboard", params={"days": 90}).json()

    assert ins["ai"]["acceptance_rate"] == qa["totals"]["ai_acceptance"]
    assert ins["ai"]["ai"] >= 1 and ins["ai"]["accepted_ai"] >= 1

    qa_rows = {row["user_id"]: row for row in qa["labelers"]}
    by_labeler: dict[str, dict[str, int]] = {}
    by_date: dict[str, int] = {}
    for row in ins["throughput"]:
        bucket = by_labeler.setdefault(row["labeler_id"], {"annotations": 0, "images": 0})
        bucket["annotations"] += row["annotations"]
        bucket["images"] += row["images"]
        by_date[row["date"]] = by_date.get(row["date"], 0) + row["annotations"]
    assert by_labeler
    for user_id, want in by_labeler.items():
        assert qa_rows[user_id]["annotations"] == want["annotations"]
        assert qa_rows[user_id]["images"] == want["images"]
    qa_daily = {row["date"]: row for row in qa["daily"]}
    for date, annotations in by_date.items():
        assert qa_daily[date]["annotations"] == annotations



def test_workspace_isolation_401_403_404(c, data):
    anon = TestClient(app)
    assert anon.get(f"{INS}/summary").status_code == 401

    tag = uuid.uuid4().hex[:8]
    email = f"insights-{tag}@example.com"
    r = anon.post(
        "/api/auth/signup",
        json={
            "name": "Other Tenant",
            "email": email,
            "password": "longenough1",
            "workspace": f"Insights WS {tag}",
        },
    )
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    me = anon.get("/api/me", headers=h).json()
    ws2 = me["workspaces"][0]["slug"]
    p2 = anon.post(f"/api/ws/{ws2}/projects", json={"name": f"Other {tag}"}, headers=h)
    assert p2.status_code == 200, p2.text
    p2 = p2.json()

    # the slug exists only in the other workspace: the demo workspace reports 404, never leaks it
    assert c.get(f"/api/ws/{WS}/projects/{p2['slug']}/insights/summary").status_code == 404
    # a real project of another tenant is forbidden to a non-member
    assert c.get(f"/api/ws/{ws2}/projects/{p2['slug']}/insights/summary").status_code == 403


def test_summary_cache_reuses_payload_and_invalidates_on_new_image(c, data):
    pid = data["project"]["id"]
    first = c.get(f"{INS}/summary").json()
    second = c.get(f"{INS}/summary").json()
    assert first == second
    key = (pid, "", "summary")
    sig = insights._CACHE[key][0]
    assert insights._CACHE[key][1] == {k: v for k, v in first.items() if k not in ("project", "version")}

    seed_image(pid, "cache-new", 96, 96, [], split="test")
    third = c.get(f"{INS}/summary").json()
    assert third["images"] == first["images"] + 1
    assert insights._CACHE[key][0] != sig


def test_class_rename_and_recolour_invalidates_cached_aggregates(c, data):
    """A class edit is a dataset change: cached class names/colours must not survive it."""
    cid = data["classes"]["person"]
    before = c.get(f"{INS}/summary").json()
    assert "person" in {x["name"] for x in before["classes"]}
    try:
        with SessionLocal() as db:
            cls = db.get(LabelClass, cid)
            cls.name, cls.color = "pedestrian", "#123456"
            db.commit()
        after = c.get(f"{INS}/summary").json()
        classes = {x["name"]: x for x in after["classes"]}
        assert "person" not in classes
        assert classes["pedestrian"]["color"] == "#123456"
        assert classes["pedestrian"]["count"] == 4
    finally:
        with SessionLocal() as db:
            cls = db.get(LabelClass, cid)
            cls.name, cls.color = "person", "#8b5cf6"
            db.commit()
    restored = c.get(f"{INS}/summary").json()
    assert restored["classes"] == before["classes"]


def test_image_list_ids_filter(c, data):
    ids = [data["ids"]["both"], data["ids"]["null"]]
    body = c.get(f"{BASE}/images", params={"ids": ",".join(ids)}).json()
    assert body["total"] == 2
    assert {x["id"] for x in body["items"]} == set(ids)


def test_summary_cache_hit_loads_no_rows(c, data, monkeypatch):
    """A cache hit must not hydrate images: the signature alone decides."""
    first = c.get(f"{INS}/summary")
    assert first.status_code == 200, first.text
    baseline = first.json()

    def boom(*_a, **_kw):
        raise AssertionError("a cache hit loaded image rows")

    monkeypatch.setattr(insights, "live_images", boom)
    try:
        second = c.get(f"{INS}/summary")
        assert second.status_code == 200, second.text
        assert second.json() == baseline
    finally:
        monkeypatch.undo()


def test_manifest_cache_returns_same_object_until_the_file_changes(c, data):
    pid = data["project"]["id"]
    vid = _make_version(pid, 90, "manifest-cache", {data["ids"]["both"]: "train"}, {"person": 1}, [data["ids"]["both"]])
    version = SimpleNamespace(id=vid)
    first = insights._manifest(version)
    second = insights._manifest(version)
    assert first is not None, "manifest was not written by _make_version"
    assert second is first                     # parsed once, reused

    path = DATA_DIR / "versions" / vid / "manifest.json"
    path.write_text(json.dumps({**first, "version_hash": "rewritten-longer"}))
    third = insights._manifest(version)
    assert third is not None and third["version_hash"] == "rewritten-longer"
    assert third is not first


def test_sample_images_is_bounded_deterministic_and_keeps_every_split():
    rows = (
        [SimpleNamespace(id=f"train-{i}", split="train") for i in range(50)]
        + [SimpleNamespace(id=f"valid-{i}", split="valid") for i in range(10)]
        + [SimpleNamespace(id=f"test-{i}", split="test") for i in range(5)]
        + [SimpleNamespace(id=f"other-{i}", split="holdout") for i in range(5)]
    )
    first = insights_embedding._sample_images(rows, 12)
    second = insights_embedding._sample_images(rows, 12)
    assert len(first) == 12
    assert [r.id for r in first] == [r.id for r in second]
    assert len({r.id for r in first}) == 12
    assert {r.split for r in first} == {"train", "valid", "test", "holdout"}
    assert insights_embedding._sample_images(rows, 1000) == rows
    assert len(insights_embedding._sample_images(rows, 3)) == 3


def test_labeling_counts_throughput_from_label_events():
    ts = time.time()
    rows = [
        SimpleNamespace(
            id="i1",
            updated=ts,
            assignee_id=None,
            review=None,
            status="done",
            n_annotations=2,
            annotations=[
                {"id": "a1", "classId": "c1", "source": "sam3"},
                {"id": "h1", "classId": "c1", "source": "human"},
            ],
        ),
        SimpleNamespace(
            id="i2",
            updated=ts,
            assignee_id=None,
            review=None,
            status="done",
            n_annotations=1,
            annotations=[{"id": "a2", "classId": "c1", "source": "vlm"}],
        ),
    ]
    events = [
        SimpleNamespace(user_id="u1", image_id="i1", annotations=2, ai_ids=["a1", "missing"], created=ts),
        SimpleNamespace(user_id="u2", image_id="i2", annotations=1, ai_ids=["a2"], created=ts),
    ]
    body = insights_dataset.labeling(rows, [], {"u1": "One", "u2": "Two"}, events)
    assert body["throughput_basis"] == "label_event"
    got = {(r["labeler_id"], r["annotations"], r["images"]) for r in body["throughput"]}
    assert got == {("u1", 2, 1), ("u2", 1, 1)}
    assert {r["labeler"] for r in body["throughput"]} == {"One", "Two"}
    assert body["ai"] == {
        "human": 1,
        "ai": 3,
        "accepted_ai": 2,
        "acceptance_rate": pytest.approx(2 / 3, abs=1e-4),
        "by_source": [{"source": "sam3", "count": 1}, {"source": "vlm", "count": 1}],
    }



def test_selection_roundtrip_and_cross_project_isolation(c, data):
    ids = [data["ids"]["both"], data["ids"]["person"]]
    r = c.post(f"{INS}/selections", json={"image_ids": ids})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["token"] and saved["count"] == 2
    assert saved["expires"] > time.time()

    got = c.get(f"{INS}/selections/{saved['token']}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["token"] == saved["token"] and body["count"] == 2
    assert set(body["image_ids"]) == set(ids)
    assert body["expires"] == saved["expires"]

    listed = c.get(f"{BASE}/images", params={"selection": saved["token"]}).json()
    assert listed["total"] == 2
    assert {x["id"] for x in listed["items"]} == set(ids)

    assert c.get(f"{INS}/selections/not-a-token").status_code == 404
    bad = c.get(f"{BASE}/images", params={"selection": "not-a-token"})
    assert bad.status_code == 404 and bad.json()["detail"] == "selection not found"

    # a token is scoped to the project it was created for
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        other = Project(
            workspace_id=ws.id,
            slug=f"insights-other-{uuid.uuid4().hex[:8]}",
            name="other",
            type="object-detection",
            settings={},
        )
        db.add(other)
        db.flush()
        img = Image(
            project_id=other.id,
            name="other-1",
            sha256="f" * 64,
            width=8,
            height=8,
            path="",
            thumb="",
            split="train",
        )
        db.add(img)
        db.commit()
        other_pid, other_image_id = other.id, img.id
    with SessionLocal() as db:
        other_token = insights.save_selection(db, db.get(Project, other_pid), [other_image_id])["token"]

    assert c.get(f"{INS}/selections/{other_token}").status_code == 404
    assert c.get(f"{BASE}/images", params={"selection": other_token}).status_code == 404


def test_embedding_job_runs_under_the_gpu_lease(c, data, monkeypatch):
    from app import worker
    from app.gpu import GpuScheduler

    seen = {}
    released = []

    def fake_scan(_db, _project, should_stop=None):
        seen["holder"] = worker.scheduler.holder
        return {"signature": [], "points": [], "projection": "pca"}

    sched = GpuScheduler(4500, None)
    monkeypatch.setattr(worker, "scheduler", sched)
    monkeypatch.setattr(worker.insights_jobs, "scan_embedding", fake_scan)
    monkeypatch.setattr(worker.insights_embedding, "clip_available", lambda: True)
    monkeypatch.setattr(worker.insights_embedding, "release_clip", lambda: released.append(True))
    worker.run_insights_embedding(SimpleNamespace(id="job-test", project_id=data["project"]["id"]))
    assert seen["holder"] == "insights embedding"
    assert released == [True]          # CLIP never outlives the scan's lease
    assert sched.state()["holder"] is None


def test_embedding_job_stays_off_the_gpu_when_clip_cannot_run(c, data, monkeypatch):
    """A CPU-only build must not pause streams or sleep vLLM for a scan that never touches the card."""
    from app import worker
    from app.gpu import GpuScheduler

    vlm_calls: list[str] = []
    seen = {}

    class FakeVlm:
        def sleep(self, level=1):
            vlm_calls.append("sleep")

        def wake(self):
            vlm_calls.append("wake")

    def fake_scan(_db, _project, should_stop=None):
        seen["holder"] = worker.scheduler.holder
        return {"signature": [], "points": [], "projection": "pca"}

    sched = GpuScheduler(4500, FakeVlm())
    monkeypatch.setattr(worker, "scheduler", sched)
    monkeypatch.setattr(worker.insights_jobs, "scan_embedding", fake_scan)
    monkeypatch.setattr(worker.insights_embedding, "clip_available", lambda: False)
    worker.run_insights_embedding(SimpleNamespace(id="job-test", project_id=data["project"]["id"]))
    assert seen["holder"] is None
    assert vlm_calls == []
    assert sched.state()["holder"] is None
