"""Tools that name an app folder must name the current one: apps/frontend and apps/backend."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
LD_TASK = ROOT / "tools" / "ld-task"
CI = ROOT / ".github" / "workflows" / "ci.yml"
FRONTEND = ROOT / "apps" / "frontend"
BACKEND = ROOT / "apps" / "backend"


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ld_task_profiles_point_at_the_current_app_folders() -> None:
    text = LD_TASK.read_text(encoding="utf-8")
    assert 'FRONTEND_APP = "apps/frontend"' in text
    assert 'BACKEND_APP = "apps/backend"' in text
    assert FRONTEND.is_dir() and BACKEND.is_dir()


def test_ci_env_matches_the_app_folders() -> None:
    if not CI.is_file():
        pytest.skip("ci.yml is outside this sparse profile; the integrator and CI see it")
    env = yaml.safe_load(CI.read_text(encoding="utf-8"))["env"]
    assert env["FRONTEND_APP"] == "apps/frontend"
    assert env["BACKEND_APP"] == "apps/backend"


def test_generators_import_the_app_from_apps_backend() -> None:
    for name in ("gen_sdk",):
        module = load_tool(name)
        assert Path(module.BACKEND_DIR) == BACKEND, f"tools/{name}.py points at a stale app folder"
