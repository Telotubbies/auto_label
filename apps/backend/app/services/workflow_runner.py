"""Execute a no-code workflow over one image.

Blocks transform a working set of **items** (the image or a crop of it) and **detections**
(root-normalized boxes). ``crop`` replaces the working items with one crop per detection, so a
following model or OCR block sees only those crops; their outputs are mapped back to root
coordinates. ``rule`` delegates to the Task 10 stream Engine (count and zone read a still image);
``sink`` returns the result or writes it into the project image as annotations.

Model calls go through the shared ``resolve`` adapter, scoped to the project's workspace.
"""
from __future__ import annotations

import time

from PIL import Image as PImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters import resolve, validate_prediction
from ..models import LabelClass, Project, new_id, set_annotations
from ..streams.rules import Engine
from .workflows import validate_blocks

MAX_ITEMS = 50
MAX_DETECTIONS = 500


def _detection(pred: dict, item: dict, ref: str) -> list[dict]:
    """Map a prediction (pixels inside the item) into root-normalized detections."""
    W, H = pred["image"]["width"], pred["image"]["height"]
    model = pred.get("model") or ref
    out: list[dict] = []
    if "top" in pred:                       # classification: the whole item is the region
        top = pred["predictions"][0] if pred["predictions"] else None
        if top is not None:
            out.append({"kind": "class", "class": top["class"], "confidence": float(top["confidence"]),
                        "x": item["x"], "y": item["y"], "w": item["w"], "h": item["h"],
                        "model": model})
        return out
    for p in pred["predictions"]:
        x = item["x"] + (p["x"] - p["width"] / 2) / W * item["w"]
        y = item["y"] + (p["y"] - p["height"] / 2) / H * item["h"]
        w = p["width"] / W * item["w"]
        h = p["height"] / H * item["h"]
        x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
        w, h = max(0.0, min(w, 1.0 - x)), max(0.0, min(h, 1.0 - y))
        det = {"kind": "bbox", "class": p["class"], "confidence": float(p["confidence"]),
               "x": x, "y": y, "w": w, "h": h, "model": model}
        if p.get("points"):
            det["kind"] = "polygon"
            det["points"] = [v for pt in p["points"] for v in
                             (item["x"] + pt["x"] / W * item["w"], item["y"] + pt["y"] / H * item["h"])]
        out.append(det)
    return out


