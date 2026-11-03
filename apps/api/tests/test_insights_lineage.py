"""Task 20c: lineage DAG, dashboard builder and stream analytics contracts."""

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

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
from app.services import insights_stream, versioning

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
                    {
                        "source": ids[k],
                        "split": split,
                        "anns": [{"cls": cls} for cls in anns],
                    }
                    for k, split, anns in (
                        ("i1", "train", (0, 0, 1)),
                        ("i2", "valid", (0,)),
                        ("i3", "test", (1, 1)),
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


def test_lineage_keeps_frozen_edges_after_images_are_soft_deleted(c, data):
    """Lineage is historical: a version's manifest still names an image after the dataset drops it."""
    doomed = [data["ids"]["i3"], data["ids"]["i4"]]
    with SessionLocal() as db:
        for row in db.scalars(select(Image).where(Image.id.in_(doomed))).all():
            row.deleted_at = now()
        db.commit()
    try:
        body = c.get(f"{INS}/lineage").json()
        assert f"batch:{data['batch2']}" in ids(body)
        assert (f"batch:{data['batch2']}", f"version:{data['version']}") in edges(body)
        node = next(n for n in body["nodes"] if n["id"] == f"batch:{data['batch2']}")
        assert node["counts"]["images"] == 0
    finally:
        with SessionLocal() as db:
            for row in db.scalars(select(Image).where(Image.id.in_(doomed))).all():
                row.deleted_at = None
            db.commit()


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


def test_query_images_respects_the_label_source_filter(c, data):
    by_class = query(
        c,
        source="dataset",
        measure="images",
        dimension="class",
        filters={"source": "human"},
    ).json()
    assert {row["key"]: row["value"] for row in by_class["rows"]} == {
        "person": 1,
        "car": 1,
    }
    assert by_class["total"] == 2
    # the source dimension uses the same filtered annotation set, not every source on the image
    by_source = query(
        c,
        source="dataset",
        measure="images",
        dimension="source",
        filters={"class": "car"},
    ).json()
    assert {row["key"]: row["value"] for row in by_source["rows"]} == {
        "human": 1,
        "sam3": 1,
    }


def test_dataset_widgets_aggregate_in_sql_without_hydrating_annotations(c, data, monkeypatch):
    """I11: a widget cache miss must not materialise every Image row (including annotations) in Python."""
    from app.services import insights, insights_common

    def hydrate(*_args, **_kwargs):
        raise AssertionError("widget aggregation loaded image rows into Python")

    insights_common.clear_cache()
    monkeypatch.setattr(insights, "dataset_rows", hydrate)
    monkeypatch.setattr(insights, "live_images", hydrate)
    cases = [
        {"source": "dataset", "measure": "annotations", "dimension": "class"},
        {"source": "dataset", "measure": "annotations", "dimension": "source",
         "filters": {"split": "test"}},
        {"source": "dataset", "measure": "images", "dimension": "class",
         "filters": {"source": "human", "tag": "day"}},
        {"source": "dataset", "measure": "images", "dimension": "tag"},
        {"source": "dataset", "measure": "images", "dimension": "class", "dimension2": "source"},
        {"source": "dataset", "measure": "annotations", "dimension": "batch", "dimension2": "tag"},
    ]
    for body in cases:
        r = query(c, **body)
        assert r.status_code == 200, (body, r.text)

    # the SQL path must keep the old image semantics: class × source is a cross product per image
    heat = query(
        c, source="dataset", measure="images", dimension="class", dimension2="source"
    ).json()
    assert {(row["key"], row["group"]): row["value"] for row in heat["rows"]} == {
        ("car", "human"): 2,
        ("person", "human"): 1,
        ("person", "sam3"): 1,
        ("car", "sam3"): 1,
        ("person", "vlm+sam3"): 1,
    }
    assert heat["total"] == 4
    tags = query(c, source="dataset", measure="images", dimension="tag").json()
    assert {row["key"]: row["value"] for row in tags["rows"]} == {"day": 2, "night": 2}
    batch_by_tag = query(
        c, source="dataset", measure="annotations", dimension="batch", dimension2="tag"
    ).json()
    assert {
        (row["key"], row["group"]): row["value"] for row in batch_by_tag["rows"]
    } == {("Morning batch", "day"): 3, ("Night batch", "night"): 2}
    assert batch_by_tag["total"] == 6


def test_dataset_widget_sql_compiles_for_postgres():
    """The JSON unnesting has a PostgreSQL branch; the deployed database must not see SQLite names."""
    from sqlalchemy.dialects import postgresql

    from app.services import insights_aggregate

    statements = []

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _DB:
        def get_bind(self):
            return _Bind()

        def scalar(self, stmt):
            statements.append(stmt)
            return 0

        def execute(self, stmt):
            statements.append(stmt)
            return []

    project = Project(id="p1", workspace_id="w1", slug="p", name="p")
    for measure, dimension, dimension2 in (
        ("annotations", "class", "source"),
        ("annotations", "batch", "tag"),
        ("images", "class", "source"),
        ("images", "tag", "none"),
    ):
        statements.clear()
        insights_aggregate.dataset_counts(
            _DB(),
            project,
            {
                "source": "dataset",
                "measure": measure,
                "dimension": dimension,
                "dimension2": dimension2,
                "filters": {"source": "human", "tag": "day"},
            },
        )
        sql = "\n".join(
            str(stmt.compile(dialect=postgresql.dialect())) for stmt in statements
        )
        assert "json_array_elements" in sql
        assert "json_each" not in sql


def test_dataset_widget_with_a_version_filter_uses_the_frozen_scope(c, data, monkeypatch):
    """A dataset read scoped to a version limits the live images and uses the manifest's split."""
    from app.services import insights, insights_common

    def hydrate(*_args, **_kwargs):
        raise AssertionError("version-scoped widget aggregation loaded image rows into Python")

    insights_common.clear_cache()
    monkeypatch.setattr(insights, "dataset_rows", hydrate)
    body = query(
        c,
        source="dataset",
        measure="images",
        dimension="split",
        filters={"version": data["version"]},
    ).json()
    assert {row["key"]: row["value"] for row in body["rows"]} == {
        "train": 1,
        "valid": 1,
        "test": 1,
    }
    assert body["total"] == 3                 # i4 is not in the version's manifest


def test_dataset_widget_postgres_guards_a_legacy_dict_annotations_row():
    """Important 1: a v1 dict-shaped annotations row must not make the unnest itself raise.

    PostgreSQL evaluates the set-returning function's argument before the object predicate, so
    ``json_array_elements('{"label":"cat"}')`` errors. The array expression itself must be
    guarded by ``json_typeof``, not filtered after unnesting.
    """
    from sqlalchemy.dialects import postgresql

    from app.services import insights_aggregate

    class _DB:
        def __init__(self):
            self.statements = []

        def get_bind(self):
            class _Bind:
                dialect = type("_Dialect", (), {"name": "postgresql"})()

            return _Bind()

        def scalar(self, stmt):
            self.statements.append(stmt)
            return 0

        def execute(self, stmt):
            self.statements.append(stmt)
            return []

    project = Project(id="p1", workspace_id="w1", slug="p", name="p")
    # Both paths unnest annotations: the annotation measure and an image dimension/filter.
    specs = (
        {"source": "dataset", "measure": "annotations", "dimension": "class",
         "dimension2": "none", "filters": {}},
        {"source": "dataset", "measure": "images", "dimension": "class",
         "dimension2": "none", "filters": {"class": "cat"}},
    )
    for spec in specs:
        db = _DB()
        insights_aggregate.dataset_counts(db, project, spec)
        sql = "\n".join(
            str(stmt.compile(dialect=postgresql.dialect())) for stmt in db.statements
        )
        assert "json_array_elements(CASE" in sql
        assert "json_typeof" in sql
        assert "json_build_array()" in sql


def test_dataset_widget_with_a_large_version_stays_under_the_parameter_limit():
    """Important 2: a version scope must be one payload, not an IN list plus a CASE per image.

    A 12k-image manifest used to compile ~24k CASE parameters (and expand a 12k-value IN),
    which exceeds SQLite's 32,766-variable ceiling near 11k images and Postgres' 65,535 near 22k.
    """
    from sqlalchemy.dialects import postgresql, sqlite

    from app.services import insights_aggregate

    project = Project(id="p1", workspace_id="w1", slug="p", name="p")
    split_of = {f"{i:016x}": "train" for i in range(12_000)}

    def statements_for(dialect_name: str) -> list:
        statements = []

        class _DB:
            def get_bind(self):
                class _Bind:
                    dialect = type("_Dialect", (), {"name": dialect_name})()

                return _Bind()

            def scalar(self, stmt):
                statements.append(stmt)
                return 0

            def execute(self, stmt):
                statements.append(stmt)
                return []

        insights_aggregate.dataset_counts(
            _DB(),
            project,
            {"source": "dataset", "measure": "images", "dimension": "class",
             "dimension2": "none", "filters": {}},
            version=object(),
            split_of=split_of,
        )
        assert statements
        return statements

    for dialect in (sqlite.dialect(), postgresql.dialect()):
        statements = statements_for(dialect.name)
        param_counts = [len(stmt.compile(dialect=dialect).params) for stmt in statements]
        assert max(param_counts) < 10, (dialect.name, param_counts)
        sql = "\n".join(str(stmt.compile(dialect=dialect)) for stmt in statements)
        if dialect.name == "postgresql":
            assert "json_each" not in sql
    pg_sql = "\n".join(str(stmt.compile(dialect=postgresql.dialect()))
                       for stmt in statements_for("postgresql"))
    assert "json_extract_path_text" in pg_sql
    assert "|| images.id" not in pg_sql


def test_query_version_source_without_batch_or_tag_reads_no_image_rows(c, data):
    """I11 root: a version widget that needs no image metadata must not hydrate project rows."""
    from sqlalchemy import event

    from app.db import engine
    from app.services import insights_common

    seen: list[str] = []

    def capture(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(statement)

    insights_common.clear_cache()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        r = query(c, source="version", measure="annotations", dimension="class",
                  filters={"version": data["version"]})
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert r.status_code == 200, r.text
    assert not [s for s in seen if "images.tags" in s]


def test_query_version_source_with_a_batch_dimension_uses_only_manifest_sources(c, data):
    """The metadata lookup still works when the widget does need batch/tag values."""
    body = query(c, source="version", measure="images", dimension="batch",
                 filters={"version": data["version"]}).json()
    assert {row["key"]: row["value"] for row in body["rows"]} == {
        "Morning batch": 2,
        "Night batch": 1,
    }
    assert body["total"] == 3


def test_dataset_version_filter_with_an_empty_manifest_returns_no_rows(c, data):
    """Minor 4: a written-but-empty manifest is an empty scope, never the live dataset."""
    with SessionLocal() as db:
        version = Version(project_id=data["pid"], number=98, name="empty", status="ready", stats={})
        db.add(version)
        db.commit()
        path = versioning.version_dir(version)
        path.mkdir(parents=True, exist_ok=True)
        (path / "manifest.json").write_text(json.dumps({"classes": [], "items": []}))
        version_id = version.id
    body = query(c, source="dataset", measure="images", dimension="none",
                 filters={"version": version_id}).json()
    assert body["total"] == 0
    assert body["rows"] == []


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


def test_query_version_source_keeps_the_frozen_annotations(c, data):
    """A later relabel must not rewrite a frozen version's class counts."""
    with SessionLocal() as db:
        row = db.get(Image, data["ids"]["i1"])
        original = row.annotations
        row.annotations = []
        row.n_annotations = 0
        db.commit()
    try:
        by_class = query(
            c,
            source="version",
            measure="annotations",
            dimension="class",
            filters={"version": data["version"]},
        ).json()
        assert {row["key"]: row["value"] for row in by_class["rows"]} == {
            "person": 3,
            "car": 3,
        }
        by_source = query(
            c,
            source="version",
            measure="images",
            dimension="split",
            filters={"version": data["version"]},
        ).json()
        assert {row["key"]: row["value"] for row in by_source["rows"]} == {
            "train": 1,
            "valid": 1,
            "test": 1,
        }
    finally:
        with SessionLocal() as db:
            row = db.get(Image, data["ids"]["i1"])
            row.annotations = original
            row.n_annotations = len(original)
            db.commit()


def test_query_version_without_a_manifest_does_not_fall_back_to_the_dataset(c, data):
    with SessionLocal() as db:
        version = Version(project_id=data["pid"], number=99, status="building")
        db.add(version)
        db.commit()
        version_id = version.id
    body = query(
        c,
        source="version",
        measure="annotations",
        dimension="split",
        filters={"version": version_id},
    )
    assert body.status_code == 404, body.text


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


def test_query_model_kpi_respects_the_class_filter(c, data):
    kpi = query(
        c,
        source="model",
        measure="ap",
        dimension="none",
        filters={"model": data["model"], "class": "person"},
    ).json()
    assert kpi["total"] == pytest.approx(0.5)
    assert [(row["key"], row["value"]) for row in kpi["rows"]] == [
        ("Total", pytest.approx(0.5))
    ]
    table = query(
        c,
        source="model",
        measure="ap",
        dimension="class",
        filters={"model": data["model"], "class": "person"},
    ).json()
    assert {row["key"]: row["value"] for row in table["rows"]} == {"person": 0.5}
    assert table["total"] == pytest.approx(0.5)


def test_query_model_rejects_a_second_heatmap_dimension(c, data):
    """The stored evaluation has one dimension; a heatmap would silently drop the second."""
    for dimension, dimension2 in (("none", "class"), ("class", "none")):
        response = query(
            c,
            source="model",
            measure="ap",
            dimension=dimension,
            dimension2=dimension2,
            filters={"model": data["model"]},
        )
        assert response.status_code == 400, (dimension, dimension2, response.text)
        assert response.json()["detail"] == "the model source has no second dimension"


def test_query_model_without_an_evaluation_is_not_a_zero_ap(c, data):
    """A queued or failed model has unknown AP; a real-looking 0.0 is a different claim."""
    with SessionLocal() as db:
        ws_id = db.get(Project, data["pid"]).workspace_id
        model = TrainedModel(
            workspace_id=ws_id,
            project_id=data["pid"],
            version_id=data["version"],
            name="unevaluated",
            arch="yolo11n",
            task="detect",
            status="queued",
            classes=["person"],
            metrics={},
        )
        db.add(model)
        db.commit()
        model_id = model.id
    try:
        response = query(
            c,
            source="model",
            measure="ap",
            dimension="class",
            filters={"model": model_id},
        )
        assert response.status_code == 404, response.text
        assert "evaluation" in response.json()["detail"].lower()
        unknown = query(
            c,
            source="model",
            measure="ap",
            dimension="class",
            filters={"model": data["model"], "class": "bus"},
        )
        assert unknown.status_code == 404, unknown.text
        assert "bus" in unknown.json()["detail"]
    finally:
        with SessionLocal() as db:
            db.delete(db.get(TrainedModel, model_id))
            db.commit()


def test_lineage_reports_missing_metrics_instead_of_zero(c, data):
    """The model node must not present an unevaluated model as AP 0.0."""
    with SessionLocal() as db:
        ws_id = db.get(Project, data["pid"]).workspace_id
        model = TrainedModel(
            workspace_id=ws_id,
            project_id=data["pid"],
            version_id=data["version"],
            name="unevaluated",
            arch="yolo11n",
            task="detect",
            status="queued",
            classes=["person"],
            metrics={},
        )
        db.add(model)
        db.commit()
        model_id = model.id
    try:
        body = c.get(f"{INS}/lineage").json()
        node = next(n for n in body["nodes"] if n["id"] == f"model:{model_id}")
        assert node["metrics"] == {"AP": None, "AP50": None}
    finally:
        with SessionLocal() as db:
            db.delete(db.get(TrainedModel, model_id))
            db.commit()


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


def test_query_stream_hour_dimension_is_padded_and_chronological(c, data):
    """Hour labels must sort lexically as time; the client orders groups with localeCompare."""
    nine = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        event = StreamEvent(
            stream_id=data["s2"],
            ts=nine.timestamp(),
            rule={"index": 0, "kind": "count", "label": "Nine o'clock"},
            summary="nine",
            classes="|car|",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    try:
        hourly = query(c, source="streams", measure="events", dimension="hour").json()
        keys = [row["key"] for row in hourly["rows"]]
        assert keys, hourly
        assert "09" in keys, keys
        assert all(len(key) == 2 and key.isdigit() for key in keys), keys
        assert keys == sorted(keys), keys
        heat = query(
            c, source="streams", measure="events", dimension="rule", dimension2="hour"
        ).json()
        groups = {row["group"] for row in heat["rows"]}
        assert "09" in groups, groups
        assert all(len(group) == 2 and group.isdigit() for group in groups), groups
    finally:
        with SessionLocal() as db:
            db.delete(db.get(StreamEvent, event_id))
            db.commit()


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


def test_query_rejects_filters_the_source_would_ignore(c, data):
    rejected = [
        {
            "source": "dataset",
            "measure": "annotations",
            "dimension": "class",
            "filters": {"stream": "camera-x"},
        },
        {
            "source": "dataset",
            "measure": "annotations",
            "dimension": "class",
            "filters": {"days": 7},
        },
        {
            "source": "streams",
            "measure": "events",
            "dimension": "rule",
            "filters": {"split": "test"},
        },
        {
            "source": "model",
            "measure": "ap",
            "dimension": "none",
            "filters": {"model": data["model"], "split": "train"},
        },
    ]
    for body in rejected:
        response = query(c, **body)
        assert response.status_code == 400, (body, response.text)
    # the accepted filters still pass
    assert (
        query(
            c, source="streams", measure="events", dimension="rule", filters={"days": 7}
        ).status_code
        == 200
    )


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
    assert set(body["over_time"]) == {
        "dates",
        "total",
        "by_rule",
        "by_zone",
        "by_class",
    }
    assert sum(sum(series["values"]) for series in body["over_time"]["by_rule"]) == 3


def test_stream_stamp_aggregate_compiles_for_postgres(c, data):
    """PostgreSQL has no sum(boolean); the cache stamp must use a portable aggregate."""
    sql = str(
        insights_stream._stamp_query(data["pid"], 0.0).compile(
            dialect=postgresql.dialect()
        )
    ).lower()
    assert "sum(stream_events.reviewed)" not in sql
    assert "case" in sql


def test_stream_analytics_buckets_events_in_the_requested_timezone(c, data):
    offset = 420  # UTC+07:00: 20:30 UTC is 03:30 the next local day
    utc_day = datetime.now(timezone.utc).date() - timedelta(days=1)
    ts = datetime(
        utc_day.year, utc_day.month, utc_day.day, 20, 30, tzinfo=timezone.utc
    ).timestamp()
    with SessionLocal() as db:
        event = StreamEvent(
            stream_id=data["s1"],
            ts=ts,
            rule={"index": 9, "kind": "count", "label": "TZ probe"},
            summary="tz probe",
            classes="|person|",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    try:
        body = c.get(f"{INS}/streams?days=30&tz_offset={offset}").json()
        assert body["window"]["tz_offset"] == offset
        local = datetime.fromtimestamp(ts + offset * 60, timezone.utc)
        assert local.date().isoformat() in body["over_time"]["dates"]
        cell = next(
            (
                value
                for value in body["hourly"]["values"]
                if value[0] == local.weekday() and value[1] == local.hour
            ),
            None,
        )
        assert cell is not None and cell[2] >= 1
    finally:
        with SessionLocal() as db:
            db.delete(db.get(StreamEvent, event_id))
            db.commit()


def test_stream_analytics_daily_total_counts_each_event_once(c, data):
    with SessionLocal() as db:
        event = StreamEvent(
            stream_id=data["s2"],
            ts=now() - 120,
            rule={"index": 0, "kind": "count", "label": "Two classes"},
            summary="two classes",
            classes="|person|car|",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    try:
        body = c.get(f"{INS}/streams?days=30").json()
        # per-class series count an event once per class; the daily total counts it once
        assert sum(body["over_time"]["total"]) == body["totals"]["events"]
        assert (
            sum(sum(series["values"]) for series in body["over_time"]["by_class"])
            > body["totals"]["events"]
        )
    finally:
        with SessionLocal() as db:
            db.delete(db.get(StreamEvent, event_id))
            db.commit()


def test_stream_analytics_daily_series_covers_the_whole_window(c, data):
    """Every event inside the rolling window needs a date bucket on the axis.

    A viewer east of UTC has a 1-day window that starts on the previous local date; when the
    axis was built as `days` dates ending today, that partial first day vanished from every
    daily series even though the event stayed in the totals.
    """
    now_dt = datetime.now(timezone.utc)
    offset = 12 * 60 - (
        now_dt.hour * 60 + now_dt.minute
    )  # local noon, so the edge is clear
    ts = (
        time.time() - DAY + 60
    )  # one minute inside a 24 h window, on the previous local day
    local_day = (
        datetime.fromtimestamp(ts + offset * 60, timezone.utc).date().isoformat()
    )
    with SessionLocal() as db:
        event = StreamEvent(
            stream_id=data["s2"],
            ts=ts,
            rule={"index": 0, "kind": "count", "label": "Window edge"},
            summary="window edge",
            classes="|car|",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    try:
        body = c.get(f"{INS}/streams?days=1&tz_offset={offset}").json()
        assert local_day in body["over_time"]["dates"], body["over_time"]["dates"]
        assert sum(body["over_time"]["total"]) == body["totals"]["events"]
        assert (
            sum(sum(series["values"]) for series in body["over_time"]["by_rule"])
            == body["totals"]["events"]
        )
    finally:
        with SessionLocal() as db:
            db.delete(db.get(StreamEvent, event_id))
            db.commit()


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


def test_labeler_cannot_read_lineage_widgets_or_dashboard_specs(c, data):
    """I11: aggregation reads are a review surface; a labeler must not trigger a full dataset scan."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    headers = {"Authorization": f"Bearer {issue_access(user.id)}"}
    assert c.get(f"{INS}/lineage", headers=headers).status_code == 403
    assert c.get(f"{INS}/streams", headers=headers).status_code == 403
    assert c.get(DASH, headers=headers).status_code == 403
    widget = {"source": "dataset", "measure": "annotations", "dimension": "class"}
    assert c.post(f"{INS}/query", json=widget, headers=headers).status_code == 403

    dash = c.post(DASH, json={"name": "Shared", "widgets": WIDGETS}).json()
    share = c.post(f"{DASH}/{dash['id']}/share").json()
    try:
        assert c.get(f"{DASH}/{dash['id']}", headers=headers).status_code == 403
        # an explicitly shared link is a deliberate read-only exception; it carries specs, not aggregates
        assert c.get(f"{DASH}/shared/{share['token']}", headers=headers).status_code == 200
    finally:
        c.delete(f"{DASH}/{dash['id']}")


def test_shared_dashboard_serves_widget_data_to_a_labeler(c, data):
    """A shared link is a read-only capability: its widgets must return data, not 403."""
    dash = c.post(DASH, json={"name": "Shared", "widgets": WIDGETS}).json()
    token = c.post(f"{DASH}/{dash['id']}/share").json()["token"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    headers = {"Authorization": f"Bearer {issue_access(user.id)}"}
    spec = {key: WIDGETS[0].get(key) for key in
            ("source", "measure", "dimension", "dimension2", "filters")}
    try:
        r = c.post(f"{DASH}/shared/{token}/query", json=spec, headers=headers)
        assert r.status_code == 200, r.text
        assert {row["key"]: row["value"] for row in r.json()["rows"]} == {
            "person": 3,
            "car": 3,
        }
        # the token is a capability for this dashboard's widgets, not an arbitrary query endpoint
        arbitrary = {"source": "dataset", "measure": "annotations", "dimension": "split"}
        assert c.post(
            f"{DASH}/shared/{token}/query", json=arbitrary, headers=headers
        ).status_code == 400
        assert c.post(
            f"{DASH}/shared/{'0' * 12}/query", json=spec, headers=headers
        ).status_code == 404
    finally:
        c.delete(f"{DASH}/{dash['id']}")


def test_widget_cache_serialises_concurrent_misses_in_one_project(data):
    """I11: a burst of distinct specs must not run several full scans at once on one worker."""
    from app.services import insights_common

    insights_common.clear_cache()
    scope = f"query:{data['pid']}"
    active: list[int] = []
    peak: list[int] = []
    lock = threading.Lock()

    def build(i):
        with lock:
            active.append(i)
            peak.append(len(active))
        time.sleep(0.02)
        with lock:
            active.pop()
        return {"rows": []}

    threads = [
        threading.Thread(
            target=insights_common.cached,
            args=(scope, f"spec-{i}", "sig", lambda i=i: build(i)),
        )
        for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert max(peak) == 1, peak


def test_widget_cache_is_bounded_per_project(data):
    """I11: distinct tag/class/batch specs must not grow one project's cache without a bound."""
    from app.services import insights_common

    insights_common.clear_cache()
    scope = f"query:{data['pid']}"
    built: list[int] = []
    for i in range(insights_common.CACHE_MAX_PER_SCOPE * 3):
        insights_common.cached(scope, f"spec-{i}", "sig", lambda i=i: built.append(i) or {"rows": []})

    assert insights_common.cache_size(scope) == insights_common.CACHE_MAX_PER_SCOPE
    assert insights_common.cache_total() <= insights_common.CACHE_MAX

    calls = len(built)
    newest = f"spec-{insights_common.CACHE_MAX_PER_SCOPE * 3 - 1}"
    payload, hit = insights_common.cached(scope, newest, "sig", lambda: built.append(-1) or {"rows": []})
    assert hit is True and payload == {"rows": []} and len(built) == calls

    other = f"query:{data['other_id']}"        # one project's keys never evict another's
    insights_common.cached(other, "spec", "sig", lambda: {"rows": []})
    assert insights_common.cache_size(other) == 1
