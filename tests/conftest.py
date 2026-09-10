"""Shared pytest fixtures for the auto_label test suite."""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def pipeline_cli():
    """Import pipeline_cli as a module (it is not inside a package)."""
    sys.path.insert(0, str(REPO_ROOT))
    import pipeline_cli
    return pipeline_cli


@pytest.fixture(scope="session")
def config_module():
    """Import the SAM config module."""
    sys.path.insert(0, str(REPO_ROOT / "sam3_auto_label" / "src"))
    import config
    return config


def _load_module_from_file(name: str, filepath: Path):
    """Load a standalone script as a module without requiring it on sys.path."""
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def prepare_dataset_module():
    """Load 01_prepare_dataset.py as a module for its pure helper functions."""
    filepath = REPO_ROOT / "yolo26_ppe" / "scripts" / "pipeline" / "01_prepare_dataset.py"
    return _load_module_from_file("prepare_dataset", filepath)


@pytest.fixture(scope="session")
def focal_patch_module():
    """Load focal_patch.py as a module."""
    filepath = REPO_ROOT / "yolo26_ppe" / "focal_patch.py"
    return _load_module_from_file("focal_patch", filepath)
