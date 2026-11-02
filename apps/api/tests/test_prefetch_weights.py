"""TDD for ``tools/prefetch_weights.py``: plan order, check/dry-run modes and injected downloads."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[3] / "tools" / "prefetch_weights.py"
CHECKPOINTS = [
    "rtdetr-l.pt",
    "yolov8s-worldv2.pt",
    "yolov8m-worldv2.pt",
    "yolo11n.pt",
    "yolo11s.pt",
]
VLM = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"
# A real zoo checkpoint is megabytes; the tool refuses to treat a stub as present.
PLAUSIBLE_CHECKPOINT_BYTES = 2 * 1024 * 1024


def _write_checkpoint(path: Path, size: int = PLAUSIBLE_CHECKPOINT_BYTES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.truncate(size)


def _seed_hub(
    tmp_path: Path,
    *,
    sealed: bool = False,
    incomplete: bool = False,
    weight_bytes: int = 1024,
) -> Path:
    """Build an ``HF_HUB_CACHE`` for ``VLM``; ``sealed=False`` models a cut connection."""
    hub = tmp_path / "hub"
    model_dir = hub / f"models--{VLM.replace('/', '--')}"
    (model_dir / "blobs").mkdir(parents=True)
    if incomplete:
        (model_dir / "blobs" / "abc.incomplete").write_bytes(b"partial")
    if sealed:
        snapshot = model_dir / "snapshots" / "rev1"
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").write_text("{}", encoding="utf-8")
        with (snapshot / "model.safetensors").open("wb") as handle:
            handle.truncate(weight_bytes)
    return hub


def _load_tool():
    spec = importlib.util.spec_from_file_location("prefetch_weights_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prefetch = _load_tool()


def test_plan_lists_the_five_checkpoints_then_the_vlm_model():
    plan = prefetch.build_plan()
    assert [item.name for item in plan] == [*CHECKPOINTS, VLM]
    assert [item.kind for item in plan] == ["ultralytics"] * 5 + ["vlm"]


def test_skip_vlm_removes_only_the_model():
    assert [item.name for item in prefetch.build_plan(skip_vlm=True)] == CHECKPOINTS


def test_check_reports_present_and_missing_and_exits_one(tmp_path, capsys):
    _write_checkpoint(tmp_path / "yolo11s.pt")
    rc = prefetch.main(["--check", "--pretrained-dir", str(tmp_path), "--skip-vlm"])
    lines = capsys.readouterr().out.splitlines()
    assert rc == 1
    assert "PASS yolo11s.pt (present)" in lines
    assert any(line.startswith("FAIL rtdetr-l.pt (") for line in lines)
    assert lines[-1].startswith("summary:")


def test_dry_run_prints_every_action_without_network(tmp_path, capsys, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("dry run must not touch the network")

    monkeypatch.setattr(prefetch, "_load_ultralytics", boom)
    monkeypatch.setattr(prefetch, "_run_hf", boom)
    rc = prefetch.main(["--dry-run", "--pretrained-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    for name in [*CHECKPOINTS, VLM]:
        assert name in out
    assert out.count("PLAN ") == 6
    assert not (tmp_path / "rtdetr-l.pt").exists()


def test_run_copies_each_checkpoint_and_builds_clip_once(tmp_path, capsys, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    dest = tmp_path / "pretrained"
    loaded: list[str] = []
    clip_calls: list[list[str]] = []
    hf_calls: list[list[str]] = []

    class FakeModel:
        def __init__(self, name: str) -> None:
            self.ckpt_path = sources / name
            self.ckpt_path.write_bytes(b"weights")

        def set_classes(self, classes: list[str]) -> None:
            clip_calls.append(list(classes))

    def loader(name: str) -> FakeModel:
        loaded.append(name)
        return FakeModel(name)

    def hf_runner(cmd: list[str]) -> int:
        hf_calls.append(cmd)
        return 0

    monkeypatch.setattr(prefetch, "_hf_command", lambda: "huggingface-cli")
    monkeypatch.setattr(prefetch, "vlm_cached", lambda *_args, **_kwargs: False)
    rc = prefetch.run(pretrained_dir=dest, loader=loader, hf_runner=hf_runner)
    assert rc == 0
    assert loaded == CHECKPOINTS
    assert clip_calls == [["person"], ["person"]]
    assert hf_calls == [["huggingface-cli", "download", VLM]]
    for name in CHECKPOINTS:
        assert (dest / name).read_bytes() == b"weights"


def test_run_skips_existing_checkpoints(tmp_path, monkeypatch, capsys):
    dest = tmp_path / "pretrained"
    dest.mkdir()
    for name in CHECKPOINTS:
        _write_checkpoint(dest / name)

    def boom(*_args, **_kwargs):
        raise AssertionError("present checkpoints must not be downloaded again")

    monkeypatch.setattr(prefetch, "vlm_cached", lambda *_args, **_kwargs: True)
    rc = prefetch.run(pretrained_dir=dest, loader=boom, hf_runner=boom)
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert all(f"PASS {name} (present)" in lines for name in CHECKPOINTS)


def test_loader_runs_inside_dest_so_hub_downloads_do_not_litter_cwd(tmp_path, monkeypatch):
    dest = tmp_path / "pretrained"
    seen: list[Path] = []

    class FakeModel:
        def __init__(self, name: str) -> None:
            seen.append(Path.cwd())
            self.ckpt_path = Path.cwd() / name
            self.ckpt_path.write_bytes(b"weights")

        def set_classes(self, _classes: list[str]) -> None:
            pass

    monkeypatch.setattr(prefetch, "vlm_cached", lambda *_args, **_kwargs: True)
    rc = prefetch.run(pretrained_dir=dest, loader=FakeModel, hf_runner=lambda _cmd: 0)
    assert rc == 0
    assert seen and all(cwd == dest.resolve() for cwd in seen)
    assert (dest / "rtdetr-l.pt").is_file()


def test_failed_loader_reports_fail_without_raising(tmp_path, monkeypatch, capsys):
    def loader(_name: str):
        raise RuntimeError("hub unreachable")

    monkeypatch.setattr(prefetch, "vlm_cached", lambda *_args, **_kwargs: True)
    rc = prefetch.run(pretrained_dir=tmp_path / "pretrained", loader=loader, hf_runner=lambda _cmd: 0)
    lines = capsys.readouterr().out.splitlines()
    assert rc == 1
    assert "FAIL rtdetr-l.pt (hub unreachable)" in lines
    assert lines[-1].startswith("summary:")


def test_partial_vlm_cache_is_not_cached(tmp_path):
    hub = _seed_hub(tmp_path, incomplete=True)
    assert prefetch.vlm_cached(VLM, hub_dir=hub) is False


def test_sealed_vlm_cache_is_cached(tmp_path):
    hub = _seed_hub(tmp_path, sealed=True)
    assert prefetch.vlm_cached(VLM, hub_dir=hub) is True


def test_zero_byte_weight_in_snapshot_is_not_cached(tmp_path):
    hub = _seed_hub(tmp_path, sealed=True, weight_bytes=0)
    assert prefetch.vlm_cached(VLM, hub_dir=hub) is False


def test_incomplete_blob_blocks_an_otherwise_sealed_snapshot(tmp_path):
    hub = _seed_hub(tmp_path, sealed=True, incomplete=True)
    assert prefetch.vlm_cached(VLM, hub_dir=hub) is False


def test_check_fails_an_interrupted_vlm_download(tmp_path, monkeypatch, capsys):
    hub = _seed_hub(tmp_path, incomplete=True)
    dest = tmp_path / "pretrained"
    for name in CHECKPOINTS:
        _write_checkpoint(dest / name)
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    rc = prefetch.run(pretrained_dir=dest, check=True)
    lines = capsys.readouterr().out.splitlines()
    assert rc == 1
    assert any(line.startswith(f"FAIL {VLM} (") for line in lines)
    assert f"PASS {VLM} (present in Hugging Face cache)" not in lines


def test_interrupted_vlm_download_is_retried(tmp_path, monkeypatch, capsys):
    hub = _seed_hub(tmp_path, incomplete=True)
    dest = tmp_path / "pretrained"
    for name in CHECKPOINTS:
        _write_checkpoint(dest / name)

    def boom(*_args, **_kwargs):
        raise AssertionError("sealed checkpoints must not be downloaded again")

    hf_calls: list[list[str]] = []

    def hf_runner(cmd: list[str]) -> int:
        hf_calls.append(cmd)
        return 0

    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    monkeypatch.setattr(prefetch, "_hf_command", lambda: "huggingface-cli")
    rc = prefetch.run(pretrained_dir=dest, loader=boom, hf_runner=hf_runner)
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert hf_calls == [["huggingface-cli", "download", VLM]]
    assert f"PASS {VLM} (downloaded)" in lines


def test_check_reports_a_zero_byte_checkpoint_as_fail(tmp_path, capsys):
    _write_checkpoint(tmp_path / "yolo11s.pt", size=0)
    rc = prefetch.main(["--check", "--pretrained-dir", str(tmp_path), "--skip-vlm"])
    lines = capsys.readouterr().out.splitlines()
    assert rc == 1
    assert any(line.startswith("FAIL yolo11s.pt (") for line in lines)
    assert "PASS yolo11s.pt (present)" not in lines


def test_zero_byte_checkpoint_is_downloaded_again(tmp_path, monkeypatch, capsys):
    dest = tmp_path / "pretrained"
    dest.mkdir()
    for name in CHECKPOINTS:
        _write_checkpoint(dest / name)
    _write_checkpoint(dest / "yolo11s.pt", size=0)
    loaded: list[str] = []

    class FakeModel:
        def __init__(self, name: str) -> None:
            loaded.append(name)
            self.ckpt_path = Path.cwd() / name
            self.ckpt_path.write_bytes(b"weights")

        def set_classes(self, _classes: list[str]) -> None:
            pass

    monkeypatch.setattr(prefetch, "vlm_cached", lambda *_args, **_kwargs: True)
    rc = prefetch.run(pretrained_dir=dest, loader=FakeModel, hf_runner=lambda _cmd: 0)
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert loaded == ["yolo11s.pt"]
    assert "PASS yolo11s.pt (downloaded)" in lines

