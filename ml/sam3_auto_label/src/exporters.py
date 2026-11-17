"""Annotation exporters — write segmentation results to standard dataset formats.

Select formats via `output.formats` in config/ppe_4class.yaml, e.g. `formats: [coco, yolo, voc]`.
What each annotation contains is controlled by the `annotation:` section:
  bbox / segmentation switches + segmentation_encoding (rle | polygon).

Supported formats:
  coco         COCO JSON (combined)                 — bbox/seg, seg = RLE or polygon
  yolo         YOLO TXT per image + data.yaml       — bbox, or polygon if segmentation on
  voc          Pascal VOC XML per image             — bbox only
  labelme      LabelMe JSON per image               — bbox/seg (polygon)
  cvat         CVAT-for-images XML (single file)    — bbox/seg (polygon)
  label_studio Label Studio tasks JSON (single file)— bbox/seg (uncompressed RLE)
  kitti        KITTI TXT per image                  — bbox only
  createml     CreateML JSON (single file)          — bbox only
  openimages   OpenImages CSV (single file)         — bbox only
  supervisely  Supervisely JSON per image + meta    — bbox/seg (polygon)
  masks        Instance mask PNGs per annotation    — seg only

Not implemented (by design): TFRecord (needs tensorflow), YOLO-OBB/DOTA (model emits
axis-aligned boxes only), Cityscapes / SAM-2 fine-tune (different task type).

Note: per-image files in output/coco/{name}.json are always written by batch_segment
as the raw internal cache (used for checkpoint/resume), independent of `formats`.
"""

import csv
import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Callable, TypedDict

import numpy as np
import yaml
from PIL import Image, ImageDraw

from config import Config
from inference import rle_to_mask, save_masks

log = logging.getLogger(__name__)


class ExporterSpec(TypedDict, total=False):
    """Callable contract and annotation prerequisites for one export format."""

    per_image: Callable[..., None]
    finalize: Callable[..., None]
    needs: tuple[str, ...]


# ---------------------------------------------------------------------------
# Polygon utilities (pure Python/NumPy — no OpenCV dependency)
# ---------------------------------------------------------------------------

# Clockwise 8-neighborhood offsets: E, SE, S, SW, W, NW, N, NE
_DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def _trace_boundary(mask, sx, sy):
    """Moore-neighbor boundary tracing of the component containing (sx, sy).

    Stops via Jacob's criterion (re-entering the start pixel from the initial
    backtrack direction). Returns list of (x, y) boundary pixels, clockwise.
    """
    H, W = mask.shape

    def fg(x, y):
        return 0 <= x < W and 0 <= y < H and mask[y, x]

    start = (sx, sy)
    start_b = (sx - 1, sy)  # start is the first fg pixel of a row scan -> west is bg/OOB
    p, b = start, start_b
    boundary = [start]
    max_steps = int(mask.sum()) * 8 + 16  # generous perimeter bound

    for _ in range(max_steps):
        delta = (b[0] - p[0], b[1] - p[1])
        d0 = _DIRS.index(delta) if delta in _DIRS else 4
        moved = False
        for i in range(1, 9):
            d = (d0 + i) % 8  # scan clockwise, starting just past the backtrack
            nx, ny = p[0] + _DIRS[d][0], p[1] + _DIRS[d][1]
            if fg(nx, ny):
                bd = _DIRS[(d0 + i - 1) % 8]  # last bg pixel before the new fg pixel
                p, b = (nx, ny), (p[0] + bd[0], p[1] + bd[1])
                moved = True
                break
        if not moved:
            break  # isolated pixel
        if p == start and b == start_b and len(boundary) > 2:
            break  # Jacob's stopping criterion
        boundary.append(p)
    return boundary


