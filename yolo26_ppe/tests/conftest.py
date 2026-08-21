"""Shared fixtures for yolo26_ppe pipeline tests."""
import importlib.util
import os

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PPE_DIR = os.path.join(BASE, "yolo26_ppe")
PREPARE_SCRIPT = os.path.join(PPE_DIR, "scripts", "01_prepare_data.py")

# Heavy deps of 01_prepare_data.py — skip unit tests if the runner lacks them
pytest.importorskip("numpy", reason="numpy not installed in this environment")
pytest.importorskip("cv2", reason="opencv not installed in this environment")
pytest.importorskip("pycocotools", reason="pycocotools not installed in this environment")


@pytest.fixture(scope="session")
def prepare_module():
    """Load 01_prepare_data.py as a module (filename starts with digits)."""
    spec = importlib.util.spec_from_file_location("prepare_data", PREPARE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
