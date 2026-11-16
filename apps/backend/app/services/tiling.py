"""SAHI-style slicing: split a large image, run inference per tile, stitch boxes back.

The grid is the same for dataset tiling and inference, so a model trained on tiled
versions sees the same object scale when served sliced.
"""
import time
from dataclasses import dataclass

from PIL import Image as PImage

from . import imaging

MIN_TILE = 64
MAX_TILE = 4096
MAX_OVERLAP = 0.9
MAX_TILES = 400          # one synchronous request must not fan out to hundreds of thousands of crops
MERGE_IOU = 0.5


@dataclass(frozen=True)
class Tiling:
    tile_size: int = 640
    overlap: float = 0.2

    @classmethod
    def parse(cls, raw) -> "Tiling | None":
        """None/False/{}/0 turns tiling off. A dict must name tile_size explicitly."""
        if raw is None or raw is False or raw == {} or raw == 0:
            return None
        if raw is True:
            return cls()
        if isinstance(raw, int):
            raw = {"tile_size": raw}
        if not isinstance(raw, dict) or "tile_size" not in raw:
            raise ValueError("tiling needs tile_size (64-4096 px)")
        try:
            tile = int(raw["tile_size"])
            overlap = float(raw.get("overlap", 0.2))
        except (TypeError, ValueError) as e:
            raise ValueError("tiling tile_size and overlap must be numbers") from e
        if not MIN_TILE <= tile <= MAX_TILE:
            raise ValueError(f"tiling tile_size must be {MIN_TILE}-{MAX_TILE} px")
        if not 0.0 <= overlap <= MAX_OVERLAP:
            raise ValueError(f"tiling overlap must be 0-{MAX_OVERLAP}")
        return cls(tile, overlap)

    def boxes(self, width: int, height: int) -> list[tuple[int, int, int, int]]:
        bw, bh = min(self.tile_size, width), min(self.tile_size, height)   # never pad past the image edge
        xs, ys = _starts(width, bw, self.overlap), _starts(height, bh, self.overlap)
        if len(xs) * len(ys) > MAX_TILES:
            raise ValueError(f"tiling would create {len(xs) * len(ys)} tiles; "
                             f"raise the tile size or lower the overlap (max {MAX_TILES})")
        return [(x, y, x + bw, y + bh) for y in ys for x in xs]


def _starts(total: int, tile: int, overlap: float) -> list[int]:
    """Tile origins covering [0, total]; the last tile is shifted back so it never overruns."""
    if total <= tile:
        return [0]
    step = max(1, round(tile * (1 - overlap)))
    starts = list(range(0, total - tile + 1, step))
    if starts[-1] != total - tile:
        starts.append(total - tile)
    return starts


def tile_boxes(width: int, height: int, tiling: Tiling) -> list[tuple[int, int, int, int]]:
    return tiling.boxes(width, height)


def tile_annotations(anns: list[dict], box: tuple[int, int, int, int], width: int, height: int) -> list[dict]:
    """Clip normalized annotations into one pixel tile and re-normalize them to that tile."""
    x1, y1, x2, y2 = box
    tw, th = x2 - x1, y2 - y1
    if tw <= 0 or th <= 0:
        return []

    def to_tile(x: float, y: float) -> tuple[float, float]:
        return (x * width - x1) / tw, (y * height - y1) / th

    out = []
    for ann in anns:
        if ann.get("shape", {}).get("kind") == "class":
            continue                            # a classification label has no geometry to tile
        moved = imaging._map_points(ann, to_tile, width, height, tw, th)
        clipped = imaging._clip(moved, tw, th)
        if clipped is not None:
            out.append(clipped)
    return out


def _iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"] - a["width"] / 2, a["y"] - a["height"] / 2
    ax2, ay2 = a["x"] + a["width"] / 2, a["y"] + a["height"] / 2
    bx1, by1 = b["x"] - b["width"] / 2, b["y"] - b["height"] / 2
    bx2, by2 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union > 0 else 0.0


def _shift(pred: dict, ox: int, oy: int, width: int, height: int) -> dict | None:
    p = dict(pred)
    x1 = max(0.0, p["x"] - p["width"] / 2 + ox)
    y1 = max(0.0, p["y"] - p["height"] / 2 + oy)
    x2 = min(float(width), p["x"] + p["width"] / 2 + ox)
    y2 = min(float(height), p["y"] + p["height"] / 2 + oy)
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    p["x"], p["y"] = round((x1 + x2) / 2, 1), round((y1 + y2) / 2, 1)
    p["width"], p["height"] = round(x2 - x1, 1), round(y2 - y1, 1)
    if p.get("points"):
        p["points"] = [{"x": round(min(width, max(0.0, q["x"] + ox)), 1),
                        "y": round(min(height, max(0.0, q["y"] + oy)), 1)} for q in p["points"]]
    return p


def stitch(tiles: list[tuple[tuple[int, int, int, int], dict]], width: int, height: int,
           iou: float = MERGE_IOU) -> list[dict]:
    """Shift every tile's boxes into image coordinates, then greedy NMS per class."""
    merged: list[dict] = []
    for box, pred in tiles:
        for p in pred.get("predictions", []):
            shifted = _shift(p, box[0], box[1], width, height)
            if shifted is not None:
                merged.append(shifted)
    merged.sort(key=lambda p: -float(p.get("confidence") or 0.0))
    kept: list[dict] = []
    for p in merged:
        if not any(k["class_id"] == p["class_id"] and _iou(k, p) > iou for k in kept):
            kept.append(p)
    return kept


def sliced_predict(model, im: PImage.Image, tiling: Tiling | dict | bool, *,
                   merge_iou: float = MERGE_IOU, **kw) -> dict:
    """Run a detector on overlapping tiles; `model` is a Resolved (predict + adapter capabilities)."""
    cfg = tiling if isinstance(tiling, Tiling) else Tiling.parse(tiling)
    if cfg is None:
        raise ValueError("tiling needs a tile size")
    # SAM 3.1 and VLM advertise segment/detect but cannot be tiled: per-crop prompts, unrefined boxes.
    if model.adapter.family in ("sam3", "vlm") or not (
            {"detect", "segment"} & set(model.adapter.capabilities(getattr(model, "variant", "")))):
        raise ValueError("tiling needs a detection or segmentation model")
    t0 = time.perf_counter()
    tiles = []
    for box in cfg.boxes(im.width, im.height):
        out = model.predict(im.crop(box), **kw)
        if "top" in out:                        # a classifier answered: refuse rather than guess
            raise ValueError("tiling needs a detection or segmentation model")
        tiles.append((box, out))
    return {
        "predictions": stitch(tiles, im.width, im.height, merge_iou),
        "time": round(time.perf_counter() - t0, 4),
        "image": {"width": im.width, "height": im.height},
        "model": getattr(model, "ref", ""),
    }