def _crop(detections: list[dict], expand: float, root: PImage.Image) -> list[dict]:
    """One root-image crop per box detection, padded by ``expand`` × the box size on every side.

    Detection boxes are root-normalized even after an earlier crop, so every crop is cut from the
    root image; cutting a nested item's image with root coordinates would shrink the box twice.
    """
    crops: list[dict] = []
    for d in detections:
        if d["kind"] == "class":
            continue
        pad_x, pad_y = d["w"] * expand, d["h"] * expand
        x0, y0 = max(0.0, d["x"] - pad_x), max(0.0, d["y"] - pad_y)
        x1, y1 = min(1.0, d["x"] + d["w"] + pad_x), min(1.0, d["y"] + d["h"] + pad_y)
        if x1 - x0 < 0.005 or y1 - y0 < 0.005:
            continue
        src = root
        box = (int(round(x0 * src.width)), int(round(y0 * src.height)),
               max(int(round(x0 * src.width)) + 1, int(round(x1 * src.width))),
               max(int(round(y0 * src.height)) + 1, int(round(y1 * src.height))))
        crop = src.crop(box)
        if crop.width < 2 or crop.height < 2:
            continue
        crops.append({"image": crop, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
        if len(crops) >= MAX_ITEMS:
            break
    return crops


def _engine_preds(detections: list[dict]) -> list[dict]:
    return [{"x": d["x"] + d["w"] / 2, "y": d["y"] + d["h"] / 2, "width": d["w"], "height": d["h"],
             "class": d["class"]} for d in detections]


def _avoid_zero(value: float) -> float:
    """The engine skips anchor-only geometry when width/height is 0; keep boxes usable."""
    return value if value > 1e-9 else 1e-9


def _rule(block: dict) -> tuple[list[dict], list[dict]]:
    if block["kind"] == "count":
        return ([{"kind": "count", "class": block["class"], "k": block["k"],
                  "op": block.get("op", ">="), "for_s": block.get("for_s", 0)}], [])
    points = block["points"]
    return ([{"kind": "zone", "class": block["class"], "zone_id": "zone"}],
            [{"id": "zone", "points": points}])


def _annotations(db: Session, project: Project, detections: list[dict]) -> tuple[int, list[dict]]:
    classes = db.scalars(select(LabelClass).where(LabelClass.project_id == project.id)).all()
    class_ids = {c.name: c.id for c in classes}
    anns = []
    for d in detections:
        cid = class_ids.get(d["class"])
        if cid is None:
            continue
        if d["kind"] == "class":
            shape = {"kind": "class"}
        elif d["kind"] == "polygon" and len(d.get("points", [])) >= 6:
            shape = {"kind": "polygon", "points": d["points"]}
        else:
            shape = {"kind": "bbox", "x": d["x"], "y": d["y"], "w": d["w"], "h": d["h"]}
        anns.append({"id": "a" + new_id(), "classId": cid, "shape": shape,
                     "confidence": round(d["confidence"], 4), "source": d["model"]})
    return len(anns), anns


def _public(detections: list[dict]) -> list[dict]:
    return [{k: v for k, v in d.items() if not k.startswith("_")} for d in detections]


def run(db: Session, project: Project, blocks: list[dict], image: PImage.Image, image_row=None) -> dict:
    """Run the workflow; returns final detections, OCR text, rule events and the sink result."""
    blocks = validate_blocks(blocks)
    t0 = time.perf_counter()
    items = [{"image": image, "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}]
    detections: list[dict] = []
    texts: list[dict] = []
    events: list[dict] = []
    annotations_added = 0

    for i, block in enumerate(blocks):
        kind = block["type"]
        if kind == "model":
            resolved = resolve(block["model_ref"], db, workspace_id=project.workspace_id)
            kw: dict = {}
            if block.get("conf") is not None:
                kw["conf"] = block["conf"]
            if block.get("classes"):
                kw["classes"] = block["classes"]
            produced: list[dict] = []
            for item in items:
                pred = resolved.predict(item["image"], **kw)
                validate_prediction(pred)
                produced.extend(_detection(pred, item, block["model_ref"]))
                if len(produced) >= MAX_DETECTIONS:
                    break
            detections = produced[:MAX_DETECTIONS]
        elif kind == "filter":
            wanted = set(block["classes"])
            min_conf = block.get("min_conf", 0)
            detections = [d for d in detections
                          if (not wanted or d["class"] in wanted) and d["confidence"] >= min_conf]
        elif kind == "crop":
            items = _crop(detections, block.get("expand", 0), image)
            detections = []
        elif kind == "ocr":
            resolved = resolve(block["model_ref"], db, workspace_id=project.workspace_id)
            for item in items:
                pred = resolved.predict(item["image"], prompt=block["prompt"])
                validate_prediction(pred)
                text = (pred.get("text") or "").strip()
                if text:
                    texts.append({"block": i, "text": text})
        elif kind == "rule":
            rules, zones = _rule(block)
            # A count/zone rule on one still frame is a single engine step; timers start at 0.
            for d in detections:
                d["w"], d["h"] = _avoid_zero(d["w"]), _avoid_zero(d["h"])
            events.extend(Engine(rules, zones, cooldown_s=0, track_ttl_s=0)
                          .step(time.time(), _engine_preds(detections)))
        elif kind == "sink":
            if block["kind"] == "annotations":
                if image_row is None:
                    raise ValueError("the annotations sink needs a project image")
                annotations_added, anns = _annotations(db, project, detections)
                if anns:
                    set_annotations(db, image_row, (image_row.annotations or []) + anns)
                    db.commit()
    return {"detections": _public(detections), "texts": texts, "events": events,
            "annotations_added": annotations_added, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
