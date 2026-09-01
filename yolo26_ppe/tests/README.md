# yolo26_ppe/tests — ทดสอบ Pipeline

ทดสอบ pipeline ของ yolo26_ppe โดยเฉพาะ (prepare dataset, split integrity, artifacts)

## ไฟล์

| ไฟล์ | ทดสอบอะไร |
|------|----------|
| `conftest.py` | fixtures — load `01_prepare_data.py`, skip ถ้าไม่มี numpy/cv2/pycocotools |
| `test_dataset_artifacts.py` | ตรวจ dataset artifacts ครบถ้วน |
| `test_split_integrity.py` | ตรวจ train/val/test split ไม่ซ้ำ ไม่รั่ว |

## วิธีรัน

```bash
# รันจาก yolo26_ppe/
pytest tests/ -v

# รันจาก repo root
pytest yolo26_ppe/tests/ -v
```

## conftest.py

- `prepare_module` — load `scripts/pipeline/01_prepare_dataset.py` เป็น module
- `pytest.importorskip` — skip ทดสอบถ้า environment ไม่มี numpy, cv2, pycocotools

## ข้อควรระวัง

- ทดสอบนี้ต้องการ dependencies หนัก (numpy, cv2, pycocotools) — ถ้าไม่มีจะ skip อัตโนมัติ
- ทดสอบ CLI หลักอยู่ที่ `../../tests/` แยกต่างหาก
- ถ้าแก้ `01_prepare_dataset.py` ให้รัน tests ก่อนเสมอ
