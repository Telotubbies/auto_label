"""GPU smoke test for the LabelDesk v2 demo — run it on the demo box, alone.

Usage::

    # 1. start vLLM (see tools/serve_vllm.sh) and the API, and seed the demo workspace once
    # 2. from the repo root:
    python tools/demo_smoke.py
    python tools/demo_smoke.py --api-url http://localhost:8010 --vlm-url http://localhost:8000/v1 \
        --ws labeldesk-demo --project ppe-detection --stream-seconds 60 --train-epochs 3 \
        --max-vram-mb 11500 --timeout 900

It exercises, in order, the six checks the demo depends on: vLLM ``/v1/models``; VLM grounding
refined by SAM 3.1 on five seed images; SAM text auto-label; vLLM sleep → yolo26s training →
wake (sleep and wake times recorded); a gate-camera stream at ≥ 5 FPS for 60 s; and the peak
GPU memory sampled every second for the whole run (< 11 500 MiB). Every line prints PASS or
FAIL, and the exit code is 1 if any check failed. Nothing outside the demo workspace is touched.

All IO sits behind three small seams — :class:`Api`, :class:`Vllm` and :class:`Gpu` — and the
decision helpers are pure, so the whole run can be driven from tests without network or GPU.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_API_URL = "http://localhost:8010"
DEFAULT_VLM_URL = "http://localhost:8000/v1"
DEFAULT_WS = "labeldesk-demo"
DEFAULT_PROJECT = "ppe-detection"
DEFAULT_STREAM_SECONDS = 60
DEFAULT_TRAIN_EPOCHS = 3
DEFAULT_MAX_VRAM_MB = 11_500
DEFAULT_TIMEOUT = 900
DEFAULT_PREVIEW_TIMEOUT = 300
FAST_REQUEST_TIMEOUT = 30.0

DEMO_EMAIL = "demo@labeldesk.dev"
DEMO_PASSWORD = "demo1234"
VLM_GROUND_REF = "vlm:qwen2.5-vl-7b"
SAM_REF = "sam3:sam3.1"
STREAM_NAME = "Gate camera"
SEED_IMAGES = 5
MIN_FPS = 5.0
STREAM_POLL_S = 2.0
STREAM_WARMUP_S = 10.0
JOB_POLL_S = 2.0
STATE_POLL_S = 1.0
STATE_TIMEOUT_S = 120.0
TERMINAL_JOB_STATUSES = frozenset({"done", "failed", "cancelled"})
BAD_STREAM_STATUSES = frozenset({"error", "failed", "stopped"})


# --- reporting ---------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One PASS/FAIL line plus how long its step took."""

    ok: bool
    name: str
    detail: str
    seconds: float


class Report:
    """Collects and prints the run: one PASS/FAIL line per step, then a timing summary."""

    def __init__(self, out: Callable[[str], None] = print) -> None:
        self._out = out
        self.entries: list[Entry] = []

    def header(self, cfg: Config) -> None:
        self._out(f"LabelDesk demo smoke — api={cfg.api_url} vllm={cfg.vlm_url} project={cfg.ws}/{cfg.project}")

    def record(self, name: str, ok: bool, detail: str = "", seconds: float = 0.0) -> None:
        self.entries.append(Entry(bool(ok), name, detail, float(seconds)))
        self._out(self.lines()[-1])

    def lines(self) -> list[str]:
        return [
            f"{'PASS' if e.ok else 'FAIL'}  {e.name}" + (f" ({e.detail})" if e.detail else "") for e in self.entries
        ]

    @property
    def ok(self) -> bool:
        return all(e.ok for e in self.entries)

    def print_summary(self, total_seconds: float) -> None:
        passed = sum(1 for e in self.entries if e.ok)
        self._out("--- timings ---")
        for e in self.entries:
            self._out(f"  {e.seconds:7.1f} s  {e.name}")
        self._out(f"{passed}/{len(self.entries)} checks passed in {total_seconds:.1f} s")


# --- pure decisions ----------------------------------------------------------


def models_ok(payload: dict) -> bool:
    """vLLM is serving when ``/models`` lists at least one model."""
    data = payload.get("data")
    return isinstance(data, list) and bool(data)


def annotations_ok(count: int) -> bool:
    return count >= 1


