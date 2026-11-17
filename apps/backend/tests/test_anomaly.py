"""Good-only anomaly detection: patch memory bank, score map, regions, persistence.

The core is deterministic CPU code (colour/layout patch descriptors) so tests need no GPU,
network or downloaded weights.
"""

import hashlib
import math
import time
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from PIL import ImageDraw
from sqlalchemy import delete, select

from app.adapters import ADAPTERS
from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import AnomalyStation, Image, Member, Project, User, Workspace, now
from app.security import issue_access
from app.services import anomaly
from conftest import login

GRID = anomaly.GRID


def normal(seed: int = 0) -> PImage.Image:
    """A flat product surface with a fixed texture and small deterministic sensor noise."""
    im = PImage.new("RGB", (96, 96), (190, 192, 188))
    d = ImageDraw.Draw(im)
    for x in range(0, 96, 8):
        shade = 180 + (x // 8) % 3
        d.rectangle([x, 0, x + 3, 95], fill=(shade, shade + 2, shade - 2))
    rng = np.random.default_rng(seed)
    noise = rng.integers(-2, 3, (96, 96, 3), dtype=np.int16)
    arr = np.clip(np.asarray(im, dtype=np.int16) + noise, 0, 255).astype(np.uint8)
    return PImage.fromarray(arr, "RGB")


def defective() -> PImage.Image:
    im = normal(99)
    ImageDraw.Draw(im).rectangle([8, 8, 28, 28], fill=(240, 20, 20))
    return im


def normals(n: int = 8) -> list[PImage.Image]:
    return [normal(seed) for seed in range(n)]


def test_patch_features_shape_finite_and_deterministic():
    a = anomaly.patch_features(normal())
    b = anomaly.patch_features(normal())
    assert a.shape == (GRID * GRID, anomaly.FEATURE_DIM)
    assert np.isfinite(a).all()
    assert np.array_equal(a, b)


def test_training_needs_enough_normal_images():
    with pytest.raises(anomaly.TrainingError, match="at least"):
        anomaly.train(normals(anomaly.MIN_NORMAL_IMAGES - 1))


def test_normal_image_scores_low_and_a_defect_scores_high():
    model = anomaly.train(normals())
    low = anomaly.score(model, normal(42), threshold=1.0)
    high = anomaly.score(model, defective(), threshold=1.0)
    assert low["score"] < 1.0
    assert low["is_anomaly"] is False
    assert high["score"] > 1.0
    assert high["is_anomaly"] is True
    assert high["score"] > low["score"]


def test_heatmap_and_region_locate_the_defect():
    model = anomaly.train(normals())
    out = anomaly.score(model, defective(), threshold=1.0)
    values = np.asarray(out["heatmap"]["values"])
    assert values.shape == (GRID, GRID)
    assert out["regions"], "a localized defect must produce at least one region"
    region = out["regions"][0]
    # the red square covers the top-left ~3x3 cells; the hottest cell must sit inside it
    hot_row, hot_col = np.unravel_index(int(values.argmax()), values.shape)
    assert hot_row < GRID * 0.45 and hot_col < GRID * 0.45
    assert region["x"] < 0.4 and region["y"] < 0.4
    assert region["score"] > 1.0


def test_save_and_load_round_trip(tmp_path):
    model = anomaly.train(normals())
    path = tmp_path / "station.npz"
    anomaly.save(path, model)
    loaded = anomaly.load(path)
    a = anomaly.score(model, defective(), threshold=1.0)
    b = anomaly.score(loaded, defective(), threshold=1.0)
    assert loaded.grid == model.grid
    assert loaded.n_images == model.n_images
    assert math.isclose(a["score"], b["score"], rel_tol=1e-6)


def test_threshold_is_per_call_and_boundary_is_inclusive():
    model = anomaly.train(normals())
    out = anomaly.score(model, defective(), threshold=1.0)
    exact = out["score"]
    assert anomaly.score(model, defective(), threshold=round(exact, 6))["is_anomaly"] is True
    assert anomaly.score(model, defective(), threshold=round(exact + 0.5, 6))["is_anomaly"] is False


# --- API + worker -------------------------------------------------------------------------

WS = "labeldesk-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.headers.update(login(c))
        yield c


@pytest.fixture(scope="module")
def project(client):
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        p = Project(
            workspace_id=ws.id,
            slug="anomaly-qa",
            name="Anomaly QA",
            type="anomaly-detection",
        )
        db.add(p)
        db.commit()
        pid = p.id
        out = {"id": pid, "slug": p.slug, "ws": ws.slug}
    yield out
    with SessionLocal() as db:  # the shared demo workspace stays under the project limit
        row = db.get(Project, pid)
        if row is not None:
            db.delete(row)
            db.commit()


@pytest.fixture()
def flag_on(monkeypatch):
    monkeypatch.setenv("LD_FLAGS_ON", "task_29")


def base(project: dict) -> str:
    return f"/api/ws/{project['ws']}/projects/{project['slug']}/anomaly"


def seed(project: dict, name: str, im: PImage.Image, annotated: bool = False) -> str:
    rel = f"anomaly-tests/{name}.jpg"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    im.save(DATA_DIR / rel, "JPEG", quality=95)
    with SessionLocal() as db:
        row = Image(
            project_id=project["id"],
            name=name,
            sha256=hashlib.sha256(name.encode()).hexdigest(),
            width=im.width,
            height=im.height,
            path=rel,
            thumb=rel,
            split="train",
            status="done",
            annotations=[
                {
                    "id": "a1",
                    "classId": "c1",
                    "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
                }
            ]
            if annotated
            else [],
            n_annotations=1 if annotated else 0,
        )
        db.add(row)
        db.commit()
        return row.id


def wait_job(client: TestClient, jid: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/ws/{WS}/projects/anomaly-qa/jobs/{jid}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            assert job["status"] == "done", job
            return job
        time.sleep(0.2)
    raise TimeoutError(jid)


def wait_failed(client: TestClient, jid: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/ws/{WS}/projects/anomaly-qa/jobs/{jid}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            assert job["status"] == "failed", job
            return job
        time.sleep(0.2)
    raise TimeoutError(jid)


@pytest.fixture()
def normals_seeded(project) -> list[str]:
    return [seed(project, f"{uuid.uuid4().hex[:8]}-normal", normal(i)) for i in range(8)]


@pytest.fixture()
def ready_station(client, project, flag_on, normals_seeded):
    r = client.post(
        f"{base(project)}/stations",
        json={"name": f"Line-{uuid.uuid4().hex[:6]}", "threshold": 1.0},
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": normals_seeded})
    assert r.status_code == 200, r.text
    wait_job(client, r.json()["job"]["id"])
    station = next(s for s in client.get(f"{base(project)}/stations").json() if s["id"] == sid)
    assert station["status"] == "ready", station
    return sid


def test_flag_off_hides_anomaly_routes_and_the_project_type(client, project):
    assert client.get(base(project) + "/stations").status_code == 404
    r = client.post(
        f"/api/ws/{WS}/projects",
        json={"name": f"Hidden {uuid.uuid4().hex[:5]}", "type": "anomaly-detection"},
    )
    assert r.status_code == 400


def test_station_crud_and_threshold_validation(client, project, flag_on):
    r = client.post(
        f"{base(project)}/stations",
        json={"name": f"Line A {uuid.uuid4().hex[:5]}", "threshold": 1.2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "untrained" and body["threshold"] == 1.2
    sid = body["id"]

    assert client.post(f"{base(project)}/stations", json={"name": body["name"]}).status_code == 409
    r = client.patch(f"{base(project)}/stations/{sid}", json={"threshold": 0.8})
    assert r.status_code == 200 and r.json()["threshold"] == 0.8
    assert client.patch(f"{base(project)}/stations/{sid}", json={"threshold": 1001}).status_code == 422
    assert client.patch(f"{base(project)}/stations/{sid}", json={"threshold": -1}).status_code == 422
    assert any(s["id"] == sid and s["threshold"] == 0.8 for s in client.get(f"{base(project)}/stations").json())


def test_train_and_predict_heatmap_threshold_per_station(client, project, flag_on, normals_seeded):
    r = client.post(f"{base(project)}/stations", json={"name": f"Line B {uuid.uuid4().hex[:5]}"})
    sid = r.json()["id"]
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": normals_seeded})
    assert r.status_code == 200, r.text
    job = wait_job(client, r.json()["job"]["id"])
    assert job["kind"] == "anomaly_train"

    station = next(s for s in client.get(f"{base(project)}/stations").json() if s["id"] == sid)
    assert station["status"] == "ready"
    assert station["metrics"]["normal_images"] == len(normals_seeded)
    assert (DATA_DIR / station["artifact"]).is_file()

    good_id = seed(project, f"{uuid.uuid4().hex[:8]}-good", normal(55))
    bad_id = seed(project, f"{uuid.uuid4().hex[:8]}-bad", defective())
    good = client.post(f"{base(project)}/stations/{sid}/predict", json={"image_id": good_id}).json()
    bad = client.post(f"{base(project)}/stations/{sid}/predict", json={"image_id": bad_id}).json()
    assert good["is_anomaly"] is False and good["score"] < 1.0
    assert bad["is_anomaly"] is True and bad["score"] > 1.0
    assert bad["heatmap"]["grid"] == 16 and len(bad["heatmap"]["values"]) == 16
    assert bad["regions"] and bad["regions"][0]["w"] > 0
    assert bad["image"]["url"].startswith("/api/files/")
    assert bad["backend"] == "colour/layout"

    # A glaring defect scores far above the calibration p99, so suppression needs a high
    # threshold — the per-station setting must accept values above 10.
    client.patch(f"{base(project)}/stations/{sid}", json={"threshold": 250})
    assert (
        client.post(f"{base(project)}/stations/{sid}/predict", json={"image_id": bad_id}).json()["is_anomaly"] is False
    )

    # The threshold belongs to the station, not to the project: a second station on the same
    # training images keeps its own verdict for the same image.
    other = client.post(
        f"{base(project)}/stations", json={"name": f"Line B2 {uuid.uuid4().hex[:5]}", "threshold": 1.0}
    ).json()["id"]
    r = client.post(f"{base(project)}/stations/{other}/train", json={"image_ids": normals_seeded})
    assert r.status_code == 200, r.text
    wait_job(client, r.json()["job"]["id"])
    strict = client.post(f"{base(project)}/stations/{other}/predict", json={"image_id": bad_id}).json()
    tolerant = client.post(f"{base(project)}/stations/{sid}/predict", json={"image_id": bad_id}).json()
    assert strict["threshold"] == 1.0 and strict["is_anomaly"] is True
    assert tolerant["threshold"] == 250 and tolerant["is_anomaly"] is False


def test_normal_images_must_be_unannotated_and_known(client, project, flag_on, normals_seeded):
    bad = seed(project, f"{uuid.uuid4().hex[:8]}-labelled", normal(77), annotated=True)
    r = client.post(f"{base(project)}/stations", json={"name": f"Line C {uuid.uuid4().hex[:5]}"})
    sid = r.json()["id"]
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": [bad]})
    assert r.status_code == 400 and "annotation" in r.json()["detail"]
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": ["does-not-exist"]})
    assert r.status_code == 400


def test_too_few_normal_images_is_rejected_before_queueing(client, project, flag_on):
    ids = [seed(project, f"{uuid.uuid4().hex[:8]}-few", normal(i)) for i in range(anomaly.MIN_NORMAL_IMAGES - 1)]
    r = client.post(f"{base(project)}/stations", json={"name": f"Line D {uuid.uuid4().hex[:5]}"})
    sid = r.json()["id"]
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": ids})
    assert r.status_code == 400 and "at least" in r.json()["detail"]


def test_predict_before_training_is_a_state_conflict(client, project, flag_on):
    sid = client.post(f"{base(project)}/stations", json={"name": f"Line E {uuid.uuid4().hex[:5]}"}).json()["id"]
    img = seed(project, f"{uuid.uuid4().hex[:8]}-untrained", normal(3))
    assert client.post(f"{base(project)}/stations/{sid}/predict", json={"image_id": img}).status_code == 409


def test_vlm_zero_shot_comparator_is_optional_and_never_breaks_a_prediction(client, project, flag_on, ready_station):
    bad_id = seed(project, f"{uuid.uuid4().hex[:8]}-vlm-bad", defective())
    station = next(s for s in client.get(f"{base(project)}/stations").json() if s["id"] == ready_station)
    client.patch(
        f"{base(project)}/stations/{ready_station}",
        json={"threshold": station["metrics"]["suggested_threshold"]},
    )

    class FakeVlm:
        def ask_yes_no(self, im, question):
            return True

    monkeypatch_original = ADAPTERS["vlm"]
    ADAPTERS["vlm"] = FakeVlm()
    try:
        r = client.post(
            f"{base(project)}/stations/{ready_station}/predict",
            json={"image_id": bad_id, "compare_vlm": True},
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["is_anomaly"] is True
        assert out["vlm"] == {"available": True, "anomaly": True, "agrees": True}

        class BrokenVlm:
            def ask_yes_no(self, im, question):
                raise RuntimeError("vLLM not reachable")

        ADAPTERS["vlm"] = BrokenVlm()
        r = client.post(
            f"{base(project)}/stations/{ready_station}/predict",
            json={"image_id": bad_id, "compare_vlm": True},
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["is_anomaly"] is True
        assert out["vlm"]["available"] is False
    finally:
        ADAPTERS["vlm"] = monkeypatch_original

    r = client.post(f"{base(project)}/stations/{ready_station}/predict", json={"image_id": bad_id})
    assert r.status_code == 200, r.text
    assert r.json()["vlm"] is None


def test_training_failure_does_not_leak_internals_into_the_station(client, project, flag_on):
    ids = [seed(project, f"{uuid.uuid4().hex[:8]}-broken", normal(i)) for i in range(6)]
    sid = client.post(f"{base(project)}/stations", json={"name": f"Line F {uuid.uuid4().hex[:5]}"}).json()["id"]
    with SessionLocal() as db:
        row = db.get(Image, ids[0])
        broken_path = row.path
        (DATA_DIR / broken_path).unlink()
    r = client.post(f"{base(project)}/stations/{sid}/train", json={"image_ids": ids})
    assert r.status_code == 200, r.text
    wait_failed(client, r.json()["job"]["id"])
    station = next(s for s in client.get(f"{base(project)}/stations").json() if s["id"] == sid)
    assert station["status"] == "failed"
    assert "training failed" in station["error"]
    assert broken_path not in station["error"] and "Traceback" not in station["error"]


def test_station_is_workspace_isolated(client, project, flag_on, ready_station):
    other = TestClient(app)
    tok = other.post(
        "/api/auth/signup",
        json={
            "name": "Outsider",
            "email": f"out-{uuid.uuid4().hex[:6]}@x.io",
            "password": "longenough1",
        },
    ).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # Non-members are rejected by the tenancy dependency before any station lookup (403, same
    # as every other project route); the station must never leak across workspaces.
    assert other.get(base(project) + "/stations", headers=h).status_code == 403
    assert (
        other.post(
            f"{base(project)}/stations/{ready_station}/predict",
            json={"image_id": "x"},
            headers=h,
        ).status_code
        == 403
    )


def test_a_station_from_another_workspace_is_never_reachable(client, project, flag_on):
    """A station id is only valid under its own workspace's project path."""
    tag = uuid.uuid4().hex[:6]
    with SessionLocal() as db:
        owner = User(email=f"anomaly-owner-{tag}@x.io", name="Foreign", email_verified=now())
        db.add(owner)
        db.flush()
        ws = Workspace(slug=f"anomaly-other-{tag}", name="Other", owner_id=owner.id)
        db.add(ws)
        db.flush()
        db.add(Member(workspace_id=ws.id, user_id=owner.id, role="admin"))
        foreign_project = Project(workspace_id=ws.id, slug=f"other-{tag}", name="Other", type="anomaly-detection")
        db.add(foreign_project)
        db.flush()
        foreign = AnomalyStation(workspace_id=ws.id, project_id=foreign_project.id, name="Line X")
        db.add(foreign)
        db.commit()
        foreign_id, foreign_project_id, foreign_ws_id, foreign_uid = (
            foreign.id,
            foreign_project.id,
            ws.id,
            owner.id,
        )
    try:
        assert all(s["id"] != foreign_id for s in client.get(f"{base(project)}/stations").json())
        assert client.patch(f"{base(project)}/stations/{foreign_id}", json={"threshold": 2}).status_code == 404
        img = seed(project, f"{uuid.uuid4().hex[:8]}-foreign", normal(9))
        assert (
            client.post(
                f"{base(project)}/stations/{foreign_id}/predict",
                json={"image_id": img},
            ).status_code
            == 404
        )
    finally:
        with SessionLocal() as db:
            db.execute(delete(AnomalyStation).where(AnomalyStation.project_id == foreign_project_id))
            db.execute(delete(Project).where(Project.id == foreign_project_id))
            db.execute(delete(Member).where(Member.workspace_id == foreign_ws_id))
            db.execute(delete(Workspace).where(Workspace.id == foreign_ws_id))
            db.execute(delete(User).where(User.id == foreign_uid))
            db.commit()


def test_permissions_split_training_from_inference(client, project, flag_on, ready_station):
    with SessionLocal() as db:
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
    h = {"Authorization": f"Bearer {issue_access(labeler.id)}"}
    assert (
        client.post(
            f"{base(project)}/stations",
            json={"name": f"Nope {uuid.uuid4().hex[:5]}"},
            headers=h,
        ).status_code
        == 403
    )
    r = client.post(
        f"{base(project)}/stations/{ready_station}/train",
        json={"image_ids": []},
        headers=h,
    )
    assert r.status_code == 403
    bad = seed(project, f"{uuid.uuid4().hex[:8]}-labeler", defective())
    assert (
        client.post(
            f"{base(project)}/stations/{ready_station}/predict",
            json={"image_id": bad},
            headers=h,
        ).status_code
        == 200
    )
