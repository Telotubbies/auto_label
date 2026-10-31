"""Versioning v2: stratified split, pHash grouping, recipe.json, version_hash, export cache."""
import json
import os
import tempfile
import time
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app.config import DATA_DIR
from app.db import SessionLocal
from app.main import app
from app.models import Version
from app.services import versioning
from app.services.versioning import phash_groups, stratified_split

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"
RATIOS = {"train": 70, "valid": 20, "test": 10}


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        tok = client.post("/api/auth/login", json={"email": "demo@labeldesk.dev", "password": "demo1234"}).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        pending = client.get(f"{BASE}/images", params={"status": "review"}).json()["items"]
        if pending:                                  # another module may already have approved the seed batch
            img = pending[0]
            cls = client.get(f"{BASE}/classes").json()[0]
            ann = [{"id": "x1", "classId": cls["id"], "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]
            client.put(f"/api/images/{img['id']}/annotations", json={"annotations": ann})
            client.post(f"/api/images/{img['id']}/review", json={"approved": True})
            client.post(f"{BASE}/board/move", json={"batch_id": img["batchId"], "from_status": "review", "to_status": "done"})
        yield client


def make_version(c, settings):
    v = c.post(f"{BASE}/versions", json={"settings": settings}).json()
    t = time.time()
    while time.time() - t < 300:
        j = c.get(f"{BASE}/jobs/{v['job']['id']}").json()
        if j["status"] in ("done", "failed", "cancelled"):
            assert j["status"] == "done", j
            break
        time.sleep(0.5)
    return c.get(f"{BASE}/versions/{v['id']}").json()


def manifest(v):
    return json.loads((DATA_DIR / "versions" / v["id"] / "manifest.json").read_text())


def test_rare_class_lands_in_valid():
    items = [(f"i{k}", {0}) for k in range(40)] + [(f"r{k}", {1}) for k in range(1, 6)]
    s = stratified_split(items, RATIOS, seed=1)
    assert any(s[i] == "valid" for i in ("r1", "r2", "r3", "r4", "r5"))


def test_single_image_class_does_not_crash():
    s = stratified_split([("a", {0}), ("b", {1})], RATIOS, seed=1)
    assert set(s) == {"a", "b"}


def test_empty_and_unlabeled_inputs_do_not_crash():
    assert stratified_split([], RATIOS, seed=1) == {}
    s = stratified_split([("a", set()), ("b", set()), ("c", {0})], RATIOS, seed=1)
    assert set(s) == {"a", "b", "c"}


def test_split_is_deterministic_and_group_atomic():
    items = [(f"i{k}", {k % 3}) for k in range(30)]
    groups = {f"i{k}": f"g{k // 3}" for k in range(30)}
    a = stratified_split(items, RATIOS, seed=7, groups=groups)
    assert a == stratified_split(items, RATIOS, seed=7, groups=groups)
    for g in set(groups.values()):
        assert len({a[i] for i in groups if groups[i] == g}) == 1


def _save(name, arr):
    rel = f"test_phash/{name}.png"
    (DATA_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    PImage.fromarray(arr).save(DATA_DIR / rel)
    return SimpleNamespace(id=name, path=rel)


def test_near_duplicates_share_a_split():
    rng = np.random.default_rng(0)
    blk = np.ones((8, 8, 1), dtype=np.uint8)
    base = np.kron(rng.integers(0, 255, (8, 8, 3), dtype=np.uint8), blk)
    other = np.kron(rng.integers(0, 255, (8, 8, 3), dtype=np.uint8), blk)
    rows = [_save("d1", base), _save("d2", base.copy()), _save("d3", np.roll(base, 1, axis=1)), _save("x", other)]
    g = phash_groups(rows)
    assert g["d1"] == g["d2"] == g["d3"] != g["x"]
    items = [(r.id, {0}) for r in rows] + [(f"f{k}", {0}) for k in range(30)]
    s = stratified_split(items, RATIOS, seed=3, groups=g)
    assert s["d1"] == s["d2"] == s["d3"]


def test_version_writes_recipe_and_hash(c):
    pre = {"resize": {"width": 320, "height": 320, "mode": "fit"}, "grayscale": True, "contrast": "adaptive"}
    v = make_version(c, {"split": RATIOS, "preprocessing": pre, "augmentation": {}})
    assert json.loads((DATA_DIR / "versions" / v["id"] / "recipe.json").read_text()) == pre
    assert len(manifest(v)["version_hash"]) == 64


def test_same_inputs_same_hash(c):
    s = {"split": RATIOS, "seed": 5, "preprocessing": {}, "augmentation": {}}
    h = [manifest(make_version(c, s))["version_hash"] for _ in range(2)]
    assert h[0] == h[1]
    assert manifest(make_version(c, {**s, "seed": 6}))["version_hash"] != h[0]


def test_cached_export_built_once(c):
    v = make_version(c, {"split": RATIOS, "preprocessing": {}, "augmentation": {}})
    with SessionLocal() as db:
        ver = db.get(Version, v["id"])
        p1 = versioning.cached_export(ver, "yolo")
        assert p1 == versioning.version_dir(ver) / "exports" / "yolo"
        assert (p1 / "data.yaml").exists()
        m = (p1 / "data.yaml").stat().st_mtime_ns
        assert versioning.cached_export(ver, "yolo") == p1
        assert (p1 / "data.yaml").stat().st_mtime_ns == m


def _class_id():
    from sqlalchemy import select
    from app.models import LabelClass
    with SessionLocal() as db:
        return db.scalars(select(LabelClass)).first().id


def _add_image(iid, rel, split, ann_cls):
    from sqlalchemy import select
    from app.models import Image, Project
    with SessionLocal() as db:
        pid = db.scalars(select(Project.id).where(Project.slug == "ppe-detection")).first()   # not the "other" test project
        db.add(Image(id=iid, project_id=pid, name=f"{iid}.png", sha256=iid * 2, width=64, height=64, path=rel,
                     thumb=rel, split=split, status="done",
                     annotations=[{"id": "a", "classId": ann_cls,
                                   "shape": {"kind": "bbox", "x": .1, "y": .1, "w": .3, "h": .3}}]))
        db.commit()


def test_keep_path_moves_near_duplicate_out_of_eval(c):
    rng = np.random.default_rng(42)
    arr = np.kron(rng.integers(0, 255, (8, 8, 3), dtype=np.uint8), np.ones((8, 8, 1), dtype=np.uint8))
    a, b = _save("leak_a", arr), _save("leak_b", arr.copy())
    cid = _class_id()
    base = make_version(c, {"preprocessing": {}, "augmentation": {}})["stats"]["leakage_moved"]   # seeded flat images
    _add_image("leakaaaa", a.path, "train", cid)
    _add_image("leakbbbb", b.path, "test", cid)
    v = make_version(c, {"preprocessing": {}, "augmentation": {}})
    m = manifest(v)
    assert {it["split"] for it in m["items"] if it["source"] in ("leakaaaa", "leakbbbb")} == {"train"}
    assert v["stats"]["leakage_moved"] - base == 1


def test_hash_changes_on_relabel_and_class_rename(c):
    from sqlalchemy import select
    from app.models import Image, LabelClass
    s = {"split": RATIOS, "seed": 5, "preprocessing": {}, "augmentation": {}}
    m0 = manifest(make_version(c, s))
    assert m0["config"] == s and m0["sources"]
    with SessionLocal() as db:
        im = db.get(Image, "leakaaaa")
        im.annotations = [{**im.annotations[0], "shape": {"kind": "bbox", "x": .5, "y": .5, "w": .2, "h": .2}}]
        db.commit()
    h1 = manifest(make_version(c, s))["version_hash"]
    assert h1 != m0["version_hash"]
    with SessionLocal() as db:
        lc = db.scalars(select(LabelClass)).first()
        lc.name = lc.name + "_renamed"
        db.commit()
    assert manifest(make_version(c, s))["version_hash"] != h1


def test_cached_export_concurrent_builders(tmp_path, monkeypatch):
    import threading
    from app.services import exporters
    calls = []

    def fake_build(fmt, vdir, out):
        calls.append(1)
        time.sleep(0.3)
        out.mkdir(parents=True)
        (out / "done").write_text("x")
        return out
    monkeypatch.setattr(exporters, "build_dir", fake_build)
    res = []
    ts = [threading.Thread(target=lambda: res.append(exporters.cached_export(tmp_path, "yolo"))) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1 and all((p / "done").exists() for p in res)
    assert [p.name for p in (tmp_path / "exports").iterdir()] == ["yolo"]
