"""T-1011: the two model routes that queue a worker job.

The API only writes a queued ``model_pull`` row and the audit that says who asked. It never
downloads, never fetches metadata and never carries a token: the payload a worker claims is
catalogue data plus a relative target. A second job on a busy host or an installed variant is a
409, an unknown catalogue id or variant is a 422, a member is a 403 and the flag off is a 404.
"""
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import WORKER_TOKEN
from app.db import SessionLocal
from app.main import app
from app.models import Job, Workspace, WorkspaceFlag
from app.services import flags, host_inventory, inference_models
from conftest import login, login_as

WS = "labeldesk-demo"
FLAG = "task_inference"
BASE = f"/api/ws/{WS}/inference"
DOWNLOAD = f"{BASE}/models/download"
HOST = "t1011-host"
MODEL = "qwen2.5-vl-7b"
VARIANT = "bf16"

CREATED: list[str] = []          # job ids this module made
FOREIGN: list[str] = []          # workspace ids this module made


def _inventory(models: list[dict] | None = None) -> dict:
    return {"os": "Linux", "arch": "x86_64",
            "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}],
            "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
            "hf_token": True, "models": models or [], "engines": []}


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _record(models: list[dict] | None = None) -> None:
    with SessionLocal() as db:
        host_inventory.record(db, HOST, HOST, _inventory(models))


def _job(jid: str) -> Job:
    with SessionLocal() as db:
        return db.get(Job, jid)


def _body(**over) -> dict:
    return {"host": HOST, "id": MODEL, "variant": VARIANT, "confirm": True, **over}


@pytest.fixture(scope="module")
def c():
    client = TestClient(app)
    client.headers.update(login(client))
    yield client


@pytest.fixture(autouse=True)
def _on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, True)
        db.commit()
    _record()
    yield


@pytest.fixture(autouse=True)
def _clean():
    yield
    with SessionLocal() as db:
        for jid in CREATED:
            row = db.get(Job, jid)
            if row is not None:
                db.delete(row)
        for wid in FOREIGN:
            row = db.get(Workspace, wid)
            if row is not None:
                db.delete(row)
        db.query(host_inventory.Worker).filter(host_inventory.Worker.id == HOST).delete()
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == FLAG))
        db.commit()
    CREATED.clear()
    FOREIGN.clear()


def _download(c: TestClient, **over):
    r = c.post(DOWNLOAD, json=_body(**over))
    if r.status_code == 200:
        CREATED.append(r.json()["job"]["id"])
    return r


def test_download_requires_confirm_and_no_duplicate(c: TestClient):
    assert _download(c, confirm=False).status_code == 400

    first = _download(c)
    assert first.status_code == 200, first.text
    assert first.json()["job"]["kind"] == "model_pull"

    # The queued row is the busy host: another download waits for it.
    busy = _download(c)
    assert busy.status_code == 409
    assert busy.json()["detail"]["job_id"] == first.json()["job"]["id"]

    # A finished job leaves only the installed variant to refuse the second download.
    with SessionLocal() as db:
        row = db.get(Job, first.json()["job"]["id"])
        row.status, row.finished = "done", time.time()
        db.commit()
    _record([{"id": MODEL, "variant": VARIANT, "bytes": 1000}])
    installed = _download(c)
    assert installed.status_code == 409

    # An id or a variant the catalogue does not list is invalid input, not a missing page.
    assert _download(c, id="not-a-model").status_code == 422
    assert _download(c, variant="not-a-variant").status_code == 422


