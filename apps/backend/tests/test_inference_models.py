"""Model catalogue (T-1010): pins, licence, gating, the repo-id boundary and a download plan.

The catalogue is the only place a model id, repo or file path may come from, so every row is
asserted here: a floating revision, a missing licence URL, a pickle weight or a byte count that
does not add up fails the suite before the API can offer a download. The fit verdict and the disk
check are the T-1004 estimator and one 20% margin, never a second implementation.
"""
import json
import os
import re
import tempfile
from datetime import date

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-inference-models-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Workspace, WorkspaceFlag, Worker
from app.services import flags, host_inventory, inference_catalog, inference_models
from conftest import login, login_as

WS = "labeldesk-demo"
FLAG = "task_inference"
MODELS_URL = f"/api/ws/{WS}/inference/models"
PLAN_URL = f"/api/ws/{WS}/inference/models/plan"
HOST = "t1010-host"
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIB = 1024 ** 3


def _inventory(**over) -> dict:
    inv = {"os": "Linux", "arch": "x86_64", "gpus": [{"name": "NVIDIA GeForce RTX 4090",
                                                      "vram_mb": 24564}],
           "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
           "hf_token": True, "models": [], "engines": []}
    inv.update(over)
    return inv


def _host_row(**over) -> dict:
    """A host as the route sees it: the id, online flag and the inventory it reported."""
    return {"id": HOST, "host": HOST, "online": True, "inventory": _inventory(**over)}


def _row(model_id: str) -> dict:
    return next(row for row in inference_models.MODELS if row["id"] == model_id)


def _ws_id() -> str:
    with SessionLocal() as db:
        return db.scalar(select(Workspace.id).where(Workspace.slug == WS))


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture(autouse=True)
def _flag_on():
    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, True)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _clean_host():
    with SessionLocal() as db:
        db.query(Worker).filter(Worker.id == HOST).delete()
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == FLAG,
                                                            WorkspaceFlag.workspace_id == _ws_id()))
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(Worker).filter(Worker.id == HOST).delete()
        db.execute(WorkspaceFlag.__table__.delete().where(WorkspaceFlag.key == FLAG,
                                                            WorkspaceFlag.workspace_id == _ws_id()))
        db.commit()


@pytest.fixture()
def host() -> str:
    with SessionLocal() as db:
        host_inventory.record(db, HOST, HOST, _inventory())
    yield HOST


@pytest.fixture()
def admin() -> TestClient:
    c = TestClient(app)
    c.headers.update(login(c, "demo@labeldesk.dev"))
    return c


@pytest.fixture()
def labeler() -> TestClient:
    c = TestClient(app)
    c.headers.update(login_as(c, "labeler@labeldesk.dev"))
    return c


# ---------- the rows -----------------------------------------------------------

def test_every_model_has_a_licence_url_a_pin_and_a_checked_date():
    assert len(inference_models.MODELS) == 5
    engines = {row["id"] for row in inference_catalog.ENGINES}
    for row in inference_models.MODELS:
        assert row["name"].strip() and row["family"].strip(), row["id"]
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*", row["repo"]), row["id"]
        assert COMMIT.match(row["revision"]), row["id"]
        assert row["revision"] != "main", row["id"]
        assert date.fromisoformat(row["checked_on"]), row["id"]
        assert row["source_url"].startswith("https://"), row["id"]
        licence = row["licence"]
        assert licence["name"].strip() and licence["url"].startswith("https://"), row["id"]
        assert isinstance(licence["gated"], bool) and isinstance(licence["non_commercial"], bool)
        assert row["engine"] and set(row["engine"]) <= engines, row["id"]
        assert 0 < row["params_b"] <= 2000, row["id"]
        assert row["layers"] > 0 and row["kv_heads"] > 0 and row["head_dim"] > 0, row["id"]
        assert row["context_max"] >= 2048, row["id"]
        assert row["variants"], row["id"]
        for variant in row["variants"]:
            assert variant["engine"] in engines, (row["id"], variant["id"])
            assert COMMIT.match(variant["revision"]), (row["id"], variant["id"])
    assert inference_models.validate() is None