def _douglas_peucker(points, epsilon):
    """Simplify a polyline, keeping points within `epsilon` px of the result."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        x0, y0 = points[i0]
        x1, y1 = points[i1]
        dx, dy = x1 - x0, y1 - y0
        denom = (dx * dx + dy * dy) ** 0.5
        max_d, max_i = -1.0, i0
        for i in range(i0 + 1, i1):
            px, py = points[i]
            if denom == 0:
                d = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
            else:
                d = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / denom
            if d > max_d:
                max_d, max_i = d, i
        if max_d > epsilon:
            keep[max_i] = True
            stack.append((i0, max_i))
            stack.append((max_i, i1))
    return [p for p, k in zip(points, keep) if k]


def mask_to_polygons(mask, epsilon: float = 2.0):
    """Binary mask -> list of simplified polygons, one per connected component.

    Each polygon is a list of (x, y) tuples. Uses boundary tracing +
    Douglas-Peucker simplification; components are erased via PIL polygon fill
    so disjoint regions become separate polygons.
    """
    m = np.asarray(mask)
    while m.ndim > 2:
        m = m[0]
    work = m > 0
    if not work.any():
        return []
    work = work.copy()
    H, W = work.shape
    polygons = []
    while work.any():
        ys, xs = np.nonzero(work)
        sx, sy = int(xs[0]), int(ys[0])
        boundary = _trace_boundary(work, sx, sy)
        if len(boundary) >= 3:
            poly = _douglas_peucker(boundary, epsilon)
            if len(poly) >= 3:
                polygons.append(poly)
            filled = Image.new("L", (W, H), 0)
            ImageDraw.Draw(filled).polygon(boundary, fill=1, outline=1)
            work &= ~np.asarray(filled, dtype=bool)
            for x, y in boundary:  # ensure traced edge pixels are gone too
                work[y, x] = False
        else:
            for x, y in boundary:  # speckle component (<3 px) — erase and skip
                work[y, x] = False
    return polygons


def mask_to_coco_polygons(mask, epsilon: float = 2.0):
    """Binary mask -> COCO polygon segmentation: list of flat [x1, y1, x2, y2, ...]."""
    return [
        [round(float(v), 1) for pt in poly for v in pt]
        for poly in mask_to_polygons(mask, epsilon)
    ]


def mask_to_rle_counts(mask):
    """Uncompressed RLE counts (Label Studio brushlabels format).

    Fortran-order flattening, counts alternate starting with background (0) run.
    """
    m = np.asarray(mask, dtype=np.uint8)
    while m.ndim > 2:
        m = m[0]
    flat = m.flatten(order="F")
    counts = []
    run, cur = 0, 0
    for v in flat:
        if v == cur:
            run += 1
        else:
            counts.append(run)
            run, cur = 1, int(v)
    counts.append(run)
    return counts


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_warned: set[str] = set()


def _stem(image_info):
    return os.path.splitext(image_info["file_name"])[0]


def _fmt_dir(cfg: Config, fmt: str) -> str:
    d = os.path.join(cfg.output_path, fmt)
    os.makedirs(d, exist_ok=True)
    return d


def _cat_name(cfg: Config, category_id: int) -> str:
    return cfg.category_names.get(category_id, "unknown")


def _yolo_class_index(cfg: Config):
    """YOLO classes are 0-based: map sorted category ids -> 0..N-1."""
    return {c.id: i for i, c in enumerate(sorted(cfg.categories, key=lambda c: c.id))}


def _largest_polygon(ann, W, H):
    """Largest component of an annotation's mask as a polygon (or None)."""
    seg = ann.get("segmentation")
    if seg is None:
        return None
    polys = mask_to_polygons(rle_to_mask(seg))
    if not polys:
        return None
    return max(polys, key=len)


def annotation_view(ann: dict, cfg: Config) -> dict:
    """Filtered copy of an annotation honoring the annotation: config switches.

    Used by the COCO exporter and the /segment API so both stay consistent.
    """
    v = {k: ann[k] for k in ("id", "image_id", "category_id", "area", "iscrowd", "score") if k in ann}
    if cfg.annotation.bbox and "bbox" in ann:
        v["bbox"] = ann["bbox"]
    if cfg.annotation.segmentation and "segmentation" in ann:
        if cfg.annotation.segmentation_encoding == "polygon":
            polys = mask_to_coco_polygons(rle_to_mask(ann["segmentation"]))
            if polys:
                v["segmentation"] = polys
        else:
            v["segmentation"] = ann["segmentation"]
    return v


def _categories_json(cfg: Config):
    return [{"id": c.id, "name": c.name, "supercategory": "object"} for c in cfg.categories]


def _images_by_id(images):
    return {img["id"]: img for img in images}


def _anns_by_image(annotations):
    grouped = {}
    for ann in annotations:
        grouped.setdefault(ann["image_id"], []).append(ann)
    return grouped


# ---------------------------------------------------------------------------
# COCO — combined JSON (per-image files are batch_segment's raw cache)
# ---------------------------------------------------------------------------

