"""Playground depth (G1): per-model runtime preflight and workspace-scoped sample images.

The GPU is faked: the preflight reads the catalog, the adapter probe cache and the scheduler's
lease ledger, so every state can be produced without a card.
"""
import os
import time
from types import SimpleNamespace

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app

WS = "labeldesk-demo"
PREFLIGHT = f"/api/ws/{WS}/playground/preflight"
SAMPLES = f"/api/ws/{WS}/playground/samples"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as cl:     # one login per module: the login endpoint is rate limited
        tok = cl.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        cl.headers["Authorization"] = f"Bearer {tok}"
        yield cl


def catalog_item(ref: str, *, family: str = "ultralytics", variant: str | None = None,
                 available: bool = True, reason: str = "") -> dict:
    return {"ref": ref, "family": family, "variant": variant or ref.split(":", 1)[1], "name": ref,
            "capabilities": ["detect"], "license": "AGPL-3.0", "available": available, "reason": reason,
            "kind": "vlm" if family == "vlm" else "zoo"}


class FakeScheduler:
    """The slice of GpuScheduler.state() the preflight reads."""

    def __init__(self, *, holder: str | None = None, leases: tuple[str, ...] = (),
                 loading: tuple[str, ...] = (), vlm_sleeping: bool | None = None):
        self.holder, self.lease_keys = holder, list(leases)
        self.loading_keys, self.vlm_sleeping = list(loading), vlm_sleeping

    def state(self) -> dict:
        return {"used_mb": 0, "budget_mb": 4500, "holder": self.holder,
                "leases": [{"key": k, "vram_mb": 100} for k in self.lease_keys]}

    def inflight(self) -> list[str]:
        return list(self.loading_keys)


def wire(monkeypatch, items: list[dict], keys: dict[str, str | None] | None = None,
         weights: dict[str, str | None] | None = None, **gpu):
    """Point the preflight at fake registry data, fake resolutions and a fake scheduler."""
    from app.services import runtime_state

    keys, weights = keys or {}, weights or {}
    monkeypatch.setattr(runtime_state, "catalog", lambda db, ws: items)
    monkeypatch.setattr(runtime_state, "scheduler", FakeScheduler(**gpu))

    def fake_resolve(ref, db, workspace_id=None):
        key = keys[ref]
        return SimpleNamespace(adapter=SimpleNamespace(runtime_key=lambda variant, weights: key),
                               variant=ref.split(":", 1)[1], weights=weights.get(ref))

    monkeypatch.setattr(runtime_state, "resolve", fake_resolve)
    return runtime_state


def test_preflight_reports_ready_for_resident_weights(client, monkeypatch):
    wire(monkeypatch, [catalog_item("ultralytics:yolo26n")],
         {"ultralytics:yolo26n": "YOLO|/data/yolo26n.pt"}, leases=("YOLO|/data/yolo26n.pt",))
    r = client.post(PREFLIGHT, json={"model_refs": ["ultralytics:yolo26n"]})
    assert r.status_code == 200, r.text
    (m,) = r.json()["models"]
    assert m["ref"] == "ultralytics:yolo26n" and m["state"] == "ready" and m["retry"] is False
    assert m["message"]


def test_preflight_reports_cold_when_weights_are_not_resident(client, monkeypatch):
    wire(monkeypatch, [catalog_item("ultralytics:yolo26n")],
         {"ultralytics:yolo26n": "YOLO|/data/yolo26n.pt"})
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["ultralytics:yolo26n"]}).json()["models"]
    assert m["state"] == "cold" and m["retry"] is False


def test_preflight_reports_loading_while_a_load_is_in_flight(client, monkeypatch):
    key = "hf|PekingU/rtdetr_v2_r18vd"
    wire(monkeypatch, [catalog_item("hf:PekingU/rtdetr_v2_r18vd", family="hf")],
         {"hf:PekingU/rtdetr_v2_r18vd": key}, loading=(key,))
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["hf:PekingU/rtdetr_v2_r18vd"]}).json()["models"]
    assert m["state"] == "loading"


def test_preflight_reports_gpu_busy_with_a_retry_hint(client, monkeypatch):
    wire(monkeypatch, [catalog_item("ultralytics:yolo26n")],
         {"ultralytics:yolo26n": "YOLO|/data/yolo26n.pt"}, holder="training yolo26n")
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["ultralytics:yolo26n"]}).json()["models"]
    assert m["state"] == "gpu_busy" and m["retry"] is True
    assert "training" not in m["message"]           # the holder name stays internal


def test_preflight_reports_a_sleeping_vllm_with_a_retry_hint(client, monkeypatch):
    wire(monkeypatch, [catalog_item("vlm:qwen2.5-vl-7b", family="vlm")],
         {"vlm:qwen2.5-vl-7b": None}, vlm_sleeping=True)
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["vlm:qwen2.5-vl-7b"]}).json()["models"]
    assert m["state"] == "sleeping" and m["retry"] is True