def test_download_payload_carries_catalogue_data_only(c: TestClient):
    created = _download(c)
    assert created.status_code == 200, created.text
    jid = created.json()["job"]["id"]
    row = inference_models.model(MODEL)
    variant = inference_models.variant(row, VARIANT)

    with SessionLocal() as db:
        job = db.get(Job, jid)
        # The row the API stores carries ids only; no repo, no files, no token.
        assert job.params == {"host": HOST, "action": "download", "model": MODEL,
                              "variant": VARIANT}
        assert "hf_" not in json.dumps(job.params)

    # A worker that advertises another kind, or sits on another host, does not get the job.
    claim = TestClient(app)
    claim.headers.update({"X-Worker-Token": WORKER_TOKEN})
    wrong_kind = claim.post("/api/worker/claim", json={
        "name": HOST, "kinds": ["train"], "inventory": _inventory()})
    assert wrong_kind.status_code == 200 and wrong_kind.json()["job"] is None
    wrong_host = claim.post("/api/worker/claim", json={
        "name": "some-other-host", "kinds": ["model_pull"], "inventory": _inventory()})
    assert wrong_host.json()["job"] is None

    claimed = claim.post("/api/worker/claim", json={
        "name": HOST, "kinds": ["model_pull"], "inventory": _inventory()})
    assert claimed.status_code == 200, claimed.text
    payload = claimed.json()["job"]["payload"]

    assert claimed.json()["job"]["id"] == jid
    assert payload["host"] == HOST and payload["action"] == "download"
    assert payload["repo"] == variant["repo"] and payload["revision"] == variant["revision"]
    assert payload["target"] == f"{MODEL}/{VARIANT}"
    assert payload["total_bytes"] == variant["bytes"] == sum(f["bytes"] for f in payload["files"])
    assert payload["files"] == [dict(file) for file in variant["files"]]
    assert all(set(file) == {"path", "bytes", "sha256"} for file in payload["files"])
    text = json.dumps(payload)
    assert "http://" not in text and "https://" not in text
    assert "hf_" not in text and "HF_TOKEN" not in text


def test_remove_unknown_model_is_404(c: TestClient):
    missing = c.delete(f"{BASE}/models/{MODEL}", params={"host": HOST, "variant": VARIANT,
                                                         "confirm": "true"})
    assert missing.status_code == 404
    assert c.delete(f"{BASE}/models/{MODEL}", params={"host": HOST, "variant": VARIANT}).status_code == 404


def test_remove_requires_confirm_and_queues_a_removal(c: TestClient):
    _record([{"id": MODEL, "variant": VARIANT, "bytes": 1000}])
    url = f"{BASE}/models/{MODEL}"
    assert c.delete(url, params={"host": HOST, "variant": VARIANT}).status_code == 400

    queued = c.delete(url, params={"host": HOST, "variant": VARIANT, "confirm": "true"})
    assert queued.status_code == 200, queued.text
    jid = queued.json()["job"]["id"]
    CREATED.append(jid)
    job = _job(jid)
    assert job.kind == "model_pull"
    assert job.params["action"] == "remove"
    assert job.params["host"] == HOST


def test_member_is_403_and_flag_off_is_404(c: TestClient):
    member = TestClient(app)
    member.headers.update(login_as(member, "labeler@labeldesk.dev"))
    assert member.post(DOWNLOAD, json=_body()).status_code == 403
    assert member.delete(f"{BASE}/models/{MODEL}", params={
        "host": HOST, "variant": VARIANT, "confirm": "true"}).status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, False)
        db.commit()
    assert c.post(DOWNLOAD, json=_body()).status_code == 404
    assert c.delete(f"{BASE}/models/{MODEL}", params={
        "host": HOST, "variant": VARIANT, "confirm": "true"}).status_code == 404


def test_another_workspace_is_404(c: TestClient, monkeypatch):
    with SessionLocal() as db:
        owner_id = db.get(Workspace, _ws_id()).owner_id
        other = Workspace(slug=f"t1011-{uuid.uuid4().hex[:8]}", name="Other", owner_id=owner_id)
        db.add(other)
        db.commit()
        FOREIGN.append(other.id)
        monkeypatch.setenv("LD_INFERENCE_WORKSPACE", other.slug)
        assert c.post(DOWNLOAD, json=_body()).status_code == 404
        assert c.delete(f"{BASE}/models/{MODEL}", params={
            "host": HOST, "variant": VARIANT, "confirm": "true"}).status_code == 404
