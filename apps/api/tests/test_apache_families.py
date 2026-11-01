"""Apache-2.0 families (RF-DETR, D-FINE, RT-DETRv2): catalog, train options and train dispatch."""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Job, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


@pytest.fixture(scope="module")
def c():
    # Mint the token directly instead of spending a login rate-limit slot the other modules need.
    with TestClient(app) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


@pytest.fixture
def version_id():
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
        n = db.scalar(select(Version.number).where(Version.project_id == p.id).order_by(Version.number.desc()))
        v = Version(project_id=p.id, number=(n or 0) + 1, name=f"apache-{(n or 0) + 1}", status="ready",
                    stats={"class_names": ["helmet", "person"], "images": 1, "splits": {"train": 1, "valid": 0}})
        db.add(v)
        db.commit()
        vid = v.id
    yield vid
    with SessionLocal() as db:
        row = db.get(Version, vid)
        if row:
            db.delete(row)
            db.commit()


@pytest.fixture
def queued_only(monkeypatch):
    """Keep the embedded worker off the jobs these tests queue."""
    from app import worker
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", ["version", "export", "autolabel"])


def _drop(model_ids=(), job_ids=()):
    with SessionLocal() as db:
        for jid in job_ids:
            row = db.get(Job, jid)
            if row:
                db.delete(row)
        for mid in model_ids:
            row = db.get(TrainedModel, mid)
            if row:
                db.delete(row)
        db.commit()


def test_registry_lists_apache_families(c):
    items = c.get(f"/api/ws/{WS}/registry").json()
    by_ref = {i["ref"]: i for i in items}
    refs = ["rfdetr:nano", "rfdetr:large", "hf:ustc-community/dfine-small-coco", "hf:PekingU/rtdetr_v2_r18vd"]
    for ref in refs:
        item = by_ref[ref]
        assert item["license"] == "Apache-2.0", ref
        assert item["kind"] == "zoo", ref
        assert isinstance(item["available"], bool), ref
        assert isinstance(item["reason"], str), ref


def test_train_options_include_apache_families(c):
    o = c.get(f"{BASE}/train/options").json()
    fams = {f["family"]: f for f in o["families"]}
    assert {"yolo", "rtdetr", "yolo-world", "rf-detr", "d-fine", "rt-detr-v2"} <= set(fams)
    assert fams["rtdetr"]["license"] == "AGPL-3.0"
    for key, adapter in (("rf-detr", "rfdetr"), ("d-fine", "hf"), ("rt-detr-v2", "hf")):
        fam = fams[key]
        assert fam["license"] == "Apache-2.0", key
        assert fam["adapter"] == adapter, key
        assert fam["variants"], key
        assert all({"id", "label", "weights"} <= set(v) for v in fam["variants"]), key


def test_family_of_display_groups():
    from app.routers.training import _family_of
    assert _family_of("small") == "rf-detr"
    assert _family_of("ustc-community/dfine-small-coco") == "d-fine"
    assert _family_of("PekingU/rtdetr_v2_r50vd") == "rt-detr-v2"


def test_final_metrics_read_the_common_keys():
    from app.services.ml import final_metrics
    history = [{"epoch": 1, "val/map50": 0.4, "val/map5095": 0.3, "val/precision": 0.6, "val/recall": 0.5},
               {"epoch": 2, "train/loss": 0.2, "val/map50": 0.5, "val/map5095": 0.35,
                "val/precision": 0.7, "val/recall": 0.6}]
    assert final_metrics(history, "detect") == {"map50": 0.5, "map5095": 0.35, "precision": 0.7, "recall": 0.6}


def _queued(c, body):
    r = c.post(f"{BASE}/train", json=body)
    assert r.status_code == 200, r.text
    m = r.json()
    job = c.get(f"{BASE}/jobs/{m['jobId']}").json()
    assert job["status"] == "queued"
    return m, job


