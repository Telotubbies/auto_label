---
title: "18 — Troubleshooting"
category: "SAM 3.1 Auto-Labeling"
order: 18
status: "Verified"
---

# 18 — Troubleshooting

> ปัญหาที่พบบ่อยและวิธีแก้
>
> **Status**: Verified + Inferred — บางข้อมาจากโค้ด, บางข้อมาจากลักษณะของ SAM 3.1

---

## ปัญหาที่พบบ่อย

### 1. Checkpoint ไม่พบ

```
FileNotFoundError: sam3.1_multiplex.pt
```

**สาเหตุ**: `setup.py` ดาวน์โหลดไป `models/sam3/` แต่ `config.py` มองหาที่ `checkpoints/`

**แก้**:
```bash {cmd=true output="text"}
echo "# ย้ายไฟล์"
echo "mv sam3_auto_label/models/sam3/sam3.1_multiplex.pt sam3_auto_label/checkpoints/"
echo ""
echo "# หรือ symlink (Linux/WSL)"
echo "ln -s ../models/sam3/sam3.1_multiplex.pt sam3_auto_label/checkpoints/sam3.1_multiplex.pt"
```

> `setup.py:35` vs `config.py:112-113`

---

### 2. GPU ไม่ถูกใช้

**อาการ**: รันช้ามาก (~10x ปกติ), `device` กลายเป็น `cpu`

**สาเหตุ**:
- PyTorch ติดตั้งเป็น CPU version
- CUDA/ROCm ไม่พร้อม
- `device: auto` ไม่ detect GPU

**แก้**:
```bash {cmd=true output="text"}
echo "# ตรวจสอบ"
echo 'python -c "import torch; print(torch.cuda.is_available())"'
echo ""
echo "# ถ้า False — ติดตั้ง PyTorch ใหม่ตาม GPU"
echo "# NVIDIA:"
echo "pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121"
echo "# AMD ROCm:"
echo "pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/rocm6.1"
```

> `src/inference.py:315-340` — `resolve_device()`

---

### 3. GPU Out of Memory

```
torch.cuda.OutOfMemoryError: CUDA out of memory
```

**สาเหตุ**: ภาพใหญ่ + resolution สูง → VRAM ไม่พอ

**แก้**:
```bash {cmd=true output="text"}
echo "# ลด resolution"
echo "python src/batch_segment.py --resolution 768"
echo ""
echo "# หรือใช้ CPU (ช้า)"
echo "python src/batch_segment.py --device cpu"
```

> **⚠️ โค้ดไม่มี OOM handling** — ถ้าเกิดขึ้นทั้ง pipeline crash ต้องเริ่มใหม่ (มี checkpoint ช่วย)

---

### 4. ภาพที่ error ถูกข้าม

**อาการ**: บางภาพไม่มี annotation ใน output

**สาเหตุ**: inference error → catch `Exception` → mark processed → ข้าม

**ตรวจสอบ**:
```bash {cmd=true output="text"}
echo "# ดู errors.json ที่ output dir"
echo "cat data/sam_outputs_ground_truth/errors.json"
echo ""
echo "# หรือ query SQLite"
echo 'sqlite3 data/sam_outputs_ground_truth/experiments.db "SELECT id, errors FROM experiments ORDER BY started_at DESC LIMIT 1"'
```

**แก้**: ไม่มี retry — ต้องแก้สาเหตุของ error แล้วรันใหม่ด้วย `--fresh` หรือลบภาพที่มีปัญหาออก

> `src/batch_segment.py:311-392`

---

### 5. Export ล้มเหลว

**อาการ**: log แสดง "export failed" แต่ pipeline ยังรันต่อ

**สาเหตุ**: format writer ใน `exporters.py` error

**ตรวจสอบ**: ดู output dir — ไฟล์ของ format ที่ fail จะหายไป

**แก้**: ดู error message ใน log, แก้ใน `exporters.py`, รันใหม่

> `src/batch_segment.py:289-295`

---

### 6. NMS กำจัด detection ที่ไม่ควร

**อาการ**: detection ของคลาส A หายไปเพราะ overlap กับคลาส B

**สาเหตุ**: `cross_class_nms` ใช้ $\text{IoU}=0.5$ — ถ้า $\text{IoU} \geq 0.5$ ระหว่างคลาส A และ B จะเก็บ score สูงกว่า

**แก้**: แก้ `iou_threshold` ใน `src/inference.py:470-474` (hard-coded ไม่ได้ config)

> `src/inference.py:470-474`

---

### 7. False positive เยอะ

**อาการ**: annotation มีจำนวนมากผิดปกติ ส่วนใหญ่ผิด

**สาเหตุ**: threshold ต่ำเกินไป ($0.25$ สำหรับ helmet/boots/shoes/harness)

**แก้**:
```bash {cmd=true output="text"}
echo "# เพิ่ม threshold รวม"
echo "python src/batch_segment.py --threshold 0.5"
echo ""
echo "# หรือแก้ per-category ใน config"
echo "# config/ppe_6class.yaml"
echo "# categories:"
echo "#   - id: 2"
echo "#     name: helmet"
echo "#     threshold: 0.5  # เพิ่มจาก 0.25"
```

> `config/ppe_6class.yaml`

---

### 8. Resume ไม่ทำงาน

**อาการ**: รัน `--resume` แต่เริ่มใหม่

**สาเหตุ**:
- `checkpoint.json` หายไป (ลบด้วยมือ หรือ `clear_on_success=true` ตอนจบสำเร็จ)
- Checkpoint corrupt → catch `Exception` → return `None` → เริ่มใหม่

**ตรวจสอบ**:
```bash {cmd=true output="text"}
echo "ls -la data/sam_outputs_ground_truth/checkpoint.json"
echo 'cat data/sam_outputs_ground_truth/checkpoint.json | python -m json.tool'
```

**แก้**: ถ้า checkpoint หาย → ต้องเริ่มใหม่ (ไม่มีวิธีกู้คืน)

> `src/batch_segment.py:52-83`

---

### 9. Docker: checkpoint path ไม่ตรง

**อาการ**: รันใน Docker แล้วไม่พบ checkpoint

**สาเหตุ**: volume mount `./checkpoints:/app/checkpoints` แต่ไฟล์อยู่ที่ `models/sam3/`

**แก้**: ย้ายไฟล์ไป `./checkpoints/` ก่อนรัน Docker หรือแก้ volume path

> `docker-compose.yml`

---

### 10. `experiments.db` lock

**อาการ**: `sqlite3.OperationalError: database is locked`

**สาเหตุ**: มี process อื่นเปิด db อยู่ หรือ crash ค้าง

**แก้**:
```bash {cmd=true output="text"}
echo "# หา process ที่ lock"
echo "lsof data/sam_outputs_ground_truth/experiments.db"
echo ""
echo "# ฆ่า process หรือรอ"
echo "# ถ้าไม่ได้ — backup แล้วลบ"
echo "cp data/sam_outputs_ground_truth/experiments.db experiments.db.bak"
echo "rm data/sam_outputs_ground_truth/experiments.db"
```

> `src/tracker.py` — ใช้ `sqlite3.connect()` ไม่ได้ตั้ง timeout

---

## อ้างอิง

- `setup.py:35` vs `config.py:112-113` — checkpoint path
- `src/inference.py:315-340` — device resolution
- `src/inference.py:470-474` — NMS threshold
- `src/batch_segment.py:52-83` — checkpoint
- `src/batch_segment.py:311-392` — error handling
- `config/ppe_6class.yaml` — thresholds
