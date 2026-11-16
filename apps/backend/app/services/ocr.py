"""OCR annotations: Thai document templates, text/key-value/table payloads and exports.

An OCR annotation is an ordinary bbox annotation with an `ocr` payload attached, so the
existing geometry tools, classes and annotation canvas keep working unchanged:

    {"kind": "text", "text": "..."}
    {"kind": "keyvalue", "key": "...", "value": "..."}
    {"kind": "table", "rows": 2, "cols": 3, "cells": [["a", "b", "c"], [...]]}

Exports read the stored annotations (not a dataset version) because OCR text is annotation
metadata: image -> Markdown / JSON, and the PaddleOCR detection label format.
"""

import json
import re
import shutil
import uuid
from pathlib import Path

OCR_KINDS = ("text", "keyvalue", "table")
EXPORT_FORMATS = ("markdown", "json", "paddleocr")
MAX_TEXT = 2000
MAX_KEY = 200
MAX_CELL = 500
MAX_ROWS, MAX_COLS = 50, 20

# Field presets for the Thai documents the Thai-document solution pack targets.
TEMPLATES: dict[str, dict] = {
    "thai_id_card": {
        "name": "บัตรประชาชนไทย",
        "fields": ["เลขประจำตัวประชาชน", "ชื่อ", "นามสกุล", "วันเกิด", "ที่อยู่"],
    },
    "delivery_note": {
        "name": "ใบขนส่ง / ใบส่งของ",
        "fields": ["เลขที่เอกสาร", "วันที่", "ผู้ส่ง", "ผู้รับ", "น้ำหนัก", "ปลายทาง"],
    },
    "meter": {
        "name": "มิเตอร์ไฟฟ้า / น้ำ",
        "fields": ["เลขมิเตอร์", "หน่วย", "วันที่จด", "ประเภท"],
    },
    "vehicle_registration": {
        "name": "ทะเบียนรถ",
        "fields": ["ทะเบียน", "จังหวัด", "ยี่ห้อ", "รุ่น", "ปี", "เจ้าของ"],
    },
}

