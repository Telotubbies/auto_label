"""Segmentation catalogue (T-1014): rows, licences, VRAM and what this host can actually run.

The catalogue is the only place a segmentation model id, licence or memory figure may come from,
so every row is asserted here. A licence badge that can be dropped by editing one flag, a ref the
registry does not ship, or a checkpoint verdict that reads Ready without the file all fail before
the hub can offer the model to auto-label.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config
from app.adapters.catalog import _zoo
from app.db import SessionLocal
from app.main import app
from app.models import Member, Project, User, Worker, Workspace, WorkspaceFlag
from app.services import flags, host_inventory, inference_segmentation as seg
from conftest import login, login_as

WS = "labeldesk-demo"
FLAG = "task_inference"
URL = f"/api/ws/{WS}/inference/segmentation"
CHECKPOINT = "checkpoints/sam3.1_multiplex.pt"


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _inventory(gpus=None) -> dict:
    """A report shaped like the worker's; a host with no GPU says so with an empty list."""
    return {
        "os": "Linux",
        "arch": "x86_64",
        "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}] if gpus is None else gpus,
        "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
    }


def _row(model_id: str) -> dict:
    return next(row for row in seg.SEGMENTATION if row["id"] == model_id)


@pytest.fixture(autouse=True)
def _flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, True)
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(
            WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == FLAG, WorkspaceFlag.workspace_id == _ws_id())
        )
        db.commit()


@pytest.fixture()
def host() -> str:
    """One host row this module owns; the cleanup deletes every worker it created."""
    name = f"t1014-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        host_inventory.record(db, name, name, _inventory())
    yield name
    with SessionLocal() as db:
        db.query(Worker).filter(Worker.id == name).delete()
        db.commit()


@pytest.fixture()
def cpu_host() -> str:
    name = f"t1014-cpu-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        host_inventory.record(db, name, name, _inventory(gpus=[]))
    yield name
    with SessionLocal() as db:
        db.query(Worker).filter(Worker.id == name).delete()
        db.commit()


@pytest.fixture()
def admin() -> TestClient:
    c = TestClient(app)
    c.headers.update(login(c, "demo@labeldesk.dev"))
    return c


# ---------- the rows -----------------------------------------------------------


def test_every_row_has_a_licence_a_source_and_two_resolutions():
    # The card says "five rows" but names four families, and YOLO26 Seg is n/s/m: that is six
    # models. All six stay; dropping one would lose a model the owner asked for.
    assert [row["id"] for row in seg.SEGMENTATION] == [
        "sam3.1",
        "sam2",
        "yolo26n-seg",
        "yolo26s-seg",
        "yolo26m-seg",
        "mask2former-swin-l",
    ]
    for row in seg.SEGMENTATION:
        assert row["name"].strip() and row["family"].strip(), row["id"]
        assert row["params_m"] > 0, row["id"]
        licence = row["licence"]
        assert licence["name"].strip(), row["id"]
        assert licence["url"].startswith("https://"), row["id"]
        assert isinstance(licence["non_commercial"], bool), row["id"]
        assert row["vram"]["512"] > 0 and row["vram"]["1024"] > 0, row["id"]
        assert row["source_url"].startswith("https://"), row["id"]
        assert row["note"].strip(), row["id"]
    assert seg.validate() is None


def test_yolo_is_agpl_and_mask2former_is_non_commercial(monkeypatch):
    yolo = [row for row in seg.SEGMENTATION if row["engine"] == "ultralytics"]
    assert len(yolo) == 3
    assert all(row["licence"]["name"] == "AGPL-3.0" for row in yolo)
    mask2former = _row("mask2former-swin-l")
    assert mask2former["licence"]["name"] == "CC-BY-NC-4.0"
    assert mask2former["licence"]["non_commercial"] is True

    # The badge cannot be dropped in a refactor: a non-commercial licence with the flag off is a
    # catalogue bug, not a quiet commercial offering.
    licence = dict(mask2former["licence"], non_commercial=False)
    monkeypatch.setitem(mask2former, "licence", licence)
    with pytest.raises(ValueError, match="non-commercial"):
        seg.validate()


# ---------- provisioned verdicts ------------------------------------------------


