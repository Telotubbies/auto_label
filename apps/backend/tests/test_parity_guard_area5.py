"""Parity guard, area 5: model table, train entry, evaluation and alias.

Pins the shipped behaviour behind the HAVE rows of `docs/research/roboflow-parity/backlog/T-005.md`:
5-F5.1 / 5-F5.2 / 5-F5.38 (one row per training with version, metrics and licence), 5-F5.12 (a queued
acknowledgement with a job id), 5-F5.16 / 5-F5.50 (a model is addressable by id and carries the history
array), 5-F5.43 (a version that is not generated), 5-F5.44 (an unsupported task x family), 5-F5.47 (an
exhausted credit allowance), 5-F5.35 (the production alias) and 5-F5.52 (good-only anomaly data).
Evaluation stages, the tuned threshold, the confusion values, the alias switch/rollback states, the
permission split and the anomaly station itself are already pinned by their own modules, so this guard
does not repeat them.

Nothing here trains a model, waits on a worker or touches a GPU: rows are inserted directly, and the
one submit test keeps the embedded worker off the job (`test_adapters.py:253-258` does the same).
"""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import worker
from app.config import PLANS
from app.db import SessionLocal
from app.main import app
from app.models import Audit, Image, Job, Member, Project, TrainedModel, User, Version, Workspace
from app.security import issue_access
from app.services import anomaly

WS = "parity-guard-area5"
FOREIGN_WS = "parity-guard-area5-foreign"
DETECT = "detect-guard"
CLASSIFY = "classify-guard"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def _user(db, email: str) -> User:
    u = User(email=email, name=email.split("@")[0], pw_hash="")
    db.add(u)
    return u


@pytest.fixture(scope="module")
def users(c):
    """One admin workspace to read, plus a second workspace whose ids must stay invisible."""
    with SessionLocal() as db:
        admin = _user(db, "area5-admin@test.local")
        outsider = _user(db, "area5-outsider@test.local")
        db.flush()
        ws = Workspace(slug=WS, name="Area 5 Guard", owner_id=admin.id)
        foreign = Workspace(slug=FOREIGN_WS, name="Area 5 Foreign", owner_id=outsider.id)
        db.add_all([ws, foreign])
        db.flush()
        db.add_all([
            Member(workspace_id=ws.id, user_id=admin.id, role="admin"),
            Member(workspace_id=foreign.id, user_id=outsider.id, role="admin"),
        ])
        db.commit()
        return {"admin": admin.id, "outsider": outsider.id}


def _headers(uid: str) -> dict:
    return {"Authorization": f"Bearer {issue_access(uid)}"}


