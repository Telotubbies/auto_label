"""v1 back-compat facade: training/inference live in adapters.ultralytics_ad."""
from ..adapters.ultralytics_ad import TASK, base_weights, predict, train  # noqa: F401

SIZES = ("n", "s", "m", "l", "x")


def _first(entry: dict, *keys):
    for key in keys:
        if entry.get(key) is not None:
            return entry[key]
    return None


def final_metrics(history: list[dict], task: str) -> dict:
    """Pick headline metrics from the best epoch (Ultralytics keys or the spec-P4 common keys)."""
    if not history:
        return {}
    if task == "classify":
        best = max(history, key=lambda h: h.get("metrics/accuracy_top1", 0))
        return {"accuracy_top1": best.get("metrics/accuracy_top1"), "accuracy_top5": best.get("metrics/accuracy_top5")}
    k = "(M)" if task == "segment" else "(B)"
    best = max(history, key=lambda h: _first(h, f"metrics/mAP50-95{k}", "metrics/mAP50-95(B)", "val/map5095") or 0)
    return {"map50": _first(best, f"metrics/mAP50{k}", "metrics/mAP50(B)", "val/map50"),
            "map5095": _first(best, f"metrics/mAP50-95{k}", "metrics/mAP50-95(B)", "val/map5095"),
            "precision": _first(best, f"metrics/precision{k}", "metrics/precision(B)", "val/precision"),
            "recall": _first(best, f"metrics/recall{k}", "metrics/recall(B)", "val/recall")}


def to_annotations(pred: dict, class_ids: dict[str, str]) -> list[dict]:
    """Convert a predict() response to editor annotations (normalized); class_ids maps name -> project class id."""
    import secrets
    W, H = pred["image"]["width"], pred["image"]["height"]
    source = pred.get("model") or "human"
    out = []
    if "top" in pred:
        top = pred["predictions"][0]["class"] if pred["predictions"] else None
        if top in class_ids:
            out.append({"id": "a" + secrets.token_hex(5), "classId": class_ids[top],
                        "shape": {"kind": "class"}, "source": source})
        return out
    for p in pred["predictions"]:
        cid = class_ids.get(p["class"])
        if not cid:
            continue
        aid = "a" + secrets.token_hex(5)
        if p.get("points") and len(p["points"]) >= 3:
            shape = {"kind": "polygon", "points": [v for pt in p["points"] for v in (pt["x"] / W, pt["y"] / H)]}
        else:
            shape = {"kind": "bbox", "x": (p["x"] - p["width"] / 2) / W, "y": (p["y"] - p["height"] / 2) / H,
                     "w": p["width"] / W, "h": p["height"] / H}
        out.append({"id": aid, "classId": cid, "shape": shape, "confidence": p["confidence"], "source": source})
    return out