def test_sam3_ready_needs_the_checkpoint(tmp_path, monkeypatch):
    sam = _row("sam3.1")
    monkeypatch.setattr(config, "SAM_ENABLED", "1")
    monkeypatch.setattr(config, "SAM_ROOT", tmp_path)
    gpu = _inventory()

    verdict = seg.provisioned(sam, gpu)
    assert verdict["ok"] is False
    assert verdict["reason"].startswith("Missing checkpoint"), verdict["reason"]
    assert str(tmp_path / CHECKPOINT) in verdict["reason"]

    checkpoint = tmp_path / CHECKPOINT
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"weights")
    verdict = seg.provisioned(sam, gpu)
    assert verdict["ok"] is True, verdict["reason"]
    assert verdict["reason"] == ""


def test_sam_disabled_reads_not_supported(tmp_path, monkeypatch):
    sam = _row("sam3.1")
    monkeypatch.setattr(config, "SAM_ROOT", tmp_path)
    checkpoint = tmp_path / CHECKPOINT
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"weights")  # the file is there; the switch still wins
    monkeypatch.setattr(config, "SAM_ENABLED", "0")

    verdict = seg.provisioned(sam, _inventory())
    assert verdict["ok"] is False
    assert verdict["reason"].startswith("Adapter not installed"), verdict["reason"]


def test_yolo_ref_matches_the_registry_zoo(monkeypatch):
    zoo = {f"{family}:{variant}" for family, variant, _ in _zoo()}
    refs = [seg.auto_label_ref(row)["ref"] for row in seg.SEGMENTATION if seg.auto_label_ref(row)["ref"]]
    assert "ultralytics:yolo26n-seg" in refs
    assert set(refs) <= zoo, set(refs) - zoo
    assert seg.validate() is None

    # A registry rename must fail the catalogue, never reach auto-label as a dangling ref.
    monkeypatch.setattr(seg, "_zoo", lambda: [(fam, var, name) for fam, var, name in _zoo() if var != "yolo26n-seg"])
    with pytest.raises(ValueError, match="yolo26n-seg"):
        seg.validate()


def test_cpu_host_marks_gpu_models_unsupported(admin, cpu_host):
    r = admin.get(URL, params={"host": cpu_host})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["models"]) == 6
    for row in body["models"]:
        assert row["provisioned"]["ok"] is False, row["id"]
        assert row["provisioned"]["reason"].startswith("Not supported on this OS"), row["id"]

    unknown = admin.get(URL, params={"host": "no-such-host"})
    assert unknown.status_code == 404


# ---------- the route -----------------------------------------------------------


def test_project_is_resolved_and_foreign_slug_is_404(admin, host):
    r = admin.get(URL, params={"host": host, "project": "ppe-detection"})
    assert r.status_code == 200, r.text
    assert r.json()["project"] == {"slug": "ppe-detection", "name": "PPE Detection"}
    # The tab (T-1015) renders these fields; a missing one is a broken handoff, not a layout choice.
    row = r.json()["models"][0]
    assert {
        "id",
        "name",
        "family",
        "params_m",
        "licence",
        "vram",
        "engine",
        "source_url",
        "provisioned",
        "auto_label",
    } <= set(row)
    assert set(row["vram"]) == {"512", "1024"}
    assert set(row["auto_label"]) == {"ref", "engine_hint", "classes_required"}

    assert admin.get(URL, params={"host": host}).json()["project"] is None
    assert admin.get(URL, params={"host": host, "project": "no-such-project"}).status_code == 404

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        other = Workspace(slug=f"t1014-{uuid.uuid4().hex[:8]}", name="Other", owner_id=user.id)
        db.add(other)
        db.flush()
        db.add(Member(workspace_id=other.id, user_id=user.id, role="admin"))
        db.add(Project(workspace_id=other.id, slug="foreign-project", name="Foreign", type="object-detection"))
        db.commit()
        other_id = other.id
    try:
        foreign = admin.get(URL, params={"host": host, "project": "foreign-project"})
        assert foreign.status_code == 404, foreign.text
    finally:
        with SessionLocal() as db:
            db.execute(Project.__table__.delete().where(Project.workspace_id == other_id))
            db.execute(Member.__table__.delete().where(Member.workspace_id == other_id))
            db.execute(Workspace.__table__.delete().where(Workspace.id == other_id))
            db.commit()


def test_member_is_403_and_flag_off_is_404(admin, host):
    member = TestClient(app)
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.get(URL, params={"host": host}).status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, False)
        db.commit()
    assert admin.get(URL, params={"host": host}).status_code == 404