def test_every_variant_lists_files_and_bytes():
    for row in inference_models.MODELS:
        for variant in row["variants"]:
            files = variant["files"]
            assert files, (row["id"], variant["id"])
            assert all(file["bytes"] > 0 for file in files), (row["id"], variant["id"])
            assert variant["bytes"] == sum(file["bytes"] for file in files), (row["id"], variant["id"])
            for file in files:
                path = file["path"]
                assert not path.startswith("/") and ".." not in path.split("/"), path
                assert file.get("sha256") is None or SHA256.match(file["sha256"]), path


def test_licences_are_honest():
    by_id = {row["id"]: row for row in inference_models.MODELS}
    assert by_id["llama-3.1-8b"]["licence"]["gated"] is True
    assert by_id["gemma-3-27b"]["licence"]["gated"] is True
    for row in inference_models.MODELS:
        licence = row["licence"]
        if licence["gated"]:
            # A gated weight set is never republished in this catalogue as Apache-2.0.
            assert licence["name"] != "Apache-2.0", row["id"]
        if "AGPL" in licence["name"].upper():
            # Ultralytics-style AGPL must be flagged, not silently carried.
            assert licence["non_commercial"] is True, row["id"]


def test_ollama_tags_sit_next_to_the_hugging_face_rows():
    """Owner decision PLAN §12.3: the catalogue names the Ollama tag for each model."""
    assert all(row["ollama_tag"] and ":" in row["ollama_tag"]
               for row in inference_models.MODELS)


# ---------- the repo-id boundary -----------------------------------------------

def test_repo_ids_reject_traversal_and_urls():
    for bad in ("../x", "http://evil/x", "a/b/c", "", "owner/name/../x", "-bad/name",
                "owner/na me", "owner/name?x=1"):
        with pytest.raises(inference_models.InvalidRepo):
            inference_models.validate_repo(bad)
    assert inference_models.validate_repo("Qwen/Qwen2.5-VL-7B-Instruct") == \
        "Qwen/Qwen2.5-VL-7B-Instruct"


def test_a_bad_repo_reaching_the_route_is_400(admin, host, monkeypatch):
    row = _row("qwen2.5-vl-7b")
    variant = row["variants"][0]
    rows = list(inference_models.MODELS)
    rows[0] = {**row, "variants": [{**variant, "repo": "../x"}]}
    monkeypatch.setattr(inference_models, "MODELS", rows)
    r = admin.post(PLAN_URL, json={"host": host, "id": row["id"], "variant": variant["id"]})
    assert r.status_code == 400, r.text


def test_pickle_files_are_refused(monkeypatch):
    row = _row("qwen2.5-7b-gguf")
    variant = row["variants"][0]
    files = [*variant["files"], {"path": "pytorch_model.bin", "bytes": 1024, "sha256": None}]
    rows = list(inference_models.MODELS)
    rows[4] = {**row, "variants": [{**variant, "files": files}]}
    monkeypatch.setattr(inference_models, "MODELS", rows)
    plan = inference_models.plan(_host_row(), row["id"], variant["id"])
    assert any("pickle" in reason.lower() or ".bin" in reason for reason in plan["blocked"]), plan


# ---------- gating, fit and disk -----------------------------------------------

def test_gated_model_without_a_token_is_blocked():
    plan = inference_models.plan(_host_row(hf_token=False), "llama-3.1-8b", "bf16")
    assert plan["token_present"] is False
    assert plan["gate"]["gated"] is True
    assert any("HF_TOKEN" in reason or "Hugging Face token" in reason
               for reason in plan["blocked"]), plan

    with_token = inference_models.plan(_host_row(hf_token=True), "llama-3.1-8b", "bf16")
    assert with_token["token_present"] is True
    assert not any("HF_TOKEN" in reason for reason in with_token["blocked"]), with_token


def test_fit_uses_the_estimator():
    bf16 = inference_models.plan(_host_row(), "gemma-3-27b", "bf16")
    assert bf16["fit"]["fits"] is False
    assert "short" in bf16["fit"]["verdict"]
    assert bf16["fit"]["shortfall_gb"] > 0
    assert any("does not fit" in reason.lower() for reason in bf16["blocked"]), bf16

    q4 = inference_models.plan(_host_row(), "gemma-3-27b", "q4_0")
    assert q4["fit"]["fits"] is True, q4


def test_disk_check_uses_a_20_percent_margin():
    needed = 9.4 * GIB
    assert inference_models.disk_block(needed, 10.0) is not None
    assert "9.4 GB" in inference_models.disk_block(needed, 10.0)
    assert inference_models.disk_block(needed, 12.0) is None
    assert inference_models.disk_block(None, 12.0) is None


