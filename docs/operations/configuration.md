---
title: "13 — Config and Parameters"
category: "SAM 3.1 Auto-Labeling"
order: 13
status: "Verified"
---

# 13 — Config and Parameters

> เอกสารของ config ทั้งหมด — ค่า, หน่วย, ช่วง, default, ผลกระทบ
>
> **Status**: Verified — สอบกับ `src/config.py:10-253` และ `config/ppe_6class.yaml`

---

## Config File

| รายการ | ค่า |
|--------|-----|
| Default path | `config/ppe_6class.yaml` |
| Override | `--config <path>` |
| Format | YAML |
| Validation | `load_config()` ใน `src/config.py:128-211` |

---

## Config จริง (live preview)

@import "../../sam3_auto_label/config/ppe_6class.yaml" {title="config/ppe_6class.yaml"}

---

## โครงสร้าง Config

```yaml
# ตัวอย่าง: config/ppe_6class.yaml
categories:
  - id: 1
    name: person
    prompt: person
    threshold: 0.7
  - id: 2
    name: helmet
    prompt: helmet
    threshold: 0.25
  # ...

inference:
  confidence_threshold: 0.25
  resolution: 1008
  device: auto
  gpu_ops: true
  pipeline_export: true

annotation:
  bbox: true
  segmentation: true
  segmentation_encoding: rle

output:
  formats:
    - coco
  save_viz: true
  input_dir: /mnt/e/02_Projects/auto_label/data/raw
  output_dir: /mnt/e/02_Projects/auto_label/data/sam_outputs_ground_truth
  viz_dpi: 150
  viz_figsize: [10, 7]

checkpoint:
  enabled: true
  auto_resume: true
  clear_on_success: false
```

---

## Parameters ทั้งหมด

### `categories` (list)

| Parameter | Type | Required | Default | Range | หน้าที่ |
|-----------|------|----------|---------|-------|---------|
| `id` | int | ✅ | — | $\geq 1$ | COCO category ID |
| `name` | str | ✅ | — | — | category name (ใช้ใน export) |
| `prompt` | str | ✅ | — | — | text prompt ส่งให้ SAM 3.1 |
| `threshold` | float | ❌ | $-1.0$ | $[-1, 1]$ | per-category confidence threshold |

> `src/config.py:10-15`

### `inference`

| Parameter | Type | Default | Range | หน้าที่ |
|-----------|------|---------|-------|---------|
| `confidence_threshold` | float | $0.4$ | $[0, 1]$ | global threshold (ใช้เมื่อ `cat.threshold = -1`) |
| `resolution` | int | $1008$ | $> 0$ | SAM processor resolution (px) — สูงกว่า = ละเอียดกว่า + ช้ากว่า |
| `device` | str | `"auto"` | `auto`/`cpu`/`cuda`/`rocm`/`mps` | compute device |
| `gpu_ops` | bool | `true` | — | ใช้ GPU RLE/NMS ops ถ้ามี |
| `pipeline_export` | bool | `true` | — | overlap CPU export กับ GPU inference |

> `src/config.py:18-26`

### `annotation`

| Parameter | Type | Default | Range | หน้าที่ |
|-----------|------|---------|-------|---------|
| `bbox` | bool | `true` | — | สร้าง bounding box output |
| `segmentation` | bool | `true` | — | สร้าง segmentation mask output |
| `segmentation_encoding` | str | `"rle"` | `rle`/`polygon` | encoding ของ mask ใน COCO output |

> `src/config.py:45-50`

### `output`

| Parameter | Type | Default | Range | หน้าที่ |
|-----------|------|---------|-------|---------|
| `formats` | list[str] | `["coco"]` | subset ของ `SUPPORTED_FORMATS` | export formats ที่ต้องการ |
| `save_viz` | bool | `true` | — | สร้าง visualization overlay |
| `input_dir` | str | `"input"` | path | โฟลเดอร์ภาพดิบ |
| `output_dir` | str | `"output"` | path | โฟลเดอร์ output |
| `viz_dpi` | int | $100$ | $> 0$ | (ไม่ได้ใช้ — OpenCV viz ไม่ใช้ DPI) |
| `viz_figsize` | tuple | $(10, 7)$ | — | (ไม่ได้ใช้ — OpenCV viz ไม่ใช้ figsize) |

> `src/config.py:53-60`

### `checkpoint`

| Parameter | Type | Default | หน้าที่ |
|-----------|------|---------|---------|
| `enabled` | bool | `true` | เปิด checkpoint/resume |
| `auto_resume` | bool | `true` | resume อัตโนมัติเมื่อ non-interactive |
| `clear_on_success` | bool | `true` | ลบ checkpoint เมื่อจบสำเร็จ |

> `src/config.py:63-67`

---

## Supported Formats (11)

@import "../../sam3_auto_label/src/config.py" {line_begin=30 line_end=42 title="config.py:30-42 — SUPPORTED_FORMATS"}

| Format | BBox | Segmentation | Encoding |
|--------|------|--------------|----------|
| `coco` | ✅ | ✅ | RLE หรือ polygon |
| `yolo` | ✅ | ✅ | normalized polygon |
| `voc` | ✅ | ❌ | VOC bbox XML |
| `labelme` | ✅ | ✅ | polygon JSON |
| `cvat` | ✅ | ✅ | polygon XML |
| `label_studio` | ✅ | ✅ | uncompressed RLE |
| `kitti` | ✅ | ❌ | KITTI txt |
| `createml` | ✅ | ❌ | center coords JSON |
| `openimages` | ✅ | ❌ | normalized bbox CSV |
| `supervisely` | ✅ | ✅ | polygon JSON + meta |
| `masks` | ❌ | ✅ | binary PNG |

---

## CLI Overrides

| Flag | Override |
|------|----------|
| `--threshold <float>` | `cfg.inference.confidence_threshold` |
| `--resolution <int>` | `cfg.inference.resolution` |
| `--device <str>` | `cfg.inference.device` |
| `--input <path>` | `cfg.output.input_dir` |
| `--output <path>` | `cfg.output.output_dir` |
| `--resume` | resume จาก checkpoint |
| `--fresh` | เริ่มใหม่ (ลบ checkpoint) |

> `src/batch_segment.py:97-107, 135-144`

---

## การ Validate Config

`load_config()` (`src/config.py:128-211`) ตรวจสอบ:

| Validation | Error ถ้า fail |
|------------|----------------|
| Category มี `id`, `name`, `prompt` | `ValueError` |
| `threshold` อยู่ใน $[-1, 1]$ | `ValueError` |
| `confidence_threshold` อยู่ใน $[0, 1]$ | `ValueError` |
| `segmentation_encoding` เป็น `rle` หรือ `polygon` | `ValueError` |
| `formats` ทุกตัวอยู่ใน `SUPPORTED_FORMATS` | `ValueError` |
| `annotation.bbox` หรือ `annotation.segmentation` อย่างน้อยอย่างเป็น `true` | `ValueError` |

---

## อ้างอิง

- `src/config.py:10-253` — dataclasses + load/save
- `config/ppe_6class.yaml` — actual values
- `src/batch_segment.py:97-107` — CLI args
