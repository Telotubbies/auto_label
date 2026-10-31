"""Static model zoo + registry: what exists, under which license, and whether it can run now."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import TrainedModel
from .base import ADAPTERS, Availability, Resolved, parse_ref

_LICENSE = {"ultralytics": "AGPL-3.0", "sam3": "SAM License", "vlm": "Apache-2.0"}
_VLM_CAPS = {"vlm", "detect", "caption"}       # until the vlm adapter registers and reports its own


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
    return out


def catalog(db: Session, workspace_id: str) -> list[dict]:
    probes: dict[str, Availability] = {f: a.probe() for f, a in ADAPTERS.items()}
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
    for m in db.scalars(select(TrainedModel).where(TrainedModel.workspace_id == workspace_id, TrainedModel.status == "done")):
        fam = m.family or "ultralytics"
        ad = ADAPTERS.get(fam)
        av = probes.get(fam) or Availability(False, f"{fam} adapter not installed")
        items.append({"ref": f"trained:{m.id}", "family": fam, "variant": m.variant or m.arch, "name": m.name,
                      "capabilities": sorted(ad.capabilities(m.variant or m.arch)) if ad else [],
                      "license": m.license or _LICENSE.get(fam, "unknown"), "available": av.ok,
                      "reason": av.reason, "kind": "trained"})
    return items


_TASK_VARIANT = {"detect": "yolo26n", "segment": "yolo26n-seg", "classify": "yolo26n-cls"}


def resolve(model_ref: str, db: Session) -> Resolved:
    """Bind a model_ref to its adapter; trained:<id> also carries the model's variant and weights."""
    fam, rest = parse_ref(model_ref)
    weights = None
    if fam == "trained":
        m = db.get(TrainedModel, rest)
        if m is None:
            raise ValueError(f"unknown trained model {rest!r}")
        fam, rest, weights = m.family or "ultralytics", m.variant or _TASK_VARIANT[m.task], m.weights
    if fam not in ADAPTERS:
        raise ValueError(f"no adapter for family {fam!r}")
    return Resolved(ADAPTERS[fam], rest, weights, model_ref)