def fps_ok(samples: list[float], minimum: float = MIN_FPS) -> bool:
    """Every post-warm-up sample must clear the floor; an empty run is a failure."""
    return bool(samples) and min(samples) >= minimum


def vram_ok(peak_mb: int | None, limit_mb: int) -> bool:
    """No reading means the check cannot be verified, which is a failure — not a pass."""
    return peak_mb is not None and peak_mb < limit_mb


def job_passed(job: dict, min_annotations: int = 0) -> bool:
    result = job.get("result") or {}
    return job.get("status") == "done" and int(result.get("annotations") or 0) >= min_annotations


def parse_nvidia_memory(text: str) -> int | None:
    """``nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits`` -> MiB."""
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


# --- GPU sampling ------------------------------------------------------------


def read_gpu_memory() -> int | None:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_nvidia_memory(out.stdout)


class Gpu:
    """Samples used VRAM once a second in the background; peak is what the demo is judged on."""

    def __init__(self, sample: Callable[[], int | None] | None = None, interval: float = 1.0) -> None:
        self._sample = sample or read_gpu_memory
        self.interval = interval
        self.samples: list[int] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._sample_once()  # guarantee one reading even for a very short run
        self._thread = threading.Thread(target=self._loop, name="vram-sampler", daemon=True)
        self._thread.start()

    def _sample_once(self) -> None:
        try:
            value = self._sample()
        except Exception:  # a telemetry hiccup must never abort the smoke run
            value = None
        if value is not None:
            with self._lock:
                self.samples.append(int(value))

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self._sample_once()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def peak(self) -> int | None:
        with self._lock:
            return max(self.samples) if self.samples else None


# --- HTTP seams --------------------------------------------------------------


class Api:
    """LabelDesk API client scoped to one workspace/project, authenticated with a bearer token."""

    def __init__(
        self,
        client: httpx.Client,
        api_url: str,
        ws: str,
        project: str,
        preview_timeout: float = DEFAULT_PREVIEW_TIMEOUT,
    ) -> None:
        self.client = client
        self.root = api_url.rstrip("/")
        self.base = f"{self.root}/api/ws/{quote(ws, safe='')}/projects/{quote(project, safe='')}"
        self.token: str | None = None
        self.preview_timeout = preview_timeout

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def login(self, email: str, password: str) -> None:
        response = self.client.post(f"{self.root}/api/auth/login", json={"email": email, "password": password})
        self.token = self._json(response)["token"]

    def get(self, path: str) -> Any:
        return self._json(self.client.get(self.base + path, headers=self._headers()))

    def post(self, path: str, payload: dict | None = None) -> Any:
        return self._json(self.client.post(self.base + path, headers=self._headers(), json=payload))

    # --- project endpoints, one method per smoke step

    def preview_ground(self, sample: int = SEED_IMAGES) -> dict:
        # Synchronous on the API: the first call cold-loads SAM 3.1 and then runs VLM+SAM on
        # `sample` images, so it needs a far longer budget than the fast job/stream calls.
        response = self.client.post(
            self.base + "/autolabel/preview",
            headers=self._headers(),
            json={
                "method": "sam",
                "model_ref": VLM_GROUND_REF,
                "only_unannotated": False,
                "sample": sample,
            },
            timeout=httpx.Timeout(self.preview_timeout),
        )
        return self._json(response)

    def autolabel(self) -> dict:
        return self.post(
            "/autolabel",
            {
                "method": "sam",
                "model_ref": SAM_REF,
                "only_unannotated": False,
                "send_to_review": True,
            },
        )

    def job(self, job_id: str) -> dict:
        return self.get(f"/jobs/{job_id}")

    def versions(self) -> list[dict]:
        return self.get("/versions")

    def train(self, version_id: str, epochs: int) -> dict:
        return self.post(
            "/train",
            {
                "version_id": version_id,
                "size": "s",
                "epochs": epochs,
                "imgsz": 640,
                "batch": 8,
                "family": "ultralytics",
            },
        )

    def streams(self) -> list[dict]:
        return self.get("/streams")

    def stream(self, stream_id: str) -> dict:
        return self.get(f"/streams/{stream_id}")

    def start_stream(self, stream_id: str) -> dict:
        return self.post(f"/streams/{stream_id}/start")

    def stop_stream(self, stream_id: str) -> dict:
        return self.post(f"/streams/{stream_id}/stop")