def test_a_second_model_is_a_warning_naming_the_installed_one():
    host = _host_row(models=[{"id": "qwen2.5-7b-gguf", "variant": "q4_k_m", "bytes": 1000}])
    plan = inference_models.plan(host, "gemma-3-27b", "q4_0")
    assert any("qwen2.5-7b-gguf" in warning for warning in plan["warnings"]), plan


def test_a_non_commercial_licence_reaches_the_row_and_the_plan(monkeypatch):
    """No shipped row is non-commercial today; the badge path must still carry a future one."""
    row = _row("qwen2.5-7b-gguf")
    rows = list(inference_models.MODELS)
    rows[4] = {**row, "licence": {**row["licence"], "name": "Non-commercial research licence",
                                  "non_commercial": True}}
    monkeypatch.setattr(inference_models, "MODELS", rows)
    assert inference_models.validate() is None
    plan = inference_models.plan(_host_row(), row["id"], "q4_k_m")
    assert plan["gate"]["non_commercial"] is True
    assert plan["gate"]["licence"] == "Non-commercial research licence"
    listed = inference_models.public_models(_host_row())["models"][4]
    assert listed["licence"]["non_commercial"] is True


# ---------- the public rows and the plan ---------------------------------------

def test_public_models_hide_files():
    body = json.dumps(inference_models.public_models(_host_row()))
    assert '"files"' not in body
    assert ".safetensors" not in body and ".gguf" not in body
    rows = inference_models.public_models(_host_row())["models"]
    assert len(rows) == 5
    assert all(row["variants"] for row in rows)


def test_plan_names_the_file_list_the_total_and_the_gate():
    plan = inference_models.plan(_host_row(), "gemma-3-27b", "q4_0")
    assert set(plan) >= {"plan_id", "model", "variant", "files", "total_bytes", "disk_free_gb",
                         "disk_after_gb", "gate", "token_present", "blocked", "warnings", "fit"}
    assert plan["model"] == "gemma-3-27b" and plan["variant"] == "q4_0"
    assert plan["total_bytes"] == sum(file["bytes"] for file in plan["files"])
    assert all({"path", "bytes", "sha256"} <= set(file) for file in plan["files"])
    assert plan["gate"]["non_commercial"] is False
    assert plan["disk_after_gb"] == pytest.approx(
        round(812.5 - plan["total_bytes"] / GIB, 1), abs=0.11)


def test_installed_variant_is_marked(host):
    row = _row("qwen2.5-7b-gguf")
    variant = row["variants"][0]
    with SessionLocal() as db:
        host_inventory.record(db, HOST, HOST, _inventory(
            models=[{"id": row["id"], "variant": variant["id"], "bytes": variant["bytes"]}]))
        row_now = next(h for h in host_inventory.hosts(db) if h["id"] == HOST)
    body = inference_models.public_models(row_now)
    installed = next(m for m in body["models"] if m["id"] == row["id"])
    assert installed["installed"] is True
    assert any(v["id"] == variant["id"] and v["installed"] for v in installed["variants"])


# ---------- the routes ---------------------------------------------------------

def test_list_and_plan_are_admin_only_and_flag_off_is_404(admin, labeler, host):
    assert admin.get(f"{MODELS_URL}?host={host}").status_code == 200
    assert labeler.get(f"{MODELS_URL}?host={host}").status_code == 403
    body = {"host": host, "id": "qwen2.5-7b-gguf", "variant": "q8_0"}
    assert admin.post(PLAN_URL, json=body).status_code == 200
    assert labeler.post(PLAN_URL, json=body).status_code == 403

    with SessionLocal() as db:
        flags.set_flag(db, _ws_id(), FLAG, False)
        db.commit()
    assert admin.get(f"{MODELS_URL}?host={host}").status_code == 404
    assert admin.post(PLAN_URL, json=body).status_code == 404


def test_unknown_host_model_and_variant_are_404(admin, host):
    assert admin.get(f"{MODELS_URL}?host=nope").status_code == 404
    assert admin.post(PLAN_URL, json={"host": host, "id": "nope", "variant": "bf16"}).status_code == 404
    assert admin.post(PLAN_URL, json={"host": host, "id": "qwen2.5-7b-gguf",
                                      "variant": "nope"}).status_code == 404
