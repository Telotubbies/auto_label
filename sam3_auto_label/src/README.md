# sam3_auto_label/src — โค้ดหลัก

โค้ด Python สำหรับรัน SAM 3.1 auto-labeling แบบ batch

## ไฟล์ทั้งหมด

| ไฟล์ | หน้าที่ | หมายเหตุ |
|------|--------|---------|
| `config.py` | load + validate YAML config, dataclass สำหรับ Category/Inference/Annotation/Output | จุดเริ่มต้น — ทุกไฟล์อื่น import จากที่นี่ |
| `inference.py` | สร้างโมเดล SAM 3.1, segment ภาพเดียว, export COCO/mask/viz | จัดการ device (CUDA > ROCm > MPS > CPU), GPU ops |
| `batch_segment.py` | รัน batch segmentation ทุกภาพใน folder, checkpoint/resume, ETA | CLI entry point — `python src/batch_segment.py` |
| `exporters.py` | export annotation เป็น 11 ฟอร์แมต (COCO, YOLO, VOC, LabelMe, CVAT, ...) | เลือกฟอร์แมตผ่าน `output.formats` ใน config |
| `tracker.py` | บันทึกประวัติทุกครั้งที่รัน (SQLite + JSON) | ไม่ต้องลง MLflow |

## ลำดับการทำงาน

```text
batch_segment.py
  ├── load_config()          ← config.py
  ├── build_model()          ← inference.py
  ├── for each image:
  │     segment_image()      ← inference.py
  │     write_image_exports()← exporters.py
  ├── finalize_exports()     ← exporters.py
  └── tracker.end_run()      ← tracker.py
```

## config.py

dataclass หลัก:

- `Category` — id, name, prompt, threshold (per-category override; -1 = ใช้ global, 0 = รับทั้งหมด)
- `InferenceConfig` — confidence_threshold, resolution, device, gpu_ops, pipeline_export
- `AnnotationConfig` — bbox, segmentation, segmentation_encoding (rle | polygon)
- `OutputConfig` — formats, save_viz, input_dir, output_dir, viz_dpi, viz_figsize
- `Config` — รวมทั้งหมด + checkpoint settings

`SUPPORTED_FORMATS` — tuple ของ 11 ฟอร์แมตที่ exporters.py รองรับ

## inference.py

- `build_model()` — สร้าง SAM 3.1 model ตาม device ที่ตรวจพบ
- `segment_image()` — segment ภาพเดียว คืน list ของ annotation
- `save_coco()` / `save_masks()` / `save_viz()` — helper export
- GPU ops (optional): `robust_rle_encode`, `gpu_mask_iou`, `generic_nms` จาก `sam3.perflib` — fallback ไป CPU ถ้า import ไม่ได้

## batch_segment.py

CLI flags:

- `--resume` — รันต่อจาก checkpoint
- `--fresh` — เริ่มใหม่ ลบ checkpoint
- `--threshold <float>` — override confidence threshold
- `--config <path>` — ระบุ config file (default: `config/ppe_6class.yaml`)

## exporters.py

แต่ละฟอร์แมตเขียนแบบไหน:

| Format | Output | Annotation type |
|--------|--------|-----------------|
| coco | JSON รวม | bbox/seg (RLE or polygon) |
| yolo | TXT per image + data.yaml | bbox หรือ polygon |
| voc | XML per image | bbox only |
| labelme | JSON per image | bbox/seg (polygon) |
| cvat | XML รวม | bbox/seg (polygon) |
| label_studio | JSON รวม | bbox/seg (uncompressed RLE) |
| kitti | TXT per image | bbox only |
| createml | JSON รวม | bbox only |
| openimages | CSV รวม | bbox only |
| supervisely | JSON per image + meta.json | bbox/seg (polygon) |
| masks | PNG per annotation | seg only |

หมายเหตุ: per-image JSON ใน `output/coco/{name}.json` เขียนเสมอ เป็น internal cache สำหรับ checkpoint/resume ไม่ขึ้นกับ `formats`

## tracker.py

`ExperimentTracker` — บันทึกทุกครั้งที่รัน:

- SQLite: `experiments.db` ใน output_dir
- JSON artifacts: `experiments/` folder
- ใช้ผ่าน `tracker.start_run()` → `tracker.log_metrics()` → `tracker.end_run()`

## ข้อควรระวัง

- import ใช้ relative path (`from config import ...`) — ต้องรันจากใน `src/` หรือเพิ่ม `src/` ใน `sys.path`
- `sam3` import ใน `inference.py` เป็น optional — ถ้าไม่มี GPU ops จะ fallback ไป CPU
- ถ้าเพิ่มฟอร์แมตใหม่ ต้องเพิ่มใน `SUPPORTED_FORMATS` ใน `config.py` ด้วย
