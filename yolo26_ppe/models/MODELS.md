# YOLO26 PPE Models — Directory & Version Guide

## Overview

โฟลเดอร์นี้เก็บโมเดล YOLO26 ที่ฝึกทั้งหมด แยกตามขนาด (n/s), ประเภท (detect/seg), และเวอร์ชันฝึก (v1/v2/v3/v4).

**โมเดลที่ใช้ใน report (canonical)** = `*_v4_recipe` เท่านั้น
โมเดลอื่นเก็บไว้เป็นประวัติการทดลอง ไม่ใช้ใน report

---

## โครงสร้าง

```
models/
├── pretrained/                          # Base weights (ไม่ได้ฝึก)
│   ├── yolo26n.pt                       # YOLO26n detection base (5.4 MB)
│   ├── yolo26n-seg.pt                   # YOLO26n segmentation base (6.6 MB)
│   ├── yolo26s.pt                       # YOLO26s detection base (19.9 MB)
│   └── yolo26s-seg.pt                   # YOLO26s segmentation base (22.9 MB)
│
├── yolo26n_detect/                      # v1 — baseline (เก่า ไม่ใช้)
├── yolo26n_detect_v2/                   # v2 — ปรับ data+epochs (เก่า ไม่ใช้)
├── yolo26n_detect_v3_adamw/             # v3 — เปลี่ยน optimizer AdamW (เก่า ไม่ใช้)
├── yolo26n_detect_v4_recipe/            # v4 — CANONICAL ★
│
├── yolo26s_detect/                      # v1 — baseline (เก่า ไม่ใช้)
├── yolo26s_detect_v2/                   # v2 — ปรับ data+epochs (เก่า ไม่ใช้)
├── yolo26s_detect_v4_recipe/            # v4 — CANONICAL ★
│
├── yolo26n_seg/                         # v1 — baseline (เก่า ไม่ใช้)
├── yolo26n_seg_v2/                      # v2 — ปรับ data+epochs (เก่า ไม่ใช้)
├── yolo26n_seg_v4_recipe/               # v4 — CANONICAL ★
│
├── yolo26s_seg/                         # v1 — baseline (เก่า ไม่ใช้)
├── yolo26s_seg_v2/                      # v2 — ปรับ data+epochs (เก่า ไม่ใช้)
└── yolo26s_seg_v4_recipe/               # v4 — CANONICAL ★
```

---

## รายละเอียดแต่ละโมเดล

### pretrained/ — Base Weights (Ultralytics)

| ไฟล์ | ประเภท | ขนาด | ที่มา |
|------|--------|------|------|
| yolo26n.pt | detect | 5.4 MB | Ultralytics pretrained |
| yolo26n-seg.pt | seg | 6.6 MB | Ultralytics pretrained |
| yolo26s.pt | detect | 19.9 MB | Ultralytics pretrained |
| yolo26s-seg.pt | seg | 22.9 MB | Ultralytics pretrained |

ใช้เป็น starting point สำหรับ transfer learning ทุกครั้ง

---

### v1 — Baseline (yolo26n_detect, yolo26s_detect, yolo26n_seg, yolo26s_seg)

| โมเดล | ประเภท | Epochs | mAP50 (val) | สถานะ |
|-------|--------|--------|-------------|--------|
| yolo26n_detect | detect | 149 | 0.369 | เก่า ไม่ใช้ |
| yolo26s_detect | detect | 150 | 0.443 | เก่า ไม่ใช้ |
| yolo26n_seg | seg | 77 | 0.342 (box) / 0.304 (mask) | เก่า ไม่ใช้ |
| yolo26s_seg | seg | 150 | 0.446 (box) / 0.394 (mask) | เก่า ไม่ใช้ |

**หมายเหตุ**: ฝึกครั้งแรกด้วย config เริ่มต้น ข้อมูลยังไม่ balanced, epochs น้อย, ผลต่ำ
แต่ละโฟลเดอร์มี `tune_trial1-3` (hyperparameter tuning trials) ด้วย

---

### v2 — Data + Epochs (yolo26n_detect_v2, yolo26s_detect_v2, yolo26n_seg_v2, yolo26s_seg_v2)

| โมเดล | ประเภท | Epochs | mAP50 (val) | สถานะ |
|-------|--------|--------|-------------|--------|
| yolo26n_detect_v2 | detect | 300 | 0.703 | เก่า ไม่ใช้ |
| yolo26s_detect_v2 | detect | 300 | 0.795 | เก่า ไม่ใช้ |
| yolo26n_seg_v2 | seg | 300 | 0.562 (box) / 0.511 (mask) | เก่า ไม่ใช้ |
| yolo26s_seg_v2 | seg | 300 | 0.673 (box) / 0.560 (mask) | เก่า ไม่ใช้ |

