"""T-1019: the mocked installer harness.

The worker calls ``subprocess`` and a hub client, so the fakes are real executables and a real local
HTTP server, not Python mocks: mocking ``subprocess`` would test the mock, not the argv. ``fake_env``
puts the scripts first on ``PATH`` and points ``FAKE_LOG`` at a throwaway file; ``FakeHub`` serves
one deterministic 1 MiB file with Range, ETag and the metadata ``lfs.oid`` the download verifies.
Nothing here creates a weight file, and the hub is loopback-only.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

FAKES = Path(__file__).resolve().parent / "fakes"
MIB = 1024 * 1024
FILENAME = "model.safetensors"
REPO = "labeldesk/fixture"
REVISION = "0" * 40
DATA = bytes(range(256)) * (MIB // 256)
DIGEST = hashlib.sha256(DATA).hexdigest()
METADATA = re.compile(r"/api/models/([^/]+/[^/]+)/revision/([^/]+)")


def _tmp_base() -> Path:
    base = Path(os.environ.get("LD_TEST_TMP") or tempfile.gettempdir()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def make_root() -> Path:
    """A fresh directory under the test temp root; the caller removes it with ``drop_root``."""
    return Path(tempfile.mkdtemp(prefix="ld-t1019-", dir=_tmp_base()))


def drop_root(root) -> None:
    shutil.rmtree(root, ignore_errors=True)


def fake_env(work) -> dict:
    """An environment with the fakes first on ``PATH`` and every invocation appended to ``FAKE_LOG``."""
    env = dict(os.environ)
    env["PATH"] = str(FAKES) + os.pathsep + env.get("PATH", "")
    env["FAKE_LOG"] = str(Path(work) / "fake-argv.log")
    env["FAKE_EXIT"] = "0"
    return env


def fake_executable(name: str) -> str:
    """The fake's path on this OS; Windows runs the ``.cmd`` twin because it cannot execute a shebang."""
    suffix = ".cmd" if os.name == "nt" else ""
    return str(FAKES / f"{name}{suffix}")


def read_fake_log(path) -> list[list[str]]:
    """One tab-separated argv per line, in call order."""
    return [line.split("\t") for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


class FakeHub:
    """Loopback stand-in for the Hugging Face endpoints the worker reads, plus ``/file``.

    ``/file`` supports ``Range`` (206), ``ETag`` and ``HEAD``; the metadata route returns the one
    sibling with ``lfs.oid`` equal to the file digest, so a checksum test is a real test.
    """

    def __init__(self):
        self.data = DATA
        self.sha256 = DIGEST
        self.filename = FILENAME
        self.repo, self.revision = REPO, REVISION
        hub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):        # the test report stays quiet
                pass

            def do_HEAD(self):
                self._serve(head=True)

            def do_GET(self):
                self._serve(head=False)

            def _serve(self, head):
                path = urlsplit(self.path).path
                if path == "/file":
                    self._file(head)
                elif METADATA.fullmatch(path):
                    self._metadata(path, head)
                else:
                    self._json({"error": "not found"}, head, status=404)

            def _json(self, body, head, status=200):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                if not head:
                    self.wfile.write(raw)

            def _range(self):
                raw = self.headers.get("Range")
                if not raw:
                    return None
                if not raw.startswith("bytes="):
                    return False
                first, _, last = raw[6:].split(",")[0].partition("-")
                if not first.isdigit():
                    return False
                start = int(first)
                end = int(last) + 1 if last.isdigit() else len(hub.data)
                if start >= len(hub.data) or end <= start:
                    return False
                return start, min(end, len(hub.data))

            def _file(self, head):
                span = self._range()
                if span is False:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(hub.data)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                start, end = span or (0, len(hub.data))
                body = hub.data[start:end]
                self.send_response(206 if span else 200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("ETag", f'"{hub.sha256}"')
                if span:
                    self.send_header("Content-Range", f"bytes {start}-{end - 1}/{len(hub.data)}")
                self.end_headers()
                if not head:
                    self.wfile.write(body)

            def _metadata(self, path, head):
                repo, revision = METADATA.fullmatch(path).groups()
                self._json({"id": repo, "sha": revision, "siblings": [{
                    "rfilename": hub.filename, "size": len(hub.data), "blobId": hub.sha256,
                    "lfs": {"oid": hub.sha256, "sha256": hub.sha256,
                            "size": len(hub.data), "pointerSize": 134}}]}, head)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    @property
    def metadata_url(self) -> str:
        return f"{self.url}/api/models/{self.repo}/revision/{self.revision}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


@pytest.fixture(autouse=True, scope="session")
def _models_dir():
    """No worker test may fall back to ``~/.labeldesk/models``; the path is under the temp root."""
    os.environ["LD_MODELS_DIR"] = str(_tmp_base() / "labeldesk-worker-models")
    yield


@pytest.fixture(scope="session")
def inference_tmp():
    """One session directory under the test temp root, removed when the session ends."""
    root = make_root()
    yield root
    drop_root(root)


@pytest.fixture
def fake_tools(tmp_path, monkeypatch) -> Path:
    """Put the fake ``uv``/``python``/``docker`` first on ``PATH``; returns the argv log."""
    env = fake_env(tmp_path)
    for key in ("PATH", "FAKE_LOG", "FAKE_EXIT"):
        monkeypatch.setenv(key, env[key])
    return Path(env["FAKE_LOG"])


@pytest.fixture
def fake_hub(monkeypatch):
    """A loopback hub; both ``HF_ENDPOINT`` and an already-imported client point at it."""
    with FakeHub() as hub:
        monkeypatch.setenv("HF_ENDPOINT", hub.url)
        try:
            from huggingface_hub import constants
        except ImportError:
            pass                                    # the base worker has no hub extra; the URL is enough
        else:
            monkeypatch.setattr(constants, "ENDPOINT", hub.url)
        yield hub
