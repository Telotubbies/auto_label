# sam3_auto_label/config — YAML Configuration

ไฟล์ config สำหรับกำหนดคลาส, threshold, inference, annotation, และ output path ของ SAM 3.1 auto-labeling

## ไฟล์

| ไฟล์ | จำนวนคลาส | ใช้เมื่อไร |
|------|-----------|----------|
| `ppe_6class.yaml` | 6 | config เริ่มต้น — ใช้กับ pipeline หลัก |

## โครงสร้าง ppe_6class.yaml

```yaml
categories:        # รายการคลาส + threshold แยกต่อคลาส
  - id, name, prompt, threshold

inference:         # การตั้งค่า inference
  confidence_threshold, resolution, device, gpu_ops, pipeline_export

annotation:        # annotation ที่จะสร้าง
  bbox, segmentation, segmentation_encoding (rle | polygon)

output:            # รูปแบบ output + path
  formats, save_viz, input_dir, output_dir, viz_dpi, viz_figsize

checkpoint:        # resume settings
  enabled, auto_resume, clear_on_success
```

ค่าคอนฟิกถูกอ่านด้วย `yaml.safe_load()` จากนั้นแปลงเป็น dataclass และตรวจสอบก่อนเริ่มโหลดโมเดล ข้อผิดพลาดจะระบุ field ที่ไม่ถูกต้อง เช่น `inference.confidence_threshold` หรือ `categories[1].id`

กฎ validation ที่สำคัญ:

- `categories` ต้องไม่ว่าง; `id` และ `name` ต้องไม่ซ้ำ
- category `threshold` ต้องเป็น `-1` หรืออยู่ในช่วง `0..1`
- `confidence_threshold` ต้องอยู่ในช่วง `0..1`; `resolution` ต้องมากกว่า `0`
- boolean ต้องเป็น YAML boolean (`true` / `false`) ไม่ใช่ string ที่ใส่ quote
- `device` ต้องเป็น `auto`, `cpu`, `cuda`, `rocm`, หรือ `mps`
- `viz_figsize` ต้องมีตัวเลขบวก 2 ค่า

## คลาสทั้งหมด (6 class)

| id | name | prompt | threshold | คำอธิบาย |
|----|------|--------|-----------|----------|
| 1 | person | person | 0.7 | คน |
| 2 | helmet | helmet | 0.25 | หมวกนิรภัย |
| 3 | boots | boots | 0.25 | บูทนิรภัย/บูทยาง |
| 4 | shoes | shoes | 0.25 | รองเท้าผ้าใบ/รองเท้าหุ้มส้น |
| 5 | sandals | flip-flops | 0.3 | รองเท้าแตะ/flip-flops |
| 6 | harness | safety harness | 0.25 | สาย safety/ชุดเดือย |

## threshold

- `threshold: -1` = ใช้ `inference.confidence_threshold` ส่วนกลาง
- `threshold: 0` = รับทั้งหมด (ไม่ filter)
- ค่าอื่น = override เฉพาะคลาสนั้น

person ใช้ 0.7 เพราะมีเยอะและชัดเจน ส่วนคลาสอื่นใช้ 0.25 เพื่อไม่ให้พลาดวัตถุเล็ก

## path

path ใน config เป็น **absolute path สำหรับ WSL2**:

```yaml
input_dir: /mnt/e/02_Projects/auto_label/data/raw
output_dir: /mnt/e/02_Projects/auto_label/data/sam_outputs_ground_truth
```

ถ้ารันบน Windows โดยตรงหรือเครื่องอื่น ให้ override ตอนรัน:

```bash
python src/batch_segment.py --input <path> --output <path>
```

## การเพิ่ม config ใหม่

ถ้าต้องการชุดคลาสหรือ threshold ใหม่:

1. คัดลอก `ppe_6class.yaml` เป็นไฟล์ใหม่
2. แก้ categories/threshold ตามต้องการ
3. รัน: `python src/batch_segment.py --config config/<ไฟล์ใหม่>.yaml`
4. อย่าลืมอัปเดต `SUPPORTED_FORMATS` ใน `src/config.py` ถ้าเพิ่มฟอร์แมตใหม่
