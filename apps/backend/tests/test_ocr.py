"""OCR annotation + Thai text: templates, text/key-value/table payloads, exports, PII mask."""

import io
import json
import os
import tempfile
import zipfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-ocr-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"

import pytest
from app.db import SessionLocal
from app.main import app
from app.models import Member, Project, ProjectMember, User, Workspace
from app.services import flags
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

WS = ""
PROJECT = "ocr-task32"
BASE = ""
FLAG = "task_32"


def jpeg(seed: int = 0) -> bytes:
    b = io.BytesIO()
    PImage.new(
        "RGB", (320, 200), (235 - seed % 70, 235 - seed % 50, 230 - seed % 90)
    ).save(b, "JPEG")
    return b.getvalue()


def flag(c, on: bool) -> None:
    r = c.put(f"/api/ws/{WS}/flags/{FLAG}", json={"enabled": on})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
def c():
    global WS, BASE
    with TestClient(app) as client:
        tok = client.post(
            "/api/auth/login",
            json={"email": "demo@labeldesk.dev", "password": "demo1234"},
        ).json()["token"]
        client.headers["Authorization"] = f"Bearer {tok}"
        # a workspace of its own keeps the demo PPE project's classes, images and project quota
        # untouched (the shared demo workspace is already at its Free-plan project limit by now)
        created = client.post("/api/workspaces", json={"name": "OCR Task 32"})
        assert created.status_code == 200, created.text
        WS = created.json()["slug"]
        BASE = f"/api/ws/{WS}/projects/{PROJECT}"
        r = client.post(
            f"/api/ws/{WS}/projects", json={"name": PROJECT, "type": "object-detection"}
        )
        assert r.status_code == 200, r.text
        flag(client, True)
        yield client
        flag(client, False)


def upload(c, name="bill.jpg") -> str:
    r = c.post(
        f"{BASE}/upload",
        files=[("files", (name, jpeg(len(name) + sum(map(ord, name)))))],
    )
    assert r.status_code == 200, r.text
    assert r.json()["images"], r.text
    return r.json()["images"][0]["id"]


def box_ann(aid: str, class_id: str, kind: str, **ocr) -> dict:
    return {
        "id": aid,
        "classId": class_id,
        "shape": {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.5, "h": 0.1},
        "ocr": {"kind": kind, **ocr},
    }


def class_ids(c) -> dict[str, str]:
    return {row["name"]: row["id"] for row in c.get(f"{BASE}/classes").json()}


def test_flag_is_registered():
    assert FLAG in flags.FLAGS


def test_templates_and_apply(c):
    r = c.get(f"{BASE}/ocr/templates")
    assert r.status_code == 200, r.text
    body = r.json()
    assert {t["id"] for t in body["templates"]} == {
        "thai_id_card",
        "delivery_note",
        "meter",
        "vehicle_registration",
    }
    assert body["current"] is None
    assert any(
        "เลขประจำตัวประชาชน" in t["fields"]
        for t in body["templates"]
        if t["id"] == "thai_id_card"
    )

    r = c.put(f"{BASE}/ocr/template", json={"template": "thai_id_card"})
    assert r.status_code == 200, r.text
    assert r.json()["current"] == "thai_id_card"
    assert c.get(f"{BASE}/ocr/templates").json()["current"] == "thai_id_card"
    assert {"text-line", "key-value", "table"} <= set(class_ids(c))

    assert c.put(f"{BASE}/ocr/template", json={"template": "nope"}).status_code == 404


def test_ocr_annotations_roundtrip(c):
    img = upload(c)
    cls = class_ids(c)
    anns = [
        box_ann("a1", cls["text-line"], "text", text="เลขที่ INV-001"),
        box_ann("a2", cls["key-value"], "keyvalue", key="ชื่อ", value="สมชาย"),
        box_ann(
            "a3",
            cls["table"],
            "table",
            rows=2,
            cols=2,
            cells=[["หัวข้อ", "ค่า"], ["a", "b"]],
        ),
    ]
    r = c.put(f"/api/images/{img}/annotations", json={"annotations": anns})
    assert r.status_code == 200, r.text
    saved = c.get(f"/api/images/{img}").json()["annotations"]
    assert saved[0]["ocr"]["text"] == "เลขที่ INV-001"
    assert saved[1]["ocr"] == {"kind": "keyvalue", "key": "ชื่อ", "value": "สมชาย"}
    assert saved[2]["ocr"]["cells"][1] == ["a", "b"]


