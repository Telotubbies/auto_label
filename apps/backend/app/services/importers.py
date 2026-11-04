"""Turn an upload (loose files and/or zips) into images + annotations.

Recognised annotation sources, matched to images by file name / stem:
  COCO JSON (*.json with images/annotations/categories), Label Studio JSON task list,
  YOLO txt (+ data.yaml / classes.txt for names), Pascal VOC xml, CVAT for Images xml.
  Classification: images inside a folder named after the class.
"""
import io
import json
import math
import re
import zipfile
from pathlib import PurePosixPath

from defusedxml import ElementTree as ET      # no entity expansion / billion-laughs on uploaded XML

from .imaging import ext_ok


class Bundle:
    def __init__(self):
        self.images: dict[str, bytes] = {}        # posix path -> bytes
        self.coco: dict[str, list] = {}           # file name -> [(class name, shape)] (pixel coords, normalized later)
        self.coco_size: dict[str, tuple[int, int]] = {}
        self.yolo: dict[str, str] = {}            # stem -> txt
        self.voc: dict[str, str] = {}             # stem -> xml
        self.cvat: dict[str, list[tuple[str, dict]]] = {}   # image basename -> [(class name, shape)]
        self.ls: dict[str, list[tuple[str, dict]]] = {}     # image basename -> [(class name, shape)]
        self.names: list[str] = []
        self.task: str = ""                      # data.yaml task: e.g. obb
        self.skeletons: dict[str, dict] = {}     # class name -> {"names": [...], "edges": [[i, j], ...]} (0-based)

    @property
    def has_annotations(self) -> bool:
        return bool(self.coco or self.yolo or self.voc or self.cvat or self.ls)


MAX_ZIP_TOTAL = 4 * 1024**3       # uncompressed bytes per upload
MAX_ZIP_FILES = 50_000
MAX_RATIO = 200                    # compression ratio above this is treated as a zip bomb
MAX_XML_BYTES = 8 * 1024 * 1024    # annotation XML larger than this is skipped, not parsed


class ImportError_(ValueError):
    pass