def _coco_final(cfg, images, annotations, out_dir):
    data = {
        "images": images,
        "annotations": [annotation_view(a, cfg) for a in annotations],
        "categories": _categories_json(cfg),
    }
    with open(os.path.join(out_dir, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# YOLO — one .txt per image + data.yaml (det or seg by annotation switches)
# ---------------------------------------------------------------------------

def _yolo_image(cfg, image_info, annotations, out_dir):
    idx_map = _yolo_class_index(cfg)
    W, H = image_info["width"], image_info["height"]
    lines = []
    for ann in annotations:
        cls = idx_map.get(ann["category_id"])
        if cls is None:
            continue
        if cfg.annotation.segmentation:
            poly = _largest_polygon(ann, W, H)
            if poly:
                coords = " ".join(f"{x / W:.6f} {y / H:.6f}" for x, y in poly)
                lines.append(f"{cls} {coords}")
                continue
        if cfg.annotation.bbox and "bbox" in ann:
            x, y, w, h = ann["bbox"]
            lines.append(f"{cls} {(x + w / 2) / W:.6f} {(y + h / 2) / H:.6f} {w / W:.6f} {h / H:.6f}")
    with open(os.path.join(out_dir, f"{_stem(image_info)}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def _yolo_final(cfg, images, annotations, out_dir):
    names = [c.name for c in sorted(cfg.categories, key=lambda c: c.id)]
    data = {"path": os.path.basename(out_dir), "names": {i: n for i, n in enumerate(names)}, "nc": len(names)}
    with open(os.path.join(out_dir, "data.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)
    with open(os.path.join(out_dir, "classes.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(names) + "\n")


# ---------------------------------------------------------------------------
# Pascal VOC — one XML per image (bbox only)
# ---------------------------------------------------------------------------

def _voc_image(cfg, image_info, annotations, out_dir):
    root = ET.Element("annotation")
    ET.SubElement(root, "folder").text = "images"
    ET.SubElement(root, "filename").text = image_info["file_name"]
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(image_info["width"])
    ET.SubElement(size, "height").text = str(image_info["height"])
    ET.SubElement(size, "depth").text = "3"
    for ann in annotations:
        if "bbox" not in ann:
            continue
        x, y, w, h = ann["bbox"]
        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = _cat_name(cfg, ann["category_id"])
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        box = ET.SubElement(obj, "bndbox")
        ET.SubElement(box, "xmin").text = str(int(round(x)))
        ET.SubElement(box, "ymin").text = str(int(round(y)))
        ET.SubElement(box, "xmax").text = str(int(round(x + w)))
        ET.SubElement(box, "ymax").text = str(int(round(y + h)))
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(os.path.join(out_dir, f"{_stem(image_info)}.xml"),
               xml_declaration=True, encoding="utf-8")


# ---------------------------------------------------------------------------
# LabelMe — one JSON per image (polygon / rectangle shapes)
# ---------------------------------------------------------------------------

def _labelme_image(cfg, image_info, annotations, out_dir):
    W, H = image_info["width"], image_info["height"]
    shapes = []
    for ann in annotations:
        label = _cat_name(cfg, ann["category_id"])
        if cfg.annotation.segmentation:
            polys = mask_to_polygons(rle_to_mask(ann["segmentation"])) if "segmentation" in ann else []
            for poly in polys:
                shapes.append({
                    "label": label,
                    "points": [[round(float(x), 1), round(float(y), 1)] for x, y in poly],
                    "group_id": ann["id"],
                    "shape_type": "polygon",
                    "flags": {},
                })
        elif cfg.annotation.bbox and "bbox" in ann:
            x, y, w, h = ann["bbox"]
            shapes.append({
                "label": label,
                "points": [[x, y], [x + w, y + h]],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
            })
    data = {
        "version": "5.3.1",
        "flags": {},
        "shapes": shapes,
        "imagePath": image_info["file_name"],
        "imageData": None,
        "imageHeight": H,
        "imageWidth": W,
    }
    with open(os.path.join(out_dir, f"{_stem(image_info)}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CVAT for images — single annotations.xml
# ---------------------------------------------------------------------------

def _cvat_final(cfg, images, annotations, out_dir):
    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"
    meta = ET.SubElement(root, "meta")
    task = ET.SubElement(meta, "task")
    labels_el = ET.SubElement(task, "labels")
    for c in cfg.categories:
        label = ET.SubElement(labels_el, "label")
        ET.SubElement(label, "name").text = c.name
        ET.SubElement(label, "attributes")

    grouped = _anns_by_image(annotations)
    for idx, img in enumerate(images):
        W, H = img["width"], img["height"]
        img_el = ET.SubElement(root, "image", id=str(idx), name=img["file_name"],
                               width=str(W), height=str(H))
        for ann in grouped.get(img["id"], []):
            name = _cat_name(cfg, ann["category_id"])
            if cfg.annotation.segmentation and "segmentation" in ann:
                for poly in mask_to_polygons(rle_to_mask(ann["segmentation"])):
                    points = ";".join(f"{x:.2f},{y:.2f}" for x, y in poly)
                    ET.SubElement(img_el, "polygon", label=name, points=points,
                                  occluded="0", source="auto")
            elif cfg.annotation.bbox and "bbox" in ann:
                x, y, w, h = ann["bbox"]
                ET.SubElement(img_el, "box", label=name,
                              xtl=f"{x:.2f}", ytl=f"{y:.2f}",
                              xbr=f"{x + w:.2f}", ybr=f"{y + h:.2f}",
                              occluded="0", source="auto")
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(os.path.join(out_dir, "annotations.xml"), xml_declaration=True, encoding="utf-8")


# ---------------------------------------------------------------------------
# Label Studio — single tasks JSON (rectanglelabels + brushlabels)
# ---------------------------------------------------------------------------

def _label_studio_final(cfg, images, annotations, out_dir):
    grouped = _anns_by_image(annotations)
    tasks = []
    for img in images:
        W, H = img["width"], img["height"]
        results = []
        for ann in grouped.get(img["id"], []):
            name = _cat_name(cfg, ann["category_id"])
            base = {"from_name": "label", "to_name": "image", "image_rotation": 0,
                    "original_width": W, "original_height": H}
            if cfg.annotation.bbox and "bbox" in ann:
                x, y, w, h = ann["bbox"]
                results.append({**base, "type": "rectanglelabels", "value": {
                    "x": round(x / W * 100, 4), "y": round(y / H * 100, 4),
                    "width": round(w / W * 100, 4), "height": round(h / H * 100, 4),
                    "rotation": 0, "rectanglelabels": [name],
                }})
            if cfg.annotation.segmentation and "segmentation" in ann:
                results.append({**base, "type": "brushlabels", "value": {
                    "format": "rle",
                    "rle": mask_to_rle_counts(rle_to_mask(ann["segmentation"])),
                    "brushlabels": [name],
                }})
        tasks.append({
            "data": {"image": f"/data/local-files/?d={img['file_name']}"},
            "annotations": [{"result": results}],
        })
    with open(os.path.join(out_dir, "tasks.json"), "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# KITTI — one TXT per image (bbox only)
# ---------------------------------------------------------------------------

def _kitti_image(cfg, image_info, annotations, out_dir):
    lines = []
    for ann in annotations:
        if "bbox" not in ann:
            continue
        x, y, w, h = ann["bbox"]
        # type truncated occluded alpha bbox(4) dimensions(3) location(3) rotation_y
        lines.append(
            f"{_cat_name(cfg, ann['category_id'])} 0.00 0 0.00 "
            f"{x:.2f} {y:.2f} {x + w:.2f} {y + h:.2f} "
            f"0.00 0.00 0.00 0.00 0.00 0.00 0.00"
        )
    with open(os.path.join(out_dir, f"{_stem(image_info)}.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


# ---------------------------------------------------------------------------
# CreateML — single JSON (bbox only, center-based absolute coordinates)
# ---------------------------------------------------------------------------

def _createml_final(cfg, images, annotations, out_dir):
    grouped = _anns_by_image(annotations)
    data = []
    for img in images:
        anns = []
        for ann in grouped.get(img["id"], []):
            if "bbox" not in ann:
                continue
            x, y, w, h = ann["bbox"]
            anns.append({
                "label": _cat_name(cfg, ann["category_id"]),
                "coordinates": {"x": round(x + w / 2, 1), "y": round(y + h / 2, 1),
                                "width": round(w, 1), "height": round(h, 1)},
            })
        data.append({"image": img["file_name"], "annotations": anns})
    with open(os.path.join(out_dir, "annotations.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# OpenImages — single CSV (bbox only, normalized coordinates)
# ---------------------------------------------------------------------------

def _openimages_final(cfg, images, annotations, out_dir):
    grouped = _anns_by_image(annotations)
    path = os.path.join(out_dir, "annotations.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ImageID", "Source", "LabelName", "Confidence",
                         "XMin", "XMax", "YMin", "YMax",
                         "IsOccluded", "IsTruncated", "IsGroupOf", "IsDepiction", "IsInside"])
        for img in images:
            W, H = img["width"], img["height"]
            for ann in grouped.get(img["id"], []):
                if "bbox" not in ann:
                    continue
                x, y, w, h = ann["bbox"]
                writer.writerow([
                    _stem(img), "sam3-auto", _cat_name(cfg, ann["category_id"]),
                    round(float(ann.get("score", 1.0)), 4),
                    round(x / W, 6), round((x + w) / W, 6),
                    round(y / H, 6), round((y + h) / H, 6),
                    0, 0, 0, 0, 0,
                ])


# ---------------------------------------------------------------------------
# Supervisely — one JSON per image + meta.json (polygon / rectangle)
# ---------------------------------------------------------------------------

_PALETTE = ["#E6194B", "#3CB44B", "#FF9A00", "#BF40BF", "#FFE119", "#42D4F4"]


def _supervisely_image(cfg, image_info, annotations, out_dir):
    W, H = image_info["width"], image_info["height"]
    objects, figures = [], []
    for ann in annotations:
        name = _cat_name(cfg, ann["category_id"])
        objects.append({"id": ann["id"], "classTitle": name, "tags": []})
        geoms = []
        if cfg.annotation.segmentation and "segmentation" in ann:
            for poly in mask_to_polygons(rle_to_mask(ann["segmentation"])):
                geoms.append(("polygon", {"exterior": [[round(float(x), 1), round(float(y), 1)]
                                                       for x, y in poly],
                                          "interior": []}))
        elif cfg.annotation.bbox and "bbox" in ann:
            x, y, w, h = ann["bbox"]
            geoms.append(("rectangle", {"exterior": [[x, y], [x + w, y + h]], "interior": []}))
        for j, (gtype, points) in enumerate(geoms):
            figures.append({"id": ann["id"] * 1000 + j, "objectId": ann["id"],
                            "geometryType": gtype, "points": points})
    data = {
        "size": {"height": H, "width": W},
        "objects": objects,
        "figures": figures,
        "tags": [],
    }
    with open(os.path.join(out_dir, f"{image_info['file_name']}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _supervisely_final(cfg, images, annotations, out_dir):
    shape = "polygon" if cfg.annotation.segmentation else "rectangle"
    meta = {
        "classes": [
            {"id": c.id, "title": c.name, "shape": shape,
             "color": _PALETTE[i % len(_PALETTE)], "geometry_config": {}, "hotkey": ""}
            for i, c in enumerate(cfg.categories)
        ],
        "tags": [],
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Instance masks — PNG per annotation (delegates to inference.save_masks)
# ---------------------------------------------------------------------------

def _masks_image(cfg, image_info, annotations, out_dir):
    save_masks(_stem(image_info), annotations, out_dir)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXPORTERS: dict[str, ExporterSpec] = {
    "coco":         {"finalize": _coco_final, "needs": ()},
    "yolo":         {"per_image": _yolo_image, "finalize": _yolo_final, "needs": ()},
    "voc":          {"per_image": _voc_image, "needs": ("bbox",)},
    "labelme":      {"per_image": _labelme_image, "needs": ()},
    "cvat":         {"finalize": _cvat_final, "needs": ()},
    "label_studio": {"finalize": _label_studio_final, "needs": ()},
    "kitti":        {"per_image": _kitti_image, "needs": ("bbox",)},
    "createml":     {"finalize": _createml_final, "needs": ("bbox",)},
    "openimages":   {"finalize": _openimages_final, "needs": ("bbox",)},
    "supervisely":  {"per_image": _supervisely_image, "finalize": _supervisely_final, "needs": ()},
    "masks":        {"per_image": _masks_image, "needs": ("seg",)},
}


def _check_needs(fmt: str, exp: ExporterSpec, cfg: Config) -> bool:
    """Skip formats whose required annotation kind is switched off (warn once)."""
    needs = exp.get("needs", ())
    if "bbox" in needs and not cfg.annotation.bbox:
        if fmt not in _warned:
            log.warning(f"format '{fmt}' requires bbox but annotation.bbox=false — skipping")
            _warned.add(fmt)
        return False
    if "seg" in needs and not cfg.annotation.segmentation:
        if fmt not in _warned:
            log.warning(f"format '{fmt}' requires segmentation but annotation.segmentation=false — skipping")
            _warned.add(fmt)
        return False
    return True


def write_image_exports(cfg: Config, image_info: dict, annotations: list):
    """Run all per-image exporters selected in cfg.output.formats."""
    for fmt in cfg.output.formats:
        exp = EXPORTERS[fmt]
        fn = exp.get("per_image")
        if fn is not None and _check_needs(fmt, exp, cfg):
            fn(cfg, image_info, annotations, _fmt_dir(cfg, fmt))


def finalize_exports(cfg: Config, images: list, annotations: list):
    """Run all combined/finalize exporters selected in cfg.output.formats."""
    for fmt in cfg.output.formats:
        exp = EXPORTERS[fmt]
        fn = exp.get("finalize")
        if fn is not None and _check_needs(fmt, exp, cfg):
            fn(cfg, images, annotations, _fmt_dir(cfg, fmt))
