"""Regression guard, area 2: upload, dataset grid, splits, deletion, health (T-002).

Pins the eleven shipped rows a later area-2 card must not break silently:
`2-F2.1` (duplicate pre-check), `2-F2.9` (one refusal rule set), `2-F2.22` (selection + bulk bar),
`2-F2.23` (the board is the dataset pipeline), `2-F2.37` / `2-F2.38` (health report and its cache),
`2-F2.39` (split decided at ingest), `2-F2.40` (bulk split), `2-F2.42` (versions freeze their split),
`2-F2.43` / `2-F2.44` (single and bulk removal).

Every test builds its own workspace through `issue_access`, so the guard never depends on the demo
workspace's Free-plan caps or another module's rows. The version rows call `versioning.generate`
directly, so nothing here waits on the embedded worker.
"""
import asyncio
import hashlib
import io
import json
import random
import time
import zipfile

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import func, select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.deps import Ctx
from app.main import app
from app.models import SPLITS, Image, Job, Member, Project, User, Version, Workspace
from app.routers import images as images_router
from app.security import issue_access
from app.services import health, metering, versioning


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _jpeg(color: tuple[int, int, int]) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", (64, 48), color).save(b, "JPEG")
    return b.getvalue()


def _workspace(slug: str, *, labeler: bool = False) -> dict:
    """A throwaway workspace, its admin and one project: the caller every area-2 row is asserted with."""
    with SessionLocal() as db:
        u = User(email=f"{slug}@guard-area2.test", name=slug, pw_hash="", email_verified=time.time())
        db.add(u)
        db.flush()
        ws = Workspace(slug=slug, name=slug, owner_id=u.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=u.id, role="admin"))
        out = {"id": ws.id, "slug": slug, "user": u.id}
        if labeler:
            lu = User(email=f"{slug}-labeler@guard-area2.test", name=f"{slug}-labeler", pw_hash="",
                      email_verified=time.time())
            db.add(lu)
            db.flush()
            db.add(Member(workspace_id=ws.id, user_id=lu.id, role="annotator"))
            out["labeler"] = lu.id
        p = Project(workspace_id=ws.id, slug=f"{slug}-p", name="Guard area 2", face_blur=False)
        db.add(p)
        db.commit()
        out.update(pid=p.id, pslug=p.slug, base=f"/api/ws/{slug}/projects/{p.slug}",
                   h={"Authorization": f"Bearer {issue_access(u.id)}"})
        return out


def _upload(c, a: dict, names: list[str], split: str = "train") -> list[str]:
    files = [("files", (f"{n}.jpg", _jpeg((i * 37 % 256, i * 91 % 256, i * 53 % 256))))
             for i, n in enumerate(names)]
    r = c.post(f"{a['base']}/upload", headers=a["h"], files=files, data={"split": split})
    assert r.status_code == 200, r.text
    return [x["id"] for x in r.json()["images"]]


def test_precheck_lists_live_duplicate_hashes_only(c):
    """`2-F2.1`: the drop zone's pre-check names hashes of rows that still exist."""
    a = _workspace("guard-area2-precheck")
    data = _jpeg((10, 20, 30))
    sha = hashlib.sha256(data).hexdigest()
    up = c.post(f"{a['base']}/upload", headers=a["h"], files=[("files", ("one.jpg", data))],
                data={"split": "train"})
    assert up.status_code == 200, up.text
    image_id = up.json()["images"][0]["id"]

    found = c.post(f"{a['base']}/uploads/check", headers=a["h"], json={"hashes": [sha]})
    assert found.status_code == 200, found.text
    assert found.json()["duplicates"] == [sha], "a live image's SHA-256 is listed exactly once"

    deleted = c.delete(f"/api/images/{image_id}", headers=a["h"])
    assert deleted.status_code == 200, deleted.text
    again = c.post(f"{a['base']}/uploads/check", headers=a["h"], json={"hashes": [sha]})
    assert again.json()["duplicates"] == [], "a soft-deleted row must not block the same bytes forever"


def test_upload_caps_files_and_bytes_before_writing(c, monkeypatch):
    """`2-F2.9`: one refusal rule set — 2,000 files per request, then the byte budget.

    Starlette's multipart parser refuses more than 1,000 parts before the route can run, so the
    route's own 2,000-file guard is asserted by calling the handler with the parsed file list it
    receives; the byte budget is reached over HTTP.
    """
    a = _workspace("guard-area2-cap")
    with SessionLocal() as db:
        u, ws = db.get(User, a["user"]), db.get(Workspace, a["id"])
        p = db.get(Project, a["pid"])
        ctx = Ctx(user=u, ws=ws, role=db.get(Member, (ws.id, u.id)).role, db=db, project=p)
        too_many = [UploadFile(file=io.BytesIO(b"x"), filename=f"{i}.jpg") for i in range(2001)]
        with pytest.raises(HTTPException) as refused:
            asyncio.run(images_router.upload(files=too_many, c=ctx))
        assert refused.value.status_code == 413
        assert "max 2000 files" in refused.value.detail
        assert db.scalar(select(func.count(Image.id)).where(Image.project_id == p.id)) == 0

    monkeypatch.setattr("app.routers.images.MAX_UPLOAD_MB", 1)
    big = c.post(f"{a['base']}/upload", headers=a["h"],
                 files=[("files", ("big.jpg", b"\0" * (2 * 1024 * 1024)))])
    assert big.status_code == 413, big.text
    assert "upload larger than 1 MB" in big.text

    assert c.get(f"{a['base']}/images", headers=a["h"]).json()["total"] == 0, \
        "both refusals answer before a single row is written"