def collect(files: list[tuple[str, bytes]]) -> Bundle:
    b = Bundle()
    queue = list(files)
    budget, count = MAX_ZIP_TOTAL, 0
    while queue:
        name, data = queue.pop()
        name = name.replace("\\", "/")
        low = name.lower()
        if low.endswith(".zip"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                raise ImportError_(f"{name} is not a valid zip")
            with z:
                for i in z.infolist():
                    if i.is_dir() or "__MACOSX" in i.filename or i.filename.lower().endswith(".zip"):
                        continue     # nested zips are skipped: no recursive bombs
                    count += 1; budget -= i.file_size
                    if count > MAX_ZIP_FILES or budget < 0:
                        raise ImportError_("archive too large (max 50,000 files / 4 GB uncompressed)")
                    if i.compress_size and i.file_size / i.compress_size > MAX_RATIO:
                        raise ImportError_(f"{i.filename}: suspicious compression ratio")
                    queue.append((i.filename, z.read(i)))
        elif ext_ok(low):
            b.images[name] = data
        elif low.endswith(".json"):
            if not _coco(b, data):
                _label_studio_file(b, data)
        elif low.endswith(".txt"):
            stem = PurePosixPath(name).stem
            if stem in ("classes", "_darknet.labels", "obj"):
                b.names = [l.strip() for l in data.decode(errors="ignore").splitlines() if l.strip()]
            else:
                b.yolo[stem] = data.decode(errors="ignore")
        elif low.endswith(".labels"):
            b.names = [l.strip() for l in data.decode(errors="ignore").splitlines() if l.strip()]
        elif low.endswith((".yaml", ".yml")):
            text = data.decode(errors="ignore")
            task = re.search(r"^task:\s*(\w+)", text, re.M)
            if task:
                b.task = task.group(1).lower()
            m = re.search(r"names:\s*(\[.*?\])", text, re.S)
            if m:
                try:
                    b.names = json.loads(m.group(1).replace("'", '"'))
                except json.JSONDecodeError:
                    pass
            else:   # block list:  names:\n  0: person\n  1: helmet   or  - person
                block = re.search(r"names:\s*\n((?:\s+.+\n?)+)", text)
                if block:
                    b.names = [re.sub(r"^\s*(?:-|\d+:)\s*", "", l).strip().strip("'\"")
                               for l in block.group(1).splitlines() if l.strip()]
        elif low.endswith(".xml"):
            if len(data) > MAX_XML_BYTES:
                continue
            if not _cvat(b, data):
                b.voc[PurePosixPath(name).stem] = data.decode(errors="ignore")
    if not b.task:
        b.task = _infer_obb_task(b.yolo)
    return b


def _infer_obb_task(yolo: dict[str, str]) -> str:
    """Task-less YOLO sets whose labels are all eight-value lines are OBB (ultralytics DOTA layout).

    Polygon segmentation labels are six or more values; a mixed set stays a polygon dataset.
    """
    lengths = {len(line.split()) - 1 for text in yolo.values() for line in text.splitlines()
               if len(line.split()) >= 5}
    return "obb" if lengths == {8} else ""


def _coco(b: Bundle, data: bytes) -> bool:
    """Parse COCO JSON. True when the file is COCO-shaped (even if it yields no shapes)."""
    try:
        d = json.loads(data)
    except ValueError:                     # JSONDecodeError or invalid UTF-8
        return False
    if not isinstance(d, dict) or "images" not in d or "annotations" not in d:
        return False
    cats = {c["id"]: c["name"] for c in d.get("categories", []) if isinstance(c, dict) and "id" in c}
    for c in d.get("categories", []):
        if not isinstance(c, dict) or not isinstance(c.get("name"), str):
            continue
        names = c.get("keypoints")
        if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
            continue
        edges = []
        for pair in c.get("skeleton") or []:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            a, e = pair
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (a, e)):
                continue
            a, e = a - 1, e - 1                       # COCO is 1-based, our contract is 0-based
            if 0 <= a < len(names) and 0 <= e < len(names) and a != e and [a, e] not in edges:
                edges.append([a, e])
        b.skeletons[c["name"]] = {"names": names, "edges": edges}
    imgs = {i["id"]: i for i in d["images"]}
    for i in d["images"]:
        b.coco_size[PurePosixPath(i["file_name"]).name] = (i.get("width", 0), i.get("height", 0))
    for a in d["annotations"]:
        im = imgs.get(a["image_id"])
        if not im or a.get("category_id") not in cats:
            continue
        fname = PurePosixPath(im["file_name"]).name
        kp = a.get("keypoints")
        if isinstance(kp, list) and len(kp) >= 3 and len(kp) % 3 == 0:
            try:
                shape = {"kind": "keypoints", "points_px": [float(v) for v in kp]}
            except (TypeError, ValueError):
                continue
        else:
            seg = a.get("segmentation")
            if isinstance(seg, list) and seg and isinstance(seg[0], list) and len(seg[0]) >= 6:
                shape = {"kind": "polygon", "points_px": seg[0]}
            elif a.get("bbox"):
                x, y, w, h = a["bbox"]
                shape = {"kind": "bbox", "px": [x, y, w, h]}
            else:
                continue
        b.coco.setdefault(fname, []).append((cats[a["category_id"]], shape))
    return True


