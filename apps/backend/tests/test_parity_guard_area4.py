"""Parity guard area 4: a version's snapshot, numbering, train-only augmentation and cached export.

Tests only. Each guard names the HAVE row it protects. Rules another module already pins are not
repeated here: stratification/hash/export-cache concurrency (`test_versioning_v2.py`), auto-orient
(`test_playground.py`), resize-with-labels geometry (`test_obb_keypoints.py`), the insights values
(`test_insights.py`) and the health cache (`test_health.py`).
"""
import hashlib
import json
import random
import shutil
import uuid
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Image, Job, LabelClass, Member, Project, ProjectMember, User, Version, Workspace
from app.security import hash_password
from app.services import exporters, imaging, versioning
from conftest import login


def _write_image(name: str, w: int = 64, h: int = 64) -> str:
    rel = f"guard4/{name}.jpg"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(name)
    PImage.frombytes("RGB", (w, h), bytes(rng.getrandbits(8) for _ in range(w * h * 3))).save(
        DATA_DIR / rel, "JPEG", quality=90)
    return rel


def _user(prefix: str) -> str:
    uid = "u" + uuid.uuid4().hex[:12]
    with SessionLocal() as db:
        db.add(User(id=uid, email=f"guard4-{prefix}-{uuid.uuid4().hex[:8]}@x.io", name=prefix.title(),
                    pw_hash=hash_password("longpassword1"), email_verified=1.0))
        db.commit()
    return uid


def _client(user_id: str) -> TestClient:
    """Sign in as that seeded guard account through the real route: it carries the guard password."""
    with SessionLocal() as db:
        email = db.get(User, user_id).email
    c = TestClient(app)
    c.headers.update(login(c, email, "longpassword1"))
    return c


def _workspace(tag: str, owner_id: str | None = None) -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    owner_id = owner_id or _user(tag)
    with SessionLocal() as db:
        ws = Workspace(id="w" + suffix, slug=f"guard4-{tag}-{suffix}", name=f"Guard 4 {tag}",
                       owner_id=owner_id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=owner_id, role="owner"))
        db.commit()
        return ws.id, ws.slug, owner_id


@pytest.fixture(scope="module")
def world():
    ws_id, ws_slug, owner_id = _workspace("main")
    w = {"ws_id": ws_id, "ws_slug": ws_slug, "owner_id": owner_id,
         "client": _client(owner_id), "versions": []}
    yield w
    w["client"].close()
    for vid in w["versions"]:
        shutil.rmtree(DATA_DIR / "versions" / vid, ignore_errors=True)


