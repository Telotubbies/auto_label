"""T-1019: the inference suite is hermetic — nothing reaches a real host.

The session fixture below wraps ``socket.socket.connect`` before any test in this module runs:
loopback stays open for the local fixtures, every other address raises ``SocketBlocked`` before DNS
or a connect. The module also proves the worker's mocked installer harness: the fake engine
executables record their argv, and the fake hub answers Range, ETag and the metadata ``lfs.oid``.
"""
import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import pytest

import conftest_inference
from conftest_inference import models_dir  # noqa: F401  # the pytest fixture, injected by name

MIB = 1024 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost", None}
OFFLINE = os.environ.get("LD_INFERENCE_OFFLINE", "1") != "0"
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
HARNESS = Path(__file__).resolve().parents[2] / "worker" / "tests" / "conftest.py"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never route via a proxy


class SocketBlocked(RuntimeError):
    """A test tried to open a real host; the harness allows loopback only."""


def _allowed(sock, address) -> bool:
    if sock.family == getattr(socket, "AF_UNIX", None):
        return True
    return isinstance(address, tuple) and address[0] in LOOPBACK


@pytest.fixture(scope="session", autouse=True)
def no_real_hosts():
    """Fail closed: every non-loopback connect in this session raises ``SocketBlocked``."""
    if not OFFLINE:
        yield
        return

    def connect(self, address):
        if not _allowed(self, address):
            raise SocketBlocked(f"blocked a connection to {address[0]}: the inference suite is offline")
        return _REAL_CONNECT(self, address)

    def connect_ex(self, address):
        if not _allowed(self, address):
            raise SocketBlocked(f"blocked a connection to {address[0]}: the inference suite is offline")
        return _REAL_CONNECT_EX(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    try:
        yield
    finally:
        socket.socket.connect = _REAL_CONNECT
        socket.socket.connect_ex = _REAL_CONNECT_EX


def _harness():
    """Load the worker's harness module under its own name, so backend and worker conftests coexist."""
    spec = importlib.util.spec_from_file_location("ld_worker_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _weights_over_one_mib(root: Path) -> list[str]:
    """Every weight file above 1 MiB in the repo tree; a downloaded checkpoint must never appear."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            if name.endswith((".gguf", ".safetensors", ".bin")):
                path = Path(dirpath) / name
                if path.stat().st_size > MIB:
                    found.append(str(path.relative_to(root)))
    return found


@pytest.mark.skipif(not OFFLINE, reason="the guard is disabled by LD_INFERENCE_OFFLINE=0")
def test_no_test_opens_a_real_host():
    assert socket.socket.connect is not _REAL_CONNECT, "the session socket wrapper is not installed"
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        with socket.socket() as client:
            client.connect(server.getsockname())        # the local fixtures keep working
    finally:
        server.close()


@pytest.mark.skipif(not OFFLINE, reason="the guard is disabled by LD_INFERENCE_OFFLINE=0")
@pytest.mark.parametrize("host", ["huggingface.co", "pypi.org", "registry-1.docker.io"])
def test_the_guard_itself_fails_closed(host):
    with socket.socket() as client:
        with pytest.raises(SocketBlocked):
            client.connect((host, 443))


def test_the_models_directory_is_a_temp_path(models_dir):  # noqa: F811  # pytest injects the fixture
    models = Path(os.environ["LD_MODELS_DIR"]).resolve()
    root = Path(tempfile.gettempdir()).resolve()
    assert root in models.parents
    assert Path(models_dir).resolve() == models == conftest_inference.MODELS_DIR.resolve()
    assert _weights_over_one_mib(Path(__file__).resolve().parents[3]) == []


def test_fake_uv_records_its_argv(tmp_path):
    harness = _harness()
    env = harness.fake_env(tmp_path)
    proc = subprocess.run([harness.fake_executable("uv"), "venv", "vllm-1.0.0"],  # noqa: S603  # our own fake
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert harness.read_fake_log(env["FAKE_LOG"]) == [["uv", "venv", "vllm-1.0.0"]]


def test_fake_hub_serves_a_1_mib_file_with_range_support():
    harness = _harness()
    with harness.FakeHub() as hub:
        with OPENER.open(hub.url + "/file") as response:
            assert response.status == 200
            assert response.headers["ETag"].strip('"') == hub.sha256
            assert len(response.read()) == MIB
        request = urllib.request.Request(hub.url + "/file",  # noqa: S310  # the loopback fake only
                                         headers={"Range": "bytes=409600-"})
        with OPENER.open(request) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == f"bytes 409600-{MIB - 1}/{MIB}"
            assert response.read() == hub.data[409600:]


def test_fake_hub_metadata_reports_lfs_oid():
    harness = _harness()
    with harness.FakeHub() as hub:
        with OPENER.open(hub.metadata_url) as response:
            body = json.load(response)
    entry = body["siblings"][0]
    assert entry["rfilename"] == hub.filename and entry["size"] == MIB
    assert entry["lfs"]["oid"] == hub.sha256


def test_paths_are_created_under_tmp_and_removed():
    harness = _harness()
    root = Path(harness.make_root())
    base = Path(tempfile.gettempdir()).resolve()
    try:
        assert root.is_dir() and base in root.resolve().parents
        (root / "probe.bin").write_bytes(b"x")
    finally:
        harness.drop_root(root)
    assert not root.exists()
