"""T-1019: worker and job fixtures for the inference suite.

The hub is admin-only and flag-gated, so a test that touches it needs the flag on, a host row the
plan can see, and a job row a worker could claim. ``models_dir`` is the one writable weight path:
it is forced under the test temp root and removed when the session ends, so no test can download
into the repo or ``~/.labeldesk/models``.
"""
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Job, Worker, Workspace, WorkspaceFlag
from app.services import flags
from conftest import login

WS = "labeldesk-demo"
MODELS_DIR = Path(tempfile.gettempdir()) / "labeldesk-inference-models"
os.environ["LD_MODELS_DIR"] = str(MODELS_DIR)

INVENTORY = {
    "os": "Linux", "arch": "x86_64", "python": "3.11.9",
    "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
              "driver": "575.51", "cuda": "12.9"}],
    "cuda": "12.9", "docker": True,
    "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
    "engines": [],
}


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


def _drop(model, ids: list[str]) -> None:
    with SessionLocal() as db:
        for id_ in ids:
            row = db.get(model, id_)
            if row is not None:
                db.delete(row)
        db.commit()


@pytest.fixture(scope="session")
def models_dir():
    """The suite's models directory, under the test temp root, gone at session end."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    yield MODELS_DIR
    shutil.rmtree(MODELS_DIR, ignore_errors=True)


@pytest.fixture(scope="module")
def inference_client():
    """An admin client with ``task_inference`` on; the flag row is removed afterwards."""
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), "task_inference", True)
        db.commit()
    client = TestClient(app)
    client.headers.update(login(client))
    yield client
    with SessionLocal() as db:
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == "task_inference"))
        db.commit()


@pytest.fixture
def make_host():
    """Create a Worker row shaped like the inventory report; delete it after the test."""
    made: list[str] = []

    def make(inventory: dict | None = None, kinds=("engine_apply", "model_pull"),
             host: str | None = None) -> str:
        wid = host or f"t1019-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as db:
            db.add(Worker(id=wid, host=wid, kinds=list(kinds), started=0.0, last_seen=9e12,
                          inventory=inventory or INVENTORY))
            db.commit()
        made.append(wid)
        return wid

    yield make
    _drop(Worker, made)


@pytest.fixture
def make_job():
    """Create a Job row a worker could claim; delete it after the test."""
    made: list[str] = []

    def make(host: str, kind: str = "engine_apply", params: dict | None = None,
             result: dict | None = None, status: str = "running",
             workspace: str = WS) -> str:
        with SessionLocal() as db:
            workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == workspace))
            job = Job(workspace_id=workspace_id, project_id=None, kind=kind, status=status,
                      params={"host": host, **(params or {})}, result=result or {},
                      created=time.time())
            db.add(job)
            db.commit()
            made.append(job.id)
            return job.id

    yield make
    _drop(Job, made)
