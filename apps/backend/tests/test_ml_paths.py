"""The ML code lives in a sibling repo (../labeldesk-ml): the backend reaches it only through
env vars, and every feature degrades cleanly when that checkout is absent.

These tests pin the env-var contract and the missing-path fallbacks, because a failed lookup must
never crash an install that runs without the ML repo (SAM off, hub weights, no demo model).
"""

import os
import tempfile
from types import SimpleNamespace

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-test-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
for _var in ("LD_SAM_ROOT", "LD_PRETRAINED_DIR", "LD_DEMO_MODEL_RUN"):
    os.environ.pop(_var, None)                    # assert the sibling defaults, not a provisioned shell

from app import config, seed_v2  # noqa: E402
from app.adapters import ultralytics_ad  # noqa: E402
from app.services import segment  # noqa: E402

SIBLING = config.REPO_ROOT.parent / "labeldesk-ml"


def test_ml_paths_default_to_the_sibling_checkout():
    assert config.SAM_ROOT == SIBLING / "sam3_auto_label"
    assert config.PRETRAINED_DIR == SIBLING / "yolo26_ppe" / "models" / "pretrained"
    assert config.DEMO_MODEL_RUN == SIBLING / "yolo26_ppe" / "models" / "archive" / "version_2_improved_baseline" \
        / "nano_detection" / "training_run"


def test_pretrained_falls_back_to_the_hub_name_without_the_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(ultralytics_ad, "PRETRAINED_DIR", tmp_path / "missing")
    assert ultralytics_ad.base_weights("detect", "n") == "yolo11n.pt"
    assert ultralytics_ad._start_weights("yolo26n", "detect") == "yolo11n.pt"
    assert ultralytics_ad._weights_path("yolo26n", None) == "yolo26n.pt"


def test_sam_reports_unavailable_without_the_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(segment, "SAM_ENABLED", "auto")
    monkeypatch.setattr(segment, "SAM_ROOT", tmp_path / "missing")
    monkeypatch.setattr(segment, "_sam", {"proc": None, "err": None})
    assert segment._load_sam() is None, "a missing checkout must not crash or load a model"
    status = segment.sam_status()
    assert status == {"enabled": True, "loaded": False, "error": "SAM is not available on this server"}


def test_demo_seed_skips_the_trained_model_without_the_checkout(monkeypatch, tmp_path, caplog):
    from app.db import SessionLocal

    monkeypatch.setattr(seed_v2, "MODEL_RUN", tmp_path / "missing")
    project = SimpleNamespace(id=-1, workspace_id=-1)      # no such rows: the lookup finds nothing
    version = SimpleNamespace(id=-1)
    with SessionLocal() as db, caplog.at_level("WARNING", logger="labeldesk.seed"):
        assert seed_v2._ensure_model(db, project, version) is None
    assert "skipping the demo model" in caplog.text