def test_ocr_validation(c):
    img = upload(c, "bad.jpg")
    cls = class_ids(c)
    poly = {
        "id": "p1",
        "classId": cls["text-line"],
        "shape": {"kind": "polygon", "points": [0.1, 0.1, 0.2, 0.1, 0.2, 0.2]},
        "ocr": {"kind": "text", "text": "x"},
    }
    assert (
        c.put(
            f"/api/images/{img}/annotations", json={"annotations": [poly]}
        ).status_code
        == 400
    )
    bad_kind = box_ann("b1", cls["text-line"], "barcode", text="x")
    assert (
        c.put(
            f"/api/images/{img}/annotations", json={"annotations": [bad_kind]}
        ).status_code
        == 400
    )
    bad_cells = box_ann(
        "b2", cls["table"], "table", rows=2, cols=2, cells=[["only one row"]]
    )
    assert (
        c.put(
            f"/api/images/{img}/annotations", json={"annotations": [bad_cells]}
        ).status_code
        == 400
    )
    too_long = box_ann("b3", cls["text-line"], "text", text="x" * 2001)
    assert (
        c.put(
            f"/api/images/{img}/annotations", json={"annotations": [too_long]}
        ).status_code
        == 400
    )
    bad_type = box_ann("b4", cls["text-line"], "text", text=42)
    assert (
        c.put(
            f"/api/images/{img}/annotations", json={"annotations": [bad_type]}
        ).status_code
        == 400
    )


