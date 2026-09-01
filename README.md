# Auto-Label PPE Pipeline

ระบบสร้างฉลากอัตโนมัติ (auto-labeling) และฝึกโมเดลตรวจจับอุปกรณ์ความปลอดภัยส่วนบุคคล (PPE) ด้วย **SAM 3.1** และ **YOLO26**

โปรเจกต์นี้เป็น pipeline ครบวงจร ตั้งแต่รับภาพดิบ → สร้าง annotation → ฝึกโมเดล → ประเมินผล → export ONNX → สร้างรายงาน ออกแบบให้คนทำต่อเข้าใจง่ายและรันซ้ำได้

## ภาพรวม pipeline

```text
data/raw/  ──[SAM 3.1]──▶  data/sam_outputs_ground_truth/  ──[prepare]──▶  yolo26_ppe/data/  ──[train]──▶  yolo26_ppe/models/production/
                                                                                         │
                                                                                         ├──[evaluate]──▶ artifacts/evaluation/
                                                                                         ├──[export]────▶ artifacts/onnx_models/
                                                                                         └──[report]────▶ reports/final/report.pdf
```

1. **SAM** — ใช้ SAM 3.1 ตรวจจับ 6 คลาส (person, helmet, boots, shoes, sandals, harness) ออกเป็น COCO annotations
2. **Prepare** — แปลง COCO → YOLO format แล้วแบ่ง train/val/test
3. **Train** — ฝึก YOLO26 4 โมเดล (nano/small × detect/segment)
4. **Evaluate** — วัด P/R/F1/mAP50/mAP50-95 รวมถึง confusion matrix และ failure analysis
5. **Export** — export เป็น ONNX แล้วประเมินเทียบกับ PyTorch
6. **Report** — สร้าง PDF report ภาษาไทย (XeLaTeX)

## โครงสร้างหลัก

```text
auto_label/
├── pipeline_cli.py          # CLI หลัก (interactive + direct mode) — ทางเข้าหลัก
├── run_pipeline.sh          # bash wrapper พร้อมตั้งค่า ROCm/WSL2 GPU
├── AGENTS.md                # กฎการทำงานสำหรับ AI agent/วิศวกร (อ่านก่อนเริ่มงาน)
├── sam3_auto_label/         # โค้ด SAM 3.1 auto-labeling
├── yolo26_ppe/              # โค้ด YOLO26 training/evaluation/report
├── data/                    # ข้อมูลดิบ + ผลลัพธ์จาก SAM (ground truth)
└── tests/                   # ทดสอบ pipeline_cli.py ระดับ repo
```

## วิธีรัน

### รันผ่าน CLI (แนะนำ)

```bash
# interactive mode — เมนูเลือก dataset/mode/model
./run_pipeline.sh

# direct mode
./run_pipeline.sh --sam --batch blurred          # auto-label ด้วย SAM
./run_pipeline.sh --yolo --model small_detection # train YOLO26
./run_pipeline.sh --pred --batch blurred         # inference ด้วยโมเดล production

# dry-run (ดูแผนโดยไม่รันจริง)
./run_pipeline.sh --dry-run --yolo --model nano_detection
```

### รันแต่ละส่วนแยก

- SAM: ดู `sam3_auto_label/README.md`
- YOLO: ดู `yolo26_ppe/README.md` และ `yolo26_ppe/scripts/pipeline/`

## คลาสทั้งหมด

SAM ใช้ 6 คลาส (เพิ่ม sandals) แต่ YOLO ใช้ 5 คลาส (รวม boots+shoes ไว้ ไม่มี sandals)

| id | SAM (6 class) | YOLO (5 class) | คำอธิบาย |
|----|---------------|----------------|----------|
| 1 | person | person | คน |
| 2 | helmet | helmet | หมวกนิรภัย |
| 3 | boots | boots | บูทนิรภัย/บูทยาง |
| 4 | shoes | shoes | รองเท้าผ้าใบ/รองเท้าหุ้มส้น |
| 5 | sandals | — | รองเท้าแตะ/flip-flops (SAM เท่านั้น) |
| 6 | harness | harness | สาย safety/ชุดเดือย |

## environment

- Python 3.12
- PyTorch ตาม GPU: ROCm 6.x (AMD), CUDA 12.x (NVIDIA), หรือ CPU
- ทดสอบบน WSL2 + AMD RX 7800 XT (gfx1101)
- ติดตั้ง SAM environment: `cd sam3_auto_label && python setup.py`

## ก่อนเริ่มทำงาน

1. อ่าน `AGENTS.md` ก่อนเสมอ — เป็นกฎการทำงานสำหรับทั้ง repo
2. ตรวจ `git status` ก่อนแก้ไขไฟล์
3. ใช้โมเดลใน `yolo26_ppe/models/production/` เท่านั้นสำหรับ production
4. ห้ามแก้ไฟล์ใน `yolo26_ppe/scripts/archive/` (เก็บไว้ทำ reproducibility)
5. ผลลัพธ์ evaluation ที่เป็นทางการมาจาก `artifacts/evaluation/yolo/production_v4_recipe/`

## อ้างอิง

- SAM 3.1: `sam3_auto_label/sam3/` (vendored source)
- YOLO26: Ultralytics framework
- Release notes: `sam3_auto_label/RELEASE_NOTES_v1.0.0.md`
