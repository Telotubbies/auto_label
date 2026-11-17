"""VRAM and throughput estimator (T-1004): the PLAN §2.3 worked example and its edges.

The estimate is pure arithmetic over a validated body, so this module pins the numbers rather
than a shape: the worked example from the plan, tensor parallel dividing only weights and KV,
the quantisation and context/batch directions, and every range that must answer 422.
"""
import os
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-inference-estimate-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import login as shared_login

WS = "labeldesk-demo"
FLAG = "task_inference"
URL = f"/api/ws/{WS}/inference/estimate"
FLAG_URL = f"/api/ws/{WS}/flags/{FLAG}"
PW = "demo1234"
SOURCES = {
    "https://blog.eleuther.ai/transformer-math/",
    "https://kipp.ly/transformer-inference-arithmetic/",
    "https://docs.vllm.ai/en/latest/configuration/conserving_memory.html",
}


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
def member():
    yield login("labeler@labeldesk.dev")


@pytest.fixture(scope="module", autouse=True)
def _flag_on():
    admin = login("demo@labeldesk.dev")
    assert admin.put(FLAG_URL, json={"enabled": True}).status_code == 200
    yield
    admin.put(FLAG_URL, json={"enabled": False})


def body(**over):
    """The PLAN §2.3 fixture: a 7.6B BF16 model on one RTX 4090 under vLLM."""
    payload = {
        "model": {"params_b": 7.6, "layers": 28, "kv_heads": 4, "head_dim": 128},
        "quant": "bf16",
        "context": 8192,
        "batch": 4,
        "users": 1,
        "prompt_tokens": 8192,
        "output_tokens": 256,
        "gpu": {"preset": "rtx4090"},
        "gpu_count": 1,
        "tensor_parallel": 1,
        "engine": "vllm",
        "usable": 0.9,
    }
    payload.update(over)
    return payload


def estimate(client, **over):
    r = client.post(URL, json=body(**over))
    assert r.status_code == 200, r.text
    return r.json()


def test_worked_example_matches_the_plan(admin):
    out = estimate(admin)
    per_gpu = out["per_gpu"]
    assert per_gpu["weights_gb"] == pytest.approx(14.2, rel=0.01)
    assert per_gpu["kv_gb"] == pytest.approx(1.75, rel=0.01)
    assert per_gpu["total_gb"] == pytest.approx(18.7, rel=0.01)
    assert out["total_gb"] == pytest.approx(18.7, rel=0.01)
    assert out["fits"] is True
    assert out["throughput"]["memory_bound_tps"] == pytest.approx(166, rel=0.01)
    assert out["throughput"]["estimate_tps"] == pytest.approx(133, rel=0.01)


def test_tensor_parallel_divides_weights_and_kv(admin):
    one = estimate(admin)["per_gpu"]
    two = estimate(admin, gpu_count=2, tensor_parallel=2)["per_gpu"]
    assert two["weights_gb"] == pytest.approx(one["weights_gb"] / 2, rel=0.001)
    assert two["kv_gb"] == pytest.approx(one["kv_gb"] / 2, rel=0.001)
    assert two["activations_gb"] == pytest.approx(one["activations_gb"], rel=0.001)
    assert two["overhead_gb"] == pytest.approx(one["overhead_gb"], rel=0.001)
    assert two["total_gb"] < one["total_gb"]


def test_kv_heads_must_divide_by_tensor_parallel(admin):
    r = admin.post(URL, json=body(gpu_count=4, tensor_parallel=3))
    assert r.status_code == 422
    message = r.json()["detail"]
    assert "KV heads (4)" in message and "tensor parallel (3)" in message


def test_does_not_fit_names_the_deficit(admin):
    out = estimate(admin, model={"params_b": 70, "layers": 80, "kv_heads": 8, "head_dim": 128},
                   context=4096, batch=1)
    assert out["fits"] is False
    assert "short" in out["verdict"]
    assert "GB" in out["verdict"]


def test_quantisation_changes_the_weight_term(admin):
    bf16 = estimate(admin)["per_gpu"]["weights_gb"]
    int4 = estimate(admin, quant="int4")["per_gpu"]["weights_gb"]
    assert int4 == pytest.approx(bf16 / 4, rel=0.001)


def test_context_and_batch_drive_the_kv_term(admin):
    base = estimate(admin)["per_gpu"]["kv_gb"]
    longer = estimate(admin, context=16384)["per_gpu"]["kv_gb"]
    wider = estimate(admin, batch=8)["per_gpu"]["kv_gb"]
    assert longer == pytest.approx(base * 2, rel=0.001)
    assert wider == pytest.approx(base * 2, rel=0.001)


def test_bounds_are_422(admin):
    for over in ({"context": 0}, {"batch": 0}, {"usable": 1.5},
                 {"gpu_count": 4, "tensor_parallel": 5}):
        r = admin.post(URL, json=body(**over))
        assert r.status_code == 422, (over, r.text)


def test_assumptions_and_sources_are_always_returned(admin):
    out = estimate(admin)
    assert out["assumptions"]
    assert all(any(ch.isdigit() for ch in line) for line in out["assumptions"])
    assert set(out["sources"]) == SOURCES


def test_custom_gpu_numbers_are_used_and_a_preset_ignores_them(admin):
    custom = estimate(admin, gpu={"preset": "custom", "vram_gb": 48, "bw_gbs": 864,
                                  "fp16_tflops": 181})["per_gpu"]
    assert custom["usable_gb"] == pytest.approx(43.2, rel=0.001)
    preset = estimate(admin, gpu={"preset": "rtx4090", "vram_gb": 9999, "bw_gbs": 1,
                                  "fp16_tflops": 1})["per_gpu"]
    assert preset["usable_gb"] == pytest.approx(21.6, rel=0.001)


def test_member_can_estimate_and_flag_off_is_404(admin, member):
    """Owner decision PLAN §12.5: any member may open the read-only Calculator."""
    assert member.post(URL, json=body()).status_code == 200
    assert admin.put(FLAG_URL, json={"enabled": False}).status_code == 200
    assert admin.post(URL, json=body()).status_code == 404
    assert admin.put(FLAG_URL, json={"enabled": True}).status_code == 200
