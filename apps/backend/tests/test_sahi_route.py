"""The Playground predict route takes every slice-inference and inference-time option (behind task_30)."""
import os

os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import login
from test_tiling_predict import FakeResolved, _clear, _enable, _jpeg, _ready_model

WS, PR = "labeldesk-demo", "ppe-detection"
BASE = f"/api/ws/{WS}/projects/{PR}"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        client.headers.update(login(client))
        yield client


@pytest.fixture(autouse=True)
def _clean():
    _clear()
    yield
    _clear()


@pytest.fixture
def fake(monkeypatch):
    model = FakeResolved()
    monkeypatch.setattr("app.routers.training.resolve", lambda *a, **k: model)
    return model


def post(c, mid, **form):
    return c.post(f"{BASE}/models/{mid}/predict", files={"file": ("a.jpg", _jpeg((800, 800)), "image/jpeg")},
                  data={k: str(v) for k, v in form.items()})


def test_slice_options_are_hidden_while_task_30_is_off(c, fake):
    assert post(c, _ready_model(), slice_width=400, slice_height=400).status_code == 404
    assert fake.calls == []


def test_separate_slice_sizes_overlaps_and_the_standard_pass_are_all_honoured(c, fake):
    _enable()

    r = post(c, _ready_model(), slice_width=400, slice_height=400, overlap_width_ratio=0, overlap_height_ratio=0,
             perform_standard_pred="true")

    assert r.status_code == 200, r.text
    assert len(fake.calls) == 5                       # 4 slices + the whole image
    assert r.json()["slices"] == 5
    assert sorted({size for size, _ in fake.calls}) == [(400, 400), (800, 800)]


def test_postprocess_options_change_how_slice_duplicates_collapse(c, fake):
    _enable()
    mid = _ready_model()

    nms = post(c, mid, slice_width=400, slice_height=400, overlap_width_ratio=0, overlap_height_ratio=0,
               postprocess_type="NMS", postprocess_match_metric="IOU", postprocess_match_threshold=0.9,
               postprocess_class_agnostic="true")
    nmm = post(c, mid, slice_width=400, slice_height=400, overlap_width_ratio=0, overlap_height_ratio=0,
               postprocess_type="NMM", postprocess_match_metric="IOS", postprocess_match_threshold=0.0,
               postprocess_class_agnostic="true")

    assert nms.status_code == nmm.status_code == 200
    assert len(nms.json()["predictions"]) == 4        # four slices, four disjoint boxes
    assert len(nmm.json()["predictions"]) >= 1


def test_auto_slice_needs_no_size(c, fake):
    _enable()

    r = post(c, _ready_model(), auto_slice="true")

    assert r.status_code == 200 and r.json()["slices"] >= 1


@pytest.mark.parametrize("bad", [{"slice_width": 10}, {"overlap_width_ratio": 0.95},
                                 {"postprocess_type": "SOFTNMS"}, {"postprocess_match_metric": "DICE"},
                                 {"postprocess_match_threshold": 2}])
def test_a_bad_slice_option_is_a_400_and_costs_nothing(c, fake, bad):
    _enable()

    r = post(c, _ready_model(), slice_width=400, **bad) if "slice_width" not in bad else post(c, _ready_model(), **bad)

    assert r.status_code == 400
    assert fake.calls == []


def test_inference_time_techniques_reach_the_model(c, fake):
    r = post(c, _ready_model(), imgsz=1280, max_det=50, agnostic_nms="true", augment="true", half="true",
             retina_masks="true", class_ids="0,2")

    assert r.status_code == 200, r.text
    kw = fake.calls[0][1]
    assert (kw["imgsz"], kw["max_det"], kw["agnostic_nms"], kw["augment"], kw["half"], kw["retina_masks"]) == \
        (1280, 50, True, True, True, True)
    assert kw["class_ids"] == [0, 2]


@pytest.mark.parametrize("bad", [{"imgsz": 8}, {"max_det": 0}, {"class_ids": "a,b"}])
def test_a_bad_inference_option_is_a_400(c, fake, bad):
    assert post(c, _ready_model(), **bad).status_code == 400
    assert fake.calls == []


def test_ultralytics_only_options_are_refused_for_other_model_families(c, fake):
    fake.adapter = type(fake.adapter)(family="rfdetr", capabilities=lambda _v: {"detect"})

    r = post(c, _ready_model(), augment="true")

    assert r.status_code == 400 and "Ultralytics" in r.text


# --- Playground: several models at once -----------------------------------------------------------

def _playground(c, refs, **form):
    return c.post(f"/api/ws/{WS}/playground/predict", files={"file": ("a.jpg", _jpeg((800, 800)), "image/jpeg")},
                  data={"model_refs": ",".join(refs), **{k: str(v) for k, v in form.items()}})


def test_playground_slices_every_model_and_skips_yolo_only_options_for_the_others(c, monkeypatch):
    _enable()
    yolo, other = FakeResolved(), FakeResolved()
    other.adapter = type(other.adapter)(family="rfdetr", capabilities=lambda _v: {"detect"})
    monkeypatch.setattr("app.routers.playground.resolve", lambda ref, *a, **k: yolo if ref == "a:yolo" else other)

    r = _playground(c, ["a:yolo", "b:rfdetr"], slice_width=400, slice_height=400, overlap_width_ratio=0,
                    overlap_height_ratio=0, augment="true", postprocess_type="NMM")

    assert r.status_code == 200, r.text
    results = {x["ref"]: x for x in r.json()["results"]}
    assert results["a:yolo"]["prediction"]["slices"] == 4 and results["a:yolo"].get("note") is None
    assert yolo.calls[0][1]["augment"] is True
    assert "augment" not in other.calls[0][1] and "Ultralytics" in results["b:rfdetr"]["note"]


def test_playground_refuses_a_bad_option_before_any_model_runs(c, monkeypatch):
    _enable()
    model = FakeResolved()
    monkeypatch.setattr("app.routers.playground.resolve", lambda *a, **k: model)

    assert _playground(c, ["a:yolo"], slice_width=400, postprocess_type="SOFTNMS").status_code == 400
    assert model.calls == []
