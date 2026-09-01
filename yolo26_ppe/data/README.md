# yolo26_ppe/data — Dataset สำหรับ YOLO26

dataset ที่เตรียมแล้วสำหรับฝึกและประเมิน YOLO26 PPE (5 คลาส)

## โครงสร้าง

```text
data/
├── combined_coco_dataset_version_2/      # COCO รวม 5 คลาส (ต้นทาง)
├── yolo_detection_dataset_version_1/     # detection v1 (6 คลาส — ประวัติ)
│   └── labels/
├── yolo_detection_dataset_version_2/     # detection v2 (5 คลาส — ปัจจุบัน)
│   ├── images/
│   └── labels/
├── yolo_segmentation_dataset_version_1/  # segmentation v1 (6 คลาส — ประวัติ)
│   └── labels/
├── yolo_segmentation_dataset_version_2/  # segmentation v2 (5 คลาส — ปัจจุบัน)
│   ├── images/
│   └── labels/
├── dataset_analysis_reports/             # รายงานวิเคราะห์ distribution/integrity
└── predictions/                          # ผล inference ด้วยโมเดล production
    ├── blurred/
    ├── custom_capture_2026-08-14/
    ├── flip_flops/
    ├── single_test/
    └── two_test/
```

## Dataset ปัจจุบัน (version 2)

| Dataset | คลาส | ใช้กับ |
|---------|------|-------|
| `yolo_detection_dataset_version_2` | 5 คลาส | `nano_detection`, `small_detection` |
| `yolo_segmentation_dataset_version_2` | 5 คลาส | `nano_segmentation`, `small_segmentation` |

5 คลาส: person, helmet, boots, shoes, harness (ไม่มี sandals)

## Dataset ประวัติ (version 1)

`*_version_1` ใช้ 6 คลาส (รวม sandals) เก็บไว้อ้างอิงเท่านั้น — **ห้ามใช้ฝึก production**

## แหล่งที่มา

```text
../data/sam_outputs_ground_truth/   (COCO จาก SAM 3.1)
        │
        │  scripts/pipeline/01_prepare_dataset.py
        ▼
combined_coco_dataset_version_2/    (COCO รวม 5 คลาส)
        │
        │  แปลง + แบ่ง train/val/test + oversampling
        ▼
yolo_detection_dataset_version_2/   (YOLO format)
yolo_segmentation_dataset_version_2/
```

## predictions/

ผล inference ด้วยโมเดล production บนภาพดิบ แยกต่อ batch โครงสร้างเหมือน `../../data/raw/`

สร้างโดย `scripts/pipeline/09_predict_raw_images.py` หรือ `run_pipeline.sh --pred --batch <ชื่อ>`

## data.yaml

แต่ละ dataset มี `data.yaml` สำหรับ Ultralytics — กำหนด path, class names, จำนวนคลาส

## ข้อควรระวัง

- อย่าแก้ dataset โดยตรง — ใช้ `01_prepare_dataset.py` สร้างใหม่ถ้าต้องการ
- ถ้าเปลี่ยนจำนวนคลาส ต้องอัปเดต `data.yaml` และ `configs/production_train.yaml`
- `dataset_analysis_reports/` มีรายงาน distribution — อ่านก่อนตัดสินใจ oversampling
- โฟลเดอร์นี้ใหญ่มาก — อยู่ใน `.gitignore` หรือใช้ Git LFS
