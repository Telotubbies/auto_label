"""Static model zoo + registry: what exists, under which license, and whether it can run now."""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DATA_DIR
from ..models import TrainedModel
from .base import ADAPTERS, Availability, Resolved, parse_ref

_LICENSE = {"ultralytics": "AGPL-3.0", "sam3": "SAM License", "vlm": "Apache-2.0",
            "rfdetr": "Apache-2.0", "hf": "Apache-2.0"}
_VLM_CAPS = {"vlm", "detect", "caption"}       # until the vlm adapter registers and reports its own

_PROBE_TTL = 15.0                               # a black-holed vLLM probe takes 3 s; don't pay it every request
_now = time.monotonic
_probes: dict[str, tuple[float, Availability]] = {}


def _probe(family: str, adapter) -> Availability:
    hit = _probes.get(family)
    if hit and _now() - hit[0] < _PROBE_TTL:
        return hit[1]
    av = adapter.probe()
    _probes[family] = (_now(), av)
    return av


def _zoo() -> list[tuple[str, str, str]]:
    """(family, variant, display name)"""
    out = []
    for sz in "nsm":
        out += [("ultralytics", f"yolo26{sz}", f"YOLO26 {sz.upper()}"),
                ("ultralytics", f"yolo26{sz}-seg", f"YOLO26 {sz.upper()} Seg")]
    for fam, label in (("yolo11", "YOLO11"), ("yolov8", "YOLOv8")):
        out += [("ultralytics", f"{fam}{sz}", f"{label} {sz.upper()}") for sz in "nsmlx"]
    out += [("ultralytics", "rtdetr-l", "RT-DETR L"), ("ultralytics", "rtdetr-x", "RT-DETR X"),
            ("ultralytics", "yolov8s-worldv2", "YOLO-World v8 S"), ("ultralytics", "yolov8m-worldv2", "YOLO-World v8 M"),
            ("sam3", "sam3.1", "SAM 3.1"), ("vlm", "qwen2.5-vl-7b", "Qwen2.5-VL 7B")]
    for variant, name in (("nano", "RF-DETR Nano"), ("small", "RF-DETR Small"),
                          ("medium", "RF-DETR Medium"), ("large", "RF-DETR Large")):
        out.append(("rfdetr", variant, name))
    for variant, name in (("ustc-community/dfine-nano-coco", "D-FINE Nano"),
                          ("ustc-community/dfine-small-coco", "D-FINE Small"),
                          ("ustc-community/dfine-medium-coco", "D-FINE Medium"),
                          ("ustc-community/dfine-large-coco", "D-FINE Large"),
                          ("PekingU/rtdetr_v2_r18vd", "RT-DETRv2 R18"),
                          ("PekingU/rtdetr_v2_r34vd", "RT-DETRv2 R34"),
                          ("PekingU/rtdetr_v2_r50vd", "RT-DETRv2 R50"),
                          ("PekingU/rtdetr_v2_r101vd", "RT-DETRv2 R101")):
        out.append(("hf", variant, name))
    return out


def catalog(db: Session, workspace_id: str) -> list[dict]:
    probes: dict[str, Availability] = {f: _probe(f, a) for f, a in ADAPTERS.items()}
    items = []
    for fam, variant, name in _zoo():
        ad = ADAPTERS.get(fam)
        if ad is None:                                  # family not installed yet (e.g. vlm before its task lands)
            av, caps = Availability(False, f"{fam} adapter not installed"), set(_VLM_CAPS) if fam == "vlm" else set()
        else:
            av, caps = probes[fam], ad.capabilities(variant)
        items.append({"ref": f"{fam}:{variant}", "family": fam, "variant": variant, "name": name,
                      "capabilities": sorted(caps), "license": _LICENSE[fam], "available": av.ok,
                      "reason": av.reason, "kind": "vlm" if fam == "vlm" else "zoo"})
    for m in db.scalars(select(TrainedModel).where(TrainedModel.workspace_id == workspace_id, TrainedModel.status == "ready")):
        fam = m.family or "ultralytics"
        ad = ADAPTERS.get(fam)
        av = probes.get(fam) or Availability(False, f"{fam} adapter not installed")
        items.append({"ref": f"trained:{m.id}", "family": fam, "variant": m.variant or m.arch, "name": m.name,
                      "capabilities": sorted(ad.capabilities(m.variant or m.arch)) if ad else [],
                      "license": m.license or _LICENSE.get(fam, "unknown"), "available": av.ok,
                      "reason": av.reason, "kind": "trained"})
    return items


_TASK_VARIANT = {"detect": "yolo26n", "segment": "yolo26n-seg", "classify": "yolo26n-cls"}


def model_conf(m: TrainedModel) -> float | None:
    """The trained model's default threshold: the evaluator's best-F1 confidence.

    None when the model has not been evaluated (or the stored value is not a usable probability),
    so callers fall back to their own historical default."""
    ev = (m.metrics or {}).get("eval") or {}
    conf = (ev.get("f1_best") or {}).get("conf")
    return float(conf) if isinstance(conf, (int, float)) and 0 < conf < 1 else None


_failed_engines: dict[str, float] = {}     # engine path -> mtime that failed to load (per process)


def mark_engine_failed(rel: str) -> None:
    """Remember a broken engine so resolve() stops selecting it until a rebuild changes the file."""
    try:
        _failed_engines[rel] = (DATA_DIR / rel).stat().st_mtime
    except OSError:
        _failed_engines[rel] = 0.0


def engine_ref(m: TrainedModel) -> str | None:
    """The cached TensorRT engine for a model, or None when it was never built / the file is gone / broken."""
    rel = (m.runtime_refs or {}).get("engine")
    if not isinstance(rel, str) or not (DATA_DIR / rel).is_file():
        return None
    try:
        if _failed_engines.get(rel) == (DATA_DIR / rel).stat().st_mtime:
            return None
    except OSError:
        return None
    return rel


def _engine_usable() -> bool:
    """Only prefer an engine where the TensorRT runtime can actually load it."""
    ad = ADAPTERS.get("tensorrt")
    return ad is not None and ad.probe().ok


def resolve(model_ref: str, db: Session, *, workspace_id: str | None = None) -> Resolved:
    """Bind a model_ref to its adapter; trained:<id> also carries the model's variant and weights.

    With workspace_id the ref is scoped: a trained model of another workspace, or one that is not
    ready, is reported as unknown — same message as a missing id, so ids don't leak across tenants.
    An exported TensorRT engine wins over the .pt checkpoint; a missing engine falls back to .pt."""
    fam, rest = parse_ref(model_ref)
    weights = conf = pt_weights = None
    base_fam = fam
    if fam == "trained":
        m = db.get(TrainedModel, rest)
        if m is None or (workspace_id is not None and (m.workspace_id != workspace_id or m.status != "ready")):
            raise ValueError(f"unknown trained model {rest!r}")
        fam, rest, weights = m.family or "ultralytics", m.variant or _TASK_VARIANT[m.task], m.weights
        conf = model_conf(m)
        engine = engine_ref(m)
        if engine is not None and "world" not in rest and _engine_usable():
            pt_weights, weights, fam = m.weights, engine, "tensorrt"
        base_fam = m.family or "ultralytics"
    if fam not in ADAPTERS:
        raise ValueError(f"no adapter for family {fam!r}")
    fallback = Resolved(ADAPTERS[base_fam], rest, pt_weights, model_ref, conf) \
        if pt_weights and base_fam in ADAPTERS else None
    return Resolved(ADAPTERS[fam], rest, weights, model_ref, conf, fallback)