def _cvat(b: Bundle, data: bytes) -> bool:
    """Parse CVAT for Images XML. False when the file is not CVAT (VOC or unparseable)."""
    try:
        root = ET.fromstring(data)
    except Exception:                    # parse error, forbidden entity/DTD, or encoding garbage
        return False
    if root.tag != "annotation" or root.find("image") is None:
        return False
    for image in root.iter("image"):
        name = PurePosixPath((image.get("name") or "").replace("\\", "/")).name
        if not name:
            continue
        try:
            W, H = float(image.get("width") or 0), float(image.get("height") or 0)
        except ValueError:
            W = H = 0.0
        sized = W > 0 and H > 0
        for el in image:
            label = el.get("label")
            if not label:
                continue
            if el.tag == "box":
                try:
                    x1, y1, x2, y2 = (float(el.get(k)) for k in ("xtl", "ytl", "xbr", "ybr"))
                except (TypeError, ValueError):
                    continue
                if sized:
                    shape = {"kind": "bbox", "x": x1 / W, "y": y1 / H,
                             "w": (x2 - x1) / W, "h": (y2 - y1) / H}
                else:   # no size on <image>: keep pixels, normalize against the real image later
                    shape = {"kind": "bbox_px", "px": [x1, y1, x2, y2]}
                b.cvat.setdefault(name, []).append((label, shape))
            elif el.tag == "polygon":
                pts = _points(el.get("points"))
                if len(pts) < 6:
                    continue
                if sized:
                    shape = {"kind": "polygon",
                             "points": [v / (W if i % 2 == 0 else H) for i, v in enumerate(pts)]}
                else:
                    shape = {"kind": "polygon_px", "points_px": pts}
                b.cvat.setdefault(name, []).append((label, shape))
    return True


def _points(raw: str | None) -> list[float]:
    """'x1,y1;x2,y2;...' or 'x1,y1 x2,y2 ...' -> flat pixel list ([] when malformed)."""
    out: list[float] = []
    if not raw:
        return out
    try:
        for token in raw.replace(";", " ").split():
            x, y = token.split(",")
            out.extend((float(x), float(y)))
    except ValueError:
        return []
    return out


def _label_studio_file(b: Bundle, data: bytes):
    try:
        d = json.loads(data)
    except ValueError:                     # JSONDecodeError or invalid UTF-8
        return
    _label_studio(b, d)


def _label_studio(b: Bundle, d) -> bool:
    """Parse a Label Studio task list (list or {"tasks": [...]}) into normalized shapes."""
    tasks = d if isinstance(d, list) else d.get("tasks") if isinstance(d, dict) else None
    if not isinstance(tasks, list):
        return False
    if not any(isinstance(t, dict) and isinstance(t.get("data"), dict) and isinstance(t.get("annotations"), list)
               for t in tasks):
        return False
    for task in tasks:
        if not isinstance(task, dict):
            continue
        data, anns = task.get("data"), task.get("annotations")
        if not isinstance(data, dict) or not isinstance(anns, list):
            continue
        image = data.get("image")
        if not isinstance(image, str):
            continue
        name = PurePosixPath(image.split("#")[0].split("?")[0].replace("\\", "/")).name
        if not name:
            continue
        for ann in anns:
            if not isinstance(ann, dict) or not isinstance(ann.get("result"), list):
                continue
            for result in ann["result"]:
                b.ls.setdefault(name, []).extend(_ls_result(result))
    return True


def _ls_result(r) -> list[tuple[str, dict]]:
    """One Label Studio result -> one shape per label (unknown types and empty labels are skipped)."""
    if not isinstance(r, dict):
        return []
    value = r.get("value")
    if not isinstance(value, dict):
        return []
    raw_labels = value.get("labels")
    labels = [label for label in raw_labels if isinstance(label, str) and label] if isinstance(raw_labels, list) else []
    if not labels:
        return []
    if r.get("type") == "rectanglelabels":
        try:
            x, y, w, h = (float(value[k]) for k in ("x", "y", "width", "height"))
        except (KeyError, TypeError, ValueError):
            return []
        return [(label, {"kind": "bbox", "x": x / 100, "y": y / 100,
                         "w": w / 100, "h": h / 100}) for label in labels]
    if r.get("type") == "polygonlabels":
        pts = value.get("points")
        if not isinstance(pts, list):
            return []
        try:
            flat = [v / 100 for p in pts for v in (float(p[0]), float(p[1]))]
        except (TypeError, ValueError, IndexError):
            return []
        if len(flat) < 6:
            return []
        return [(label, {"kind": "polygon", "points": list(flat)}) for label in labels]
    return []


