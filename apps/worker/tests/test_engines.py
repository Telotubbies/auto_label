"""T-1008: the worker runs an engine plan in a guarded subprocess and stops cleanly.

Every command is a real process (``python -c …``), so the guard, the streaming, the exit code and
the group kill are exercised without uv, pip, docker or a network. ``collect`` is patched, so the
plan check compares against a known inventory; the server is a fake that records every post and can
answer a progress call with ``cancel``.
"""
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # apps/worker on the path

from labeldesk_worker import engines                             # noqa: E402

INVENTORY = {"os": "Linux", "arch": "x86_64", "cuda": "12.9",
             "gpus": [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564,
                       "driver": "575.51", "cuda": "12.9"}],
             "disk": {"models_free_gb": 812.5, "models_total_gb": 1863.0},
             "engines": []}


class FakeServer:
    """Records what the worker posted; a progress call after ``cancel_after`` asks for a cancel."""

    def __init__(self, cancel_after: int | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.cancel_after = cancel_after

    def post(self, path, **kw):
        self.calls.append((path, kw))
        posted = sum(1 for name, _ in self.calls if name.endswith("/progress"))
        return {"cancel": self.cancel_after is not None and posted > self.cancel_after}

    def progress(self) -> list[dict]:
        return [kw.get("json") or {} for name, kw in self.calls if name.endswith("/progress")]

    def last(self) -> tuple[str, dict]:
        return self.calls[-1]


def _canonical(host: str, steps: list[dict], inventory: dict | None) -> str:
    """The plan id the API computed, re-derived here the way the worker's own copy does it."""
    inv = inventory or {}
    free = (inv.get("disk") or {}).get("models_free_gb")
    gpus = sorted(([gpu.get("name"), gpu.get("vram_mb"), gpu.get("driver"), gpu.get("cuda")]
                   for gpu in inv.get("gpus") or [] if isinstance(gpu, dict)), key=json.dumps)
    seen = sorted(([row.get("id"), row.get("version"), row.get("runtime")]
                   for row in inv.get("engines") or [] if isinstance(row, dict)), key=json.dumps)
    stamp = {"os": inv.get("os"), "arch": inv.get("arch"), "cuda": inv.get("cuda"), "gpus": gpus,
             "engines": seen, "disk_free_gb": None if free is None else round(float(free))}
    body = json.dumps({"host": host, "steps": steps, "inventory": stamp},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _step(engine_id: str, argv: list[list[str]], runtime: str = "uv") -> dict:
    return {"id": engine_id, "version": "1.0.0", "runtime": runtime, "argv": argv,
            "disk_mb": 100, "status": "install"}


def _script(root: Path, name: str, body: str) -> list[str]:
    """A real command: a small Python file inside the engines directory, run by the allowlisted python."""
    path = root / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return ["python", str(path)]


def _wrapper(root: Path, marker: Path) -> list[str]:
    """A command that only leaves ``marker`` behind when it actually ran."""
    return _script(root, "mark", f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n")


def _job(payload: dict) -> dict:
    return {"id": "job-1", "payload": payload}


def _payload(steps: list[dict], plan_id: str = "", action: str = "install") -> dict:
    return {"host": "gpu-a", "action": action, "engines": steps, "plan_id": plan_id}


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(engines_dir=str(tmp_path / "engines"),
                           models_dir=str(tmp_path / "models"))


@pytest.fixture(autouse=True)
def allowed(monkeypatch):
    """Installs are opt-in; every test that runs a command opts in explicitly."""
    monkeypatch.setenv("LD_ALLOW_ENGINE_INSTALL", "1")


def test_guard_rejects_an_outside_path(tmp_path):
    root = tmp_path / "engines"
    root.mkdir()
    for argv in (["rm", "-rf", "/etc"],
                 ["uv", "pip", "install", "--target", "/tmp/x"],
                 ["python", "-m", "pip", "install", "../../x"]):
        with pytest.raises(engines.GuardError):
            engines.guard(argv, root)


def test_guard_allows_the_planned_argv(tmp_path):
    """The exact T-1006 argv of every runtime, install and uninstall."""
    root = tmp_path / "engines"
    root.mkdir()
    target = "vllm-0.6.3"
    for argv in (["uv", "venv", target],
                 ["uv", "pip", "install", "--python", f"{target}/bin/python", "vllm==0.6.3"],
                 ["python", "-m", "venv", target],
                 [f"{target}/bin/python", "-m", "pip", "install", "--no-input", "vllm==0.6.3"],
                 ["docker", "pull", "ollama/ollama@sha256:6a1b2c3d"],
                 ["rm", "-rf", target],
                 ["docker", "rmi", "ollama/ollama@sha256:6a1b2c3d"]):
        engines.guard(argv, root)


def test_success_reports_each_engine(tmp_path, monkeypatch):
    srv = FakeServer()
    root = tmp_path / "engines"
    (root / "vllm-1.0.0").mkdir(parents=True)
    (root / "llamacpp-1.0.0").mkdir()
    steps = [_step("vllm", [_script(root, "ok", "print('vllm ok')\n")]),
             _step("llamacpp", [_script(root, "ok2", "print('llamacpp ok')\n")])]
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)
    monkeypatch.setenv("HF_TOKEN", "hf_must-not-reach-the-install")

    engines.run_engine_apply(srv, _job(_payload(steps, _canonical("gpu-a", steps, INVENTORY))),
                             _args(tmp_path))

    path, kw = srv.last()
    assert path.endswith("/complete")
    result = json.loads(kw["data"]["result"])
    assert [engine["id"] for engine in result["engines"]] == ["vllm", "llamacpp"]
    assert [engine["path"] for engine in result["engines"]] == ["vllm-1.0.0", "llamacpp-1.0.0"]
    logs = [line for post in srv.progress() for line in post.get("log") or []]
    assert "vllm ok" in logs and "llamacpp ok" in logs
    assert "HF_TOKEN" not in engines.minimal_env()
    assert "hf_must-not-reach-the-install" not in json.dumps(engines.minimal_env())


def test_nonzero_exit_fails_with_the_last_line(tmp_path, monkeypatch):
    srv = FakeServer()
    root = tmp_path / "engines"
    (root / "vllm-1.0.0").mkdir(parents=True)
    (root / "llamacpp-1.0.0").mkdir()
    steps = [_step("vllm", [_script(root, "first", "print('first ok')\n")]),
             _step("llamacpp", [_script(root, "boom", "import sys\nprint('boom')\nsys.exit(1)\n")])]
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)

    engines.run_engine_apply(srv, _job(_payload(steps, _canonical("gpu-a", steps, INVENTORY))),
                             _args(tmp_path))

    path, kw = srv.last()
    assert path.endswith("/fail")
    assert "boom" in kw["json"]["error"] and "1" in kw["json"]["error"]
    assert [engine["id"] for engine in kw["json"]["result"]["engines"]] == ["vllm"]


def test_cancel_stops_and_removes_the_half_built_env(tmp_path, monkeypatch):
    srv = FakeServer(cancel_after=1)                    # the second progress post asks to stop
    root = tmp_path / "engines"
    target = root / "vllm-1.0.0"
    target.mkdir(parents=True)
    (target / "partial").write_text("half built")
    (root / "llamacpp-1.0.0").mkdir()
    steps = [_step("vllm", [_script(root, "sleep", "import time\ntime.sleep(60)\n")]),
             _step("llamacpp", [_script(root, "never", "print('never')\n")])]
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)
    monkeypatch.setattr(engines, "HEARTBEAT_S", 0.1)

    started = time.monotonic()
    engines.run_engine_apply(srv, _job(_payload(steps, _canonical("gpu-a", steps, INVENTORY))),
                             _args(tmp_path))

    assert time.monotonic() - started < engines.CANCEL_GRACE_S
    assert not target.exists()
    path, kw = srv.last()
    assert path.endswith("/complete")
    assert json.loads(kw["data"]["result"]) == {"cancelled": True, "engines": []}