def test_bulk_split_and_tags_touch_only_the_selection(c):
    """`2-F2.22` / `2-F2.40`: Move split, Tag act on the selection and nowhere else."""
    a = _workspace("guard-area2-bulk")
    ids = _upload(c, a, ["one", "two", "three"])
    selected = ids[:2]

    moved = c.post(f"{a['base']}/images/bulk", headers=a["h"],
                   json={"ids": selected, "action": "split", "value": "valid"})
    assert moved.status_code == 200, moved.text
    assert moved.json() == {"updated": 2}
    third = c.get(f"{a['base']}/images", headers=a["h"], params={"ids": ids[2]}).json()["items"]
    assert third[0]["split"] == "train", "the unselected image keeps its split"
    assert c.get(f"{a['base']}/images", headers=a["h"], params={"split": "valid"}).json()["total"] == 2

    added = c.post(f"{a['base']}/images/bulk", headers=a["h"],
                   json={"ids": selected, "action": "add_tag", "value": "keep"})
    assert added.json() == {"updated": 2}
    tagged = c.get(f"{a['base']}/images", headers=a["h"], params={"tag": "keep"}).json()
    assert tagged["total"] == 2 and all("keep" in x["tags"] for x in tagged["items"])

    removed = c.post(f"{a['base']}/images/bulk", headers=a["h"],
                     json={"ids": selected, "action": "remove_tag", "value": "keep"})
    assert removed.json() == {"updated": 2}
    assert c.get(f"{a['base']}/images", headers=a["h"], params={"tag": "keep"}).json()["total"] == 0


def test_bulk_delete_reports_the_count_and_hides_the_rows(c):
    """`2-F2.43` / `2-F2.44`: the counted delete hides the rows, erases the bytes and refunds once."""
    a = _workspace("guard-area2-delete")
    ids = _upload(c, a, ["d-one", "d-two", "d-three"])
    with SessionLocal() as db:
        paths = [db.get(Image, i).path for i in ids[:2]]
        before = metering.used(db, db.get(Workspace, a["id"]), "storage_bytes")
    assert before > 0

    first = c.post(f"{a['base']}/images/bulk", headers=a["h"], json={"ids": ids[:2], "action": "delete"})
    assert first.status_code == 200, first.text
    assert first.json() == {"updated": 2}
    assert c.get(f"{a['base']}/images", headers=a["h"]).json()["total"] == 1
    for rel in paths:
        assert not (DATA_DIR / rel).exists(), "the deleted bytes are gone from storage"

    with SessionLocal() as db:
        after_first = metering.used(db, db.get(Workspace, a["id"]), "storage_bytes")
    assert after_first < before, "the storage meter credits the erased bytes"

    again = c.post(f"{a['base']}/images/bulk", headers=a["h"], json={"ids": ids[:2], "action": "delete"})
    assert again.status_code == 200, again.text
    assert again.json() == {"updated": 2}
    with SessionLocal() as db:
        assert metering.used(db, db.get(Workspace, a["id"]), "storage_bytes") == after_first, \
            "a second delete must not refund the same bytes twice"
        rows = db.scalars(select(Image).where(Image.id.in_(ids[:2]))).all()
        assert all(r.deleted_at is not None for r in rows)
    assert c.get(f"{a['base']}/images", headers=a["h"]).json()["total"] == 1, "hidden rows stay hidden"


def test_health_queues_one_scan_and_reports_staleness(c):
    """`2-F2.37` / `2-F2.38`: one queued scan, then the service's no-retry guard and a stale-aware report."""
    a = _workspace("guard-area2-health")
    r = c.post(f"{a['base']}/health", headers=a["h"], json={"imgsz": 640})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "health"

    # Pin the job as running for the current signature so the guard, not the worker's timing, decides.
    with SessionLocal() as db:
        p = db.get(Project, a["pid"])
        j = db.get(Job, job["id"])
        j.status = "running"
        j.params = {**(j.params or {}), "signature": health.signature(db, p), "model_id": None}
        db.commit()

        def health_jobs() -> int:
            return db.scalar(select(func.count(Job.id)).where(Job.project_id == p.id, Job.kind == "health"))

        before = health_jobs()
        health.checks(db, p, auto_scan=True)
        assert health_jobs() == before, "a running scan for this signature blocks a second automatic scan"

    an = c.get(f"{a['base']}/analytics", headers=a["h"])
    assert an.status_code == 200, an.text
    body = an.json()
    assert {"checks", "health_stale", "health_job"} <= set(body)
    assert body["health_job"]["id"] == job["id"] and body["health_job"]["kind"] == "health"
    assert body["health_stale"] is False, "nothing changed since the queued scan"


