# yolo26_ppe/artifacts — ผลลัพธ์การทดลอง

เก็บผลลัพธ์จาก training, evaluation, ONNX export, MLflow และ robustness test

## โครงสร้าง

```text
artifacts/
├── evaluation/                 # ผล evaluation
│   ├── yolo/
│   │   └── production_v4_recipe/   # ← ผลลัพธ์ทางการ (ใช้ตัวนี้เท่านั้น)
│   └── sam3/
│       ├── archive3_v1/
│       └── archive3_v2/
├── logs/                       # log การ training/tuning/report/service
├── mlflow/                     # MLflow database + runs
│   ├── backend/                # MLflow ปัจจุบัน (mlflow.db + mlruns/)
│   ├── legacy_root_runs/       # runs เก่า (root level)
│   └── legacy_yolo_runs/       # runs เก่า (yolo project)
├── onnx_models/
│   └── production/             # ONNX ของ 4 โมเดล production
├── onnx_inference_results/
│   └── blur_robustness/        # ผล inference ภาพเบลอ แยกต่อโมเดล
└── ultralytics_training_runs/ # raw Ultralytics output (val, train batch images)
    ├── detect/
    └── segment/
```

## evaluation/

| Folder | คืออะไร | ใช้ปัจจุบัน? |
|--------|---------|------------|
| `yolo/production_v4_recipe/` | ผล evaluation ของ 4 โมเดล production | **ใช้** — เป็นทางการ |
| `sam3/archive3_v1/` | benchmark SAM 3.1 ครั้งที่ 1 | อ้างอิง |
| `sam3/archive3_v2/` | benchmark SAM 3.1 ครั้งที่ 2 | อ้างอิง |

ไฟล์สำคัญใน `production_v4_recipe/`:
- `all_metrics.json` — ผล metrics รวมทุกโมเดล (P/R/F1/mAP50/mAP50-95)
- per-class metrics, confusion matrix

## mlflow/

- `backend/mlflow.db` — SQLite database ปัจจุบัน
- `backend/mlruns/` — artifacts ของ runs ปัจจุบัน
- `legacy_*` — ย้ายมาจากที่เก่า เก็บไว้อ้างอิง

ดู config: `../configs/mlflow.yaml`

## onnx_models/production/

ONNX export ของ 4 โมเดล production ใช้สำหรับ deployment

## onnx_inference_results/blur_robustness/

ผล inference ด้วย ONNX บนภาพเบลอ แยกต่อโมเดล:
- `nano_detection/`, `nano_segmentation/`
- `small_detection/`, `small_segmentation/`

## ultralytics_training_runs/

raw output จาก Ultralytics ระหว่าง training — val images, train batch previews ไม่ใช้ใน production แต่เก็บไว้ตรวจสอบ

## ข้อควรระวัง

- โฟลเดอร์นี้มีขนาดใหญ่ — ตรวจ `.gitignore` และ Git LFS ก่อน commit
- ผลลัพธ์ทางการสำหรับ report มาจาก `evaluation/yolo/production_v4_recipe/` เท่านั้น
- อย่าลบ `legacy_*` ถ้ายังต้องอ้างอิงประวัติ
- ถ้ารัน training ใหม่ ผลเก่าอาจถูกเขียนทับ — สำรองก่อนถ้าจำเป็น
