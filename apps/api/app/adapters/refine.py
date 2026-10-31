"""One auto-label pipeline for both the worker and the preview endpoint:
model_ref resolution, SAM 3.1 box refinement, VLM grounding/verify, editor annotations."""
import secrets

import httpx

from .. import config
from ..services import ml
from .base import ADAPTERS
from .catalog import resolve

_VLM_ERRORS = (httpx.HTTPError, KeyError, RuntimeError)


def _vlm_down(adapter) -> RuntimeError:
    return RuntimeError(f"vLLM not reachable at {getattr(adapter, 'url', config.VLM_URL)}")


def _xyxy(p: dict) -> tuple[float, float, float, float]:
    return (p["x"] - p["width"] / 2, p["y"] - p["height"] / 2,
            p["x"] + p["width"] / 2, p["y"] + p["height"] / 2)


def refine_with_sam(pred: dict, im, project_type: str) -> dict | None:
    """Box -> SAM 3.1 mask -> refined centre box (+ polygon points on segmentation projects).

    None when SAM is not installed or finds nothing, so callers can drop or fall back."""
    sam = ADAPTERS.get("sam3")
    if sam is None:
        return None
    poly, _ = sam.segment_box(im, _xyxy(pred))
    if not poly or len(poly) < 6:
        return None
    xs, ys = poly[0::2], poly[1::2]
    out = dict(pred)
    out["x"] = round((min(xs) + max(xs)) / 2 * im.width, 1)
    out["y"] = round((min(ys) + max(ys)) / 2 * im.height, 1)
    out["width"] = round((max(xs) - min(xs)) * im.width, 1)
    out["height"] = round((max(ys) - min(ys)) * im.height, 1)
    if project_type == "instance-segmentation":
        out["points"] = [{"x": round(x * im.width, 1), "y": round(y * im.height, 1)}
                         for x, y in zip(xs, ys)]
    else:
        out.pop("points", None)
    return out


def _bbox(p: dict, im) -> dict:
    x1, y1, x2, y2 = _xyxy(p)
    return {"kind": "bbox", "x": x1 / im.width, "y": y1 / im.height,
            "w": (x2 - x1) / im.width, "h": (y2 - y1) / im.height}


def _polygon(p: dict, im) -> dict:
    pts = p.get("points") or []
    if len(pts) >= 3:
        return {"kind": "polygon", "points": [v for pt in pts for v in (pt["x"] / im.width, pt["y"] / im.height)]}
    b = _bbox(p, im)
    return {"kind": "polygon", "points": [b["x"], b["y"], b["x"] + b["w"], b["y"],
                                          b["x"] + b["w"], b["y"] + b["h"], b["x"], b["y"] + b["h"]]}


def _shape(p: dict, im, project_type: str) -> dict:
    return _polygon(p, im) if project_type == "instance-segmentation" else _bbox(p, im)


def _ann(p: dict, class_id: str, im, project_type: str, source: str) -> dict:
    out = {"id": "a" + secrets.token_hex(5), "classId": class_id,
           "shape": _shape(p, im, project_type), "source": source}
    if isinstance(p.get("confidence"), (int, float)):
        out["confidence"] = round(float(p["confidence"]), 4)
    return out


def _phrases(text: str) -> list[str]:
    """VLM prompt parser; empty list lets the caller fall back to the raw text."""
    vlm = ADAPTERS.get("vlm")
    if vlm is None or not hasattr(vlm, "parse_prompt"):
        return []
    try:
        return [p for p in vlm.parse_prompt(text) if p]
    except _VLM_ERRORS as e:
        raise _vlm_down(vlm) from e


def _verified(vlm, im, pred: dict, cls_name: str) -> bool:
    try:
        return bool(vlm.verify(im, _xyxy(pred), cls_name))
    except _VLM_ERRORS as e:
        raise _vlm_down(vlm) from e


def _sam_ok() -> bool:
    sam = ADAPTERS.get("sam3")
    try:
        return bool(sam and sam.probe().ok)
    except Exception:
        return False


def _ref(params: dict) -> str:
    if params.get("model_ref"):
        return params["model_ref"]
    if params.get("method") == "sam":
        return "sam3:sam3.1"
    if params.get("model_id"):
        return f"trained:{params['model_id']}"
    raise ValueError("choose a model_ref or a trained model")


def label_image(im, *, project_type: str, params: dict, classes: list, db, workspace_id: str) -> list[dict]:
    """Run the selected model over one image and return editor annotations (never writes)."""
    r = resolve(_ref(params), db, workspace_id=workspace_id)
    family = r.adapter.family
    conf = float(raw) if (raw := params.get("confidence")) is not None else None
    conf_kw = {} if conf is None else {"conf": conf}      # None = let Resolved.conf (best-F1) decide
    prompt = params.get("prompt")
    wanted = [c for c in classes if not params.get("class_ids") or c.id in params["class_ids"]]
    by_name = {c.name: c.id for c in wanted}          # the dialog's class list filters output too
    chosen = next((c for c in classes if params.get("class_ids") and c.id == params["class_ids"][0]), None) \
        or (classes[0] if classes else None)
    vlm = ADAPTERS.get("vlm")
    verify = bool(params.get("vlm_verify")) and vlm is not None

    if family == "sam3":
        prompts = (_phrases(prompt) or [prompt]) if prompt else [c.name for c in wanted]
        out = r.predict(im, classes=prompts, **conf_kw)
        anns = []
        for p in out.get("predictions", []):
            cid = chosen.id if (prompt and chosen) else by_name.get(p.get("class"))
            if not cid:
                continue
            name = chosen.name if (prompt and chosen) else p.get("class")
            if verify and not _verified(vlm, im, p, name):
                continue
            anns.append(_ann(p, cid, im, project_type, "sam3"))
        return anns

    if family == "vlm":
        names = (_phrases(prompt) or [prompt]) if prompt else [c.name for c in wanted]
        try:
            out = r.adapter.ground(im, names)
        except _VLM_ERRORS as e:
            raise _vlm_down(r.adapter) from e
        anns = []
        for p in out.get("predictions", []):
            cid = chosen.id if (prompt and chosen) else by_name.get(p.get("class"))
            if not cid:
                continue
            refined = refine_with_sam(p, im, project_type)       # VLM boxes are never saved unrefined
            if refined is None:
                continue
            refined["confidence"] = 0.5                          # VLMs give no calibrated score (spec 3.4)
            name = chosen.name if (prompt and chosen) else p.get("class")
            if verify and not _verified(vlm, im, refined, name):
                continue
            anns.append(_ann(refined, cid, im, project_type, "vlm+sam3"))
        return anns

    out = r.predict(im, classes=[c.name for c in wanted] or None, **conf_kw)
    if "top" not in out and project_type == "instance-segmentation" and _sam_ok():
        for p in out.get("predictions", []):
            if p.get("points"):          # native segmenters already return a mask polygon
                continue
            refined = refine_with_sam(p, im, project_type)
            if refined is not None:
                p.update(refined)
    if verify and "top" not in out:
        out["predictions"] = [p for p in out.get("predictions", []) if _verified(vlm, im, p, p.get("class"))]
    return ml.to_annotations(out, by_name)
