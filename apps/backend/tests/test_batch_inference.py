"""Batch inference jobs: batch/video/bucket inputs, CSV/COCO files and dataset write-back.

Fakes only at the GPU and network seams: the adapter registry is swapped per test and the
connector listing/download functions are replaced, so no GPU, SDK or network is needed.
"""
import csv
import io
import json
import os
import time
import uuid

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import delete, func, select

from app.adapters import ADAPTERS, Availability
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Batch, Connector, Image, Job, LabelClass, Member, Project, User, Video, Workspace, WorkspaceFlag
from app.security import issue_access
from app.services import batch_inference, flags, metering

WS = "labeldesk-demo"
THAI = "ป้ายทะเบียน"


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def set_flag(enabled: bool) -> None:
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_36", enabled)
        db.commit()


def token(email: str = "demo@labeldesk.dev") -> str:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
    return issue_access(user.id)


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token()}"
        yield client


@pytest.fixture(scope="module")
def labeler():
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token('labeler@labeldesk.dev')}"
        yield client


@pytest.fixture(autouse=True)
def flag_on():
    """Every test starts with the feature enabled; the off test flips it and restores it."""
    set_flag(True)
    yield


@pytest.fixture(scope="module", autouse=True)
def _drop_flag_rows():
    yield
    with SessionLocal() as db:
        db.execute(delete(WorkspaceFlag).where(WorkspaceFlag.key == "task_36"))
        db.commit()


def jpeg(color=(200, 50, 50), size=(320, 240)) -> bytes:
    b = io.BytesIO()
    PImage.new("RGB", size, color).save(b, "JPEG")
    return b.getvalue()


def box(cls="person", conf=0.9, x=50.0, y=40.0, w=30.0, h=20.0) -> dict:
    return {"class": cls, "class_id": 0, "confidence": conf, "x": x, "y": y, "width": w, "height": h}


class FakeDetector:
    family = "ultralytics"

    def __init__(self, preds=None, error: Exception | None = None):
        self.preds = [box()] if preds is None else preds
        self.error = error
        self.calls = 0

    def probe(self):
        return Availability(True)

    def capabilities(self, variant):
        return {"detect"}

    def predict(self, variant, im, *, classes=None, prompt=None, weights=None, conf=0.4, iou=0.5):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {
            "predictions": [dict(p) for p in self.preds],
            "time": 0.0,
            "image": {"width": im.width, "height": im.height},
        }


@pytest.fixture(scope="module")
def project(c):
    name = f"batch-infer-{uuid.uuid4().hex[:8]}"
    p = c.post(f"/api/ws/{WS}/projects",
               json={"name": name, "type": "object-detection", "classes": ["person"]}).json()
    base = f"/api/ws/{WS}/projects/{p['slug']}"
    files = [("files", (f"batch-{i}.jpg", jpeg((20 + i * 40, 70, 90)))) for i in range(3)]
    up = c.post(f"{base}/upload", files=files, data={"split": "train", "batch_name": "batch inference"})
    assert up.status_code == 200 and up.json()["uploaded"] == 3, up.text
    yield {
        "id": p["id"],
        "slug": p["slug"],
        "base": base,
        "batch_id": up.json()["batch"]["id"],
        "images": [x["id"] for x in up.json()["images"]],
    }
    c.delete(base)


def wait_job(c, base, jid, timeout=90):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"{base}/batch-inference/{jid}").json()
        if j.get("status") in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.2)
    raise TimeoutError(jid)


def run(c, base, payload):
    r = c.post(f"{base}/batch-inference", json=payload)
    assert r.status_code == 200, r.text
    return wait_job(c, base, r.json()["id"])


def read_result(job):
    return (DATA_DIR / job["result"]["file"]).read_bytes()


# --- feature flag -------------------------------------------------------------------


def test_routes_are_404_while_the_flag_is_off(c, project, monkeypatch):
    monkeypatch.delenv("LD_FLAGS_ON", raising=False)      # a dev shell may force the key on
    set_flag(False)
    try:
        assert c.get(f"{project['base']}/batch-inference").status_code == 404
        r = c.post(
            f"{project['base']}/batch-inference",
            json={"model_ref": "ultralytics:yolo26n", "source": {"kind": "batch", "batch_id": project["batch_id"]}},
        )
        assert r.status_code == 404
    finally:
        set_flag(True)


