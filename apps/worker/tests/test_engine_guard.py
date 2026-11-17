"""T-1018: the worker's guard refuses a tampered plan, an unknown executable, a writing option,
a symlink out of the engines directory, and stores a log line without a token or a home path.

A plan id is a hash of the host, the steps and the host's own inventory, so an argv edited after
review no longer matches — even when the step count is identical. Every command here is a real
process (`python <script>`), so nothing is patched except ``collect`` and the server.
"""
import hashlib
import json
import sys
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
    """Records every post; the progress posts are the log an admin would read."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def post(self, path, **kw):
        self.calls.append((path, kw))
        return {"cancel": False}

    def progress(self) -> list[dict]:
        return [kw.get("json") or {} for name, kw in self.calls if name.endswith("/progress")]

    def posted(self) -> str:
        return json.dumps(self.calls)


def _canonical(host: str, steps: list[dict], inventory: dict | None) -> str:
    """The plan id the API computed, re-derived the way the worker's own copy does it."""
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
    """A real command: a small Python file inside the engines directory."""
    path = root / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return ["python", str(path)]


def _job(payload: dict) -> dict:
    return {"id": "job-1", "payload": payload}


def _payload(steps: list[dict], plan_id: str) -> dict:
    return {"host": "gpu-a", "action": "install", "engines": steps, "plan_id": plan_id}


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(engines_dir=str(tmp_path / "engines"),
                           models_dir=str(tmp_path / "models"))


@pytest.fixture(autouse=True)
def allowed(monkeypatch):
    """Installs are opt-in; every test here opts in explicitly."""
    monkeypatch.setenv("LD_ALLOW_ENGINE_INSTALL", "1")


def test_tampered_plan_id_is_refused_before_exec(tmp_path, monkeypatch):
    """The same step count with a different argv fails the hash: no marker, no exec."""
    srv = FakeServer()
    root = tmp_path / "engines"
    root.mkdir()
    marker = root / "ran.txt"
    reviewed = [_step("vllm", [_script(root, "reviewed", "print('reviewed')\n")])]
    tampered = [_step("vllm", [_script(root, "tampered",
                                       f"from pathlib import Path\n"
                                       f"Path({str(marker)!r}).write_text('ran')\n")])]
    assert len(tampered) == len(reviewed)                       # the attack the card names
    plan_id = _canonical("gpu-a", reviewed, INVENTORY)
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)

    with pytest.raises(engines.PlanChanged) as raised:
        engines.run_engine_apply(srv, _job(_payload(tampered, plan_id)), _args(tmp_path))

    assert "stale_plan" in str(raised.value)
    assert srv.progress()[-1]["phase"] == "stale_plan"
    assert not marker.exists()


@pytest.mark.parametrize("exe", ["bash", "sh", "powershell", "curl"])
def test_every_executable_outside_the_allowlist_is_refused(tmp_path, exe):
    """Only the catalogue's own tools may run; a shell or a downloader is never one of them."""
    root = tmp_path / "engines"
    root.mkdir()

    with pytest.raises(engines.GuardError):
        engines.guard([exe, "x"], root)
    assert exe not in engines.ALLOWED_EXECUTABLES


@pytest.mark.parametrize("option", ["--target", "--prefix", "-t", "--root"])
def test_option_that_writes_outside_is_refused(tmp_path, option):
    """A pip option that plants files at a caller's path is refused, relative or not."""
    root = tmp_path / "engines"
    root.mkdir()

    for value in ("x", "/tmp/x", str(tmp_path / "outside")):
        with pytest.raises(engines.GuardError):
            engines.guard(["uv", "pip", "install", option, value], root)


def test_symlink_escape_is_refused(tmp_path):
    """A link inside the engines directory that resolves outside it is not a path we may run."""
    root = tmp_path / "engines"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:                 # a Windows box without Developer Mode cannot make one
        pytest.skip(f"this host cannot create a symlink: {exc}")

    with pytest.raises(engines.GuardError):
        engines.guard(["python", str(link / "run.py")], root)
    assert root not in (link / "run.py").resolve().parents      # the link really points outside


def test_log_redacts_a_token_and_a_home_path(tmp_path, monkeypatch):
    """A host's own output is stored for an admin to read: keep the sentence, drop both secrets."""
    srv = FakeServer()
    root = tmp_path / "engines"
    (root / "vllm-1.0.0").mkdir(parents=True)
    line = "pip using hf_secret_abcdef0123456789 from /home/alice/.ssh/id_rsa"
    steps = [_step("vllm", [_script(root, "leak", f"print({line!r})\n")])]
    monkeypatch.setattr(engines, "collect", lambda *_a, **_k: INVENTORY)

    engines.run_engine_apply(srv, _job(_payload(steps, _canonical("gpu-a", steps, INVENTORY))),
                             _args(tmp_path))

    stored = srv.posted()
    assert "hf_secret" not in stored and "abcdef0123456789" not in stored
    assert "/home/alice" not in stored and ".ssh" not in stored
    logs = [entry for post in srv.progress() for entry in post.get("log") or []]
    assert any("hf_***" in entry and "<path>" in entry for entry in logs), logs
