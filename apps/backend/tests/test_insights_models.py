"""Insights Studio 20b: training curves, evaluation analytics (calibration, slices, PR) and model compare."""

import json
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import (
    Batch,
    Image,
    Member,
    Project,
    TrainedModel,
    User,
    Version,
    Workspace,
)
from app.security import issue_access
from app.services import insights

WS = "insights-20b-qa"
NAME = "insights-20b"
COCO_KEYS = (
    "AP",
    "AP50",
    "AP75",
    "APs",
    "APm",
    "APl",
    "AR1",
    "AR10",
    "AR100",
    "ARs",
    "ARm",
    "ARl",
)


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
            if not db.scalar(select(Workspace).where(Workspace.slug == WS)):
                ws = Workspace(slug=WS, name="Insights QA", owner_id=user.id)
                db.add(ws)
                db.flush()
                db.add(Member(workspace_id=ws.id, user_id=user.id, role="admin"))
                db.commit()
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


@pytest.fixture(scope="module")
def project(c):
    r = c.post(
        f"/api/ws/{WS}/projects", json={"name": NAME, "classes": ["person", "helmet"]}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _image(
    pid: str,
    name: str,
    w: int,
    h: int,
    level: int,
    *,
    tag: str = "",
    batch: str | None = None,
    anns: list[dict] | None = None,
    split: str = "test",
) -> str:
    """Store a solid-grey image so brightness bins are deterministic."""
    rel = f"insights/{name}"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    PImage.new("RGB", (w, h), (level, level, level)).save(
        DATA_DIR / rel, "JPEG", quality=95
    )
    with SessionLocal() as db:
        row = Image(
            project_id=pid,
            name=name,
            sha256=name,
            width=w,
            height=h,
            path=rel,
            thumb=rel,
            split=split,
            status="done",
            tags=[tag] if tag else [],
            batch_id=batch,
            annotations=anns or [],
            n_annotations=len(anns or []),
        )
        db.add(row)
        db.commit()
        return row.id


def _ann(
    cid: str, x: float, y: float, w: float, h: float, source: str = "human"
) -> dict:
    return {
        "id": f"a-{cid}-{x}",
        "classId": cid,
        "source": source,
        "shape": {"kind": "bbox", "x": x, "y": y, "w": w, "h": h},
    }


def _det(
    file: str,
    w: int,
    h: int,
    gt: list[tuple[str, list[float]]],
    pred: list[tuple[str, float, list[float]]],
) -> dict:
    return {
        "file": file,
        "width": w,
        "height": h,
        "gt": [{"cls": cls, "bbox": box} for cls, box in gt],
        "pred": [{"cls": cls, "conf": conf, "bbox": box} for cls, conf, box in pred],
    }


def _eval(files: list[dict], *, latency: float = 12.0) -> dict:
    return {
        "split": "test",
        "note": "",
        "iou": "bbox",
        "coco": {
            k: (0.5 if k == "AP" else 0.7 if k == "AP50" else 0.0) for k in COCO_KEYS
        },
        "per_class": [
            {"class": "person", "AP": 0.5, "AP50": 0.7},
            {"class": "helmet", "AP": 0.2, "AP50": 0.3},
        ],
        "f1_best": {"conf": 0.4, "f1": 0.66},
        "pr_curve": [
            {"recall": 0.1, "precision": 1.0},
            {"recall": 0.5, "precision": 0.8},
            {"recall": 0.9, "precision": 0.5},
        ],
        "confusion": {
            "labels": ["person", "helmet", "background"],
            "matrix": [[2, 0, 0], [0, 1, 1], [1, 0, 0]],
            "images": [[["a.jpg"]], [["c.jpg"]], [["b.jpg"]]],
        },
        "tide": {
            "cls": 0.01,
            "loc": 0.02,
            "both": 0.0,
            "dupe": 0.0,
            "bkg": 0.03,
            "missed": 0.04,
        },
        "worst": ["b.jpg"],
        "latency_ms": latency,
        "detections": files,
        "split_images": 3,
    }


@pytest.fixture(scope="module")
def data(c, project):
    pid = project["id"]
    with SessionLocal() as db:
        b1 = Batch(project_id=pid, name="Morning batch")
        b2 = Batch(project_id=pid, name="Night batch")
        db.add_all([b1, b2])
        db.commit()
        b1id, b2id = b1.id, b2.id

    a = _image(
        pid,
        "a.jpg",
        800,
        600,
        20,
        tag="day",
        batch=b1id,
        anns=[_ann("person", 0.1, 0.1, 0.2, 0.2), _ann("helmet", 0.5, 0.5, 0.1, 0.1)],
    )
    b = _image(
        pid,
        "b.jpg",
        1600,
        1200,
        250,
        tag="night",
        batch=b1id,
        anns=[_ann("person", 0.2, 0.2, 0.3, 0.3, source="sam3")],
    )
    c = _image(
        pid,
        "c.jpg",
        400,
        300,
        128,
        batch=b2id,
        anns=[
            _ann("helmet", 0.1, 0.1, 0.2, 0.2),
            _ann("helmet", 0.6, 0.6, 0.1, 0.1, source="vlm+sam3"),
        ],
    )

    files = [
        _det(
            "a.jpg",
            800,
            600,
            [("person", [10, 10, 100, 100]), ("helmet", [200, 200, 50, 50])],
            [
                ("person", 0.9, [10, 10, 100, 100]),
                ("helmet", 0.8, [200, 200, 50, 50]),
                ("person", 0.2, [400, 400, 30, 30]),
            ],
        ),
        _det(
            "b.jpg",
            1600,
            1200,
            [("person", [100, 100, 200, 200])],
            [
                ("person", 0.7, [100, 100, 200, 200]),
                ("person", 0.4, [500, 500, 60, 60]),
            ],
        ),
        _det("c.jpg", 400, 300, [("helmet", [20, 20, 40, 40])], []),
    ]

    with SessionLocal() as db:
        v = Version(
            project_id=pid,
            number=1,
            name="insights",
            status="ready",
            stats={"images": 3, "class_names": ["person", "helmet"]},
        )
        db.add(v)
        db.flush()
        vid = v.id
        db.commit()

    manifest = {
        "classes": ["person", "helmet"],
        "version_hash": "abc",
        "items": [
            {
                "file": "test/a.jpg",
                "split": "test",
                "source": a,
                "width": 800,
                "height": 600,
            },
            {
                "file": "test/b.jpg",
                "split": "test",
                "source": b,
                "width": 1600,
                "height": 1200,
            },
            {
                "file": "test/c.jpg",
                "split": "test",
                "source": c,
                "width": 400,
                "height": 300,
            },
        ],
    }
    (DATA_DIR / "versions" / vid).mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "versions" / vid / "manifest.json").write_text(json.dumps(manifest))

    def model(
        name: str, version_id: str, *, latency: float, ev: dict | None = None
    ) -> str:
        with SessionLocal() as db:
            p = db.get(Project, pid)
            m = TrainedModel(
                workspace_id=p.workspace_id,
                project_id=pid,
                version_id=version_id,
                name=name,
                arch="yolo26n",
                task="detect",
                status="ready",
                weights="fake.pt",
                classes=["person", "helmet"],
                metrics={
                    "map50": 0.7,
                    "map5095": 0.5,
                    "precision": 0.8,
                    "recall": 0.6,
                    "eval": ev if ev is not None else _eval(files, latency=latency),
                },
                history=[
                    {"epoch": 1, "metrics/mAP50(B)": 0.2, "train/box_loss": 1.4},
                    {"epoch": 2, "metrics/mAP50(B)": 0.4, "train/box_loss": 1.0},
                    {"epoch": 3, "metrics/mAP50(B)": 0.6, "train/box_loss": 0.8},
                ],
            )
            db.add(m)
            db.commit()
            return m.id

    m1 = model("run-a", vid, latency=10.0)
    files2 = json.loads(json.dumps(files))
    files2[0]["pred"] = [p for p in files2[0]["pred"] if p["cls"] != "helmet"]
    m2 = model("run-b", vid, latency=25.0, ev=_eval(files2, latency=25.0))
    with SessionLocal() as db:
        v2 = Version(project_id=pid, number=2, name="other", status="ready", stats={})
        db.add(v2)
        db.commit()
        v2id = v2.id
    m3 = model("run-c", v2id, latency=15.0)
    m4 = model("run-d", vid, latency=30.0)
    m5 = model("run-e", vid, latency=12.0)
    m6 = model("run-no-dets", vid, latency=8.0, ev=_eval([], latency=8.0))

    # A frozen version whose evaluation spans two splits while the live rows say something else:
    # the slice dimension must follow the manifest, never Image.split.
    with SessionLocal() as db:
        v3 = Version(project_id=pid, number=3, name="mixed", status="ready", stats={})
        db.add(v3)
        db.commit()
        v3id = v3.id
    mixed = {
        "classes": ["person", "helmet"],
        "version_hash": "mixed",
        "items": [
            {"file": "test/a.jpg", "split": "test", "source": a},
            {"file": "valid/b.jpg", "split": "valid", "source": b},
        ],
    }
    (DATA_DIR / "versions" / v3id).mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "versions" / v3id / "manifest.json").write_text(json.dumps(mixed))
    m7 = model("run-mixed", v3id, latency=9.0)
    with SessionLocal() as db:
        renamed = db.get(TrainedModel, m5)
        renamed.classes = [
            "renamed-person",
            "renamed-helmet",
        ]  # a Task 7 class rename after eval
        db.commit()
    with SessionLocal() as db:
        p = db.get(Project, pid)
        other = Project(
            workspace_id=p.workspace_id,
            slug="insights-20b-other",
            name="Other insights project",
        )
        db.add(other)
        db.flush()
        ov = Version(
            project_id=other.id, number=1, name="other", status="ready", stats={}
        )
        db.add(ov)
        db.flush()
        om = TrainedModel(
            workspace_id=p.workspace_id,
            project_id=other.id,
            version_id=ov.id,
            name="foreign",
            arch="yolo26n",
            task="detect",
            status="ready",
            weights="fake.pt",
            classes=["person"],
            metrics={"eval": _eval(files)},
            history=[],
        )
        db.add(om)
        db.commit()
        other_model = om.id
    with SessionLocal() as db:
        row = db.get(TrainedModel, m4)
        row.metrics = {"map50": 0.1}
        row.history = []
        db.commit()

    return {
        "pid": pid,
        "vid": vid,
        "v2id": v2id,
        "v3id": v3id,
        "m1": m1,
        "m2": m2,
        "m3": m3,
        "m4": m4,
        "m5": m5,
        "m6": m6,
        "m7": m7,
        "other_model": other_model,
        "files": files,
    }


