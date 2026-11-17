"""T-1011: a model download resumes, verifies and never fills the disk.

The hub is a fake module: it serves bytes from memory, honours the partial ``.incomplete`` file the
same way the real client does, and reports progress through the ``tqdm_class`` hook. No test opens
a socket. ``model_pull.disk_usage`` is the one seam that lets a test move the free-space needle
mid-transfer.
"""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # apps/worker on the path

from labeldesk_worker import hf, model_pull                   # noqa: E402

MIB = 1024 * 1024
GIB = 1024 ** 3


class FakeServer:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def post(self, path, **kw):
        self.calls.append((path, kw))
        return {"cancel": False}

    def progress(self) -> list[dict]:
        return [kw.get("json") or {} for name, kw in self.calls if name.endswith("/progress")]

    def last(self) -> tuple[str, dict]:
        return self.calls[-1]

    def complete(self) -> dict:
        name, kw = self.last()
        assert name.endswith("/complete")
        return json.loads(kw["data"]["result"])


class _Api:
    def __init__(self, hub):
        self.hub = hub

    def model_info(self, repo, revision=None, token=None, files_metadata=False):
        self.hub.metadata_calls += 1
        self.hub.metadata_args = {"repo": repo, "revision": revision, "token": token}
        siblings = []
        for path, data in self.hub.data.items():
            oid = self.hub.oids.get(path)
            siblings.append(SimpleNamespace(
                rfilename=path, size=len(data),
                lfs=SimpleNamespace(sha256=oid) if oid else None))
        return SimpleNamespace(siblings=siblings)