def test_ocr_is_off_when_flag_is_off(c):
    img = upload(c, "off.jpg")
    cls = class_ids(c)
    flag(c, False)
    try:
        r = c.put(
            f"/api/images/{img}/annotations",
            json={"annotations": [box_ann("o1", cls["text-line"], "text", text="x")]},
        )
        assert r.status_code == 400, r.text
        assert c.get(f"{BASE}/ocr/templates").status_code == 404
        assert c.post(f"{BASE}/ocr/export", json={"format": "json"}).status_code == 404
        assert c.get(f"/api/images/{img}/ocr/export?format=markdown").status_code == 404
        # a plain box still saves: only the OCR payload is gated
        plain = {
            "id": "o2",
            "classId": cls["text-line"],
            "shape": {"kind": "bbox", "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.2},
        }
        assert (
            c.put(
                f"/api/images/{img}/annotations", json={"annotations": [plain]}
            ).status_code
            == 200
        )
    finally:
        flag(c, True)


def test_exports_markdown_json_and_paddleocr(c):
    img = upload(c, "invoice.jpg")
    cls = class_ids(c)
    pii_text = "โทร 0812345678 เลขบัตร 1234567890123"
    c.put(
        f"/api/images/{img}/annotations",
        json={
            "annotations": [
                box_ann("t1", cls["text-line"], "text", text="เลขที่ INV-001"),
                box_ann("t2", cls["text-line"], "text", text=pii_text),
                box_ann("t3", cls["key-value"], "keyvalue", key="ชื่อ", value="สมชาย"),
                box_ann(
                    "t4",
                    cls["table"],
                    "table",
                    rows=2,
                    cols=2,
                    cells=[["หัวข้อ", "ค่า"], ["a", "b"]],
                ),
            ]
        },
    ).raise_for_status()

    r = c.post(f"{BASE}/ocr/export", json={"format": "markdown", "mask_pii": True})
    assert r.status_code == 200, r.text
    assert r.json()["images"] >= 1
    z = zipfile.ZipFile(io.BytesIO(c.get(r.json()["url"]).content))
    md = z.read("markdown/invoice.md").decode()
    assert "# invoice.jpg" in md
    assert "- เลขที่ INV-001" in md
    assert "**ชื่อ**: สมชาย" in md
    assert "| a | b |" in md
    assert "0812345678" not in md and "1234567890123" not in md and "*" in md

    r = c.post(f"{BASE}/ocr/export", json={"format": "json", "mask_pii": False})
    data = json.loads(
        zipfile.ZipFile(io.BytesIO(c.get(r.json()["url"]).content)).read("ocr.json")
    )
    image = next(x for x in data["images"] if x["image"] == "invoice.jpg")
    assert [x["text"] for x in image["text_lines"]] == ["เลขที่ INV-001", pii_text]
    assert image["key_values"] == [
        {"key": "ชื่อ", "value": "สมชาย", "box": [0.1, 0.1, 0.5, 0.1]}
    ]
    assert image["tables"][0]["cells"] == [["หัวข้อ", "ค่า"], ["a", "b"]]

    r = c.post(f"{BASE}/ocr/export", json={"format": "paddleocr", "mask_pii": False})
    z = zipfile.ZipFile(io.BytesIO(c.get(r.json()["url"]).content))
    label = z.read("label.txt").decode()
    assert "images/invoice.jpg\t" in label
    assert '"transcription": "เลขที่ INV-001"' in label
    assert '"transcription": "ชื่อ: สมชาย"' in label
    assert '"points": [[32.0, 20.0]' in label
    assert "images/invoice.jpg" in z.namelist()
    # a table has no per-cell geometry: it is exported through JSON/Markdown only
    assert '"transcription": "หัวข้อ"' not in label


def test_pii_masking_covers_thai_id_spacing(c):
    """Thai ID cards print the number with spaces as often as dashes; both must be masked."""
    c.put(f"{BASE}/ocr/template", json={"template": "thai_id_card"}).raise_for_status()
    img = upload(c, "spaced-id.jpg")
    cls = class_ids(c)
    spaced = "1 2345 67890 12 3"
    c.put(
        f"/api/images/{img}/annotations",
        json={
            "annotations": [
                box_ann("p1", cls["text-line"], "text", text=f"เลขบัตร {spaced}")
            ]
        },
    ).raise_for_status()
    r = c.get(f"/api/images/{img}/ocr/export?format=markdown")
    assert r.status_code == 200, r.text
    assert spaced not in r.text
    assert "*" * len(spaced) in r.text


def test_pii_masking_hides_thai_numerals_and_thai_script_email(c):
    """The UI's maskPii matches these Unicode classes; an export must not leak what it hides."""
    img = upload(c, "thai-pii.jpg")
    cls = class_ids(c)
    thai_id, email = "๑๒๓๔๕๖๗๘๙๐๑๒๓", "สมชาย@example.co.th"
    c.put(
        f"/api/images/{img}/annotations",
        json={
            "annotations": [
                box_ann("u1", cls["text-line"], "text", text=f"เลขบัตร {thai_id}"),
                box_ann("u2", cls["text-line"], "text", text=email),
            ]
        },
    ).raise_for_status()
    md = c.get(f"/api/images/{img}/ocr/export?format=markdown").text
    assert thai_id not in md and "*" * len(thai_id) in md
    assert email not in md and "*" * len(email) in md


def test_single_image_export(c):
    img = upload(c, "single.jpg")
    cls = class_ids(c)
    c.put(
        f"/api/images/{img}/annotations",
        json={
            "annotations": [
                box_ann("s1", cls["text-line"], "text", text="เอกสารทดสอบ"),
            ]
        },
    ).raise_for_status()
    r = c.get(f"/api/images/{img}/ocr/export?format=markdown")
    assert r.status_code == 200, r.text
    assert "เอกสารทดสอบ" in r.text
    r = c.get(f"/api/images/{img}/ocr/export?format=json")
    assert json.loads(r.text)["images"][0]["text_lines"][0]["text"] == "เอกสารทดสอบ"
    assert c.get(f"/api/images/{img}/ocr/export?format=docx").status_code == 400


def test_export_requires_ocr_annotations(c):
    other = c.post("/api/workspaces", json={"name": "OCR Empty"})
    assert other.status_code == 200, other.text
    slug = other.json()["slug"]
    p = c.post(
        f"/api/ws/{slug}/projects",
        json={"name": "empty-ocr", "type": "object-detection"},
    )
    assert p.status_code == 200, p.text
    assert (
        c.put(f"/api/ws/{slug}/flags/{FLAG}", json={"enabled": True}).status_code == 200
    )
    r = c.post(f"/api/ws/{slug}/projects/empty-ocr/ocr/export", json={"format": "json"})
    assert r.status_code == 400, r.text


def test_ocr_export_is_scoped_to_the_workspace(c):
    other = c.post("/api/workspaces", json={"name": "OCR Other"})
    assert other.status_code == 200, other.text
    slug = other.json()["slug"]
    assert c.get(f"/api/ws/{slug}/projects/{PROJECT}/ocr/templates").status_code == 404


def test_viewer_reads_templates_but_cannot_export(c):
    """Reading OCR text is a project read; applying a template or exporting the dataset is not."""
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        project = db.scalar(
            select(Project).where(
                Project.workspace_id == ws.id, Project.slug == PROJECT
            )
        )
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        db.add(Member(workspace_id=ws.id, user_id=labeler.id, role="member"))
        db.add(ProjectMember(project_id=project.id, user_id=labeler.id, role="viewer"))
        db.commit()
    with TestClient(app) as v:
        tok = v.post(
            "/api/auth/login",
            json={"email": "labeler@labeldesk.dev", "password": "demo1234"},
        ).json()["token"]
        v.headers["Authorization"] = f"Bearer {tok}"
        assert v.get(f"{BASE}/ocr/templates").status_code == 200
        assert (
            v.put(f"{BASE}/ocr/template", json={"template": "meter"}).status_code == 403
        )
        assert v.post(f"{BASE}/ocr/export", json={"format": "json"}).status_code == 403
