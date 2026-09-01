# SAM 3.1 Auto-Labeling

โมดูลสร้าง annotation อัตโนมัติด้วย **SAM 3.1** (Segment Anything Model 3.1) สำหรับภาพ PPE 6 คลาส

รับภาพดิบจาก `../data/raw/` → ตรวจจับด้วย text prompt → export เป็น COCO/YOLO และอีก 9 ฟอร์แมต → เก็บที่ `../data/sam_outputs_ground_truth/`

## โครงสร้าง

```text
sam3_auto_label/
├── src/                     # โค้ดหลัก (config, inference, batch_segment, exporters, tracker)
├── config/                  # YAML config สำหรับแต่ละชุดข้อมูล
├── sam3/                    # SAM 3.1 source code (vendored — ห้ามแก้)
├── checkpoints/             # SAM 3.1 model weights (ดาวน์โหลดอัตโนมัติ)
├── setup.py                 # ติดตั้ง environment ตาม hardware (CUDA/ROCm/CPU)
├── requirements.txt         # dependencies (ยกเว้น torch ที่ติดตั้งแยก)
├── Dockerfile               # container สำหรับ deployment
├── docker-compose.yml       # orchestration
├── RELEASE_NOTES_v1.0.0.md  # release notes
└── sam3_source_locked.zip   # snapshot ของ sam3/ (สำรอง)
```

## วิธีติดตั้ง

```bash
cd sam3_auto_label
python setup.py              # full setup — สร้าง venv + ลง torch + ดาวน์โหลด checkpoint
python setup.py --check      # ตรวจ hardware อย่างเดียว ไม่ลงอะไร
python setup.py --force-cpu  # บังคับ CPU-only
```

`setup.py` ตรวจ hardware อัตโนมัติ:
- GPU: NVIDIA CUDA / AMD ROCm / Apple MPS / CPU
- เลือก PyTorch index URL ที่ถูกต้อง
- ดาวน์โหลด `sam3.1_multiplex.pt` จาก Hugging Face

## วิธีรัน

```bash
# ใช้ config เริ่มต้น (config/ppe_6class.yaml)
python src/batch_segment.py

# resume จาก checkpoint (ถ้ารันค้างไว้)
python src/batch_segment.py --resume

# เริ่มใหม่ (ลบ checkpoint)
python src/batch_segment.py --fresh

# override threshold
python src/batch_segment.py --threshold 0.5
```

หรือรันผ่าน CLI หลัก: `../run_pipeline.sh --sam --batch <ชื่อbatch>`

## คุณสมบัติเด่น

- **Text-prompted segmentation** — ใช้ชื่อคลาสเป็น prompt ไม่ต้องวาด bbox มือ
- **GPU acceleration** — RLE encode + mask IoU NMS บน GPU, BF16 autocast
- **Pipeline export** — ทับซ้อน CPU export กับ GPU inference → GPU utilization ~100%
- **Checkpoint/resume** — บันทึกความคืบหน้า รันต่อได้ถ้าคอมดับกลางคัน
- **Multi-format export** — COCO, YOLO, VOC, LabelMe, CVAT, Label Studio, KITTI, CreateML, OpenImages, Supervisely, masks
- **Experiment tracking** — SQLite + JSON (ไม่ต้องลง MLflow server)
- **Visualization** — ภาพ overlay ทุกใบ (OpenCV, เร็วกว่า matplotlib 10-50x)

## config

ดู `config/README.md` สำหรับรายละเอียดการตั้งค่าแต่ละไฟล์

config หลัก: `config/ppe_6class.yaml` — กำหนด 6 คลาส, threshold, resolution, output format, path

## ข้อควรระวัง

- `sam3/` เป็น vendored source ของ SAM 3.1 — **ห้ามแก้ไข** ถ้าจะอัปเดตให้ดาวน์โหลดจาก upstream ใหม่
- `sam3_source_locked.zip` (63 MB) เป็น snapshot สำรอง
- `checkpoints/` เก็บ model weights ขนาดใหญ่ — อยู่ใน `.gitignore` ถ้าไม่ใช้ Git LFS
- path ใน config เป็น absolute path สำหรับ WSL2 (`/mnt/e/...`) — override ด้วย `--input`/`--output` ถ้ารันที่อื่น