# --- outputs ------------------------------------------------------------------------


def test_csv_output_has_one_row_per_detection(c, project, monkeypatch):
    fake = FakeDetector([box("person", 0.9), box("helmet", 0.8, x=100, y=80, w=20, h=20)])
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    job = run(
        c,
        project["base"],
        {
            "model_ref": "ultralytics:yolo26n",
            "output": "csv",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert job["status"] == "done", job
    assert job["result"]["images"] == 3 and job["result"]["predictions"] == 6
    assert job["result"]["quota_clamped"] is False
    rows = list(csv.DictReader(io.StringIO(read_result(job).decode("utf-8-sig"))))
    assert len(rows) == 6
    assert rows[0]["image"] == "batch-0.jpg"
    assert rows[0]["class"] == "person" and float(rows[0]["confidence"]) == pytest.approx(0.9)
    assert [float(rows[0][k]) for k in ("x_min", "y_min", "x_max", "y_max")] == pytest.approx([35, 30, 65, 50])
    assert job["url"].startswith("/api/files/")


def test_csv_escapes_formula_cells_and_writes_a_bom(tmp_path):
    path = tmp_path / "out.csv"
    rows = [
        {"image": "=1+1.jpg", "class": THAI, "confidence": 0.5, "box": (1, 2, 3, 4), "points": None},
        {"image": "batch-a.jpg", "class": "+SUM(A1)", "confidence": None, "box": None, "points": None},
    ]
    batch_inference._write_csv(path, rows)
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                     # Excel reads Thai without mojibake
    text = raw.decode("utf-8-sig")
    cells = list(csv.reader(io.StringIO(text)))[1:]
    assert cells[0][0] == "'=1+1.jpg" and cells[0][1] == THAI
    assert cells[0][2] == "0.5"
    assert cells[1][0] == "batch-a.jpg" and cells[1][1] == "'+SUM(A1)"
    assert cells[1][2:] == ["", "", "", "", ""]


def test_coco_output_is_a_valid_coco_document(c, project, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box("person", 0.9)]))
    job = run(
        c,
        project["base"],
        {
            "model_ref": "ultralytics:yolo26n",
            "output": "coco",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert job["status"] == "done", job
    d = json.loads(read_result(job))
    assert len(d["images"]) == 3 and len(d["annotations"]) == 3
    assert {x["name"] for x in d["categories"]} == {"person"}
    ann = d["annotations"][0]
    assert ann["bbox"] == pytest.approx([35, 30, 30, 20])
    assert ann["area"] == pytest.approx(600) and ann["score"] == pytest.approx(0.9)
    assert ann["category_id"] == d["categories"][0]["id"]
    assert next(i for i in d["images"] if i["id"] == ann["image_id"])["file_name"] == "batch-0.jpg"


def test_coco_is_rejected_for_a_classification_model(c, project):
    r = c.post(
        f"{project['base']}/batch-inference",
        json={
            "model_ref": "ultralytics:yolo26n-cls",
            "output": "coco",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert r.status_code == 400 and "COCO" in r.json()["detail"]


def test_dataset_output_saves_annotations_with_the_model_source(c, project, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box("person", 0.9)]))
    payload = {
        "model_ref": "ultralytics:yolo26n",
        "output": "dataset",
        "source": {"kind": "batch", "batch_id": project["batch_id"]},
    }
    job = run(c, project["base"], payload)
    assert job["status"] == "done" and job["result"]["annotations"] == 3, job
    with SessionLocal() as db:
        anns = [a for i in project["images"] for a in (db.get(Image, i).annotations or [])]
    assert len(anns) == 3 and all(a["source"] == "ultralytics:yolo26n" for a in anns)
    # append semantics: a second run adds its own annotations instead of replacing the first result
    run(c, project["base"], payload)
    with SessionLocal() as db:
        anns = [a for i in project["images"] for a in (db.get(Image, i).annotations or [])]
    assert len(anns) == 6


# --- inputs -------------------------------------------------------------------------


def test_video_source_runs_on_its_sampled_frames(c, project, monkeypatch):
    with SessionLocal() as db:
        v = Video(project_id=project["id"], workspace_id=_ws_id(), name="clip.mp4", path="videos/clip.mp4",
                  status="ready")
        db.add(v)
        db.flush()
        for index, img_id in enumerate(project["images"][:2]):
            img = db.get(Image, img_id)
            img.video_id, img.frame_index = v.id, index
        db.commit()
        vid = v.id
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    job = run(
        c,
        project["base"],
        {"model_ref": "ultralytics:yolo26n", "output": "csv", "source": {"kind": "video", "video_id": vid}},
    )
    assert job["status"] == "done" and job["result"]["images"] == 2, job


def test_connector_source_downloads_through_the_bucket_reader(c, project, monkeypatch):
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{uuid.uuid4().hex[:6]}", kind="s3",
                         config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
    seen = []

    def fake_list(conn, prefix="", limit=100):
        return [{"key": f"{prefix}p{b}.jpg", "size": 1} for b in range(2)]

    def fake_fetch(conn, key):
        seen.append(key)
        return jpeg((10 + len(seen) * 40, 20, 30))

    monkeypatch.setattr(batch_inference.connectors, "list_objects", fake_list)
    monkeypatch.setattr(batch_inference.connectors, "fetch_bytes", fake_fetch)
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    try:
        job = run(
            c,
            project["base"],
            {
                "model_ref": "ultralytics:yolo26n",
                "output": "csv",
                "source": {"kind": "connector", "connector_id": cid, "prefix": "in/", "limit": 2},
            },
        )
        assert job["status"] == "done" and job["result"]["images"] == 2, job
        assert seen == ["in/p0.jpg", "in/p1.jpg"]
        rows = list(csv.DictReader(io.StringIO(read_result(job).decode("utf-8-sig"))))
        assert {r["image"] for r in rows} == {"in/p0.jpg", "in/p1.jpg"}
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()


def test_connector_dataset_materialises_only_new_images(c, project, monkeypatch):
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{uuid.uuid4().hex[:6]}", kind="s3",
                         config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
    images = [jpeg((90, 10, 10)), jpeg((10, 90, 10))]
    monkeypatch.setattr(batch_inference.connectors, "list_objects",
                        lambda conn, prefix="", limit=100: [{"key": f"in/{i}.jpg"} for i in range(2)])
    monkeypatch.setattr(batch_inference.connectors, "fetch_bytes", lambda conn, key: images[int(key[-5])])
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box("helmet", 0.8)]))
    payload = {
        "model_ref": "ultralytics:yolo26n",
        "output": "dataset",
        "source": {"kind": "connector", "connector_id": cid, "prefix": "in/", "limit": 2},
    }
    try:
        job = run(c, project["base"], payload)
        assert job["status"] == "done", job
        assert job["result"]["images"] == 2 and job["result"]["annotations"] == 2
        assert job["result"]["batch_id"]
        with SessionLocal() as db:
            stored = db.scalar(select(Image.id).where(Image.project_id == project["id"],
                                                      Image.batch_id == job["result"]["batch_id"]))
            assert stored is not None, "the materialised images belong to the job's batch"
            assert db.scalar(select(LabelClass).where(LabelClass.project_id == project["id"],
                                                      LabelClass.name == "helmet")) is not None
        # identical bytes dedupe against the project, so the rerun stores nothing and reports no empty batch
        again = run(c, project["base"], payload)
        assert again["status"] == "done", again
        assert again["result"]["images"] == 2 and again["result"]["annotations"] == 2
        assert not again["result"].get("batch_id")
        with SessionLocal() as db:
            empty = db.scalar(select(Image.id).where(Image.project_id == project["id"],
                                                      Image.batch_id == again["result"].get("batch_id", "")))
            assert empty is None
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()