def _project(ws_slug: str, slug: str, type_: str = "object-detection") -> str:
    """Seed the project row directly: this guard reads what the Models/Train pages read."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == ws_slug))
        p = Project(workspace_id=ws.id, slug=slug, name=slug, type=type_, settings={})
        db.add(p)
        db.flush()
        pid = p.id
        db.commit()
    return pid


def _version(project_id: str, number: int = 1, status: str = "ready") -> str:
    with SessionLocal() as db:
        v = Version(project_id=project_id, number=number, name=f"guard-{number}", status=status,
                    stats={"class_names": ["person"], "splits": {"train": 12, "valid": 3}})
        db.add(v)
        db.flush()
        vid = v.id
        db.commit()
    return vid


def _model(project_id: str, version_id: str, name: str, *, status: str = "ready", ap: float | None = None,
           latency: float | None = None, arch: str = "yolo26n", family: str = "ultralytics",
           license: str = "AGPL-3.0", history: list | None = None) -> str:
    """One training row. `license` is what the family copied onto it at creation."""
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        metrics = {}
        if ap is not None or latency is not None:
            metrics = {"eval": {"coco": {"AP": ap} if ap is not None else {},
                                "latency_ms": latency if latency is not None else 0.0}}
        m = TrainedModel(workspace_id=p.workspace_id, project_id=p.id, version_id=version_id, name=name,
                         arch=arch, family=family, variant=arch, task="detect", status=status,
                         license=license, history=history or [], classes=["person"], metrics=metrics)
        db.add(m)
        db.flush()
        mid = m.id
        db.commit()
    return mid


def _image(project_id: str, name: str, annotated: bool = False) -> str:
    with SessionLocal() as db:
        row = Image(project_id=project_id, name=name, sha256=name, width=32, height=32, path=name, thumb=name,
                    split="train", status="done",
                    annotations=[{"id": "a1", "classId": "c1",
                                  "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}]
                    if annotated else [],
                    n_annotations=1 if annotated else 0)
        db.add(row)
        db.flush()
        rid = row.id
        db.commit()
    return rid


def _model_rows(project_id: str) -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(TrainedModel)
                             .where(TrainedModel.project_id == project_id)) or 0)


# --- 5-F5.12: submit acknowledges with a queued model and its job -----------------------------

def test_train_submit_returns_a_queued_model_and_its_job(c, users, monkeypatch):
    """5-F5.12: Start answers with a queued model, its job id and the audit entry, nothing more."""
    pid = _project(WS, DETECT)
    vid = _version(pid)
    # Keep the embedded worker off this job: the acknowledgement is the assertion, not the run.
    monkeypatch.setattr(worker, "LOCAL_JOB_KINDS", ["version", "export"])

    r = c.post(f"/api/ws/{WS}/projects/{DETECT}/train", headers=_headers(users["admin"]),
               json={"version_id": vid, "variant": "yolo26n", "epochs": 3, "imgsz": 320, "batch": 4})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["status"] == "queued", "5-F5.12: submit acknowledges with a queued model"
    assert m["id"] and m["jobId"], "5-F5.12: the row and its job id are returned together"
    assert m["versionId"] == vid and m["arch"] == "yolo26n", "5-F5.12: it names the version and architecture"
    assert m["license"] == "AGPL-3.0", "5-F5.38: the family's licence is copied at creation"

    with SessionLocal() as db:
        job = db.get(Job, m["jobId"])
        assert job is not None and job.kind == "train", "5-F5.12: the queued work is a train job"
        assert job.params["model_id"] == m["id"], "5-F5.12: the job points back at the model row"
        audit = db.scalar(select(Audit).where(Audit.action == "train.start", Audit.target == m["name"]))
        assert audit is not None, "5-F5.12: starting a run leaves a train.start audit row"


# --- 5-F5.43: a version that is not generated ------------------------------------------------

def test_train_refuses_a_version_that_is_not_ready(c, users):
    """5-F5.43: a building version and a foreign version both answer 400 with the fix."""
    pid = _project(WS, "detect-version-guard")
    building = _version(pid, number=1, status="building")
    foreign_pid = _project(FOREIGN_WS, "foreign-detect")
    foreign = _version(foreign_pid, number=1)

    before = _model_rows(pid)
    for vid in (building, foreign):
        r = c.post(f"/api/ws/{WS}/projects/detect-version-guard/train", headers=_headers(users["admin"]),
                   json={"version_id": vid})
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "pick a generated version to train on", \
            "5-F5.43: the documented fix is the answer, not a status code alone"
    assert _model_rows(pid) == before, "5-F5.43: a refused submit creates no model row"


# --- 5-F5.47: the credit allowance is spent ---------------------------------------------------

def test_train_refuses_when_the_credit_allowance_is_spent(c, users):
    """5-F5.47: 402 before anything is queued, and no model row is created."""
    pid = _project(WS, "detect-credit-guard")
    vid = _version(pid)
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        # `charge` rolls a stale period first, so the spent counter must belong to this month.
        ws.credits_period = time.strftime("%Y-%m")
        ws.credits_used = float(PLANS[ws.plan]["credits"])
        db.commit()
    try:
        before = _model_rows(pid)
        r = c.post(f"/api/ws/{WS}/projects/detect-credit-guard/train", headers=_headers(users["admin"]),
                   json={"version_id": vid})
        assert r.status_code == 402, r.text
        assert r.json()["detail"].startswith("monthly credit limit reached"), \
            "5-F5.47: the refusal names the exhausted allowance"
        assert _model_rows(pid) == before, "5-F5.47: the 402 lands before the TrainedModel row exists"
        with SessionLocal() as db:
            jobs = db.scalar(select(func.count()).select_from(Job)
                             .where(Job.project_id == pid, Job.kind == "train"))
            assert jobs == 0, "5-F5.47: nothing is queued when the allowance is gone"
    finally:
        with SessionLocal() as db:
            ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
            ws.credits_used = 0.0
            db.commit()


# --- 5-F5.44: an unsupported task x family ----------------------------------------------------

def test_train_options_print_a_reason_for_every_family_and_reject_a_foreign_family(c, users):
    """5-F5.44: every family explains itself, and a task/family mismatch answers 400."""
    _project(WS, "detect-options-guard")
    classify_pid = _project(WS, CLASSIFY, type_="classification")

    opts = c.get(f"/api/ws/{WS}/projects/detect-options-guard/train/options", headers=_headers(users["admin"]))
    assert opts.status_code == 200, opts.text
    body = opts.json()
    assert body["supported"] is True and body["task"] == "detect"
    assert body["families"], "5-F5.44: the picker needs at least one family"
    for fam in body["families"]:      # family names grow with area 5, so only the shape is pinned
        assert isinstance(fam["available"], bool), fam
        assert isinstance(fam["reason"], str), fam
        assert fam["variants"] and all({"id", "label"} <= set(v) for v in fam["variants"]), fam

    detect_version = _version(_project(WS, "detect-family-guard"))
    # The YOLO variant under another family's adapter is not a family the model belongs to.
    r = c.post(f"/api/ws/{WS}/projects/detect-family-guard/train", headers=_headers(users["admin"]),
               json={"version_id": detect_version, "variant": "yolo26n", "family": "rfdetr"})
    assert r.status_code == 400 and r.json()["detail"] == "bad training options", r.text

    classify_version = _version(classify_pid, number=1)
    r = c.post(f"/api/ws/{WS}/projects/{CLASSIFY}/train", headers=_headers(users["admin"]),
               json={"version_id": classify_version, "variant": "rtdetr-l", "family": "rtdetr"})
    assert r.status_code == 400, r.text
    assert "RT-DETR" in r.json()["detail"] and "detection projects only" in r.json()["detail"], \
        "5-F5.44: a detection-only family names itself and what it can train"


# --- 5-F5.1 / 5-F5.2 / 5-F5.38: one row per training, with version and licence ----------------

def test_models_list_keeps_one_row_per_training_with_version_and_licence(c, users):
    """5-F5.1 / 5-F5.2 / 5-F5.38: several runs on one version, each with its own row and licence."""
    pid = _project(WS, "detect-models-guard")
    vid = _version(pid, number=4)
    a = _model(pid, vid, "guard-a", ap=0.42, latency=41.5, arch="yolo26n")
    b = _model(pid, vid, "guard-b", ap=0.61, latency=88.0, arch="rtdetr-l", family="rfdetr",
               license="Apache-2.0")

    rows = c.get(f"/api/ws/{WS}/projects/detect-models-guard/models", headers=_headers(users["admin"]))
    assert rows.status_code == 200, rows.text
    by_id = {r["id"]: r for r in rows.json()}
    assert set(by_id) == {a, b}, "5-F5.2: two trainings on one version are two rows"
    for mid, arch, lic in ((a, "yolo26n", "AGPL-3.0"), (b, "rtdetr-l", "Apache-2.0")):
        row = by_id[mid]
        assert row["version"] == 4, "5-F5.1: every row carries the version number it trained on"
        assert row["arch"] == arch and row["family"], "5-F5.1: the row names its architecture"
        assert row["license"] == lic, "5-F5.38: the licence is shown per model"
        assert row["created"], "5-F5.1: every row carries when it was created"

    lb = c.get(f"/api/ws/{WS}/projects/detect-models-guard/leaderboard", headers=_headers(users["admin"]))
    assert lb.status_code == 200, lb.text
    ranked = {r["id"]: r for r in lb.json()}
    assert set(ranked) == {a, b}, "5-F5.1: the comparison table holds both rows"
    assert ranked[a]["ap"] == pytest.approx(0.42) and ranked[b]["ap"] == pytest.approx(0.61)
    assert ranked[a]["latency_ms"] == pytest.approx(41.5), "5-F5.38: latency is a per-model number"
    assert ranked[a]["versionId"] == vid and ranked[b]["versionId"] == vid
    assert ranked[b]["comparable"] is True, "5-F5.1: same-version rows are directly comparable"


# --- 5-F5.16 / 5-F5.50: addressable by id, everything else is 404 -----------------------------

def test_a_model_is_addressable_by_id_and_unknown_ids_are_404(c, users):
    """5-F5.16 / 5-F5.50: `TrainedModel.id` alone addresses the run and its history; unknown is 404."""
    pid = _project(WS, "detect-detail-guard")
    vid = _version(pid)
    mid = _model(pid, vid, "guard-detail", history=[{"epoch": 1, "metrics/mAP50(B)": 0.5}])

    r = c.get(f"/api/ws/{WS}/projects/detect-detail-guard/models/{mid}", headers=_headers(users["admin"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == mid, "5-F5.50: the id alone is the address, no composite alias"
    assert body["history"] == [{"epoch": 1, "metrics/mAP50(B)": 0.5}], \
        "5-F5.16: the detail carries the history array the graphs read"

    unknown = c.get(f"/api/ws/{WS}/projects/detect-detail-guard/models/does-not-exist",
                    headers=_headers(users["admin"]))
    assert unknown.status_code == 404, "5-F5.50: an unknown id is not found"
    assert unknown.json()["detail"] == "model not found"

    foreign_pid = _project(FOREIGN_WS, "foreign-detail")
    foreign_mid = _model(foreign_pid, _version(foreign_pid), "foreign-detail")
    leaked = c.get(f"/api/ws/{WS}/projects/detect-detail-guard/models/{foreign_mid}",
                   headers=_headers(users["admin"]))
    assert leaked.status_code == 404, "5-F5.50: another workspace's model id is never addressable here"


# --- 5-F5.35: the production pointer and its rollback state -----------------------------------

def test_the_served_alias_still_resolves_after_a_guard_run(c, users):
    """5-F5.35: production takes a ready model and keeps `previous_model_id` empty on the first move."""
    pid = _project(WS, "detect-alias-guard")
    mid = _model(pid, _version(pid), "guard-alias")

    r = c.put(f"/api/ws/{WS}/projects/detect-alias-guard/deployments/production",
              headers=_headers(users["admin"]), json={"model_id": mid})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["alias"] == "production" and out["model_id"] == mid
    assert out["previous_model_id"] is None, "5-F5.35: the first production move has no rollback target"

    rb = c.post(f"/api/ws/{WS}/projects/detect-alias-guard/deployments/production/rollback",
                headers=_headers(users["admin"]))
    assert rb.status_code == 409, rb.text
    assert rb.json()["detail"] == "no previous model to roll back to"


# --- 5-F5.52: good-only anomaly data (flag task_29) -------------------------------------------

def test_a_good_only_station_refuses_images_it_cannot_learn_from(c, users, monkeypatch):
    """5-F5.52: the anomaly station takes normal images only and refuses too few of them.

    The routes are flagged, so this assertion runs only with `LD_FLAGS_ON=task_29` — and it proves the
    off state first. Nothing is queued: both refusals happen before the job row exists.
    """
    pid = _project(WS, "anomaly-guard", type_="anomaly-detection")
    base = f"/api/ws/{WS}/projects/anomaly-guard/anomaly"

    monkeypatch.delenv("LD_FLAGS_ON", raising=False)
    assert c.get(base + "/stations", headers=_headers(users["admin"])).status_code == 404, \
        "5-F5.52: with the flag off the surface is not there"

    monkeypatch.setenv("LD_FLAGS_ON", "task_29")
    created = c.post(base + "/stations", headers=_headers(users["admin"]), json={"name": "Guard Line"})
    assert created.status_code == 200, created.text
    sid = created.json()["id"]

    few = [_image(pid, "normal-1")]
    r = c.post(f"{base}/stations/{sid}/train", headers=_headers(users["admin"]), json={"image_ids": few})
    assert r.status_code == 400, r.text
    assert f"at least {anomaly.MIN_NORMAL_IMAGES} normal images" in r.json()["detail"], \
        "5-F5.52: too few normal images is refused with the count it needs"

    labelled = _image(pid, "labelled-1", annotated=True)
    r = c.post(f"{base}/stations/{sid}/train", headers=_headers(users["admin"]),
               json={"image_ids": [labelled]})
    assert r.status_code == 400, r.text
    assert "no annotations" in r.json()["detail"], "5-F5.52: a labelled image is not a normal image"

    with SessionLocal() as db:
        queued = db.scalar(select(func.count()).select_from(Job)
                           .where(Job.project_id == pid, Job.kind == "anomaly_train"))
        assert queued == 0, "5-F5.52: a refused good-only set queues no training job"