class FakeHub:
    """A hub that writes from memory; ``after_chunk`` lets a test change the world mid-file."""

    def __init__(self, data: dict[str, bytes], oids: dict[str, str | None] | None = None):
        self.data, self.oids = data, oids or {}
        self.downloads: list[dict] = []
        self.metadata_calls = 0
        self.metadata_args: dict = {}
        self.after_chunk = None

    def HfApi(self):
        return _Api(self)

    def hf_hub_download(self, repo_id, revision, filename, local_dir, token=None,
                        resume=True, tqdm_class=None):
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        incomplete = path.with_name(path.name + ".incomplete")
        start = incomplete.stat().st_size if incomplete.exists() else (
            path.stat().st_size if path.exists() else 0)
        self.downloads.append({"filename": filename, "resume_from": start, "resume": resume,
                               "token": token, "repo": repo_id, "revision": revision})
        bar = tqdm_class(total=len(self.data[filename]), initial=start) if tqdm_class else None
        remaining = self.data[filename][start:]
        chunk = max(1, len(remaining) // 4)
        with open(path, "wb") as handle:
            if start:
                handle.write(self.data[filename][:start])   # the resumed prefix moves into place
            for offset in range(0, len(remaining), chunk):
                piece = remaining[offset:offset + chunk]
                handle.write(piece)
                handle.flush()
                if bar:
                    bar.update(len(piece))
                if self.after_chunk:
                    self.after_chunk(filename)
        if incomplete.exists():
            incomplete.unlink()
        return str(path)


def _payload(files: list[dict], target: str = "qwen/bf16", action: str = "download") -> dict:
    return {"host": "gpu-a", "action": action, "repo": "Qwen/Qwen2.5-VL-7B-Instruct",
            "revision": "cc594898137f460bfe9f0759e9844b3ce807cfb5",
            "files": files, "target": target,
            "total_bytes": sum(file["bytes"] for file in files)}


def _job(payload: dict) -> dict:
    return {"id": "job-model-1", "payload": payload}


def _args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(models_dir=str(tmp_path / "models"))


def _hub(monkeypatch, data: dict[str, bytes], oids: dict[str, str | None] | None = None) -> FakeHub:
    fake = FakeHub(data, oids)
    monkeypatch.setattr(hf, "_hub", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _no_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)


def test_resume_starts_from_the_partial_file(tmp_path, monkeypatch):
    data = {"model.safetensors": bytes(range(256)) * (MIB // 256)}
    fake = _hub(monkeypatch, data)
    partial = tmp_path / "models" / "qwen" / "bf16.partial"
    partial.mkdir(parents=True)
    prefix = data["model.safetensors"][:400 * 1024]
    (partial / "model.safetensors.incomplete").write_bytes(prefix)
    srv = FakeServer()

    model_pull.run_model_pull(srv, _job(_payload(
        [{"path": "model.safetensors", "bytes": len(data["model.safetensors"]), "sha256": None}])),
        _args(tmp_path))

    assert fake.downloads[0]["resume_from"] == 400 * 1024
    assert fake.downloads[0]["resume"] is True
    target = tmp_path / "models" / "qwen" / "bf16"
    assert (target / "model.safetensors").read_bytes() == data["model.safetensors"]
    assert not partial.exists()
    assert srv.complete()["files"][0]["verified"] == "size"
    assert any("resuming at" in line for line in
               [line for post in srv.progress() for line in post.get("log") or []])


def test_checksum_mismatch_deletes_the_partial_directory(tmp_path, monkeypatch):
    content = b"x" * 4096
    fake = _hub(monkeypatch, {"model.safetensors": content},
                {"model.safetensors": "0" * 64})
    srv = FakeServer()
    payload = _payload([{"path": "model.safetensors", "bytes": len(content),
                         "sha256": "0" * 64}])

    model_pull.run_model_pull(srv, _job(payload), _args(tmp_path))

    name, kw = srv.last()
    assert name.endswith("/fail")
    assert "checksum_failed" in kw["json"]["error"]
    assert not (tmp_path / "models" / "qwen" / "bf16.partial").exists()
    assert not (tmp_path / "models" / "qwen" / "bf16").exists()
    assert any(post.get("phase") == "verifying" for post in srv.progress())
    assert fake.downloads[0]["filename"] == "model.safetensors"


def test_disk_full_before_the_first_byte(tmp_path, monkeypatch):
    data = {"model.safetensors": b"y" * 2048}
    fake = _hub(monkeypatch, data)
    monkeypatch.setattr(model_pull, "disk_usage",
                        lambda _path: SimpleNamespace(free=100 * MIB, total=200 * MIB,
                                                      used=100 * MIB))
    srv = FakeServer()
    payload = _payload([{"path": "model.safetensors", "bytes": GIB, "sha256": None}])

    model_pull.run_model_pull(srv, _job(payload), _args(tmp_path))

    name, kw = srv.last()
    assert name.endswith("/fail")
    assert "disk_full" in kw["json"]["error"] and "short" in kw["json"]["error"]
    assert fake.downloads == []
    assert not (tmp_path / "models" / "qwen" / "bf16.partial").exists()
    assert not list((tmp_path / "models").rglob("*.safetensors"))


def test_disk_full_mid_transfer_aborts(tmp_path, monkeypatch):
    data = {"model.safetensors": bytes(range(256)) * (MIB // 256)}
    fake = _hub(monkeypatch, data)
    free = [10 * GIB]

    def shrink(_filename):
        free[0] = 1 * MIB                      # the volume fills while the file is arriving

    fake.after_chunk = shrink
    monkeypatch.setattr(model_pull, "disk_usage",
                        lambda _path: SimpleNamespace(free=free[0], total=20 * GIB,
                                                      used=20 * GIB - free[0]))
    srv = FakeServer()

    model_pull.run_model_pull(srv, _job(_payload(
        [{"path": "model.safetensors", "bytes": len(data["model.safetensors"]), "sha256": None}])),
        _args(tmp_path))

    name, kw = srv.last()
    assert name.endswith("/fail")
    assert "disk_full" in kw["json"]["error"]
    assert not (tmp_path / "models" / "qwen" / "bf16.partial").exists()
    assert not (tmp_path / "models" / "qwen" / "bf16").exists()


@pytest.mark.parametrize("path", ["../../etc/passwd", "/etc/passwd", "C:\\Windows\\x",
                                  "files/../../../etc/passwd"])
def test_a_path_outside_the_target_is_refused(tmp_path, monkeypatch, path):
    fake = _hub(monkeypatch, {"ok.bin": b"ok"})
    srv = FakeServer()

    with pytest.raises(model_pull.GuardError):
        model_pull.run_model_pull(
            srv, _job(_payload([{"path": path, "bytes": 2, "sha256": None}])), _args(tmp_path))

    assert fake.metadata_calls == 0
    assert fake.downloads == []
    assert srv.calls == []


def test_a_target_outside_the_models_directory_is_refused(tmp_path, monkeypatch):
    _hub(monkeypatch, {"ok.bin": b"ok"})
    srv = FakeServer()
    for target in ("../escape/bf16", "/abs/bf16", "qwen", "qwen/bf16/extra"):
        with pytest.raises(model_pull.GuardError):
            model_pull.run_model_pull(
                srv, _job(_payload([{"path": "ok.bin", "bytes": 2, "sha256": None}],
                                   target=target)), _args(tmp_path))
    assert srv.calls == []


def test_token_is_never_logged(tmp_path, monkeypatch):
    token = "hf_" + "s3cret" * 5
    monkeypatch.setenv("HF_TOKEN", token)
    data = {"model.safetensors": b"z" * 1024}
    fake = _hub(monkeypatch, data)
    srv = FakeServer()

    model_pull.run_model_pull(srv, _job(_payload(
        [{"path": "model.safetensors", "bytes": 1024, "sha256": None}])), _args(tmp_path))

    posted = json.dumps(srv.calls)
    assert token not in posted
    assert fake.downloads[0]["token"] == token          # the hub receives it, the log does not
    assert "hf_" not in posted.replace("hf_***", "")


def test_missing_extra_names_the_install_command(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)     # an import that must fail
    srv = FakeServer()

    with pytest.raises(hf.MissingExtra) as raised:
        model_pull.run_model_pull(
            srv, _job(_payload([{"path": "ok.bin", "bytes": 2, "sha256": None}])), _args(tmp_path))

    assert "missing_extra" in str(raised.value)
    assert 'pip install "labeldesk-worker[inference]"' in str(raised.value)


def test_remove_frees_the_target(tmp_path, monkeypatch):
    _hub(monkeypatch, {"ok.bin": b"ok"})
    target = tmp_path / "models" / "qwen" / "bf16"
    target.mkdir(parents=True)
    (target / "a.bin").write_bytes(b"a" * 1024)
    (target / "b.bin").write_bytes(b"b" * 2048)
    monkeypatch.setattr(model_pull, "disk_usage",
                        lambda _path: SimpleNamespace(free=5 * GIB, total=10 * GIB, used=5 * GIB))
    srv = FakeServer()

    model_pull.run_model_pull(srv, _job(_payload([], action="remove")), _args(tmp_path))

    assert not target.exists()
    result = srv.complete()
    assert result["freed_bytes"] == 3072
    assert result["disk_free_gb"] == 5.0
    assert any(post.get("phase", "").startswith("removing") for post in srv.progress())
    assert os.sep not in result["target"] and ":" not in result["target"]
