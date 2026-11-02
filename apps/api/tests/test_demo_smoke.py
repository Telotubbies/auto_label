"""Behaviour of tools/demo_smoke.py against a fake API/vLLM — no network, no GPU, no real waiting.

The script is loaded by path (it is not an installed package) and every step is driven by
`httpx.MockTransport`, an injected peak-VRAM sampler and a fake clock, so the whole six-step
run finishes in milliseconds.
"""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

import httpx

TOOL = Path(__file__).resolve().parents[3] / "tools" / "demo_smoke.py"
PREFIX = "/api/ws/labeldesk-demo/projects/ppe-detection"
PREVIEW_IDS = ["i1", "i2", "i3", "i4", "i5"]
GROUND_TRUTH = {
    "i1": [{"id": "g1", "classId": "person", "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.3}}],
    "i2": [{"id": "g2", "classId": "helmet", "shape": {"kind": "bbox", "x": 0.2, "y": 0.2, "w": 0.1, "h": 0.1}}],
    "i3": [],
    "i4": [{"id": "g4", "classId": "harness", "shape": {"kind": "bbox", "x": 0.3, "y": 0.3, "w": 0.1, "h": 0.2}}],
    "i5": [],
}


def _load_tool():
    spec = importlib.util.spec_from_file_location("demo_smoke_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo_smoke = _load_tool()


class FakeClock:
    """Injected clock: sleeping advances time instantly, so 70 s of polling costs nothing."""

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += max(0.0, seconds)


def _api_handler(state: dict, calls: list[tuple[str, str]]):
    def handle(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        calls.append((method, path))
        if path == "/api/auth/login":
            assert request.headers["content-type"] == "application/json"
            return httpx.Response(200, json={"token": "tok-123"})
        auth = request.headers.get("authorization")
        assert auth == "Bearer tok-123", "every project call must be authenticated"
        image = re.fullmatch(r"/api/images/([^/]+)(/annotations)?", path)
        if image:
            image_id, suffix = image.group(1), image.group(2)
            if method == "GET":
                stored = state["images"][image_id]
                return httpx.Response(
                    200,
                    json={"id": image_id, "annotations": copy.deepcopy(stored["annotations"]),
                          "status": stored["status"]},
                )
            body = json.loads(request.content or b"{}")
            if method == "PUT" and suffix == "/annotations":
                state["images"][image_id]["annotations"] = body["annotations"]
                state["restored"].append(image_id)
                return httpx.Response(200, json={"saved": len(body["annotations"]), "status": "done"})
            if method == "PATCH" and suffix is None:
                state["images"][image_id]["status"] = body["status"]
                state["statuses_restored"].append(image_id)
                return httpx.Response(200, json={"id": image_id, **body})
            raise AssertionError(f"unexpected image call {method} {path}")
        if path == f"{PREFIX}/images":
            return httpx.Response(
                200,
                json={"total": len(PREVIEW_IDS), "items": [{"id": i} for i in PREVIEW_IDS]},
            )
        if path == f"{PREFIX}/autolabel/preview":
            if not state.get("preview_ok", True):
                return httpx.Response(503, json={"detail": "vLLM not reachable"})
            state["preview_timeout"] = request.extensions.get("timeout", {})
            return httpx.Response(
                200,
                json={
                    "images": [{"id": image_id, "annotations": [{"x": 1.0}]} for image_id in PREVIEW_IDS],
                    "counts": {"person": 1},
                },
            )
        if path == f"{PREFIX}/autolabel":
            payload = json.loads(request.content or b"{}")
            state["autolabel_payload"] = payload
            # The real worker appends its boxes to whatever the image already has.
            for image_id in payload.get("image_ids") or []:
                state["images"][image_id]["annotations"].append(
                    {"id": f"sam-{image_id}", "classId": "helmet", "source": "sam3"}
                )
            return httpx.Response(200, json={"id": "job-auto", "status": "queued"})
        if path == f"{PREFIX}/jobs/job-auto":
            return httpx.Response(
                200,
                json={"id": "job-auto", "status": "done", "result": {"annotations": 3}},
            )
        if path == f"{PREFIX}/versions":
            return httpx.Response(200, json=[{"id": "v1", "number": 1, "status": "ready"}])
        if path == f"{PREFIX}/train":
            return httpx.Response(200, json={"id": "m1", "jobId": "job-train", "status": "queued"})
        if path == f"{PREFIX}/jobs/job-train":
            return httpx.Response(200, json={"id": "job-train", "status": "done", "result": {}})
        if path == f"{PREFIX}/streams":
            return httpx.Response(200, json=[{"id": "s1", "name": "Gate camera"}])
        if path == f"{PREFIX}/streams/s1/start":
            state["started"] = True
            return httpx.Response(200, json={"id": "s1", "status": "live"})
        if path == f"{PREFIX}/streams/s1/stop":
            state["stops"] += 1
            return httpx.Response(200, json={"id": "s1", "status": "stopped"})
        if path == f"{PREFIX}/streams/s1":
            return httpx.Response(200, json={"id": "s1", "status": "live", "fps": state["fps"]})
        raise AssertionError(f"unexpected API call {method} {path}")

    return handle


def _vllm_handler(state: dict, calls: list[tuple[str, str]]):
    def handle(request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        calls.append((method, path))
        if path == "/v1/models":
            return httpx.Response(200, json={"data": state["models"]})
        if path == "/sleep":
            assert request.url.params.get("level") == "1"
            state["sleeping"] = True
            return httpx.Response(200, json={})
        if path == "/is_sleeping":
            return httpx.Response(200, json={"is_sleeping": state["sleeping"]})
        if path == "/wake_up":
            state["sleeping"] = False
            return httpx.Response(200, json={})
        raise AssertionError(f"unexpected vLLM call {method} {path}")

    return handle


def _run(state: dict, *, fps: float = 6.0) -> tuple[int, list[tuple[str, str]], dict]:
    clock = FakeClock()
    api_calls: list[tuple[str, str]] = []
    vllm_calls: list[tuple[str, str]] = []
    images = copy.deepcopy(GROUND_TRUTH)
    state = {
        **state,
        "fps": fps,
        "stops": 0,
        "images": {image_id: {"annotations": anns, "status": "done"} for image_id, anns in images.items()},
        "restored": [],
        "statuses_restored": [],
    }
    api_client = httpx.Client(transport=httpx.MockTransport(_api_handler(state, api_calls)))
    vllm_client = httpx.Client(transport=httpx.MockTransport(_vllm_handler(state, vllm_calls)))
    gpu = demo_smoke.Gpu(sample=lambda: 4096, interval=0.01)
    try:
        code = demo_smoke.main(
            ["--stream-seconds", "60"],
            api_client=api_client,
            vlm_client=vllm_client,
            gpu=gpu,
            clock=clock.now,
            sleep=clock.sleep,
        )
    finally:
        api_client.close()
        vllm_client.close()
    return code, api_calls + vllm_calls, state


def _pass_lines(capsys) -> list[str]:
    return [line for line in capsys.readouterr().out.splitlines() if line.startswith("PASS  ")]


def test_all_six_steps_pass_in_order_with_sleep_and_wake_times(capsys):
    code, calls, state = _run({"models": [{"id": "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"}], "sleeping": False})

    assert code == 0
    passes = _pass_lines(capsys)
    assert len(passes) == 6, passes
    order = [
        "vLLM /v1/models",
        "VLM->SAM",
        "SAM text",
        "sleep ->",
        "stream",
        "GPU memory peak",
    ]
    for line, marker in zip(passes, order):
        assert marker in line, (marker, line)
    assert re.search(r"sleep \d+\.\d+ s", passes[3]), passes[3]
    assert re.search(r"wake \d+\.\d+ s", passes[3]), passes[3]
    assert state["stops"] == 1
    assert ("POST", "/wake_up") in calls
    assert state["preview_timeout"]["read"] == demo_smoke.DEFAULT_PREVIEW_TIMEOUT


def test_autolabel_is_scoped_to_the_preview_images_and_restores_annotations(capsys):
    code, _, state = _run({"models": [{"id": "qwen"}], "sleeping": False})

    assert code == 0
    payload = state["autolabel_payload"]
    assert payload["method"] == "sam"
    assert payload["model_ref"] == demo_smoke.SAM_REF
    assert payload["image_ids"] == PREVIEW_IDS, "the job must only touch the previewed images"
    assert state["restored"] == PREVIEW_IDS
    assert state["statuses_restored"] == PREVIEW_IDS
    for image_id in PREVIEW_IDS:
        assert state["images"][image_id]["annotations"] == GROUND_TRUTH[image_id]
        assert state["images"][image_id]["status"] == "done"


def test_autolabel_falls_back_to_project_images_when_preview_fails(capsys):
    code, _, state = _run({"models": [{"id": "qwen"}], "sleeping": False, "preview_ok": False})

    assert code == 1, "the ground check fails; the other five still run"
    assert state["autolabel_payload"]["image_ids"] == PREVIEW_IDS
    assert state["restored"] == PREVIEW_IDS
    fails = [line for line in capsys.readouterr().out.splitlines() if line.startswith("FAIL  ")]
    assert fails[0].startswith("FAIL  VLM->SAM")


def test_preview_gets_a_long_timeout_and_fast_calls_keep_the_short_one():
    timeouts: dict[str, dict] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": "tok"})
        timeouts[request.url.path.rsplit("/", 1)[-1]] = request.extensions.get("timeout", {})
        if request.url.path.endswith("/preview"):
            return httpx.Response(200, json={"images": [{"annotations": [{}]}], "counts": {}})
        return httpx.Response(200, json={"id": "job-1", "status": "queued"})

    client = httpx.Client(transport=httpx.MockTransport(handle), timeout=demo_smoke.FAST_REQUEST_TIMEOUT)
    try:
        api = demo_smoke.Api(client, "http://api", "ws", "p", preview_timeout=300.0)
        api.login("demo@labeldesk.dev", "demo1234")
        api.preview_ground()
        api.autolabel()
    finally:
        client.close()

    assert timeouts["preview"]["read"] == 300.0
    assert timeouts["autolabel"]["read"] == 30.0


def test_preview_timeout_flag_is_parsed():
    assert demo_smoke.parse_args([]).preview_timeout == demo_smoke.DEFAULT_PREVIEW_TIMEOUT
    assert demo_smoke.parse_args(["--preview-timeout", "45"]).preview_timeout == 45


def test_failing_step_prints_fail_and_exits_one(capsys):
    code, _, _ = _run({"models": [], "sleeping": False})

    assert code == 1
    out = capsys.readouterr().out
    fails = [line for line in out.splitlines() if line.startswith("FAIL  ")]
    assert fails and fails[0].startswith("FAIL  vLLM /v1/models")
    assert "(" in fails[0] and ")" in fails[0]


def test_stream_is_stopped_even_when_fps_is_below_the_floor(capsys):
    code, calls, state = _run({"models": [{"id": "qwen"}], "sleeping": False}, fps=1.0)

    assert code == 1
    lines = capsys.readouterr().out.splitlines()
    stream_fail = next(line for line in lines if line.startswith("FAIL  stream"))
    assert "FPS" in stream_fail
    assert state["stops"] == 1, "stop must run in a finally block"
    assert ("POST", f"{PREFIX}/streams/s1/stop") in calls


def test_vram_and_fps_decisions_are_pure():
    assert demo_smoke.fps_ok([5.0, 6.2, 9.9])
    assert not demo_smoke.fps_ok([4.9, 6.0])
    assert not demo_smoke.fps_ok([])
    assert demo_smoke.vram_ok(11_499, 11_500)
    assert not demo_smoke.vram_ok(11_500, 11_500)
    assert not demo_smoke.vram_ok(None, 11_500)


def test_every_report_line_is_ascii_so_any_windows_code_page_can_print_it(capsys):
    code, _, _ = _run({"models": [{"id": "qwen"}], "sleeping": False})

    assert code == 0
    out = capsys.readouterr().out
    assert out.isascii(), [line for line in out.splitlines() if not line.isascii()]


class LegacyConsole:
    """A Windows console whose code page (cp874 here) cannot encode arrows or dashes.

    ``TextIOWrapper.write`` raises ``UnicodeEncodeError`` before writing anything, so the
    fake raises from ``write`` in the same way a real console does.
    """

    encoding = "cp874"

    def __init__(self) -> None:
        self.written = ""

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        self.written += text
        return len(text)

    def flush(self) -> None:
        pass


def test_report_survives_a_non_utf8_console_and_a_unicode_detail(monkeypatch):
    console = LegacyConsole()
    monkeypatch.setattr(sys, "stdout", console)

    demo_smoke.Report().record("VLM→SAM ground", True, "sleep ≥ 1 s")

    assert "PASS  VLM?SAM ground (sleep ? 1 s)" in console.written
