"""T-1023: the worker's Ollama health probe and a catalogue-only `ollama pull`.

No real Ollama is installed, called or downloaded. The health check talks to a local HTTP fake on
127.0.0.1, and the pull is exercised as the argv the API queued: a recorder proves the exact argv
reaches the process layer, and on POSIX a fake `ollama` script proves the real subprocess path.
Windows cannot launch a `.cmd` with `shell=False` through CreateProcess, so that one real-exec case
skips there; the T-1019 harness owns the executable twins.
"""
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # apps/worker on the path

from labeldesk_worker import engines, ollama                     # noqa: E402


class FakeServer:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def post(self, path, **kw):
        self.calls.append((path, kw))
        return {}

    def last(self) -> tuple[str, dict]:
        return self.calls[-1]


class VersionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/version":
            self.send_response(404)
            self.end_headers()
            return
        body = b'{"version": "0.40.16"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@pytest.fixture()
def version_url():
    """A real HTTP server on loopback; the probe reads it exactly as it would read Ollama."""
    server = HTTPServer(("127.0.0.1", 0), VersionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/version"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def allowed(monkeypatch):
    monkeypatch.setenv("LD_ALLOW_ENGINE_INSTALL", "1")


def _closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(engines_dir=str(tmp_path / "engines"),
                           models_dir=str(tmp_path / "models"))


def _pull_job(tag: str = "qwen3:4b", row_id: str = "qwen3-4b") -> dict:
    return {"id": "job-pull", "payload": {
        "host": "gpu-a", "action": "pull", "plan_id": "",
        "engines": [{"id": row_id, "version": "q4_k_m", "runtime": "ollama", "tag": tag,
                     "argv": [["ollama", "pull", tag]]}]}}


def test_the_health_probe_reads_api_version_over_loopback(version_url):
    assert ollama.version(version_url) == "0.40.16"


def test_the_probe_fails_closed_when_nothing_answers():
    url = f"http://127.0.0.1:{_closed_port()}/api/version"
    with pytest.raises(ollama.OllamaUnreachable) as raised:
        ollama.version(url, timeout=0.3)
    assert "ollama_unreachable" in str(raised.value)


def test_the_guard_allows_the_catalogue_pull_argv(tmp_path):
    root = tmp_path / "engines"
    root.mkdir()
    engines.guard(["ollama", "pull", "qwen3:4b"], root)


def test_the_guard_refuses_every_other_ollama_command(tmp_path):
    root = tmp_path / "engines"
    root.mkdir()
    for argv in (["ollama", "rm", "qwen3:4b"], ["ollama", "serve"],
                 ["ollama", "pull", "../../x"], ["ollama", "pull", "Qwen3:4B"]):
        with pytest.raises(engines.GuardError):
            engines.guard(argv, root)


def test_a_pull_passes_the_catalogue_argv_and_marks_the_host(tmp_path, monkeypatch):
    srv = FakeServer()
    seen: list[list[str]] = []
    monkeypatch.setattr(engines.ollama, "version", lambda *a, **k: "0.40.16")
    monkeypatch.setattr(engines, "_stream",
                        lambda _srv, _job, argv, _cwd, _phase, _pct: (seen.append(argv) or 0, ["ok"]))
    args = _args(tmp_path)

    engines.run_engine_apply(srv, _pull_job(), args)

    assert seen == [["ollama", "pull", "qwen3:4b"]]
    assert (Path(args.models_dir) / "qwen3-4b" / "tag.txt").read_text() == "qwen3:4b"
    path, kw = srv.last()
    assert path.endswith("/complete")
    assert json.loads(kw["data"]["result"])["engines"][0]["id"] == "qwen3-4b"


def test_a_pull_stops_before_exec_when_the_server_is_down(tmp_path, monkeypatch):
    srv = FakeServer()
    ran: list[list[str]] = []

    def _down(*_a, **_k):
        raise ollama.OllamaUnreachable("ollama_unreachable: nothing answers on 127.0.0.1:11434")

    monkeypatch.setattr(engines.ollama, "version", _down)
    monkeypatch.setattr(engines, "_stream",
                        lambda _srv, _job, argv, *_a: (ran.append(argv) or 0, []))
    args = _args(tmp_path)

    engines.run_engine_apply(srv, _pull_job(), args)

    assert ran == []
    path, kw = srv.last()
    assert path.endswith("/fail")
    assert "ollama_unreachable" in kw["json"]["error"]
    assert not (Path(args.models_dir) / "qwen3-4b").exists()


@pytest.mark.skipif(os.name == "nt", reason="CreateProcess cannot launch a .cmd with shell=False; "
                                           "the T-1019 harness owns the executable twins")
def test_a_real_fake_ollama_runs_without_a_real_ollama(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "argv.txt"
    fake = bin_dir / "ollama"
    fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\n', encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(engines.ollama, "version", lambda *a, **k: "0.40.16")

    engines.run_engine_apply(FakeServer(), _pull_job(), _args(tmp_path))

    assert log.read_text().strip() == "pull qwen3:4b"