def test_preflight_reports_unavailable_without_leaking_the_probe_reason(client, monkeypatch):
    item = catalog_item("sam3:sam3.1", family="sam3", available=False,
                        reason="SAM checkpoint missing under /srv/secret/checkpoints")
    wire(monkeypatch, [item], {"sam3:sam3.1": "sam3"})
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["sam3:sam3.1"]}).json()["models"]
    assert m["state"] == "unavailable" and m["retry"] is False
    assert "/srv" not in m["message"] and "checkpoint" not in m["message"]


def test_preflight_treats_unknown_refs_as_unavailable(client, monkeypatch):
    wire(monkeypatch, [], {})
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["trained:gone"]}).json()["models"]
    assert m["state"] == "unavailable"


def test_preflight_reports_unavailable_when_a_trained_checkpoint_is_gone(client, monkeypatch):
    """The registry probe only sees the family, so the preflight must check this model's weights."""
    item = catalog_item("trained:gone", family="ultralytics")
    wire(monkeypatch, [item], {"trained:gone": "YOLO|/nope/best.pt"},
         {"trained:gone": "models/missing/best.pt"})
    (m,) = client.post(PREFLIGHT, json={"model_refs": ["trained:gone"]}).json()["models"]
    assert m["state"] == "unavailable" and m["retry"] is False
    assert "workspace" not in m["message"]              # it is listed here; its files are what is missing
    assert "models" not in m["message"] and "/nope" not in m["message"]


def test_preflight_accepts_a_trained_hf_model_directory(client, monkeypatch):
    """HF training saves models/<id>/ as a directory, not a checkpoint file; it must count as present."""
    from app.config import DATA_DIR

    model_dir = DATA_DIR / "models" / "g1-hf-dir"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}")
    try:
        item = catalog_item("trained:hfdir", family="hf")
        wire(monkeypatch, [item], {"trained:hfdir": "hf|models/g1-hf-dir"},
             {"trained:hfdir": "models/g1-hf-dir"})
        (m,) = client.post(PREFLIGHT, json={"model_refs": ["trained:hfdir"]}).json()["models"]
        assert m["state"] == "cold" and m["retry"] is False
    finally:
        (model_dir / "config.json").unlink(missing_ok=True)
        model_dir.rmdir()


def test_preflight_recognises_weights_leased_by_the_real_loader(client, monkeypatch):
    """Lease through the adapter's own predict -> _load path, not through the key under test."""
    import sys
    import types

    from PIL import Image as PImage

    from app.adapters import ADAPTERS
    from app.gpu import GpuScheduler
    from app.services import runtime_state

    class FakeBoxes:
        def __len__(self):
            return 0

    class FakeResult:
        names, boxes, masks, probs = {}, FakeBoxes(), None, None

    class FakeYOLO:
        def __init__(self, weights):
            self.weights = weights

        def predict(self, _im, conf=0.4, iou=0.5, verbose=False):
            return [FakeResult()]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=FakeYOLO))
    scheduler = GpuScheduler(4500, None)
    monkeypatch.setattr("app.gpu.scheduler", scheduler)      # _load imports this at call time
    monkeypatch.setattr(runtime_state, "scheduler", scheduler)
    ref = "ultralytics:yolo26n"
    monkeypatch.setattr(runtime_state, "catalog", lambda db, ws: [catalog_item(ref)])

    ADAPTERS["ultralytics"].predict("yolo26n", PImage.new("RGB", (8, 8)))
    assert scheduler.state()["leases"], "the loader did not lease a model"
    (m,) = client.post(PREFLIGHT, json={"model_refs": [ref]}).json()["models"]
    assert m["state"] == "ready"


def test_preflight_requires_one_to_three_refs(client, monkeypatch):
    wire(monkeypatch, [], {})
    assert client.post(PREFLIGHT, json={"model_refs": []}).status_code == 400
    assert client.post(PREFLIGHT, json={"model_refs": ["a:a", "b:b", "c:c", "d:d"]}).status_code == 400