def test_connector_job_stops_at_the_ai_call_allowance(c, project, monkeypatch):
    with SessionLocal() as db:
        ws = db.get(Workspace, _ws_id())
        conn = Connector(workspace_id=ws.id, name=f"bucket-{uuid.uuid4().hex[:6]}", kind="s3",
                         config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
        used = metering.used(db, ws, "ai_calls", since=metering.month_start())
        before = dict(ws.quotas or {})
        ws.quotas = {**before, "ai_calls": used + 1}       # one call left on the plan
        db.commit()
    monkeypatch.setattr(batch_inference.connectors, "list_objects",
                        lambda conn, prefix="", limit=100: [{"key": f"in/{i}.jpg"} for i in range(2)])
    monkeypatch.setattr(batch_inference.connectors, "fetch_bytes", lambda conn, key: jpeg((5, 5, 5)))
    fake = FakeDetector([box()])
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    try:
        job = run(
            c,
            project["base"],
            {
                "model_ref": "ultralytics:yolo26n",
                "output": "csv",
                "source": {"kind": "connector", "connector_id": cid, "prefix": "in/", "limit": 2},
            },
        )
        assert job["status"] == "done", job
        assert job["result"]["images"] == 1 and job["result"]["quota_clamped"] is True, job
        with SessionLocal() as db:
            ws = db.get(Workspace, _ws_id())
            assert metering.used(db, ws, "ai_calls", since=metering.month_start()) <= used + 1
    finally:
        with SessionLocal() as db:
            ws = db.get(Workspace, _ws_id())
            ws.quotas = before or None
            db.commit()
            db.delete(db.get(Connector, cid))
            db.commit()


def test_connector_listing_failure_is_reported_without_a_framework_name(c, project, monkeypatch):
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{uuid.uuid4().hex[:6]}", kind="s3",
                         config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id

    def broken(conn, prefix="", limit=100):
        raise HTTPException(502, "connector listing failed")

    monkeypatch.setattr(batch_inference.connectors, "list_objects", broken)
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    try:
        job = run(
            c,
            project["base"],
            {"model_ref": "ultralytics:yolo26n", "source": {"kind": "connector", "connector_id": cid}},
        )
        assert job["status"] == "failed"
        assert job["error"] == "connector listing failed", job
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()


def test_a_failing_detector_reports_a_readable_job_error(c, project, monkeypatch):
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector(error=RuntimeError("detector unavailable")))
    job = run(
        c,
        project["base"],
        {
            "model_ref": "ultralytics:yolo26n",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert job["status"] == "failed"
    assert "inference failed for every image" in job["error"] and "detector unavailable" in job["error"]


def test_a_cancelled_inference_marks_the_job_cancelled(c, project, monkeypatch):
    from app.adapters import Cancelled

    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector(error=Cancelled("job cancelled")))
    job = run(
        c,
        project["base"],
        {
            "model_ref": "ultralytics:yolo26n",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert job["status"] == "cancelled", job          # a cancel must not be reported as a failure


# --- validation, permissions, isolation ----------------------------------------------


def test_unknown_and_foreign_sources_are_404(c, project, monkeypatch):
    r = c.post(
        f"{project['base']}/batch-inference",
        json={"model_ref": "ultralytics:yolo26n", "source": {"kind": "batch", "batch_id": "nope"}},
    )
    assert r.status_code == 404
    name = f"other-{uuid.uuid4().hex[:8]}"
    other = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"}).json()
    other_base = f"/api/ws/{WS}/projects/{other['slug']}"
    up = c.post(f"{other_base}/upload", files=[("files", ("x.jpg", jpeg((1, 2, 3))))])
    assert up.status_code == 200, up.text
    foreign_batch = up.json()["batch"]["id"]
    try:
        r = c.post(
            f"{project['base']}/batch-inference",
            json={"model_ref": "ultralytics:yolo26n",
                  "source": {"kind": "batch", "batch_id": foreign_batch}},
        )
        assert r.status_code == 404, r.text
        # a source in another workspace is equally invisible
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
            ws = Workspace(slug=f"tenant-{uuid.uuid4().hex[:8]}", name="Tenant", owner_id=user.id)
            db.add(ws)
            db.flush()
            db.add(Member(workspace_id=ws.id, user_id=user.id, role="admin"))
            p = Project(workspace_id=ws.id, slug="tenant", name="Tenant")
            db.add(p)
            db.commit()
            tenant_slug = ws.slug
        r = c.post(
            f"/api/ws/{tenant_slug}/projects/tenant/batch-inference",
            json={"model_ref": "ultralytics:yolo26n",
                  "source": {"kind": "batch", "batch_id": project["batch_id"]}},
        )
        assert r.status_code == 404, r.text
    finally:
        c.delete(other_base)
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == tenant_slug))
            if ws is not None:
                db.execute(delete(Project).where(Project.workspace_id == ws.id))
                db.execute(delete(Member).where(Member.workspace_id == ws.id))
                db.delete(ws)
                db.commit()


def test_connector_sources_require_workspace_connectors(c, labeler, project):
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{uuid.uuid4().hex[:6]}", kind="s3",
                         config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
    try:
        r = labeler.post(
            f"{project['base']}/batch-inference",
            json={"model_ref": "ultralytics:yolo26n",
                  "source": {"kind": "connector", "connector_id": cid, "limit": 1}},
        )
        assert r.status_code == 403 and "workspace.connectors" in r.json()["detail"]
        # a labeler may still run a batch source (project.infer)
        r = labeler.get(f"{project['base']}/batch-inference")
        assert r.status_code == 200
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()


def test_vlm_cannot_write_to_the_dataset(c, project):
    r = c.post(
        f"{project['base']}/batch-inference",
        json={
            "model_ref": "vlm:qwen2.5-vl-7b",
            "output": "dataset",
            "source": {"kind": "batch", "batch_id": project["batch_id"]},
        },
    )
    assert r.status_code == 400 and "SAM" in r.json()["detail"]


def test_workflow_source_reports_that_it_ships_with_task_31(c, project):
    r = c.post(
        f"{project['base']}/batch-inference",
        json={"model_ref": "ultralytics:yolo26n", "source": {"kind": "workflow"}},
    )
    assert r.status_code == 501 and "Task 31" in r.json()["detail"]


def test_limit_is_rejected_outside_connector_sources(c, project):
    r = c.post(
        f"{project['base']}/batch-inference",
        json={"model_ref": "ultralytics:yolo26n",
              "source": {"kind": "batch", "batch_id": project["batch_id"], "limit": 2}},
    )
    assert r.status_code == 400 and "limit" in r.json()["detail"]


def test_jobs_are_listed_for_the_project_only(c, project):
    r = c.get(f"{project['base']}/batch-inference")
    assert r.status_code == 200 and isinstance(r.json(), list)
    assert all(j["kind"] == "batch_infer" for j in r.json())


# --- quota clamp, erasure and the brief's edge cases ---------------------------------


def direct_job(project, **params) -> str:
    """A running job row as if a worker had claimed it; the in-process worker cannot lose a race."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        job = Job(workspace_id=_ws_id(), project_id=project["id"], kind="batch_infer", status="running",
                  params={"model_ref": "ultralytics:yolo26n", "classes": [], **params}, created_by=user.id)
        db.add(job)
        db.commit()
        return job.id


def _set_ai_calls(quota: float) -> dict:
    """Override the workspace's AI-call allowance; returns the previous overrides to restore."""
    with SessionLocal() as db:
        ws = db.get(Workspace, _ws_id())
        before = dict(ws.quotas or {})
        ws.quotas = {**before, "ai_calls": quota}
        db.commit()
    return before


def _restore_quotas(before: dict) -> None:
    with SessionLocal() as db:
        db.get(Workspace, _ws_id()).quotas = before or None
        db.commit()


def test_an_exhausted_allowance_completes_the_job_with_zero_work(c, project, monkeypatch):
    """I1: clamping before image 1 is a done, zero-work job — not 'every image was unreadable'."""
    from app import worker

    with SessionLocal() as db:
        ws = db.get(Workspace, _ws_id())
        used = metering.used(db, ws, "ai_calls", since=metering.month_start())
    before = _set_ai_calls(used)                       # nothing left on the plan
    fake = FakeDetector([box()])
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    jid = direct_job(project, output="csv", source={"kind": "batch", "batch_id": project["batch_id"]})
    try:
        worker.run_one(jid)
        with SessionLocal() as db:
            row = db.get(Job, jid)
        assert row.status == "done", row.error
        assert row.error == ""
        assert row.result["images"] == 0 and row.result["predictions"] == 0 and row.result["failed"] == 0
        assert row.result["quota_clamped"] is True
        assert fake.calls == 0                                    # not one billable call was attempted
    finally:
        _restore_quotas(before)
        with SessionLocal() as db:
            db.delete(db.get(Job, jid))
            db.commit()


def test_project_purge_erases_batch_inference_exports(c, monkeypatch):
    """I2: an export under DATA_DIR/batch_inference belongs to its project and no other."""
    import shutil

    from app.services import erasure

    name = f"batch-export-{uuid.uuid4().hex[:8]}"
    p = c.post(f"/api/ws/{WS}/projects", json={"name": name, "type": "object-detection"}).json()
    base = f"/api/ws/{WS}/projects/{p['slug']}"
    up = c.post(f"{base}/upload", files=[("files", ("export.jpg", jpeg((33, 44, 55))))])
    assert up.status_code == 200, up.text
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    job = run(
        c,
        base,
        {"model_ref": "ultralytics:yolo26n", "output": "csv",
         "source": {"kind": "batch", "batch_id": up.json()["batch"]["id"]}},
    )
    assert job["status"] == "done", job
    export = DATA_DIR / job["result"]["file"]
    assert export.exists() and export.parent == DATA_DIR / "batch_inference" / p["id"] / job["id"]
    other = DATA_DIR / "batch_inference" / f"other-{uuid.uuid4().hex[:8]}" / "job" / "predictions.csv"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"keep")
    try:
        with SessionLocal() as db:
            freed, ok = erasure.delete_project_data(db, db.get(Project, p["id"]))
        assert ok and freed > 0
        assert not (DATA_DIR / "batch_inference" / p["id"]).exists()
        assert other.exists(), "another project's export must survive the purge"
    finally:
        shutil.rmtree(other.parents[1], ignore_errors=True)
        c.delete(base)


