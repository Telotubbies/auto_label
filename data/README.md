# data — ข้อมูลดิบและผลลัพธ์ SAM

เก็บข้อมูลภาพดิบและ annotation ที่ได้จาก SAM 3.1 (ใช้เป็น ground truth สำหรับฝึก YOLO26)

## โครงสร้าง

```text
data/
├── raw/                        # ภาพดิบจากกล้อง/CCTV (input ของ SAM)
│   ├── blurred/                # ภาพเบลอ (robustness test)
│   ├── custom_capture_2026-08-14/
│   ├── flip_flops/
│   ├── single_test/
│   └── two_test/
├── sam_outputs_ground_truth/   # ผลลัพธ์จาก SAM (COCO + viz + experiments)
│   ├── blurred/
│   ├── custom_capture_2026-08-14/
│   ├── flip_flops/
│   ├── single_test/
│   ├── two_test/
│   ├── coco/                   # COCO รวม
│   └── viz/                    # visualization รวม
└── processed/                  # dataset ที่ประมวลผลแล้ว
    └── combined_coco_dataset_version_1/
        ├── images/
        └── annotations.json
```

## การไหลของข้อมูล

```text
data/raw/<batch>/
        │
        │  SAM 3.1 (sam3_auto_label/src/batch_segment.py)
        ▼
data/sam_outputs_ground_truth/<batch>/
    ├── coco/
    │   └── <image>.json        # COCO per-image (internal cache)
    ├── experiments/
    │   ├── experiments.db      # SQLite tracking
    │   └── <run_id>.json       # JSON artifacts
    └── viz/
        └── <image>.jpg         # overlay visualization
        │
        │  prepare dataset (yolo26_ppe/scripts/pipeline/01_prepare_dataset.py)
        ▼
yolo26_ppe/data/                # YOLO format dataset
```

## raw/

แต่ละ subfolder = 1 batch ของภาพดิบ ชื่อ folder คือชื่อ batch ที่ใช้ใน CLI:

```bash
./run_pipeline.sh --sam --batch blurred
```

รองรับไฟล์: `.jpg`, `.png` (ไฟล์อื่นถูก ignore)

## sam_outputs_ground_truth/

โครงสร้าง subfolder เหมือน `raw/` — แต่ละ batch มี:

- `coco/` — COCO JSON per-image (internal cache สำหรับ checkpoint/resume)
- `experiments/` — SQLite + JSON tracking
- `viz/` — ภาพ overlay แสดง annotation

## processed/

dataset ที่รวมและประมวลผลแล้ว เช่น `combined_coco_dataset_version_1` ที่มี `annotations.json` รวมทุก batch

## ข้อควรระวัง

- โฟลเดอร์นี้เก็บข้อมูลขนาดใหญ่ — ตรวจ `.gitignore` ก่อน commit
- อย่าลบ `sam_outputs_ground_truth/` ถ้าจะใช้ฝึก YOLO ต่อ เพราะเป็น ground truth
- ถ้ารัน SAM ใหม่กับ batch เดิม ใช้ `--fresh` เพื่อลบ checkpoint ก่อน ไม่งั้นจะ resume จากของเก่า
- path ใน config เป็น WSL2 absolute path (`/mnt/e/...`) — override ด้วย `--input`/`--output` ถ้ารันที่อื่น
