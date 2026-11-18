"""Edge presets take a dtype (FP32 / FP16 / INT8) and NCNN joins the list.

A preset lists the dtypes it can really build; the first is its default. The artifact of a non-default
dtype is its own entry (`ncnn:fp16`) so FP32 and FP16 builds of one model sit side by side.
"""
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app import worker
from app.config import DATA_DIR
from app.db import SessionLocal
from app.handlers import versioning as vhandlers
from app.main import app
from app.models import Job, TrainedModel
from app.services import edge
from conftest import login
from test_edge_export import (BASE, FakePresetAdapter, _cancel, _demo, _drop, _enable_flag, _model_files, _new_model,
                              _new_version)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.headers.update(login(c))
        yield c


# --- catalog and plans ----------------------------------------------------------

def test_ncnn_is_a_preset_with_fp32_and_fp16():
    spec = edge.get_preset("ncnn")

    assert spec["format"] == "ncnn"
    assert spec["dtypes"] == ["fp32", "fp16"]


def test_the_public_catalog_names_every_dtype_and_marks_the_default():
    items = {p["id"]: p for p in edge.public_presets()}

    assert [d["id"] for d in items["ncnn"]["dtypes"]] == ["fp32", "fp16"]
    assert [d["id"] for d in items["ncnn"]["dtypes"] if d["default"]] == ["fp32"]
    assert items["openvino"]["dtypes"][-1] == {"id": "int8", "label": "INT8 (quantized)", "default": False, "needs_data": True}
    assert [d["id"] for d in items["hailo"]["dtypes"]] == ["int8"]


@pytest.mark.parametrize("preset,dtype,plan", [
    ("ncnn", None, ("ncnn", {})),
    ("ncnn", "fp16", ("ncnn", {"half": True})),
    ("openvino", "int8", ("openvino", {"int8": True})),
    ("openvino", "fp16", ("openvino", {"half": True})),
    ("onnx", "fp16", ("onnx", {"half": True})),
    ("jetson", None, ("engine", {"half": True})),
    ("jetson", "int8", ("engine", {"int8": True})),
    ("jetson", "fp32", ("engine", {})),
])
def test_export_plan_turns_a_dtype_into_the_matching_ultralytics_switch(preset, dtype, plan):
    assert edge.export_plan(preset, dtype) == plan


def test_tflite_keeps_its_int8_default_and_offers_the_others(monkeypatch):
    monkeypatch.setattr(edge, "_ultralytics_version", lambda: (8, 4, 146))

    assert edge.export_plan("tflite-int8") == ("litert", {"quantize": 8})
    assert edge.export_plan("tflite-int8", "fp16") == ("litert", {"half": True})
    assert edge.export_plan("tflite-int8", "fp32") == ("litert", {})
    monkeypatch.setattr(edge, "_ultralytics_version", lambda: (8, 3, 0))
    assert edge.export_plan("tflite-int8", "fp16") == ("tflite", {"half": True})


def test_a_dtype_the_preset_cannot_build_is_refused_and_none_means_the_default():
    assert edge.resolve_dtype("ncnn", None) == "fp32"
    assert edge.resolve_dtype("hailo", None) == "int8"
    with pytest.raises(ValueError, match="hailo"):
        edge.resolve_dtype("hailo", "fp16")
    with pytest.raises(ValueError):
        edge.resolve_dtype("ncnn", "int8")


def test_the_artifact_key_is_the_preset_for_its_default_dtype_and_carries_the_dtype_otherwise():
    assert edge.artifact_key("ncnn", None) == "ncnn"
    assert edge.artifact_key("ncnn", "fp32") == "ncnn"
    assert edge.artifact_key("ncnn", "fp16") == "ncnn:fp16"
    assert edge.artifact_key("tflite-int8", "int8") == "tflite-int8"


def test_int8_needs_calibration_data_whichever_preset_asks_for_it():
    assert edge.needs_data("openvino", "int8") is True
    assert edge.needs_data("openvino", None) is False
    assert edge.needs_data("tflite-int8", None) is True
    assert edge.needs_data("hailo", None) is True
    assert edge.needs_data("ncnn", "fp16") is False


# --- route ----------------------------------------------------------------------

def _model(client):
    _enable_flag(client)
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v)
        mid, vid = m.id, v.id
        db.commit()
    return mid, vid


def test_the_route_queues_a_dtype_build_once_per_dtype(client):
    mid, vid = _model(client)
    jobs = []
    try:
        a = client.post(f"{BASE}/models/{mid}/export", json={"preset": "ncnn", "dtype": "fp16"})
        again = client.post(f"{BASE}/models/{mid}/export", json={"preset": "ncnn", "dtype": "fp16"})
        b = client.post(f"{BASE}/models/{mid}/export", json={"preset": "ncnn"})
        jobs = [a.json()["id"], b.json()["id"]]

        assert a.status_code == again.status_code == b.status_code == 200
        assert a.json()["params"] == {"model_id": mid, "preset": "ncnn", "dtype": "fp16"}
        assert again.json()["id"] == a.json()["id"]
        assert b.json()["id"] != a.json()["id"] and b.json()["params"] == {"model_id": mid, "preset": "ncnn"}
    finally:
        for jid in jobs:
            _cancel(jid)
        _drop(model_ids=[mid], version_ids=[vid], job_ids=jobs)


@pytest.mark.parametrize("body", [{"preset": "ncnn", "dtype": "int8"}, {"preset": "ncnn", "dtype": "bf16"},
                                  {"preset": "hailo", "dtype": "fp16"}])
def test_a_dtype_the_preset_cannot_build_is_a_400(client, body):
    mid, vid = _model(client)
    try:
        assert client.post(f"{BASE}/models/{mid}/export", json=body).status_code == 400
    finally:
        _drop(model_ids=[mid], version_ids=[vid])


# --- worker ---------------------------------------------------------------------

def test_a_dtype_job_builds_with_its_switch_and_stores_its_own_artifact(client, monkeypatch):
    FakePresetAdapter.calls.clear()
    with SessionLocal() as db:
        ws, p = _demo(db)
        v = _new_version(db, p)
        m = _new_model(db, ws, p, v, variant="yolo26n")
        job = Job(workspace_id=ws.id, project_id=p.id, kind="export_preset", status="running",
                  params={"model_id": m.id, "preset": "ncnn", "dtype": "fp16"})
        db.add(job)
        db.flush()
        mid, vid, jid = m.id, v.id, job.id
        db.commit()
    _model_files(mid)
    monkeypatch.setattr(worker, "ADAPTERS", {"ultralytics": FakePresetAdapter(directory=True)})
    try:
        with SessionLocal() as db:
            out = vhandlers.run_export_preset(db.get(Job, jid))

        assert out["file"] == f"edge/{mid}/ncnn-fp16.zip" and (DATA_DIR / out["file"]).is_file()
        call = FakePresetAdapter.calls[0]
        assert call["fmt"] == "ncnn" and call["options"] == {"half": True}
        with SessionLocal() as db:
            assert "ncnn:fp16" in db.get(TrainedModel, mid).runtime_refs["edge"]
    finally:
        _drop(model_ids=[mid], version_ids=[vid], job_ids=[jid])
