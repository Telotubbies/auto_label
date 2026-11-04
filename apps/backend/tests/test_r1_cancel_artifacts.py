"""I22: cancellation reaches the version build, the dataset export and the engine build."""
import json
import os
import uuid
from contextlib import nullcontext
from pathlib import Path

os.environ.setdefault("LD_WORKER_TOKEN", "test-worker-token-0123456789abcdef")
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from PIL import Image as PImage
from sqlalchemy import update

from app import bootstrap, worker
from app.adapters.base import Cancelled
from app.config import DATA_DIR
from app.db import Base, SessionLocal, engine
from app.models import Image, Job, Project, TrainedModel, User, Version, Workspace
from app.services import exporters, versioning


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    bootstrap.init_db()


def _project(images: int = 0) -> dict:
    """A workspace/project plus (optionally) real JPEGs under DATA_DIR so the splitter can read them."""
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        u = User(id="u" + suffix, email=f"cx-{suffix}@x.io", name="CX", pw_hash="x")
        db.add(u); db.flush()
        ws = Workspace(id="w" + suffix, slug=f"cx-{suffix}", name="CX", owner_id=u.id)
        db.add(ws); db.flush()
        p = Project(id="p" + suffix, workspace_id=ws.id, slug=f"cxp-{suffix}", name="CX")
        db.add(p); db.flush()
        v = Version(project_id=p.id, number=1, settings={}, status="generating")
        db.add(v); db.flush()
        for i in range(images):
            rel = f"projects/{p.id}/images/{i}.jpg"
            path = DATA_DIR / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            PImage.new("RGB", (8, 8), (i, i, i)).save(path, "JPEG")
            db.add(Image(id=f"i{suffix}{i}", project_id=p.id, name=f"{i}.jpg", sha256=f"{suffix}{i}", width=8,
                         height=8, size=1, path=rel, thumb=rel, status="done", split="train"))
        db.commit()
        return {"ws": ws.id, "project": p.id, "version": v.id}


def test_version_build_stops_between_images(monkeypatch):
    """A cancelled version build must raise before it can be committed as ready."""
    ids = _project(images=3)
    seen: list[float] = []
    with SessionLocal() as db:
        v = db.get(Version, ids["version"])

        def progress(f: float) -> None:
            seen.append(f)

        def should_stop() -> bool:
            return bool(seen)                    # ask again after the first image was written

        with pytest.raises(Cancelled):
            versioning.generate(db, v, progress=progress, should_stop=should_stop)
        assert seen, "generate never reported progress"
        assert not (versioning.version_dir(v) / "manifest.json").exists()


def test_run_version_marks_the_version_cancelled_not_ready(monkeypatch):
    ids = _project(images=2)
    with SessionLocal() as db:
        j = Job(workspace_id=ids["ws"], project_id=ids["project"], kind="version", status="running",
                params={"version_id": ids["version"]})
        db.add(j); db.commit()
        jid = j.id
        job = db.get(Job, jid)
        db.expunge(job)
    from app import jobs
    monkeypatch.setattr(jobs, "is_cancelled", lambda _jid: False)     # the handler itself starts
    monkeypatch.setattr(worker, "_cancelled", lambda _jid: True)      # then the user cancels

    with pytest.raises(Cancelled):
        worker.run_version(job)
    with SessionLocal() as db:
        v = db.get(Version, ids["version"])
        assert v.status != "ready"
        assert not (DATA_DIR / "versions" / v.id / "manifest.json").exists()


def test_export_build_stops_between_items():
    """A cancelled export must not finish writing the dataset or its README."""
    vdir = DATA_DIR / "versions" / f"cx{uuid.uuid4().hex[:8]}"
    for name in ("a", "b", "c"):
        (vdir / "train").mkdir(parents=True, exist_ok=True)
        PImage.new("RGB", (8, 8), (1, 2, 3)).save(vdir / "train" / f"{name}.jpg", "JPEG")
    (vdir / "manifest.json").write_text(json.dumps({
        "classes": ["person"], "type": "object-detection", "skeletons": [],
        "items": [{"file": f"train/{n}.jpg", "split": "train", "width": 8, "height": 8, "anns": []}
                  for n in ("a", "b", "c")]}))
    out = DATA_DIR / "exports" / "cxtest" / "yolo"
    calls = {"n": 0}

    def should_stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    with pytest.raises(Cancelled):
        exporters.build_dir("yolo", vdir, out, should_stop=should_stop)
    assert not (out / "README.labeldesk.txt").exists()
    assert len(list(out.rglob("*.jpg"))) < 3


def test_cancelled_engine_build_writes_no_reference(monkeypatch):
    ids = _project()
    with SessionLocal() as db:
        rel = f"models/{uuid.uuid4().hex[:8]}/best.pt"
        src = DATA_DIR / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"weights")
        tm = TrainedModel(workspace_id=ids["ws"], project_id=ids["project"], version_id=ids["version"],
                          name="engine", arch="yolo26n", variant="yolo26n", task="detect", status="ready",
                          family="ultralytics", classes=[], weights=rel, runtime_refs={})
        db.add(tm); db.flush()
        j = Job(workspace_id=ids["ws"], project_id=ids["project"], kind="export_engine", status="running",
                params={"model_id": tm.id})
        db.add(j); db.commit()
        jid, mid = j.id, tm.id

    class _Adapter:
        def export(self, _src, _fmt, half=True, dest=None):
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"engine")                  # the build finished before the user cancelled
            with SessionLocal() as db:
                db.execute(update(Job).where(Job.id == jid).values(status="cancelling"))
                db.commit()
            return dest

    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": _Adapter()})
    monkeypatch.setattr(worker.scheduler, "exclusive", lambda *_a, **_k: nullcontext())
    with SessionLocal() as db:
        job = db.get(Job, jid)
        db.expunge(job)

    with pytest.raises(Cancelled):
        worker.run_export_engine(job)
    with SessionLocal() as db:
        tm = db.get(TrainedModel, mid)
        assert "engine" not in (tm.runtime_refs or {})
    assert not (DATA_DIR / "engines" / f"{mid}.engine").exists()