def _project(world, tag: str, splits=("train", "valid", "test"), ptype="object-detection",
             ws_slug: str | None = None) -> dict:
    slug = f"guard4-{tag}-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        p = Project(workspace_id=world["ws_id"], slug=slug, name=slug, type=ptype, settings={})
        db.add(p)
        db.flush()
        widget = LabelClass(project_id=p.id, name="widget", color="#6366f1")
        gadget = LabelClass(project_id=p.id, name="gadget", color="#22c55e")
        db.add_all([widget, gadget])
        db.flush()
        for i, split in enumerate(splits):
            name = f"{slug}-{i}"
            rel = _write_image(name)
            db.add(Image(id=f"g4{uuid.uuid4().hex[:10]}", project_id=p.id, name=f"{name}.jpg",
                         sha256=hashlib.sha256(name.encode()).hexdigest(), width=64, height=64,
                         path=rel, thumb=rel, split=split, status="done",
                         annotations=[{"id": f"a{i}", "classId": widget.id,
                                       "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]))
        db.commit()
        return {"id": p.id, "slug": slug, "class_id": widget.id,
                "base": f"/api/ws/{ws_slug or world['ws_slug']}/projects/{slug}"}


def _version(world, project: dict, settings: dict, name: str = "") -> str:
    """A ready Version row plus one direct generate call: no job is created or awaited."""
    with SessionLocal() as db:
        n = (db.scalar(select(func.max(Version.number)).where(Version.project_id == project["id"])) or 0) + 1
        v = Version(project_id=project["id"], number=n, name=name, settings=settings)
        db.add(v)
        db.flush()
        v.stats, v.status = versioning.generate(db, v), "ready"
        db.commit()
        vid = v.id
    world["versions"].append(vid)
    return vid


def _manifest(vid: str) -> dict:
    return json.loads((DATA_DIR / "versions" / vid / "manifest.json").read_text())


def test_version_numbers_are_sequential_and_unnamed_versions_fall_back_to_vn(world):
    """4-F4.2: number is max+1 per project and an empty name renders as v{n}."""
    p = _project(world, "numbers", splits=("train",))
    c = world["client"]
    before = c.get(f"{p['base']}/versions").json()
    assert before == []                              # empty list state, as the Versions screen shows it
    top = max((v["number"] for v in before), default=0)

    first = c.post(f"{p['base']}/versions", json={"settings": {}}).json()
    second = c.post(f"{p['base']}/versions", json={"settings": {}}).json()
    assert (first["number"], second["number"]) == (top + 1, top + 2)

    rows = c.get(f"{p['base']}/versions").json()
    assert [r["number"] for r in rows] == [second["number"], first["number"]]
    assert all(r["name"] == f"v{r['number']}" for r in rows)


def test_an_existing_version_manifest_is_unchanged_by_later_edits(world):
    """4-F4.1: the manifest and its hash are frozen; later dataset edits never reach the version."""
    p = _project(world, "snapshot", splits=("train", "test"))
    vid = _version(world, p, {"preprocessing": {}, "augmentation": {}})
    m0 = _manifest(vid)
    path = DATA_DIR / "versions" / vid / "manifest.json"
    before = path.read_bytes()
    items0, hash0 = m0["items"], m0["version_hash"]
    splits0 = dict(Counter(it["split"] for it in items0))

    with SessionLocal() as db:
        img = db.scalars(select(Image).where(Image.project_id == p["id"]).order_by(Image.created)).first()
        img.annotations = [{**img.annotations[0], "shape": {"kind": "bbox", "x": .5, "y": .5, "w": .2, "h": .2}}]
        img.split = "valid" if img.split != "valid" else "train"
        db.commit()
        edited, edited_split = img.id, img.split

    assert path.read_bytes() == before                     # the file on disk is the frozen truth
    m1 = _manifest(vid)
    assert m1["items"] == items0
    assert dict(Counter(it["split"] for it in m1["items"])) == splits0
    assert m1["version_hash"] == hash0

    served = world["client"].get(f"{p['base']}/versions/{vid}").json()
    assert served["stats"]["images"] == len(items0)
    assert served["stats"]["splits"] == splits0

    # the edit is real: a version generated now carries it, the frozen one still does not
    fresh = _manifest(_version(world, p, {"preprocessing": {}, "augmentation": {}}))
    assert [it["split"] for it in fresh["items"] if it["source"] == edited] == [edited_split]
    assert [it["split"] for it in items0 if it["source"] == edited] != [edited_split]


def test_augmentation_copies_are_written_only_under_train(world):
    """4-F4.28: augmentation scope is the train split; valid and test keep their source images."""
    p = _project(world, "augment", splits=("train", "test"))
    vid = _version(world, p, {"preprocessing": {}, "augmentation": {"outputs": 2, "flip_h": True}})
    items = _manifest(vid)["items"]
    copies = [it for it in items if Path(it["file"]).stem.endswith("_aug1")]
    assert copies and all(it["split"] == "train" for it in copies)
    counts = Counter(it["split"] for it in items)
    assert counts["test"] == 1                              # one source image, no copies
    assert counts["train"] == 2                             # the original plus one augmented copy


def test_grayscale_preprocessing_keeps_size_and_drops_colour():
    """4-F4.19: grayscale keeps the image size and the normalized annotations."""
    im = PImage.new("RGB", (40, 20), (200, 40, 90))
    anns = [{"classId": "widget", "shape": {"kind": "bbox", "x": .1, "y": .2, "w": .3, "h": .4}}]
    out, out_anns = imaging.preprocess(im, anns, {"grayscale": True})
    assert out.size == (40, 20)
    r, g, b = out.getpixel((7, 5))
    assert r == g == b
    assert (r, g, b) != (200, 40, 90)
    assert out_anns == anns
    assert im.getpixel((7, 5)) == (200, 40, 90)             # the source image is untouched


def test_versions_list_is_newest_first_and_reports_counts(world):
    """4-F4.8 + 4-F4.10: the index is newest-first with counts, exports and job state."""
    p = _project(world, "index")
    for _ in range(3):
        _version(world, p, {"preprocessing": {}, "augmentation": {}})
    rows = world["client"].get(f"{p['base']}/versions").json()
    assert [r["number"] for r in rows] == [3, 2, 1]
    for r in rows:
        assert {"status", "stats", "exports", "job"} <= set(r)
        assert isinstance(r["stats"]["images"], int)
        assert sum(r["stats"]["splits"].values()) == r["stats"]["images"]
        assert isinstance(r["exports"], dict)

    other = _project(world, "index-other", splits=("train",))
    foreign = _version(world, other, {"preprocessing": {}, "augmentation": {}})
    r = world["client"].get(f"{p['base']}/versions/{foreign}")
    assert r.status_code == 404, r.text


def test_export_is_filtered_by_project_type_and_reuses_the_done_job(world):
    """4-F4.36: formats follow the project type; a repeat request reuses the cached artefact."""
    p = _project(world, "export", splits=("train",))
    c = world["client"]
    formats = c.get(f"{p['base']}/versions/formats").json()
    assert {f["id"] for f in formats} == {k for k, v in exporters.FORMATS.items()
                                          if "object-detection" in v["tasks"]}
    assert "folder" not in {f["id"] for f in formats}       # classification-only format stays out

    vid = _version(world, p, {"preprocessing": {}, "augmentation": {}})
    rel = f"exports/{vid}/coco.zip"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / rel).write_bytes(b"zip")
    with SessionLocal() as db:
        job = Job(workspace_id=world["ws_id"], project_id=p["id"], kind="export", status="done",
                  params={"version_id": vid, "format": "coco"}, result={"file": rel})
        db.add(job)
        db.commit()
        job_id = job.id

    def export_rows() -> int:
        with SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(Job)
                             .where(Job.project_id == p["id"], Job.kind == "export"))

    before = export_rows()
    again = c.post(f"{p['base']}/versions/{vid}/export", json={"format": "coco"})
    assert again.status_code == 200, again.text
    assert again.json()["id"] == job_id
    assert again.json()["url"].startswith(f"/api/files/exports/{vid}/coco.zip?")
    assert export_rows() == before                          # no second row

    with SessionLocal() as db:
        pending = Version(project_id=p["id"], number=99, status="building", settings={})
        db.add(pending)
        db.commit()
        pending_id = pending.id
    r = c.post(f"{p['base']}/versions/{pending_id}/export", json={"format": "coco"})
    assert r.status_code == 409
    assert r.json()["detail"] == "version is still generating"


def test_export_needs_project_export_permission_and_a_foreign_version_is_404(world):
    """4-F4.36 permissions + workspace isolation: a labeler gets 403, a foreign version is 404."""
    p = _project(world, "auth", splits=("train",))
    vid = _version(world, p, {"preprocessing": {}, "augmentation": {}})

    labeler = _user("labeler")
    with SessionLocal() as db:
        db.add(Member(workspace_id=world["ws_id"], user_id=labeler, role="member"))
        db.add(ProjectMember(project_id=p["id"], user_id=labeler, role="labeler"))
        db.commit()
    with _client(labeler) as lc:
        r = lc.post(f"{p['base']}/versions/{vid}/export", json={"format": "coco"})
        assert r.status_code == 403, r.text

    ws2_id, ws2_slug, manager2 = _workspace("other")
    with SessionLocal() as db:
        p2 = Project(workspace_id=ws2_id, slug=f"guard4-other-{uuid.uuid4().hex[:6]}", name="other")
        db.add(p2)
        db.commit()
        p2_slug = p2.slug
    with _client(manager2) as mc:
        r = mc.get(f"/api/ws/{ws2_slug}/projects/{p2_slug}/versions/{vid}")
        assert r.status_code == 404, r.text


def test_version_scoped_analytics_and_diff_keep_their_documented_shape(world):
    """4-F4.40, 4-F4.41, 4-F4.45: the version-scoped analytics payload keys the UI reads."""
    p = _project(world, "analytics", splits=("train", "test"))
    base = _version(world, p, {"preprocessing": {}, "augmentation": {}})
    target = _version(world, p, {"preprocessing": {}, "augmentation": {}})
    c = world["client"]
    diff = c.get(f"{p['base']}/insights/version-diff", params={"base": base, "target": target}).json()
    assert {"added", "removed", "split_moves", "class_delta", "summary"} <= set(diff)
    assert set(diff["summary"]) == {"added", "removed", "moved"}

    dist = c.get(f"{p['base']}/insights/distribution", params={"version": target}).json()
    assert "split_classes" in dist
    geo = c.get(f"{p['base']}/insights/geometry", params={"version": target}).json()
    assert "aspect" in geo and "area_buckets" in geo