def test_empty_batch_source_is_rejected(c, project):
    with SessionLocal() as db:
        b = Batch(project_id=project["id"], name="empty batch")
        db.add(b)
        db.commit()
        bid = b.id
    try:
        r = c.post(f"{project['base']}/batch-inference",
                   json={"model_ref": "ultralytics:yolo26n", "source": {"kind": "batch", "batch_id": bid}})
        assert r.status_code == 400 and "no images" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Batch, bid))
            db.commit()


def test_video_source_must_be_ready_and_have_frames(c, project):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        v = Video(project_id=project["id"], workspace_id=_ws_id(), name="clip.mp4",
                  path=f"videos/{suffix}.mp4", status="extracting")
        db.add(v)
        db.commit()
        vid = v.id
    payload = {"model_ref": "ultralytics:yolo26n", "source": {"kind": "video", "video_id": vid}}
    try:
        r = c.post(f"{project['base']}/batch-inference", json=payload)
        assert r.status_code == 400 and "still being extracted" in r.json()["detail"]
        with SessionLocal() as db:
            db.get(Video, vid).status = "ready"
            db.commit()
        r = c.post(f"{project['base']}/batch-inference", json=payload)
        assert r.status_code == 400 and "no images" in r.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Video, vid))
            db.commit()


def test_connector_prefix_with_no_images_fails_readably(c, project, monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{suffix}", kind="s3", config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
    monkeypatch.setattr(batch_inference.connectors, "list_objects", lambda conn, prefix="", limit=100: [])
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    try:
        job = run(c, project["base"],
                  {"model_ref": "ultralytics:yolo26n",
                   "source": {"kind": "connector", "connector_id": cid, "prefix": "in/", "limit": 2}})
        assert job["status"] == "failed"
        assert job["error"] == "no image objects found at that prefix"
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()


def test_foreign_workspace_connector_is_404_on_enqueue_and_stops_the_worker(c, project):
    from app import worker

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        ws = Workspace(id="w" + suffix, slug=f"foreign-{suffix}", name="Foreign", owner_id=user.id)
        db.add(ws)
        db.flush()
        conn = Connector(workspace_id=ws.id, name=f"bucket-{suffix}", kind="s3", config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
    jid = None
    try:
        r = c.post(f"{project['base']}/batch-inference",
                   json={"model_ref": "ultralytics:yolo26n",
                         "source": {"kind": "connector", "connector_id": cid, "limit": 1}})
        assert r.status_code == 404 and r.json()["detail"] == "connector not found"
        # the worker re-checks: a row that somehow references it never reads the bucket
        jid = direct_job(project, output="csv",
                         source={"kind": "connector", "connector_id": cid, "prefix": "", "limit": 1})
        worker.run_one(jid)
        with SessionLocal() as db:
            row = db.get(Job, jid)
            assert row.status == "failed" and row.error == "connector not found"
    finally:
        with SessionLocal() as db:
            if jid:
                db.delete(db.get(Job, jid))
            db.delete(db.get(Connector, cid))
            db.delete(db.get(Workspace, ws.id))
            db.commit()


def test_a_cancelling_job_stops_before_the_next_image(c, project, monkeypatch):
    """A real DB-driven cancel keeps the image already written and leaves the rest untouched."""
    def annotations_now() -> int:
        with SessionLocal() as db:
            return sum(len(db.get(Image, i).annotations or []) for i in project["images"])

    class CancellingDetector(FakeDetector):
        def predict(self, *args, **kwargs):
            out = super().predict(*args, **kwargs)
            with SessionLocal() as db:
                for row in db.scalars(select(Job).where(Job.kind == "batch_infer", Job.status == "running")):
                    row.status = "cancelling"
                db.commit()
            return out

    before = annotations_now()
    fake = CancellingDetector([box()])
    monkeypatch.setitem(ADAPTERS, "ultralytics", fake)
    job = run(c, project["base"],
              {"model_ref": "ultralytics:yolo26n", "output": "dataset",
               "source": {"kind": "batch", "batch_id": project["batch_id"]}})
    assert job["status"] == "cancelled", job
    assert fake.calls == 1, "the job must stop before the next billable call"
    assert annotations_now() == before + 1, "the finished image stays; no later image is written"


def test_connector_materialisation_respects_the_plan_image_limit(c, project, monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        conn = Connector(workspace_id=_ws_id(), name=f"bucket-{suffix}", kind="s3", config={"bucket": "demo"})
        db.add(conn)
        db.commit()
        cid = conn.id
        have = db.scalar(select(func.count(Image.id)).join(Project).where(
            Project.workspace_id == _ws_id(), Image.deleted_at.is_(None)))
    monkeypatch.setattr(batch_inference, "plan", lambda ws: {"images": int(have) + 1})
    monkeypatch.setattr(batch_inference.connectors, "list_objects",
                        lambda conn, prefix="", limit=100: [{"key": f"in/{i}.jpg"} for i in range(2)])
    monkeypatch.setattr(batch_inference.connectors, "fetch_bytes",
                        lambda conn, key: jpeg((7, int(key[-5]) * 20, 9)))
    monkeypatch.setitem(ADAPTERS, "ultralytics", FakeDetector([box()]))
    try:
        job = run(c, project["base"],
                  {"model_ref": "ultralytics:yolo26n", "output": "dataset",
                   "source": {"kind": "connector", "connector_id": cid, "prefix": "in/", "limit": 2}})
        assert job["status"] == "failed", job
        assert "image limit" in job["error"]
        with SessionLocal() as db:
            after = db.scalar(select(func.count(Image.id)).join(Project).where(
                Project.workspace_id == _ws_id(), Image.deleted_at.is_(None)))
        assert after == int(have) + 1, "the cap let exactly one new image through"
    finally:
        with SessionLocal() as db:
            db.delete(db.get(Connector, cid))
            db.commit()