def test_ingest_split_follows_the_folder_then_falls_back(c):
    """`2-F2.39`: a split folder decides the split; an unknown folder takes the request/random default."""
    a = _workspace("guard-area2-ingest")
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("valid/images/v.jpg", _jpeg((1, 2, 3)))
        f.writestr("train2017/x.jpg", _jpeg((4, 5, 6)))
    r = c.post(f"{a['base']}/upload", headers=a["h"], files=[("files", ("split.zip", z.getvalue()))],
               data={"split": "keep"})
    assert r.status_code == 200, r.text
    by_name = {x["name"]: x["split"] for x in r.json()["images"]}
    assert by_name["v.jpg"] == "valid", "valid/images/v.jpg follows its folder"
    assert by_name["x.jpg"] in SPLITS, "train2017 is not a split folder, so it falls back inside SPLITS"


def test_version_freezes_the_split_it_was_generated_with(c):
    """`2-F2.42`: a version keeps the split each image had at generation; a later move never reaches it."""
    a = _workspace("guard-area2-version")
    with SessionLocal() as db:
        ids = []
        for name, split in (("v-train", "train"), ("v-test", "test")):
            rel = f"guard2/version/{name}.jpg"
            rng = random.Random(name)
            im = PImage.frombytes("RGB", (96, 96), bytes(rng.getrandbits(8) for _ in range(96 * 96 * 3)))
            (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
            im.save(DATA_DIR / rel, "JPEG", quality=90)
            row = Image(project_id=a["pid"], name=f"{name}.jpg", sha256=name, width=96, height=96,
                        path=rel, thumb=rel, split=split, status="done", annotations=[], n_annotations=0)
            db.add(row)
            db.flush()
            ids.append(row.id)
        v1 = Version(project_id=a["pid"], number=1, name="frozen", status="ready", settings={})
        db.add(v1)
        db.commit()
        v1_id = v1.id

    with SessionLocal() as db:
        versioning.generate(db, db.get(Version, v1_id))

    first = json.loads((DATA_DIR / "versions" / v1_id / "manifest.json").read_text())
    assert {i["source"]: i["split"] for i in first["items"]} == {ids[0]: "train", ids[1]: "test"}

    moved = c.patch(f"/api/images/{ids[0]}", headers=a["h"], json={"split": "valid"})
    assert moved.status_code == 200, moved.text

    with SessionLocal() as db:
        v2 = Version(project_id=a["pid"], number=2, name="after-move", status="ready", settings={})
        db.add(v2)
        db.commit()
        v2_id = v2.id
        versioning.generate(db, db.get(Version, v2_id))

    second = json.loads((DATA_DIR / "versions" / v2_id / "manifest.json").read_text())
    assert {i["source"]: i["split"] for i in second["items"]} == {ids[0]: "valid", ids[1]: "test"}
    reread = json.loads((DATA_DIR / "versions" / v1_id / "manifest.json").read_text())
    assert {i["source"]: i["split"] for i in reread["items"]} == {ids[0]: "train", ids[1]: "test"}, \
        "the first version's manifest is frozen"


def test_a_labeler_sees_only_assigned_images_and_a_foreign_project_is_404(c):
    """Isolation line for all eleven rows: own rows only, and a foreign project slug never resolves."""
    a = _workspace("guard-area2-isolation", labeler=True)
    ids = _upload(c, a, ["mine", "someone-else"])
    assigned = c.post(f"{a['base']}/images/bulk", headers=a["h"],
                      json={"ids": [ids[0]], "action": "assign", "value": a["labeler"]})
    assert assigned.status_code == 200, assigned.text

    lab = {"Authorization": f"Bearer {issue_access(a['labeler'])}"}
    seen = c.get(f"{a['base']}/images", headers=lab)
    assert seen.status_code == 200, seen.text
    assert [x["id"] for x in seen.json()["items"]] == [ids[0]], "a labeler's grid holds assigned images only"

    other = _workspace("guard-area2-foreign")
    foreign = c.get(f"/api/ws/{other['slug']}/projects/{a['pslug']}/images", headers=other["h"])
    assert foreign.status_code == 404, "a second workspace's token on this project slug answers 404, not 403"
