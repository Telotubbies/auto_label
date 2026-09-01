import argparse
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import batch_segment
from config import Category, CheckpointConfig, Config, InferenceConfig, OutputConfig


def make_config(tmp_path, *, checkpoint=None):
    return Config(
        categories=[Category(1, "person", "person")],
        output=OutputConfig(output_dir=str(tmp_path)),
        checkpoint=checkpoint or CheckpointConfig(),
    )


def make_args(**overrides):
    values = {
        "threshold": None,
        "resolution": None,
        "device": None,
        "input": None,
        "output": None,
        "resume": False,
        "fresh": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_apply_cli_overrides_updates_config_and_validates(tmp_path):
    cfg = make_config(tmp_path)

    batch_segment.apply_cli_overrides(
        cfg,
        make_args(threshold=0.6, resolution=640, device="cpu", input="in", output="out"),
    )

    assert cfg.inference == InferenceConfig(confidence_threshold=0.6, resolution=640, device="cpu")
    assert cfg.output.input_dir == "in"
    assert cfg.output.output_dir == "out"


def test_apply_cli_overrides_rejects_invalid_threshold(tmp_path):
    cfg = make_config(tmp_path)

    with pytest.raises(ValueError, match="inference.confidence_threshold"):
        batch_segment.apply_cli_overrides(cfg, make_args(threshold=1.5))


def test_disabled_checkpoint_does_not_write(tmp_path):
    cfg = make_config(tmp_path, checkpoint=CheckpointConfig(enabled=False))

    batch_segment.save_checkpoint(cfg, {"processed": {}})

    assert not Path(batch_segment.checkpoint_path(cfg)).exists()


@pytest.mark.parametrize(
    ("args", "auto_resume", "interactive", "expected"),
    [
        (make_args(resume=True), False, False, True),
        (make_args(), True, False, True),
        (make_args(), False, False, False),
        (make_args(fresh=True), True, False, False),
    ],
)
def test_should_resume_checkpoint_uses_cli_and_config(args, auto_resume, interactive, expected, tmp_path):
    cfg = make_config(tmp_path, checkpoint=CheckpointConfig(auto_resume=auto_resume))

    assert batch_segment.should_resume_checkpoint(cfg, args, {"processed": {}}, interactive) is expected


def test_export_image_adds_image_context_to_failure(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(batch_segment, "save_coco", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(RuntimeError, match="photo.jpg") as exc_info:
        batch_segment.export_image(cfg, object(), "photo", "photo.jpg", {"id": 1}, [])

    assert "disk full" in str(exc_info.value)


def test_complete_export_commits_only_after_future_succeeds(tmp_path):
    cfg = make_config(tmp_path)
    future = Future()
    future.set_result(None)
    processed = {}
    checkpoint = {"processed": {}}
    images = []
    annotations = []
    errors = []
    result = {
        "image_info": {"id": 1, "file_name": "photo.jpg"},
        "annotations": [{"id": 1}],
        "elapsed": 1.25,
    }

    state = batch_segment.BatchResults(
        processed, checkpoint, MagicMock(), None, images, annotations, errors,
    )
    succeeded = batch_segment.complete_export(cfg, future, result, state)

    assert succeeded is True
    assert images == [result["image_info"]]
    assert annotations == result["annotations"]
    assert processed["photo.jpg"] == {"time": 1.2, "annotations": 1}
    assert errors == []


def test_complete_export_records_failure_without_committing_result(tmp_path):
    cfg = make_config(tmp_path)
    future = Future()
    future.set_exception(OSError("disk full"))
    processed = {}
    checkpoint = {"processed": {}}
    images = []
    annotations = []
    errors = []
    result = {
        "image_info": {"id": 1, "file_name": "photo.jpg"},
        "annotations": [{"id": 1}],
        "elapsed": 1.25,
    }

    state = batch_segment.BatchResults(
        processed, checkpoint, MagicMock(), None, images, annotations, errors,
    )
    succeeded = batch_segment.complete_export(cfg, future, result, state)

    assert succeeded is False
    assert images == []
    assert annotations == []
    assert processed["photo.jpg"]["error"] == "disk full"
    assert errors == [{"image": "photo.jpg", "error": "disk full"}]


def test_main_returns_failure_when_background_export_fails(monkeypatch, tmp_path):
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"not-used")
    cfg = make_config(tmp_path, checkpoint=CheckpointConfig(enabled=False))
    cfg.inference.pipeline_export = True
    cfg.output.input_dir = str(tmp_path)
    cfg.output.save_viz = False
    args = make_args()
    args.config = "config.yaml"
    tracker = MagicMock()
    tracker.start_run.return_value = "run-1"

    monkeypatch.setattr(batch_segment, "parse_args", lambda: args)
    monkeypatch.setattr(batch_segment, "load_config", lambda path: cfg)
    monkeypatch.setattr(batch_segment, "glob", lambda pattern: [str(image_path)])
    monkeypatch.setattr(batch_segment, "build_model", lambda config: object())
    monkeypatch.setattr(batch_segment, "segment_image", lambda *args: ([], 1))
    monkeypatch.setattr(batch_segment.Image, "open", lambda path: batch_segment.Image.new("RGB", (10, 10)))
    monkeypatch.setattr(batch_segment, "save_coco", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(batch_segment, "finalize_exports", lambda *args: None)
    monkeypatch.setattr(batch_segment, "ExperimentTracker", lambda config: tracker)

    exit_code = batch_segment.main()

    assert exit_code == 1
    tracker.end_run.assert_called_once_with("run-1", status="failed")
