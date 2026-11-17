"""T-1001: what a worker reports about its own machine.

The probes are faked at the OS seam only: PATH holds no `nvidia-smi`, torch is absent from
sys.modules and shutil.disk_usage is replaced, so no GPU, driver or network is needed.
"""
import json
import sys
from collections import namedtuple
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # apps/worker on the path

from labeldesk_worker import inventory                            # noqa: E402

Usage = namedtuple("Usage", "total used free")


@pytest.fixture
def no_gpu(monkeypatch, tmp_path):
    """Nothing on PATH and no torch: the state of a CPU-only host."""
    empty = tmp_path / "bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setitem(sys.modules, "torch", None)               # `import torch` now raises ImportError
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("LD_ALLOW_ENGINE_INSTALL", raising=False)
    return tmp_path


def test_missing_nvidia_smi_reports_cpu_only(no_gpu):
    d = inventory.collect(no_gpu / "models")

    assert d["gpus"] == []
    assert d["reasons"]["gpus"]
    assert d["cuda"] is None
    assert d["os"] and d["arch"] and d["python"]                    # the rest of the report still lands


def test_disk_and_token_flags_come_from_the_environment(no_gpu, monkeypatch):
    models = no_gpu / "models"
    models.mkdir()
    gib = 1024 ** 3
    monkeypatch.setattr(inventory.shutil, "disk_usage",
                        lambda _p: Usage(total=1863 * gib, used=1862 * gib, free=1 * gib))
    monkeypatch.setenv("HF_TOKEN", "hf_secret-value-that-must-not-leak")

    d = inventory.collect(models)

    assert d["disk"]["models_free_gb"] == 1.0
    assert d["hf_token"] is True
    assert "hf_secret-value-that-must-not-leak" not in json.dumps(d)
