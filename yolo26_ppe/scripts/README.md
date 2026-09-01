# yolo26_ppe/scripts — Pipeline และ Utilities

สคริปต์สำหรับฝึก ประเมิน export และสร้างรายงาน YOLO26 PPE

## โครงสร้าง

```text
scripts/
├── pipeline/      # pipeline ปัจจุบัน — รันตามลำดับเลข
├── tools/         # utility แยก (ไม่อยู่ในลำดับ pipeline)
├── services/      # จัดการ MLflow (foreground/background)
└── archive/       # pipeline และ experiment เก่า — ห้ามใช้กับ production
```

## pipeline/ — pipeline ปัจจุบัน

รันตามลำดับเลขหน้าไฟล์:

| ขั้นตอน | ไฟล์ | ทำอะไร |
|--------|------|--------|
| 01 | `01_prepare_dataset.py` | แปลง COCO → YOLO format, แบ่ง train/val/test, oversampling |
| 02 | `02_train_models.py` | ฝึก 4 โมเดล (nano/small × detect/segment) |
| 03 | `03_evaluate_models.py` | วัด P/R/F1/mAP50/mAP50-95, confusion matrix |
| 04 | `04_export_and_evaluate_onnx.py` | export ONNX + ประเมินเทียบ PyTorch |
| 05 | `05_generate_failure_montage.py` | สร้าง montage ของ failure cases |
| 06 | `06_run_blur_robustness.py` | ทดสอบความทนต่อภาพเบลอ |
| 07 | `07_analyze_blur_robustness.py` | วิเคราะห์ผล blur robustness |
| 08 | `08_generate_report_figures.py` | สร้างกราฟ PDF/PNG สำหรับ report |
| 09 | `09_predict_raw_images.py` | inference ด้วยโมเดล production ลงภาพดิบ |

หรือรันผ่าน CLI หลัก: `../../run_pipeline.sh --yolo --model <ชื่อโมเดล>`

## tools/ — utility แยก

| ไฟล์ | ทำอะไร |
|------|--------|
| `export_legacy_models.py` | export โมเดลเก่าใน archive เป็น ONNX |
| `filter_annotations.py` | กรอง annotation ตามเงื่อนไข |
| `generate_visualizations.py` | สร้าง visualization นอก pipeline |

## services/ — MLflow

| ไฟล์ | ทำอะไร |
|------|--------|
| `manage_mlflow_background.sh` | start/stop MLflow ใน background |
| `run_mlflow_foreground.sh` | รัน MLflow ใน foreground |
| `mlflow_env.sh` | ตั้งค่า environment สำหรับ MLflow |

MLflow config อยู่ที่ `../configs/mlflow.yaml`

## archive/ — ประวัติการทดลอง

**ห้ามใช้กับ production** — เก็บไว้ทำ reproducibility เท่านั้น

| Folder | คืออะไร |
|--------|---------|
| `version_1_baseline_pipeline/` | pipeline แรก (01-08 + shell scripts) |
| `version_2_baseline_training/` | training ของ v2 |
| `dataset_migration/` | สคริปต์ย้าย dataset |
| `historical_analysis/` | benchmark SAM3, error analysis, viz |
| `legacy_stage_2_fine_tuning/` | fine-tuning stage 2 แบบเก่า |
| `optimizer_comparison_experiments/` | ทดลองเปรียบเทียบ optimizer (AdamW) |

## ข้อควรระวัง

- ไฟล์ใน `pipeline/` ขึ้นต้นด้วยเลข — โหลดเป็น module ต้องใช้ `importlib.util` (ชื่อขึ้นต้นด้วยตัวเลข import ตรงไม่ได้)
- ถ้าเพิ่มขั้นตอนใหม่ใน pipeline ให้ใช้เลขถัดไป (เช่น `10_...`)
- อย่าลบไฟล์ใน `archive/` ถ้าไม่ได้ยืนยันกับทีม
- ผลลัพธ์ evaluation ที่เป็นทางการมาจาก `production_v4_recipe` เท่านั้น