def test_installs_disabled_fails_before_any_process(tmp_path, monkeypatch):
    srv = FakeServer()
    root = tmp_path / "engines"
    root.mkdir()
    marker = root / "ran.txt"
    steps = [_step("vllm", [_wrapper(root, marker)])]
    monkeypatch.delenv("LD_ALLOW_ENGINE_INSTALL", raising=False)

    with pytest.raises(engines.InstallsDisabled) as raised:
        engines.run_engine_apply(srv, _job(_payload(steps)), _args(tmp_path))

    assert "installs_disabled" in str(raised.value)
    assert not marker.exists()
    assert srv.calls == []


def test_stale_plan_is_refused(tmp_path, monkeypatch):
    srv = FakeServer()
    root = tmp_path / "engines"
    (root / "vllm-1.0.0").mkdir(parents=True)
    marker = root / "ran.txt"
    steps = [_step("vllm", [_wrapper(root, marker)])]
    other = {**INVENTORY, "disk": {"models_free_gb": 12.0, "models_total_gb": 1863.0}}
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)

    with pytest.raises(engines.PlanChanged) as raised:
        engines.run_engine_apply(
            srv, _job(_payload(steps, _canonical("gpu-a", steps, other))), _args(tmp_path))

    assert "stale_plan" in str(raised.value)
    assert not marker.exists()
    assert srv.progress()[-1]["phase"] == "stale_plan"