# PDPA: the values masked in the UI and on export. Order matters (dashed ID before plain digits).
# Thai ID cards print the number with dashes, spaces or non-breaking spaces, so accept all three.
_PII_PATTERNS = (
    re.compile(
        r"(?<!\d)\d[-\u00a0 ]\d{4}[-\u00a0 ]\d{5}[-\u00a0 ]\d{2}[-\u00a0 ]\d(?!\d)"
    ),
    re.compile(r"(?<!\d)\d{13}(?!\d)"),
    re.compile(r"(?<!\d)0[1-9](?:[-\s]?\d){8}(?!\d)"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
)


def mask_pii(text: str) -> str:
    """Replace detected personal data with `*` of the same length (keeps layout readable)."""
    for pattern in _PII_PATTERNS:
        text = pattern.sub(lambda m: "*" * len(m.group(0)), text)
    return text


def clean_ocr(raw) -> dict:
    """Validate and normalise an annotation `ocr` payload. Raises ValueError for bad input."""
    if not isinstance(raw, dict):
        raise ValueError("ocr must be an object")
    kind = raw.get("kind")
    if kind not in OCR_KINDS:
        raise ValueError("ocr.kind must be text | keyvalue | table")

    def text_field(name: str, limit: int, default: str = "") -> str:
        value = raw.get(name, default)
        if not isinstance(value, str):
            raise ValueError(f"ocr.{name} must be a string")
        if len(value) > limit:
            raise ValueError(f"ocr.{name} is longer than {limit} characters")
        return value

    if kind == "text":
        return {"kind": "text", "text": text_field("text", MAX_TEXT)}
    if kind == "keyvalue":
        return {
            "kind": "keyvalue",
            "key": text_field("key", MAX_KEY),
            "value": text_field("value", MAX_TEXT),
        }

    rows, cols = raw.get("rows"), raw.get("cols")
    if not isinstance(rows, int) or isinstance(rows, bool) or not 1 <= rows <= MAX_ROWS:
        raise ValueError(f"ocr.rows must be an integer from 1 to {MAX_ROWS}")
    if not isinstance(cols, int) or isinstance(cols, bool) or not 1 <= cols <= MAX_COLS:
        raise ValueError(f"ocr.cols must be an integer from 1 to {MAX_COLS}")
    cells = raw.get("cells")
    if not isinstance(cells, list) or len(cells) != rows:
        raise ValueError(f"ocr.cells must have exactly {rows} rows")
    clean_cells = []
    for row in cells:
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError(f"each ocr.cells row must have exactly {cols} cells")
        clean_row = []
        for cell in row:
            if not isinstance(cell, str) or len(cell) > MAX_CELL:
                raise ValueError(
                    f"ocr cells must be strings of at most {MAX_CELL} characters"
                )
            clean_row.append(cell)
        clean_cells.append(clean_row)
    return {"kind": "table", "rows": rows, "cols": cols, "cells": clean_cells}


def ocr_of(ann: dict) -> dict | None:
    raw = ann.get("ocr")
    return raw if isinstance(raw, dict) and raw.get("kind") in OCR_KINDS else None


def _box(ann: dict) -> list[float] | None:
    shape = ann.get("shape") or {}
    if shape.get("kind") != "bbox":
        return None
    return [round(float(shape[k]), 4) for k in ("x", "y", "w", "h")]


def _sort_key(ann: dict):
    box = _box(ann)
    return (box[1], box[0]) if box else (1.0, 1.0)


def _cells(ocr: dict) -> list[list[str]]:
    """Table rows as stored; a hand-edited row without cells exports as nothing, not a 500."""
    cells = ocr.get("cells")
    return (
        [row for row in cells if isinstance(row, list)]
        if isinstance(cells, list)
        else []
    )


def _text_of(ann: dict, mask: bool) -> str:
    ocr = ocr_of(ann) or {}
    text = ""
    if ocr.get("kind") == "text":
        text = ocr.get("text", "")
    elif ocr.get("kind") == "keyvalue":
        key, value = ocr.get("key", ""), ocr.get("value", "")
        text = f"{key}: {value}" if key else value
    return mask_pii(text) if mask else text


def markdown_for(name: str, anns: list[dict], mask: bool = True) -> str:
    """One Markdown document per image: text lines, key/value fields and tables."""
    lines = [f"# {name}", ""]
    ocr_anns = sorted((a for a in anns if ocr_of(a) and _box(a)), key=_sort_key)
    texts = [a for a in ocr_anns if ocr_of(a)["kind"] == "text"]
    pairs = [a for a in ocr_anns if ocr_of(a)["kind"] == "keyvalue"]
    tables = [a for a in ocr_anns if ocr_of(a)["kind"] == "table"]

    if texts:
        lines += ["## Text", ""]
        for ann in texts:
            lines.append(f"- {_text_of(ann, mask)}")
        lines.append("")
    if pairs:
        lines += ["## Fields", ""]
        for ann in pairs:
            ocr = ocr_of(ann)
            key = ocr.get("key", "")
            value = ocr.get("value", "")
            lines.append(
                f"- **{mask_pii(key) if mask else key}**: {mask_pii(value) if mask else value}"
            )
        lines.append("")
    if tables:
        lines += ["## Tables", ""]
        for ann in tables:
            rows = _cells(ocr_of(ann))
            if not rows:
                continue
            width = max(len(r) for r in rows)
            for i, row in enumerate(rows):
                cells = [(mask_pii(c) if mask else c).replace("|", "\\|") for c in row]
                cells += [""] * (width - len(cells))
                lines.append("| " + " | ".join(cells) + " |")
                if i == 0:
                    lines.append("| " + " | ".join(["---"] * width) + " |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def json_for(items: list[dict], mask: bool = True) -> dict:
    """Aggregate JSON export. `items` are {name,width,height,annotations} dicts."""
    images = []
    for item in items:
        ocr_anns = sorted(
            (a for a in item["annotations"] if ocr_of(a) and _box(a)), key=_sort_key
        )
        entry = {
            "image": item["name"],
            "width": item["width"],
            "height": item["height"],
            "text_lines": [],
            "key_values": [],
            "tables": [],
        }
        for ann in ocr_anns:
            ocr = ocr_of(ann)
            if ocr["kind"] == "text":
                text = ocr.get("text", "")
                entry["text_lines"].append(
                    {"text": mask_pii(text) if mask else text, "box": _box(ann)}
                )
            elif ocr["kind"] == "keyvalue":
                key, value = ocr.get("key", ""), ocr.get("value", "")
                entry["key_values"].append(
                    {
                        "key": mask_pii(key) if mask else key,
                        "value": mask_pii(value) if mask else value,
                        "box": _box(ann),
                    }
                )
            else:
                rows = _cells(ocr)
                if not rows:
                    continue
                cells = [[mask_pii(c) if mask else c for c in row] for row in rows]
                entry["tables"].append(
                    {
                        "rows": ocr.get("rows", len(cells)),
                        "cols": ocr.get("cols", max(len(r) for r in cells)),
                        "cells": cells,
                        "box": _box(ann),
                    }
                )
        images.append(entry)
    return {"format": "labeldesk-ocr", "version": 1, "images": images}


def paddleocr_label(items: list[dict], mask: bool = True) -> str:
    """PaddleOCR detection label file: `image\\t[{transcription, points, difficulty}]`.

    Tables have no per-cell geometry, so they are exported through the JSON/Markdown formats only.
    """
    lines = []
    for item in items:
        W, H = item["width"], item["height"]
        entries = []
        for ann in sorted(
            (a for a in item["annotations"] if ocr_of(a) and _box(a)), key=_sort_key
        ):
            if ocr_of(ann)["kind"] == "table":
                continue
            x, y, w, h = _box(ann)
            points = [
                [round(x * W, 2), round(y * H, 2)],
                [round((x + w) * W, 2), round(y * H, 2)],
                [round((x + w) * W, 2), round((y + h) * H, 2)],
                [round(x * W, 2), round((y + h) * H, 2)],
            ]
            entries.append(
                {
                    "transcription": _text_of(ann, mask),
                    "points": points,
                    "difficulty": 0,
                    "id": len(entries),
                }
            )
        if entries:
            lines.append(
                f"images/{Path(item['name']).name}\t{json.dumps(entries, ensure_ascii=False)}"
            )
    return "\n".join(lines) + ("\n" if lines else "")


def write_export(
    fmt: str, out: Path, items: list[dict], images_root: Path, mask: bool = True
) -> int:
    """Write an export tree under `out`; returns the number of images written."""
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"format must be one of {', '.join(EXPORT_FORMATS)}")
    out.mkdir(parents=True, exist_ok=True)
    if fmt == "markdown":
        (out / "markdown").mkdir()
        used: set[str] = set()
        for item in items:
            stem = Path(item["name"]).stem or "image"
            name, n = stem, 1
            while name in used:
                n += 1
                name = f"{stem}-{n}"
            used.add(name)
            (out / "markdown" / f"{name}.md").write_text(
                markdown_for(item["name"], item["annotations"], mask), encoding="utf-8"
            )
    elif fmt == "json":
        (out / "ocr.json").write_text(
            json.dumps(json_for(items, mask), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        (out / "label.txt").write_text(paddleocr_label(items, mask), encoding="utf-8")
        (out / "images").mkdir()
        for item in items:
            src = images_root / item["path"]
            if src.is_file():
                shutil.copyfile(src, out / "images" / Path(item["name"]).name)
    (out / "README.labeldesk.txt").write_text(
        f"Exported from LabelDesk\nformat: OCR {fmt}\nimages: {len(items)}\nPII masked: {'yes' if mask else 'no'}\n",
        encoding="utf-8",
    )
    return len(items)


def build_export(
    fmt: str, out: Path, items: list[dict], images_root: Path, mask: bool = True
) -> Path:
    """Build into a unique temp dir then rename, so a concurrent request never sees a half export."""
    tmp = out.with_name(f".{out.name}.{uuid.uuid4().hex}.tmp")
    try:
        write_export(fmt, tmp, items, images_root, mask)
        if out.exists():
            shutil.rmtree(out)
        tmp.rename(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out