def test_train_rfdetr_stores_adapter_family(c, version_id, queued_only):
    m, job = _queued(c, {"version_id": version_id, "variant": "small", "family": "rfdetr"})
    try:
        assert m["family"] == "rfdetr" and m["variant"] == "small" and m["license"] == "Apache-2.0"
        assert job["params"]["options"]["family"] == "rfdetr"
    finally:
        _drop(model_ids=[m["id"]], job_ids=[m["jobId"]])


def test_train_dfine_stores_hf_family(c, version_id, queued_only):
    m, job = _queued(c, {"version_id": version_id, "variant": "ustc-community/dfine-small-coco", "family": "hf"})
    try:
        assert m["family"] == "hf" and m["variant"] == "ustc-community/dfine-small-coco"
        assert m["license"] == "Apache-2.0"
        assert job["params"]["options"]["family"] == "hf"
    finally:
        _drop(model_ids=[m["id"]], job_ids=[m["jobId"]])


def test_train_rejects_mismatched_family(c, version_id, queued_only):
    r = c.post(f"{BASE}/train", json={"version_id": version_id, "variant": "small", "family": "ultralytics"})
    assert r.status_code == 400 and r.json()["detail"] == "bad training options"


def test_evaluate_scores_a_trained_apache_model(version_id, monkeypatch):
    """resolve(trained:<id>) binds the family adapter and evaluate() scores it on the test split."""
    import json
    import shutil

    from PIL import Image as PImage

    from app.adapters import resolve
    from app.adapters.base import ADAPTERS
    from app.config import DATA_DIR
    from app.services.evaluate import evaluate

    vdir = DATA_DIR / "versions" / version_id
    (vdir / "test").mkdir(parents=True, exist_ok=True)
    PImage.new("RGB", (40, 30)).save(vdir / "test" / "a.jpg", "JPEG")
    (vdir / "manifest.json").write_text(json.dumps({
        "classes": ["helmet"], "type": "object-detection",
        "items": [{"file": "test/a.jpg", "split": "test", "width": 40, "height": 30, "source": "s1",
                   "anns": [{"cls": 0, "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]}]}))

    class FakeRFDetr:
        family = "rfdetr"

        def predict(self, variant, im, **kw):
            return {"predictions": [{"class": "helmet", "class_id": 0, "confidence": 0.9,
                                     "x": 10.0, "y": 7.5, "width": 12.0, "height": 9.0}],
                    "time": 0.0, "image": {"width": im.width, "height": im.height}}

    monkeypatch.setitem(ADAPTERS, "rfdetr", FakeRFDetr())
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == PR))
        common = dict(project_id=p.id, version_id=version_id, task="detect", status="ready",
                      classes=["helmet"], license="Apache-2.0")
        rf = TrainedModel(workspace_id=ws.id, name="rf", arch="small", family="rfdetr", variant="small", **common)
        hf = TrainedModel(workspace_id=ws.id, name="hf", arch="ustc-community/dfine-small-coco",
                          family="hf", variant="ustc-community/dfine-small-coco", **common)
        db.add_all([rf, hf])
        db.commit()
        ids, ws_id = [rf.id, hf.id], ws.id
    try:
        with SessionLocal() as db:
            assert resolve(f"trained:{ids[0]}", db, workspace_id=ws_id).adapter.family == "rfdetr"
            assert resolve(f"trained:{ids[1]}", db, workspace_id=ws_id).adapter.family == "hf"
            with pytest.raises(ValueError):        # another tenant cannot resolve them
                resolve(f"trained:{ids[0]}", db, workspace_id="other-workspace")
            ev = evaluate(f"trained:{ids[0]}", vdir, "detect", db=db, workspace_id=ws_id)
        assert ev["split"] == "test" and ev["coco"]["AP"] == 1.0
    finally:
        _drop(model_ids=ids)
        shutil.rmtree(vdir, ignore_errors=True)