def _normalize(shape: dict, W: int, H: int) -> dict:
    """Resolve CVAT pixel shapes that had no declared image size."""
    if shape["kind"] == "bbox_px":
        x1, y1, x2, y2 = shape["px"]
        return {"kind": "bbox", "x": x1 / W, "y": y1 / H, "w": (x2 - x1) / W, "h": (y2 - y1) / H}
    if shape["kind"] == "polygon_px":
        return {"kind": "polygon",
                "points": [v / (W if i % 2 == 0 else H) for i, v in enumerate(shape["points_px"])]}
    return shape


def _obb_from_corners(vals: list[float], W: int, H: int) -> dict:
    """YOLO-OBB's eight normalized corner values -> normalized obb (angles derived in pixel space)."""
    pts = [(vals[i] * W, vals[i + 1] * H) for i in range(0, 8, 2)]
    cx = sum(p[0] for p in pts) / 4
    cy = sum(p[1] for p in pts) / 4
    w = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    h = math.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    angle = math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])
    return {"kind": "obb", "cx": cx / W, "cy": cy / H, "w": w / W, "h": h / H, "angle": angle}


def _normalized_keypoints(points_px: list[float], cw: int, ch: int) -> list[float]:
    out: list[float] = []
    for i in range(0, len(points_px) - 2, 3):
        out.extend((points_px[i] / cw, points_px[i + 1] / ch, int(points_px[i + 2])))
    return out


def annotations_for(b: Bundle, path: str, W: int, H: int) -> list[tuple[str, dict]]:
    """-> [(class name, normalized shape)] for one image (coco, then cvat, then label studio)."""
    name, stem = PurePosixPath(path).name, PurePosixPath(path).stem
    out = []
    if name in b.coco:
        cw, ch = b.coco_size.get(name) or (W, H)
        cw, ch = cw or W, ch or H
        for cls, s in b.coco[name]:
            if s["kind"] == "bbox":
                x, y, w, h = s["px"]
                out.append((cls, {"kind": "bbox", "x": x / cw, "y": y / ch, "w": w / cw, "h": h / ch}))
            elif s["kind"] == "keypoints":
                out.append((cls, {"kind": "keypoints", "points": _normalized_keypoints(s["points_px"], cw, ch)}))
            else:
                out.append((cls, {"kind": "polygon", "points": [v / (cw if i % 2 == 0 else ch) for i, v in enumerate(s["points_px"])]}))
    for source in (b.cvat, b.ls):
        for cls, s in source.get(name, ()):
            out.append((cls, _normalize(s, W, H)))
    if not out and stem in b.yolo:
        for line in b.yolo[stem].splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            ci = int(float(parts[0])); vals = [float(v) for v in parts[1:]]
            cls = b.names[ci] if ci < len(b.names) else f"class_{ci}"
            if b.task == "obb" and len(vals) == 8:
                out.append((cls, _obb_from_corners(vals, W, H)))
            elif len(vals) == 4:
                cx, cy, w, h = vals
                out.append((cls, {"kind": "bbox", "x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h}))
            elif len(vals) >= 6:
                out.append((cls, {"kind": "polygon", "points": vals}))
    elif not out and stem in b.voc:
        try:
            root = ET.fromstring(b.voc[stem])
            for o in root.iter("object"):
                bb = o.find("bndbox")
                x1, y1, x2, y2 = (float(bb.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
                out.append((o.find("name").text, {"kind": "bbox", "x": x1 / W, "y": y1 / H, "w": (x2 - x1) / W, "h": (y2 - y1) / H}))
        except Exception:
            pass
    return out


def folder_class(path: str) -> str | None:
    """Classification import: train/cat/img.jpg -> 'cat' (ignores split folder names)."""
    parts = [p for p in PurePosixPath(path).parts[:-1] if p.lower() not in ("train", "valid", "val", "test", "images")]
    return parts[-1] if parts else None


def split_of(path: str) -> str | None:
    for p in PurePosixPath(path).parts[:-1]:
        p = p.lower()
        if p in ("train", "test"):
            return p
        if p in ("valid", "val"):
            return "valid"
    return None
