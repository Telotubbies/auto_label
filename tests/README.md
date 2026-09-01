# tests — ทดสอบ pipeline_cli.py

ทดสอบ CLI หลักของ repo (`../pipeline_cli.py`) ระดับ unit + integration + UAT

## ไฟล์

| ไฟล์ | ประเภท | ทดสอบอะไร |
|------|-------|----------|
| `conftest.py` | fixtures | load `pipeline_cli.py` เป็น module, mock args, tmp data dir |
| `test_pipeline_cli_unit.py` | unit | ฟังก์ชันเดี่ยวใน CLI (path resolution, model config, batch discovery) |
| `test_pipeline_cli_comprehensive.py` | unit | ครอบคลุมทุก branch ของ CLI logic |
| `test_pipeline_cli_advanced.py` | unit | edge cases และ advanced features |
| `test_pipeline_cli_uat.py` | UAT | user acceptance — จำลองการใช้งานจริง |
| `test_dry_run_integration.py` | integration | dry-run mode ทั้งระบบ (ไม่รันจริง) |
| `test_prepare_dataset.py` | integration | ทดสอบขั้นตอน prepare dataset |

## วิธีรัน

```bash
# รันทั้งหมด
pytest tests/ -v

# รันเฉพาะไฟล์
pytest tests/test_pipeline_cli_unit.py -v

# รันพร้อม coverage
pytest tests/ --cov=pipeline_cli --cov-report=term-missing
```

## conftest.py

fixtures หลัก:

- `cli_module` — load `pipeline_cli.py` เป็น module (scope=session)
- `mock_args` — MagicMock สำหรับจำลอง CLI args
- `tmp_raw_dir` — สร้าง `data/raw/` ชั่วคราวใน tmp_path พร้อม batch ตัวอย่าง

## ข้อควรระวัง

- ทดสอบนี้ไม่ต้องการ GPU — ใช้ mock และ dry-run
- `pipeline_cli.py` อยู่ที่ repo root (ไม่ใช่ package) จึงโหลดด้วย `importlib.util`
- ถ้าแก้ `pipeline_cli.py` ให้รัน tests ก่อนเสมอเพื่อยืนยันไม่ break
- ทดสอบ YOLO pipeline อยู่ที่ `../yolo26_ppe/tests/` แยกต่างหาก