**หมายเหตุ**: เพิ่ม epochs เป็น 300, ปรับ data pipeline, ใช้ dataset v2
ผลดีขึ้นมาก แต่ยังไม่ใช้เพราะ v4 ใหม่กว่าและครบถ้วนกว่า

---

### v3 — AdamW Optimizer (yolo26n_detect_v3_adamw)

| โมเดล | ประเภท | Epochs | mAP50 (val) | สถานะ |
|-------|--------|--------|-------------|--------|
| yolo26n_detect_v3_adamw | detect | 194 | 0.684 | เก่า ไม่ใช้ |

**หมายเหตุ**: ทดลองเปลี่ยนจาก SGD เป็น AdamW optimizer
ผลใกล้เคียง v2 แต่ไม่ได้ทำ seg version จึงไม่สมบูรณ์

---

### v4 — Recipe (CANONICAL) ★

เวอร์ชันสุดท้ายที่ใช้ใน report ทั้ง 4 โมเดล ฝึกด้วย recipe เดียวกัน เปรียบเทียบกันได้

| โมเดล | ประเภท | Run | Epochs | mAP50 (val) | mAP50-95 (val) | สถานะ |
|-------|--------|-----|--------|-------------|-----------------|--------|
| yolo26n_detect_v4_recipe | detect | run1 | 150 | 0.529 | 0.361 | ★ CANONICAL |
| yolo26s_detect_v4_recipe | detect | run1 | 150 | 0.681 | 0.503 | ★ CANONICAL |
| yolo26n_seg_v4_recipe | seg | run1 | 150 | 0.444 (box) / 0.399 (mask) | 0.301 / 0.231 | ★ CANONICAL |
| yolo26s_seg_v4_recipe | seg | run2_stage2 | 50 | 0.549 (box) / 0.485 (mask) | 0.393 / 0.284 | ★ CANONICAL |

**หมายเหตุ**:
- detect รัน 150 epochs รอบเดียว
- seg รัน 2 stage: run1 (150 epochs full) + run2_stage2 (50 epochs fine-tune)
- yolo26s_seg_v4_recipe ใช้ `run2_stage2/best.pt` เป็น canonical weights
- ผล test set อยู่ใน `eval_results/v4_recipe/all_metrics.json`

### v4 Recipe — Test Set Results (from all_metrics.json)

| โมเดล | P | R | F1 | mAP50 | mAP50-95 | Size | Params |
|-------|---|---|----|----|---------|------|--------|
| n_detect | 0.663 | 0.524 | 0.585 | 0.585 | 0.428 | 5.1 MB | 2.38M |
| s_detect | 0.822 | 0.676 | 0.742 | 0.738 | 0.574 | 19.4 MB | 9.47M |
| n_seg | 0.682 | 0.427 | 0.525 | 0.464 | 0.316 | 24.1 MB | 2.69M |
| s_seg | 0.740 | 0.480 | 0.582 | 0.537 | 0.386 | 22.3 MB | 10.37M |

---

## โครงสร้างภายในแต่ละโฟลเดอร์โมเดล

```
yolo26X_v4_recipe/
├── run1/
│   ├── weights/
│   │   ├── best.pt              # Best model (ใช้สำหรับ eval/export)
│   │   └── last.pt              # Last epoch model
│   ├── results.csv              # Training metrics per epoch
│   ├── args.yaml                # Training arguments
│   ├── BoxF1_curve.png          # Validation curves
│   ├── BoxPR_curve.png
│   ├── confusion_matrix.png
│   └── ...
└── run2_stage2/                  # (seg only — stage 2 fine-tune)
    ├── weights/
    │   ├── best.pt
    │   └── last.pt
    └── results.csv
```

---

## วิธีใช้

### โหลด canonical model
```python
from ultralytics import YOLO
model = YOLO("models/yolo26s_detect_v4_recipe/run1/weights/best.pt")
```

### โหลด canonical seg model (s_seg ใช้ run2_stage2)
```python
model = YOLO("models/yolo26s_seg_v4_recipe/run2_stage2/weights/best.pt")
```

### Export ONNX
ดู `scripts/15_onnx_export_eval.py` หรือ `scripts/08_export_onnx_all.py`
