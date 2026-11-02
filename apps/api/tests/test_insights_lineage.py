"""Task 20c: lineage DAG, dashboard builder and stream analytics contracts."""

import hashlib
import json
import os
import tempfile
import time

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import (
    Batch,
    Image,
    Job,
    LabelClass,
    Project,
    Stream,
    StreamEvent,
    TrainedModel,
    User,
    Version,
    Workspace,
    now,
)
from app.security import issue_access
from app.services import versioning

WS = "labeldesk-demo"
SLUG = "lineage-qa"
BASE = f"/api/ws/{WS}/projects/{SLUG}"
INS = f"{BASE}/insights"
DASH = f"{BASE}/dashboards"
DAY = 86400


@pytest.fixture(scope="module")
def c():
    with TestClient(app, client=("lineage-test", 50000)) as client:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        client.headers["Authorization"] = f"Bearer {issue_access(user.id)}"
        yield client


@pytest.fixture(scope="module")
def data(c):
    """One project with 2 batches, 4 images, a version, a run + model, 2 streams and 4 events."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        project = Project(
            workspace_id=ws.id,
            slug=SLUG,
            name=SLUG,
            type="object-detection",
            settings={},
        )
        db.add(project)
        db.flush()
        person = LabelClass(project_id=project.id, name="person", color="#8b5cf6")
        car = LabelClass(project_id=project.id, name="car", color="#22c55e")
        other = Project(
            workspace_id=ws.id,
            slug=f"{SLUG}-other",
            name="other",
            type="object-detection",
            settings={},
        )
        db.add_all([person, car, other])
        db.flush()
        b1 = Batch(project_id=project.id, name="Morning batch")
        b2 = Batch(project_id=project.id, name="Night batch")
        db.add_all([b1, b2])
        db.flush()
        pid, person_id, car_id, other_id = project.id, person.id, car.id, other.id
        b1_id, b2_id = b1.id, b2.id
        db.commit()

    def ann(cid, source=None):
        out = {
            "id": hashlib.sha256(f"{cid}{source}{time.time()}".encode()).hexdigest()[
                :8
            ],
            "classId": cid,
            "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
        }
        if source:
            out["source"] = source
        return out

    rows = {
        "i1": (
            pid,
            "i1",
            b1_id,
            "train",
            ["day"],
            [ann(person_id, "human"), ann(person_id, "human"), ann(car_id, "sam3")],
        ),
        "i2": (pid, "i2", b1_id, "valid", [], [ann(person_id, "vlm+sam3")]),
        "i3": (
            pid,
            "i3",
            b2_id,
            "test",
            ["night"],
            [ann(car_id, "human"), ann(car_id, "human")],
        ),
        "i4": (pid, "i4", b2_id, "train", ["day", "night"], []),
    }
    ids = {}
    with SessionLocal() as db:
        for key, (project_id, name, batch_id, split, tags, anns) in rows.items():
            row = Image(
                project_id=project_id,
                batch_id=batch_id,
                name=name,
                sha256=hashlib.sha256(name.encode()).hexdigest(),
                width=640,
                height=480,
                path=f"lineage/{name}.jpg",
                thumb=f"lineage/{name}.jpg",
                split=split,
                tags=tags,
                annotations=anns,
                n_annotations=len(anns),
            )
            db.add(row)
            db.flush()
            ids[key] = row.id
        version = Version(
            project_id=pid,
            number=1,
            name="first",
            status="ready",
            stats={
                "splits": {"train": 2, "valid": 1, "test": 1},
                "classes": {"person": 3, "car": 3},
                "version_hash": "abc123def456",
                "leakage_moved": 2,
            },
        )
        db.add(version)
        db.flush()
        job = Job(
            workspace_id=ws.id,
            project_id=pid,
            kind="train",
            status="done",
            progress=1.0,
            params={"version_id": version.id, "model_id": "pending"},
        )
        db.add(job)
        db.flush()
        model = TrainedModel(
            workspace_id=ws.id,
            project_id=pid,
            version_id=version.id,
            job_id=job.id,
            name="ppe-yolo",
            arch="yolo11n",
            task="detect",
            status="ready",
            classes=["person", "car"],
            metrics={
                "eval": {
                    "coco": {"AP": 0.42, "AP50": 0.61},
                    "per_class": [
                        {"class": "person", "AP": 0.5, "AP50": 0.7},
                        {"class": "car", "AP": 0.34, "AP50": 0.52},
                    ],
                }
            },
        )
        db.add(model)
        db.flush()
        job.params = {**job.params, "model_id": model.id}
        s1 = Stream(
            workspace_id=ws.id,
            project_id=pid,
            name="Loading bay",
            model_ref=f"trained:{model.id}",
            source="file:videos/a.mp4",
            zones=[{"id": "gate", "label": "Gate", "points": [0, 0, 1, 0, 1, 1]}],
            rules=[{"kind": "zone", "class": "person", "zone_id": "gate"}],
        )
        s2 = Stream(
            workspace_id=ws.id,
            project_id=pid,
            name="Car park",
            model_ref="ultralytics:yolo11n",
            source="file:videos/b.mp4",
        )
        db.add_all([s1, s2])
        db.flush()
        base = now() - 2 * DAY
        events = [
            StreamEvent(
                stream_id=s1.id,
                ts=base,
                rule={
                    "index": 0,
                    "kind": "zone",
                    "label": "Person at gate",
                    "zone_id": "gate",
                },
                summary="person in zone gate",
                classes="|person|",
            ),
            StreamEvent(
                stream_id=s1.id,
                ts=base + 3600,
                rule={
                    "index": 1,
                    "kind": "dwell",
                    "label": "Long dwell",
                    "seconds": 42,
                    "zone_id": "gate",
                },
                summary="person #3 dwelled 42s in zone gate",
                classes="|person|",
            ),
            StreamEvent(
                stream_id=s2.id,
                ts=now() - 600,
                rule={"index": 0, "kind": "count", "label": "Cars over 5"},
                summary="6 car >= 5",
                classes="|car|",
                reviewed=True,
            ),
            StreamEvent(
                stream_id=s2.id,
                ts=now() - 40 * DAY,
                rule={"index": 0, "kind": "count", "label": "Cars over 5"},
                summary="old",
                classes="|car|",
            ),
        ]
        db.add_all(events)
        db.commit()
        out = {
            "pid": pid,
            "other_id": other_id,
            "version": version.id,
            "job": job.id,
            "model": model.id,
            "s1": s1.id,
            "s2": s2.id,
            "batch1": b1_id,
            "batch2": b2_id,
            "ids": ids,
        }
    # The manifest is what makes a version's frozen splits and its source images real.
    path = versioning.version_dir(version)
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "classes": ["person", "car"],
                "version_hash": "abc123def456",
                "items": [
                    {"source": ids[k], "split": split, "anns": [{}] * n}
                    for k, split, n in (
                        ("i1", "train", 3),
                        ("i2", "valid", 1),
                        ("i3", "test", 2),
                    )
                ],
            }
        )
    )
    return out


def ids(payload):
    return {n["id"] for n in payload["nodes"]}


def edges(payload):
    return {(e["source"], e["target"]) for e in payload["edges"]}


# --- lineage -----------------------------------------------------------------


def test_lineage_links_batches_versions_runs_models_and_streams(c, data):
    r = c.get(f"{INS}/lineage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert f"batch:{data['batch1']}" in ids(body) and f"batch:{data['batch2']}" in ids(
        body
    )
    assert f"version:{data['version']}" in ids(body)
    assert f"run:{data['job']}" in ids(body)
    assert f"model:{data['model']}" in ids(body)
    assert f"stream:{data['s1']}" in ids(body) and f"stream:{data['s2']}" in ids(body)
    assert (f"batch:{data['batch1']}", f"version:{data['version']}") in edges(body)
    assert (f"batch:{data['batch2']}", f"version:{data['version']}") in edges(body)
    assert (f"version:{data['version']}", f"run:{data['job']}") in edges(body)
    assert (f"run:{data['job']}", f"model:{data['model']}") in edges(body)
    assert (f"model:{data['model']}", f"stream:{data['s1']}") in edges(body)
    # a zoo model is not an in-platform node, so its stream stays unlinked rather than dangling
    assert not [e for e in body["edges"] if e["target"] == f"stream:{data['s2']}"]


def test_lineage_nodes_carry_their_outputs(c, data):
    body = c.get(f"{INS}/lineage").json()
    node = next(n for n in body["nodes"] if n["id"] == f"model:{data['model']}")
    assert node["kind"] == "model"
    assert node["metrics"]["AP"] == pytest.approx(0.42)
    assert node["detail"]["classes"] == ["person", "car"]
    version = next(n for n in body["nodes"] if n["id"] == f"version:{data['version']}")
    assert version["counts"]["images"] == 3 and version["counts"]["annotations"] == 6
    run = next(n for n in body["nodes"] if n["id"] == f"run:{data['job']}")
    assert run["detail"]["status"] == "done"


def test_lineage_ignores_other_projects(c, data):
    with SessionLocal() as db:
        foreign = Version(project_id=data["other_id"], number=1, status="ready")
        db.add(foreign)
        db.commit()
        foreign_id = foreign.id
    body = c.get(f"{INS}/lineage").json()
    assert f"version:{foreign_id}" not in ids(body)


# --- widget query ------------------------------------------------------------


def query(c, **body):
    return c.post(f"{INS}/query", json=body)


def test_query_dataset_counts_annotations_per_class(c, data):
    r = query(c, source="dataset", measure="annotations", dimension="class")
    assert r.status_code == 200, r.text
    body = r.json()
    rows = {row["key"]: row["value"] for row in body["rows"]}
    assert rows == {"person": 3, "car": 3}
    assert body["total"] == 6


def test_query_dataset_filters_and_label_source(c, data):
    body = query(
        c,
        source="dataset",
        measure="annotations",
        dimension="source",
        filters={"split": "test"},
    ).json()
    assert {row["key"]: row["value"] for row in body["rows"]} == {"human": 2}
    images = query(c, source="dataset", measure="images", dimension="class").json()
    assert {row["key"]: row["value"] for row in images["rows"]} == {
        "person": 2,
        "car": 2,
    }


def test_query_version_source_uses_the_frozen_manifest(c, data):
    body = query(
        c,
        source="version",
        measure="annotations",
        dimension="split",
        filters={"version": data["version"]},
    ).json()
    assert {row["key"]: row["value"] for row in body["rows"]} == {
        "train": 3,
        "valid": 1,
        "test": 2,
    }


def test_query_model_source_reads_stored_per_class_ap(c, data):
    body = query(
        c,
        source="model",
        measure="ap",
        dimension="class",
        filters={"model": data["model"]},
    ).json()
    assert {row["key"]: row["value"] for row in body["rows"]} == {
        "person": 0.5,
        "car": 0.34,
    }
    total = query(
        c,
        source="model",
        measure="ap",
        dimension="none",
        filters={"model": data["model"]},
    ).json()
    assert total["total"] == pytest.approx(0.42)
    # dimension "none" describes the whole evaluation, not a class breakdown
    assert [(r["key"], r["value"]) for r in total["rows"]] == [
        ("Total", pytest.approx(0.42))
    ]


def test_query_stream_source_buckets_events(c, data):
    per_rule = query(c, source="streams", measure="events", dimension="rule").json()
    assert {row["key"]: row["value"] for row in per_rule["rows"]}["Person at gate"] == 1
    assert per_rule["total"] == 3  # the 40-day-old event is outside the default window
    dwell = query(c, source="streams", measure="dwell_seconds", dimension="zone").json()
    assert {row["key"]: row["value"] for row in dwell["rows"]} == {"Gate": 42}
    by_stream = query(c, source="streams", measure="events", dimension="stream").json()
    assert {row["key"]: row["value"] for row in by_stream["rows"]} == {
        "Loading bay": 2,
        "Car park": 1,
    }


def test_query_rejects_measure_that_does_not_belong_to_the_source(c, data):
    assert (
        query(c, source="dataset", measure="ap", dimension="class").status_code == 400
    )
    assert (
        query(c, source="streams", measure="images", dimension="rule").status_code
        == 400
    )
    assert (
        query(c, source="model", measure="ap", dimension="class").status_code == 400
    )  # model filter missing


# --- stream analytics --------------------------------------------------------


def test_stream_analytics_breakdowns_dwell_and_hourly_heatmap(c, data):
    r = c.get(f"{INS}/streams?days=30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"]["events"] == 3
    assert body["totals"]["dwell_seconds"] == 42
    assert {row["key"]: row["value"] for row in body["breakdown"]["rule"]}[
        "Long dwell"
    ] == 1
    assert {row["key"]: row["value"] for row in body["breakdown"]["class"]} == {
        "person": 2,
        "car": 1,
    }
    assert {row["key"]: row["value"] for row in body["breakdown"]["zone"]} == {
        "Gate": 2
    }
    assert body["top_cameras"][0] == {
        "id": data["s1"],
        "name": "Loading bay",
        "events": 2,
        "reviewed": 0,
        "last_event": body["top_cameras"][0]["last_event"],
    }
    buckets = dict(zip(body["dwell"]["buckets"], body["dwell"]["counts"]))
    assert buckets["30–60 s"] == 1
    assert len(body["hourly"]["days"]) == 7 and len(body["hourly"]["hours"]) == 24
    assert sum(point[2] for point in body["hourly"]["values"]) == 3
    assert set(body["over_time"]) == {"dates", "by_rule", "by_zone", "by_class"}
    assert sum(sum(series["values"]) for series in body["over_time"]["by_rule"]) == 3


def test_stream_analytics_respects_the_window(c, data):
    body = c.get(f"{INS}/streams?days=1").json()
    # only events from the last day survive; the two-day-old pair is excluded
    assert body["totals"]["events"] == 1


def test_stream_analytics_refreshes_when_a_camera_is_renamed(c, data):
    first = c.get(f"{INS}/streams?days=30").json()
    assert first["top_cameras"][0]["name"] == "Loading bay"
    with SessionLocal() as db:
        stream = db.get(Stream, data["s1"])
        stream.name = "Loading bay east"
        db.commit()
    try:
        body = c.get(f"{INS}/streams?days=30").json()
        assert body["top_cameras"][0]["name"] == "Loading bay east"
    finally:
        with SessionLocal() as db:
            stream = db.get(Stream, data["s1"])
            stream.name = "Loading bay"
            db.commit()


# --- dashboards --------------------------------------------------------------


WIDGETS = [
    {
        "id": "w1",
        "title": "Annotations per class",
        "source": "dataset",
        "measure": "annotations",
        "dimension": "class",
        "chart": "bar",
        "filters": {},
        "w": 6,
    },
    {
        "id": "w2",
        "title": "Events per rule",
        "source": "streams",
        "measure": "events",
        "dimension": "rule",
        "chart": "table",
        "filters": {"days": 30},
        "w": 6,
    },
]


def test_dashboard_crud_round_trip(c, data):
    r = c.post(DASH, json={"name": "Ops overview", "widgets": WIDGETS})
    assert r.status_code == 200, r.text
    dash = r.json()
    assert (
        dash["name"] == "Ops overview"
        and len(dash["widgets"]) == 2
        and dash["share_token"] == ""
    )
    listed = c.get(DASH).json()
    assert [d["id"] for d in listed] == [dash["id"]]
    one = c.get(f"{DASH}/{dash['id']}").json()
    assert one["widgets"][0]["id"] == "w1"

    patched = c.patch(
        f"{DASH}/{dash['id']}", json={"name": "Ops", "widgets": WIDGETS[:1]}
    )
    assert patched.status_code == 200 and patched.json()["name"] == "Ops"
    assert len(c.get(f"{DASH}/{dash['id']}").json()["widgets"]) == 1
    assert c.delete(f"{DASH}/{dash['id']}").status_code == 200
    assert c.get(f"{DASH}/{dash['id']}").status_code == 404


def test_dashboard_share_token_grants_read_not_write(c, data):
    dash = c.post(DASH, json={"name": "Shared", "widgets": WIDGETS}).json()
    share = c.post(f"{DASH}/{dash['id']}/share")
    assert share.status_code == 200, share.text
    token = share.json()["token"]
    assert token and share.json()["path"].endswith(f"/dashboards/shared/{token}")
    shared = c.get(f"{DASH}/shared/{token}")
    assert shared.status_code == 200 and shared.json()["id"] == dash["id"]
    assert c.get(f"{DASH}/shared/{'0' * 12}").status_code == 404
    assert c.patch(f"{DASH}/shared/{token}", json={"name": "nope"}).status_code == 405
    c.delete(f"{DASH}/{dash['id']}")


def test_dashboard_validation_rejects_unknown_chart_and_widget_overrun(c, data):
    bad = [{**WIDGETS[0], "chart": "sunburst"}]
    assert c.post(DASH, json={"name": "bad", "widgets": bad}).status_code == 400
    too_many = [dict(WIDGETS[0], id=f"w{i}") for i in range(25)]
    assert c.post(DASH, json={"name": "big", "widgets": too_many}).status_code == 400
    assert c.post(DASH, json={"name": "", "widgets": WIDGETS}).status_code == 400


def test_dashboard_is_scoped_to_its_project(c, data):
    dash = c.post(DASH, json={"name": "Mine", "widgets": WIDGETS}).json()
    other = f"/api/ws/{WS}/projects/{SLUG}-other/dashboards"
    assert c.get(f"{other}/{dash['id']}").status_code == 404
    assert c.get(f"{other}/shared/{'x' * 12}").status_code == 404
    c.delete(f"{DASH}/{dash['id']}")


def test_annotator_can_read_but_not_save_dashboards(c, data):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    headers = {"Authorization": f"Bearer {issue_access(user.id)}"}
    assert c.get(DASH, headers=headers).status_code == 200
    assert c.get(f"{INS}/lineage", headers=headers).status_code == 200
    assert (
        c.post(
            DASH, json={"name": "nope", "widgets": WIDGETS}, headers=headers
        ).status_code
        == 403
    )