def test_training_curves_overlay_runs(c, data):
    r = c.get(
        f"/api/ws/{WS}/projects/{NAME}/insights/training?runs={data['m1']},{data['m2']}"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [run["id"] for run in body["runs"]] == [data["m1"], data["m2"]]
    assert body["runs"][0]["history"][0]["epoch"] == 1
    assert body["runs"][0]["version"] == 1
    keys = {k["key"]: k for k in body["keys"]}
    assert keys["metrics/mAP50(B)"]["group"] == "quality"
    assert keys["train/box_loss"]["group"] == "loss"
    assert all(k["label"] for k in body["keys"])


def test_training_curves_reject_foreign_model(c, data):
    r = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/training?runs=nope")
    assert r.status_code == 404


def test_training_curves_default_is_newest_first(c, data):
    body = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/training").json()
    ids = [run["id"] for run in body["runs"]]
    assert set(ids) == {
        data["m1"],
        data["m2"],
        data["m3"],
        data["m5"],
        data["m6"],
        data["m7"],
    }


def test_eval_insights_shapes(c, data):
    insights.clear_cache()
    r = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m1']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"]["name"] == "run-a"
    ev = body["eval"]
    assert (
        ev["split"] == "test" and ev["sample_images"] == 3 and ev["split_images"] == 3
    )
    assert len(ev["f1_curve"]) == 19
    assert all({"conf", "precision", "recall", "f1"} <= set(p) for p in ev["f1_curve"])
    assert ev["per_class_pr"] and ev["per_class_pr"][0]["points"]
    assert ev["has_detections"] is True
    cal = ev["calibration"]
    assert 0 <= cal["ece"] <= 1 and 0 <= cal["brier"] <= 1
    assert (
        sum(b["count"] for b in cal["bins"]) == 5
    )  # every stored prediction above 0.05
    assert all(0 <= b["conf"] <= 1 and 0 <= b["accuracy"] <= 1 for b in cal["bins"])
    dims = {s["dimension"] for s in ev["slices"]}
    # "split" is dropped: this evaluation lives on one frozen split, so the slice would be a
    # single bucket (see insights_eval.slices).
    assert dims == {"size", "tag", "batch", "brightness", "source"}
    for s in ev["slices"]:
        assert s["images"] >= 0 and s["instances"] >= 0
        assert s["AP50"] is None or 0 <= s["AP50"] <= 1
    values = {(s["dimension"], s["value"]) for s in ev["slices"]}
    assert ("brightness", "dark") in values and ("brightness", "bright") in values
    assert (
        ("source", "human") in values
        and ("source", "ai") in values
        and ("source", "mixed") in values
    )
    assert ("tag", "day") in values and ("batch", "Morning batch") in values
    assert set(body["images"]) >= {"a.jpg", "b.jpg", "c.jpg"}
    assert body["images"]["a.jpg"].startswith("/api/files/")
    assert body["reason"] is None


def test_eval_insights_cached_by_signature(c, data):
    insights.clear_cache()
    url = f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m1']}"
    first = c.get(url).json()
    second = c.get(url).json()
    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert first["cache"]["signature"] == second["cache"]["signature"]
    with SessionLocal() as db:
        m = db.get(TrainedModel, data["m1"])
        m.metrics = {**m.metrics, "eval": {**m.metrics["eval"], "latency_ms": 99.0}}
        db.commit()
    third = c.get(url).json()
    assert third["cache"]["signature"] != first["cache"]["signature"]
    assert third["eval"]["latency_ms"] == 99.0
    with SessionLocal() as db:
        m = db.get(TrainedModel, data["m1"])
        m.metrics = {**m.metrics, "eval": {**m.metrics["eval"], "latency_ms": 10.0}}
        db.commit()
    insights.clear_cache()


def test_eval_insights_without_eval(c, data):
    body = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m4']}").json()
    assert body["eval"] is None and body["reason"]
    assert body["model"]["id"] == data["m4"]


def test_eval_without_detections_returns_no_calibration(c, data):
    """An eval that stored COCO metrics but no per-image rows must not render zeros as values."""
    insights.clear_cache()
    body = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m6']}").json()
    ev = body["eval"]
    assert ev["has_detections"] is False
    assert ev["calibration"] is None
    assert ev["f1_curve"] == [] and ev["per_class_pr"] == [] and ev["slices"] == []
    assert ev["sample_images"] == 0
    # The stored full-eval numbers survive, so the UI can fall back to them.
    assert ev["f1_best"] == {"conf": 0.4, "f1": 0.66}
    assert ev["coco"]["AP50"] == 0.7


def test_slice_split_uses_the_frozen_manifest_split(c, data):
    """Re-splitting after an evaluation must not move images between slice buckets."""
    insights.clear_cache()

    def live_split(name: str) -> None:
        with SessionLocal() as db:
            row = db.scalar(
                select(Image).where(Image.project_id == data["pid"], Image.name == name)
            )
            row.split = "train"
            db.commit()

    for name in ("a.jpg", "b.jpg"):
        live_split(name)
    try:
        body = c.get(
            f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m7']}"
        ).json()
        values = {(s["dimension"], s["value"]) for s in body["eval"]["slices"]}
        assert ("split", "test") in values and ("split", "valid") in values
        assert ("split", "train") not in values
    finally:
        with SessionLocal() as db:
            for name in ("a.jpg", "b.jpg"):
                row = db.scalar(
                    select(Image).where(
                        Image.project_id == data["pid"], Image.name == name
                    )
                )
                row.split = "test"
            db.commit()
        insights.clear_cache()


def test_cache_invalidated_by_tag_rename(c, data):
    insights.clear_cache()
    url = f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m1']}"
    first = c.get(url).json()
    assert any(
        s["dimension"] == "tag" and s["value"] == "day" for s in first["eval"]["slices"]
    )
    try:
        r = c.post(
            f"/api/ws/{WS}/projects/{NAME}/tags/rename",
            json={"name": "day", "new_name": "daylight"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["images_updated"] >= 1
        second = c.get(url).json()
        assert second["cache"]["signature"] != first["cache"]["signature"]
        assert second["cache"]["hit"] is False
        tags = {s["value"] for s in second["eval"]["slices"] if s["dimension"] == "tag"}
        assert "daylight" in tags and "day" not in tags
    finally:
        c.post(
            f"/api/ws/{WS}/projects/{NAME}/tags/rename",
            json={"name": "daylight", "new_name": "day"},
        )
        insights.clear_cache()


def test_eval_insights_isolated_by_project(c, data):
    # an existing project of the same workspace cannot read another project's model
    r = c.get(f"/api/ws/{WS}/projects/insights-20b-other/insights/models/{data['m1']}")
    assert r.status_code == 404
    r = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['other_model']}")
    assert r.status_code == 404


def test_detections_endpoint_returns_requested_files_only(c, data):
    r = c.get(
        f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m1']}/detections?files=a.jpg,c.jpg"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert {d["file"] for d in body["detections"]} == {"a.jpg", "c.jpg"}
    assert body["images"]["a.jpg"].startswith("/api/files/")
    assert (
        c.get(
            f"/api/ws/{WS}/projects/{NAME}/insights/models/nope/detections"
        ).status_code
        == 404
    )


def test_eval_survives_a_class_rename(c, data):
    insights.clear_cache()
    body = c.get(f"/api/ws/{WS}/projects/{NAME}/insights/models/{data['m5']}").json()
    classes = {c["class"] for c in body["eval"]["per_class_pr"]}
    assert classes == {"person", "helmet"}
    assert any(
        s["dimension"] == "source" and s["AP50"] is not None
        for s in body["eval"]["slices"]
    )


def test_compare_two_models(c, data):
    r = c.get(
        f"/api/ws/{WS}/projects/{NAME}/insights/compare?models={data['m1']},{data['m2']}"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (
        body["version_id"] == data["vid"]
        and body["version"] == 1
        and body["split"] == "test"
    )
    assert [m["id"] for m in body["models"]] == [data["m1"], data["m2"]]
    assert body["pareto"] == [data["m1"]]  # same AP, lower latency wins
    assert body["threshold"] == 0.4 and body["has_detections"] is True
    assert body["disagreement"]
    assert all(d["url"].startswith("/api/files/") for d in body["disagreement"])
    assert {m["id"] for m in body["disagreement"][0]["models"]} == {
        data["m1"],
        data["m2"],
    }


def test_compare_rejects_bad_selection(c, data):
    assert (
        c.get(
            f"/api/ws/{WS}/projects/{NAME}/insights/compare?models={data['m1']}"
        ).status_code
        == 400
    )
    r = c.get(
        f"/api/ws/{WS}/projects/{NAME}/insights/compare?models={data['m1']},{data['m3']}"
    )
    assert r.status_code == 400 and "version" in r.json()["detail"]
    assert (
        c.get(
            f"/api/ws/{WS}/projects/{NAME}/insights/compare?models={data['m1']},nope"
        ).status_code
        == 404
    )


def test_insights_are_read_only(c, data):
    r = c.post(
        f"/api/ws/{WS}/projects/{NAME}/insights/compare?models={data['m1']},{data['m2']}"
    )
    assert r.status_code == 405