class Vllm:
    """vLLM OpenAI surface plus the dev-mode sleep endpoints at the server root (outside ``/v1``)."""

    def __init__(self, client: httpx.Client, vlm_url: str) -> None:
        self.client = client
        self.url = vlm_url.rstrip("/")
        self.root = self.url[: -len("/v1")] if self.url.endswith("/v1") else self.url

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        response.raise_for_status()
        return response.json()

    def models(self) -> dict:
        return self._json(self.client.get(f"{self.url}/models"))

    def sleep(self, level: int = 1) -> None:
        # No raise: an already-sleeping server can reject the call, and the state check decides.
        self.client.post(f"{self.root}/sleep?level={int(level)}")

    def is_sleeping(self) -> bool:
        return bool(self._json(self.client.get(f"{self.root}/is_sleeping")).get("is_sleeping"))

    def wake(self) -> None:
        self.client.post(f"{self.root}/wake_up")


# --- polling helpers ---------------------------------------------------------


def wait_until(
    check: Callable[[], bool],
    *,
    timeout: float,
    interval: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> bool:
    deadline = clock() + timeout
    while True:
        if check():
            return True
        remaining = deadline - clock()
        if remaining <= 0:
            return False
        sleep(min(interval, remaining))


def wait_job(
    api: Api,
    job_id: str,
    *,
    timeout: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> dict:
    deadline = clock() + timeout
    while True:
        job = api.job(job_id)
        if job.get("status") in TERMINAL_JOB_STATUSES:
            return job
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError(f"job {job_id} still {job.get('status')} after {timeout:.0f} s")
        sleep(min(JOB_POLL_S, remaining))


def _err(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _seconds(value: float | None) -> str:
    return f"{value:.1f} s" if value is not None else "n/a"


# --- steps -------------------------------------------------------------------


def step_models(vllm: Vllm) -> tuple[bool, str]:
    try:
        payload = vllm.models()
    except Exception as exc:
        return False, _err(exc)
    count = len(payload.get("data") or [])
    return models_ok(payload), f"{count} model(s)"


def step_ground(api: Api) -> tuple[bool, str]:
    try:
        payload = api.preview_ground()
    except Exception as exc:
        return False, _err(exc)
    images = payload.get("images") or []
    count = sum(len(image.get("annotations") or []) for image in images)
    return annotations_ok(count), f"{count} annotation(s) over {len(images)} image(s)"


def step_autolabel(
    api: Api, timeout: float, clock: Callable[[], float], sleep: Callable[[float], None]
) -> tuple[bool, str]:
    try:
        job = wait_job(api, api.autolabel()["id"], timeout=timeout, clock=clock, sleep=sleep)
    except Exception as exc:
        return False, _err(exc)
    count = int((job.get("result") or {}).get("annotations") or 0)
    detail = f"job {job.get('status')}, {count} annotation(s)"
    if job.get("error"):
        detail += f": {job['error']}"
    return job_passed(job, 1), detail


def _first_ready_version(api: Api) -> str | None:
    for version in api.versions():
        if version.get("status") == "ready":
            return version.get("id")
    return None


def step_sleep_train_wake(
    cfg: Config,
    api: Api,
    vllm: Vllm,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> tuple[bool, str]:
    """Sleep vLLM, train while the GPU is free, then wake it — one composite PASS/FAIL line."""
    failures: list[str] = []
    state_timeout = min(cfg.timeout, STATE_TIMEOUT_S)
    sleep_s: float | None = None
    wake_s: float | None = None

    started = clock()
    try:
        vllm.sleep(1)
    except (httpx.HTTPError, OSError):
        pass  # already asleep: the state check below decides
    try:
        sleeping = wait_until(
            vllm.is_sleeping,
            timeout=state_timeout,
            interval=STATE_POLL_S,
            clock=clock,
            sleep=sleep,
        )
    except Exception as exc:
        sleeping = False
        failures.append(f"is_sleeping: {_err(exc)}")
    if sleeping:
        sleep_s = clock() - started
    else:
        failures.append("vLLM did not report is_sleeping=true")

    trained = False
    if sleeping:
        try:
            version_id = _first_ready_version(api)
            if version_id is None:
                failures.append("no ready version to train on")
            else:
                model = api.train(version_id, cfg.train_epochs)
                job = wait_job(api, model["jobId"], timeout=cfg.timeout, clock=clock, sleep=sleep)
                if job.get("status") == "done":
                    trained = True
                else:
                    failures.append(
                        f"train job {job.get('status')}" + (f": {job.get('error')}" if job.get("error") else "")
                    )
        except Exception as exc:
            failures.append(f"train: {_err(exc)}")
    else:
        failures.append("training skipped while vLLM is awake")

    started = clock()
    try:
        vllm.wake()
    except (httpx.HTTPError, OSError):
        pass  # already awake: the state check below decides
    try:
        awake = wait_until(
            lambda: not vllm.is_sleeping(),
            timeout=state_timeout,
            interval=STATE_POLL_S,
            clock=clock,
            sleep=sleep,
        )
    except Exception as exc:
        awake = False
        failures.append(f"wake_up: {_err(exc)}")
    if awake:
        wake_s = clock() - started
    else:
        failures.append("vLLM did not report is_sleeping=false after wake_up")

    detail = f"sleep {_seconds(sleep_s)}, wake {_seconds(wake_s)}"
    if failures:
        detail += "; " + "; ".join(failures)
    return sleeping and trained and awake, detail


def step_stream(cfg: Config, api: Api, clock: Callable[[], float], sleep: Callable[[float], None]) -> tuple[bool, str]:
    stream_id: str | None = None
    samples: list[float] = []
    problem = ""
    try:
        gauge = next((s for s in api.streams() if s.get("name") == STREAM_NAME), None)
        if gauge is None:
            return False, f'stream "{STREAM_NAME}" not found'
        stream_id = gauge["id"]
        api.start_stream(stream_id)
        sleep(STREAM_WARMUP_S)
        deadline = clock() + cfg.stream_seconds
        while clock() < deadline:
            state = api.stream(stream_id)
            status = state.get("status")
            samples.append(float(state.get("fps") or 0.0))
            if status in BAD_STREAM_STATUSES and not problem:
                problem = f"status {status}" + (f": {state.get('lastError')}" if state.get("lastError") else "")
            remaining = deadline - clock()
            if remaining > 0:
                sleep(min(STREAM_POLL_S, remaining))
    except Exception as exc:
        problem = problem or _err(exc)
    finally:
        if stream_id is not None:  # never leave the camera running
            try:
                api.stop_stream(stream_id)
            except Exception as exc:
                problem = problem or f"stop: {_err(exc)}"

    detail = (
        f"min {min(samples):.1f}, avg {sum(samples) / len(samples):.1f} FPS over {len(samples)} sample(s)"
        if samples
        else "no FPS samples"
    )
    if problem:
        detail += f"; {problem}"
    return not problem and fps_ok(samples), detail


def step_vram(gpu: Gpu, limit_mb: int) -> tuple[bool, str]:
    peak = gpu.peak
    if peak is None:
        return False, "nvidia-smi missing or returned no memory value"
    return vram_ok(peak, limit_mb), f"peak {peak} MiB (limit {limit_mb} MiB)"


# --- the run -----------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    api_url: str = DEFAULT_API_URL
    vlm_url: str = DEFAULT_VLM_URL
    ws: str = DEFAULT_WS
    project: str = DEFAULT_PROJECT
    stream_seconds: int = DEFAULT_STREAM_SECONDS
    train_epochs: int = DEFAULT_TRAIN_EPOCHS
    max_vram_mb: int = DEFAULT_MAX_VRAM_MB
    timeout: int = DEFAULT_TIMEOUT
    preview_timeout: int = DEFAULT_PREVIEW_TIMEOUT
    skip_vram: bool = False


def _record(
    report: Report,
    name: str,
    step: Callable[[], tuple[bool, str]],
    clock: Callable[[], float],
) -> None:
    started = clock()
    try:
        ok, detail = step()
    except Exception as exc:  # one broken step must not take the run down
        ok, detail = False, _err(exc)
    report.record(name, ok, detail, clock() - started)


def run(
    cfg: Config,
    *,
    api: Api,
    vllm: Vllm,
    report: Report,
    gpu: Gpu | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    started = clock()
    if gpu is not None:
        gpu.start()
    try:
        _record(report, "vLLM /v1/models", lambda: step_models(vllm), clock)
        _record(report, "VLM→SAM ground (5 seed images)", lambda: step_ground(api), clock)
        _record(
            report,
            "SAM text auto-label",
            lambda: step_autolabel(api, cfg.timeout, clock, sleep),
            clock,
        )
        _record(
            report,
            "sleep → train yolo26s → wake",
            lambda: step_sleep_train_wake(cfg, api, vllm, clock, sleep),
            clock,
        )
        _record(
            report,
            f"stream ≥ {MIN_FPS:g} FPS for {cfg.stream_seconds} s",
            lambda: step_stream(cfg, api, clock, sleep),
            clock,
        )
    finally:
        if gpu is not None:
            gpu.stop()
    if gpu is not None:
        _record(
            report,
            f"GPU memory peak < {cfg.max_vram_mb} MiB",
            lambda: step_vram(gpu, cfg.max_vram_mb),
            clock,
        )
    report.print_summary(clock() - started)
    return 0 if report.ok else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LabelDesk v2 GPU demo smoke test (see module docstring).")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="LabelDesk API base URL")
    parser.add_argument(
        "--vlm-url",
        default=os.environ.get("LD_VLM_URL", DEFAULT_VLM_URL),
        help="vLLM OpenAI base URL, normally ending in /v1",
    )
    parser.add_argument("--ws", default=DEFAULT_WS, help="workspace slug")
    parser.add_argument("--project", default=DEFAULT_PROJECT, help="project slug")
    parser.add_argument(
        "--stream-seconds",
        type=int,
        default=DEFAULT_STREAM_SECONDS,
        help="length of the FPS window after the 10 s warm-up",
    )
    parser.add_argument("--train-epochs", type=int, default=DEFAULT_TRAIN_EPOCHS)
    parser.add_argument(
        "--max-vram-mb",
        type=int,
        default=DEFAULT_MAX_VRAM_MB,
        help="peak GPU memory must stay below this",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="seconds to wait for an auto-label/train job",
    )
    parser.add_argument(
        "--preview-timeout",
        type=int,
        default=DEFAULT_PREVIEW_TIMEOUT,
        help="seconds to wait for the synchronous VLM-to-SAM preview (cold SAM load + 5 images)",
    )
    parser.add_argument("--skip-vram", action="store_true", help="skip the GPU memory check")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    api_client: httpx.Client | None = None,
    vlm_client: httpx.Client | None = None,
    gpu: Gpu | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    args = parse_args(argv)
    cfg = Config(
        api_url=args.api_url,
        vlm_url=args.vlm_url,
        ws=args.ws,
        project=args.project,
        stream_seconds=args.stream_seconds,
        train_epochs=args.train_epochs,
        max_vram_mb=args.max_vram_mb,
        timeout=args.timeout,
        preview_timeout=args.preview_timeout,
        skip_vram=args.skip_vram,
    )
    report = Report()
    report.header(cfg)

    own_api_client = api_client is None
    own_vlm_client = vlm_client is None
    api_client = api_client or httpx.Client(timeout=FAST_REQUEST_TIMEOUT)
    vlm_client = vlm_client or httpx.Client(timeout=FAST_REQUEST_TIMEOUT)
    try:
        api = Api(api_client, cfg.api_url, cfg.ws, cfg.project, preview_timeout=cfg.preview_timeout)
        vllm = Vllm(vlm_client, cfg.vlm_url)
        try:
            api.login(DEMO_EMAIL, DEMO_PASSWORD)
        except Exception as exc:
            report.record("login", False, _err(exc))
            report.print_summary(0.0)
            return 1
        sampler = None if cfg.skip_vram else (gpu or Gpu())
        return run(
            cfg,
            api=api,
            vllm=vllm,
            report=report,
            gpu=sampler,
            clock=clock,
            sleep=sleep,
        )
    finally:
        if own_api_client:
            api_client.close()
        if own_vlm_client:
            vlm_client.close()


if __name__ == "__main__":
    sys.exit(main())