@pytest.fixture
def sample_rows():
    """Annotated + blank images here, an annotated image in another workspace, and an empty workspace."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Image, Member, Project, User, Workspace

    stamp = str(int(time.time() * 1000))[-10:]
    ids = {
        "new": f"g1-new-{stamp}", "old": f"g1-old-{stamp}", "blank": f"g1-blank-{stamp}",
        "mine": f"g1-mine-{stamp}", "foreign": f"g1-fgn-{stamp}",
        "project": f"g1p-{stamp}", "other_project": f"g1o-{stamp}",
        "other_ws": f"g1o-{stamp}", "empty_ws": f"g1e-{stamp}",
    }
    now = time.time()
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        user = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        project = Project(id=ids["project"], workspace_id=ws.id, slug=f"g1-samples-{stamp}",
                          name="G1 samples", type="object-detection")
        other_ws = Workspace(id=ids["other_ws"], slug=f"g1-other-{stamp}", name="G1 other", owner_id=ws.owner_id)
        other_project = Project(id=ids["other_project"], workspace_id=other_ws.id, slug=f"g1-other-{stamp}",
                                name="G1 other", type="object-detection")
        empty_ws = Workspace(id=ids["empty_ws"], slug=f"g1-empty-{stamp}", name="G1 empty", owner_id=ws.owner_id)
        rows = [
            Image(id=ids["new"], project_id=project.id, name="new.png", sha256="a" * 64, width=20, height=10,
                  path=f"projects/{project.id}/new.png", thumb=f"projects/{project.id}/new-thumb.png",
                  assignee_id=user.id, n_annotations=2, created=now + 200),
            Image(id=ids["old"], project_id=project.id, name="old.png", sha256="b" * 64, width=20, height=10,
                  path=f"projects/{project.id}/old.png", thumb=f"projects/{project.id}/old-thumb.png",
                  assignee_id=user.id, n_annotations=1, created=now + 100),
            Image(id=ids["blank"], project_id=project.id, name="blank.png", sha256="c" * 64, width=20, height=10,
                  path=f"projects/{project.id}/blank.png", thumb=f"projects/{project.id}/blank-thumb.png",
                  assignee_id=user.id, n_annotations=0, created=now + 300),
            Image(id=ids["mine"], project_id=project.id, name="mine.png", sha256="e" * 64, width=20, height=10,
                  path=f"projects/{project.id}/mine.png", thumb=f"projects/{project.id}/mine-thumb.png",
                  assignee_id=labeler.id, n_annotations=1, created=now + 150),
            Image(id=ids["foreign"], project_id=other_project.id, name="foreign.png", sha256="d" * 64,
                  width=20, height=10, path=f"projects/{other_project.id}/foreign.png",
                  thumb=f"projects/{other_project.id}/foreign-thumb.png", n_annotations=3, created=now + 400),
        ]
        db.add_all([other_ws, empty_ws])
        db.flush()                                  # parents before rows that point at them
        db.add_all([project, other_project])
        db.flush()
        db.add(Member(workspace_id=empty_ws.id, user_id=user.id, role="owner"))
        db.add_all(rows)
        db.commit()
    yield {**ids, "empty_slug": f"g1-empty-{stamp}"}
    with SessionLocal() as db:
        for image_id in ("new", "old", "blank", "mine", "foreign"):
            row = db.get(Image, ids[image_id])
            if row:
                db.delete(row)
        for key in ("project", "other_project"):
            row = db.get(Project, ids[key])
            if row:
                db.delete(row)
        for key in ("other_ws", "empty_ws"):
            row = db.get(Workspace, ids[key])
            if row:
                db.delete(row)
        db.commit()


def test_samples_return_recent_annotated_images_of_this_workspace(client, sample_rows):
    r = client.get(SAMPLES, params={"limit": 12})
    assert r.status_code == 200, r.text
    samples = r.json()["samples"]
    by_id = {s["id"]: s for s in samples}
    assert sample_rows["new"] in by_id and sample_rows["old"] in by_id
    assert sample_rows["blank"] not in by_id                    # unannotated images are not samples
    assert sample_rows["foreign"] not in by_id                  # another workspace never leaks
    assert samples.index(by_id[sample_rows["new"]]) < samples.index(by_id[sample_rows["old"]])
    s = by_id[sample_rows["new"]]
    assert s["thumbnail"].startswith("/api/files/") and "sig=" in s["thumbnail"]
    assert "url" not in s                     # the strip only ever receives a signed thumbnail


def test_samples_hide_images_a_labeler_is_not_assigned(client, sample_rows):
    """The image list hides unassigned images from labelers; the sample strip must obey the same rule."""
    tok = client.post("/api/auth/login", json={"email": "labeler@labeldesk.dev", "password": "demo1234"}).json()["token"]
    saved = client.headers["Authorization"]
    try:
        client.headers["Authorization"] = f"Bearer {tok}"
        r = client.get(SAMPLES, params={"limit": 12})
    finally:
        client.headers["Authorization"] = saved
    assert r.status_code == 200, r.text
    by_id = {s["id"]: s for s in r.json()["samples"]}
    assert sample_rows["mine"] in by_id                 # assigned to this labeler
    assert sample_rows["new"] not in by_id              # assigned to someone else
    assert sample_rows["old"] not in by_id
    assert all("url" not in s for s in by_id.values())


def test_samples_respect_the_limit(client, sample_rows):
    samples = client.get(SAMPLES, params={"limit": 1}).json()["samples"]
    assert len(samples) == 1


def test_samples_are_empty_for_a_workspace_without_images(client, sample_rows):
    r = client.get(f"/api/ws/{sample_rows['empty_slug']}/playground/samples")
    assert r.status_code == 200 and r.json()["samples"] == []
