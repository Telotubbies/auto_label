"""Shared fixtures for pipeline CLI tests."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "pipeline_cli.py"


@pytest.fixture(scope="session")
def cli_module():
    """Load pipeline_cli.py as a module (importable despite living at repo root)."""
    spec = importlib.util.spec_from_file_location("pipeline_cli", str(CLI_PATH))
    module = importlib.util.module_from_spec(spec)
    # Prevent the module's main() from running during import
    sys.modules["pipeline_cli"] = module
    spec.loader.exec_module(module)
    return module


def make_mock_args(**overrides):
    """Create a MagicMock args object with all CLI attributes pre-set.
    Override any attribute via kwargs.
    """
    defaults = dict(
        mode=None,
        batch=None,
        model=None,
        stage=12,
        conf=0.25,
        iou=0.45,
        imgsz=640,
        device="0",
        fresh=False,
        resume=False,
        prepare=False,
        copy_tmp=False,
        input=None,
        output=None,
        epochs=None,
        batch_size=None,
        workers=None,
        optimizer=None,
        lr0=None,
        patience=None,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


@pytest.fixture
def mock_args():
    """Fixture providing the make_mock_args factory."""
    return make_mock_args


@pytest.fixture
def tmp_raw_dir(tmp_path):
    """Create a temporary data/raw/ directory with sample datasets."""
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)

    # Dataset 1: 3 images
    ds1 = raw / "batch_a"
    ds1.mkdir()
    for i in range(3):
        (ds1 / f"img_{i}.jpg").write_bytes(b"fake")

    # Dataset 2: 5 images
    ds2 = raw / "batch_b"
    ds2.mkdir()
    for i in range(5):
        (ds2 / f"photo_{i}.png").write_bytes(b"fake")

    # Dataset 3: 0 images (should be ignored)
    ds3 = raw / "empty_batch"
    ds3.mkdir()

    # Non-image files should be ignored
    (ds1 / "readme.txt").write_text("not an image")

    return raw
