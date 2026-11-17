"""Inference catalogue (T-1002): exact engine pins, sourced GPU presets, admin-only read.

The catalogue is the allowlist that keeps a client string out of an install command, so every
row is asserted here: a floating pin, an unpinned container, a version with no source or an
engine with no vendor numbers fails the suite before the API ever serves it.
"""
import os
import re
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-inference-catalog-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import inference_catalog as cat
from conftest import login as shared_login

WS = "labeldesk-demo"
FLAG = "task_inference"
CATALOG = f"/api/ws/{WS}/inference/catalog"
PW = "demo1234"
STARTS_WITH_A_DIGIT = re.compile(r"^[0-9]")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def login(email: str) -> TestClient:
    c = TestClient(app)
    c.headers.update(shared_login(c, email, PW))
    return c


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture(scope="module")
def admin():
    yield login("demo@labeldesk.dev")


@pytest.fixture(scope="module")
def labeler():
    yield login("labeler@labeldesk.dev")


@pytest.fixture(scope="module", autouse=True)
def _flag_off_after():
    yield
    # Leave the workspace as the module found it: the next module must not inherit the flag.
    admin = login("demo@labeldesk.dev")
    admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False})


def test_every_engine_has_an_exact_pin_and_a_source():
    assert cat.ENGINES, "the catalogue is empty"
    for row in cat.ENGINES:
        assert row["version"], row["id"]
        assert row["version"] != "latest", row["id"]
        assert "latest" not in row["version"].lower(), row["id"]
        assert STARTS_WITH_A_DIGIT.match(row["version"]), row["id"]
        assert row["source_url"].startswith("https://"), row["id"]
        assert STARTS_WITH_A_DIGIT.match(row["checked_on"]), row["id"]
        assert row["summary"].strip(), row["id"]
        assert row["runtimes"], row["id"]
    assert cat.validate() is None


def test_every_container_is_pinned_by_digest():
    for row in cat.ENGINES:
        container = row["container"]
        if container is None:
            continue
        assert DIGEST.search(container), row["id"]
        assert ":latest" not in container, row["id"]


def test_install_spec_refuses_unknown_engines_and_runtimes():
    with pytest.raises(KeyError):
        cat.engine("not-an-engine")
    with pytest.raises(KeyError):
        cat.install_spec("vllm", "binary")
    with pytest.raises(KeyError):
        cat.gpu("not-a-gpu")
    # A known pair is built from the pin alone, never from a caller-supplied string.
    assert cat.install_spec("vllm", "uv")["argv"][-1] == cat.engine("vllm")["package"]
    assert cat.install_spec("ollama", "docker")["argv"][-1] == cat.engine("ollama")["container"]


def test_every_gpu_has_vendor_numbers_and_a_source():
    rows = cat.GPUS
    assert len(rows) == 11
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows:
        if row["id"] == "cpu":
            assert row["vram_gb"] == 0 and row["bw_gbs"] == 0 and row["fp16_tflops"] == 0
            continue
        assert row["vram_gb"] > 0, row["id"]
        assert row["bw_gbs"] > 0, row["id"]
        assert row["fp16_tflops"] > 0, row["id"]
        assert row["source_url"].startswith("https://"), row["id"]
    for row in rows:
        cat.gpu(row["id"]) is row


def test_public_catalog_hides_the_install_argv_and_digest():
    import json

    body = json.dumps(cat.public_catalog())
    assert "argv" not in body
    assert "package" not in body
    assert "sha256:" not in body
    public = cat.public_catalog()
    assert [row["id"] for row in public["engines"]] == [row["id"] for row in cat.ENGINES]
    assert public["sources"] and all(url.startswith("https://") for url in public["sources"])
    for row in cat.ENGINES:
        assert row["source_url"] in public["sources"]


def test_catalog_is_admin_only_and_flag_gated(admin, labeler):
    assert admin.get(CATALOG).status_code == 404          # flag off by default
    assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": True}).status_code == 200
    r = admin.get(CATALOG)
    assert r.status_code == 200
    body = r.json()
    assert len(body["engines"]) == len(cat.ENGINES)
    assert len(body["gpus"]) == 11
    assert labeler.get(CATALOG).status_code == 403
    assert admin.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": False}).status_code == 200
    assert admin.get(CATALOG).status_code == 404
