---
title: "06 — Class Diagram"
category: "SAM 3.1 Auto-Labeling"
order: 6
status: "Verified"
---

# 06 — Class Diagram

> โครงสร้าง class และความสัมพันธ์ในระบบ
>
> **Status**: Verified — สอบกับ `src/config.py`, `src/inference.py`, `src/tracker.py`, `src/exporters.py`

---

## Class Diagram

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam package {
  BorderColor #4285F4
  BackgroundColor #F0F4FF
}

package "inference.py" {
  [build_model\ncfg → processor] as BM
  [segment_image\nprocessor + image → annotations] as SI
  [save_coco\nannotations → JSON] as SC
  [save_masks\nannotations → PNG] as SM
  [save_viz\nimage + annotations → overlay PNG] as SV
  [resolve_device\ncfg → device string] as RD
}

package "NMS" {
  [cross_class_nms\nCPU path] as CN
  [cross_class_nms_gpu\nGPU path] as CNG
  [_gpu_nms] as GN
  [_gpu_bbox_nms] as GBN
}

package "RLE" {
  [mask_to_rle\nCPU] as MR
  [mask_to_rle_gpu\nGPU] as MRG
  [masks_batch_to_rle_gpu] as MBR
}

BM --> SI
SI --> CN
CN --> CNG
CNG --> GN
GN --> GBN
SI --> MR
MR --> MRG
MRG --> MBR
SI --> SC
SI --> SM
SI --> SV
@enduml
```

### `exporters.py` — Export Registry

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam package {
  BorderColor #34A853
  BackgroundColor #F0F8F0
}

package "exporters.py" {
  [write_image_exports\nper-image] as WE
  [finalize_exports\nend-of-run] as FE
  [EXPORTERS registry] as REG

  [_coco_final] as CF
  [_yolo_image + _yolo_final] as YOLO
  [_voc_image] as VOC
  [_labelme_image] as LM
  [_cvat_final] as CVAT
  [_label_studio_final] as LS
  [_kitti_image] as KITTI
  [_createml_final] as CM
  [_openimages_final] as OI
  [_supervisely_image + _supervisely_final] as SUP
  [_masks_image] as MASKS
}

WE --> REG
FE --> REG
REG --> CF
REG --> YOLO
REG --> VOC
REG --> LM
REG --> CVAT
REG --> LS
REG --> KITTI
REG --> CM
REG --> OI
REG --> SUP
REG --> MASKS
@enduml
```

---

## สิ่งที่ระบบทั่วไปมักมี (แต่โค้ดนี้ไม่มี)

| Class ทั่วไป | สถานะ | หมายเหตุ |
|----------------|-------|---------|
| `Segmenter` interface (abstract) | ❌ | `build_model` ผูกกับ SAM 3.1 โดยตรง |
| `SAM3Segmenter`, `SAM2Segmenter`, `YOLOSegmenter` | ❌ | ไม่มี polymorphism — เปลี่ยน model ต้องแก้ `inference.py` |
| `ImageLoader` class | ❌ | เป็นฟังก์ชัน `load_image` ใน `batch_segment.py` |
| `Preprocessor` class | ❌ | SAM processor จัดการ resize เอง |
| `PromptGenerator` class | ❌ | prompt มาจาก config ตรง ๆ |
| `MaskProcessor` class | ❌ | กระจายอยู่ใน `inference.py` (NMS, RLE, clamp) |
| `Classifier` class | ❌ | ไม่มี classifier แยก |
| `ConfidenceScorer` class | ❌ | ใช้ score ดิบจาก model |
| `LabelValidator` class | ❌ | ไม่มี validation ก่อน export |
| `AutoLabeler`, `HumanReviewer` class | ❌ | ไม่มี review process |
| `DatasetExporter` class | ❌ | เป็น registry ของฟังก์ชัน ไม่ใช่ class |

---

## อ้างอิง

- `src/config.py:10-125` — dataclasses
- `src/tracker.py:23-229` — ExperimentTracker
- `src/inference.py:347-365` — build_model (ไม่ใช่ class)
- `src/exporters.py:577-589` — EXPORTERS registry (ไม่ใช่ class)
