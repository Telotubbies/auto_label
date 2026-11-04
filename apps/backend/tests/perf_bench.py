"""Load benchmark: seeds N synthetic images into a fresh DB and times the hot endpoints.

    cd apps/backend && python tests/perf_bench.py 20000
Rows are inserted directly (no image files) — this measures API/DB cost, not disk I/O.
"""
import os
import random
import statistics
import sys
import tempfile
import time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
_PERF_TMP = tempfile.TemporaryDirectory(prefix="ld-perf-", dir=os.environ.get("LD_TEST_TMP") or None)
os.environ["LD_DATA_DIR"] = _PERF_TMP.name
os.environ["LD_EMBEDDED_WORKER"] = "0"
os.environ["LD_SEED_IMAGES"] = os.environ["LD_DATA_DIR"]      # no sample images
os.environ["LD_RATE_LIMIT"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Batch, Image, LabelClass, Project  # noqa: E402
try:
    from app.models import set_annotations  # noqa: E402
except ImportError:                          # pre-optimisation schema (baseline runs)
    def set_annotations(db, img, anns):
        img.annotations, img.n_annotations = anns, len(anns)

with TestClient(app) as c:
    tok = c.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    with SessionLocal() as db:
        p = db.query(Project).first()
        cls = [x.id for x in db.query(LabelClass).filter_by(project_id=p.id)]
        rng = random.Random(1)
        for b in range(N // 1000):
            batch = Batch(project_id=p.id, name=f"batch {b}")
            db.add(batch); db.flush()
            for i in range(1000):
                img = Image(project_id=p.id, batch_id=batch.id, name=f"img_{b}_{i}.jpg", sha256=f"{b}-{i}", width=1280, height=720,
                            path="x.jpg", thumb="x.jpg", split=rng.choice(["train", "train", "valid", "test"]),
                            status=rng.choice(["unassigned", "annotating", "review", "done"]), tags=["site-a"] if i % 7 == 0 else [])
                db.add(img)
                anns = [{"id": f"a{j}", "classId": rng.choice(cls), "shape": {"kind": "bbox", "x": rng.random() * .8, "y": rng.random() * .8, "w": .1, "h": .1}}
                        for j in range(rng.randint(0, 12))]
                set_annotations(db, img, anns)
            db.commit()
    base = "/api/ws/labeldesk-demo/projects/ppe-detection"
    cases = {
        "projects list": "/api/ws/labeldesk-demo/projects",
        "project detail": base,
        "classes": base + "/classes",
        "images page 1 (200)": base + "/images?limit=200",
        "images filter class": base + f"/images?limit=200&class_id={cls[1]}",
        "images filter tag": base + "/images?limit=200&tag=site-a",
        "images deep page": base + f"/images?limit=200&offset={N - 400}",
        "board": base + "/board",
        "analytics": base + "/analytics",
    }
    print(f"{N} images\n{'endpoint':28} {'median ms':>10} {'p95 ms':>8} {'KB':>7}")
    for name, url in cases.items():
        ts, size = [], 0
        for _ in range(7):
            t = time.perf_counter(); r = c.get(url); ts.append((time.perf_counter() - t) * 1000)
            assert r.status_code == 200, (url, r.text[:200]); size = len(r.content)
        ts.sort()
        print(f"{name:28} {statistics.median(ts):10.1f} {ts[-1]:8.1f} {size / 1024:7.1f}")
