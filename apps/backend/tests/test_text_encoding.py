"""Text encoding guard for the images router (T-053).

Seven user-visible strings were UTF-8 text read as Windows-874 and saved back as UTF-8, so the
API returned ``โ€”`` instead of ``—`` and approving an image stamped the same garbage into
``Comment.text``. These tests pin the repaired literals, the review prefixes and a repo-wide
guard that matches the mojibake sequences rather than any Thai codepoint.
"""
import io
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage
from sqlalchemy import select

import app as app_package
from app.db import SessionLocal
from app.main import app
from app.models import Comment, User
from app.security import issue_access

DEMO = "demo@labeldesk.dev"
BAD_SEQUENCES = ("โ€", "ยฑ")


def _offending(line: str) -> bool:
    """True for a double-encoded sequence or a C1 control character; ordinary Thai is fine."""
    return any(seq in line for seq in BAD_SEQUENCES) or any(0x80 <= ord(ch) <= 0x9F for ch in line)


def test_no_double_encoded_source():
    """No line under apps/backend/app carries a mojibake sequence or a C1 control character."""
    app_root = Path(app_package.__file__).resolve().parent
    hits = []
    for path in sorted(app_root.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _offending(line):
                hits.append(f"{path.relative_to(app_root)}:{number}: {line.strip()!r}")
    assert hits == [], "double-encoded text found:\n" + "\n".join(hits)
    # The guard matches the sequences, not the Thai range: real Thai prose stays clean.
    assert not _offending("ภาพตัวอย่าง: ยานพาหนะ วันที่ ฑ — ปกติ")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEMO))
    header = {"Authorization": f"Bearer {issue_access(user.id)}"}
    client.headers["Authorization"] = header["Authorization"]
    return {"id": user.id, "h": header}


@pytest.fixture(scope="module")
def project(client, auth):
    slug = client.post("/api/workspaces", json={"name": f"Encoding {uuid.uuid4().hex[:8]}"}).json()["slug"]
    p = client.post(f"/api/ws/{slug}/projects", json={"name": f"encoding-{uuid.uuid4().hex[:8]}",
                                                      "classes": ["part"]}).json()
    base = f"/api/ws/{slug}/projects/{p['slug']}"
    buffer = io.BytesIO()
    PImage.new("RGB", (64, 48), (40, 80, 120)).save(buffer, "JPEG")
    uploaded = client.post(f"{base}/upload", files=[("files", ("part.jpg", buffer.getvalue()))],
                           data={"split": "train"})
    assert uploaded.status_code == 200, uploaded.text
    return {"base": base, "image": uploaded.json()["images"][0]["id"]}


def test_approve_writes_a_readable_prefix(client, auth, project):
    note = "looks right"
    response = client.post(f"/api/images/{project['image']}/review", json={"approved": True, "note": note},
                           headers=auth["h"])
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        texts = [row.text for row in db.scalars(select(Comment).where(Comment.image_id == project["image"]))]
    assert texts == ["✓ " + note]


def test_reject_writes_a_readable_prefix(client, auth, project):
    note = "missing box"
    response = client.post(f"/api/images/{project['image']}/review", json={"approved": False, "note": note},
                           headers=auth["h"])
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        texts = [row.text for row in db.scalars(select(Comment).where(Comment.image_id == project["image"])
                                                .order_by(Comment.created))]
    assert texts[-1] == "✗ Rejected: " + note


def test_upload_error_reads_in_english(client, auth, project):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "no images here")
    response = client.post(f"{project['base']}/upload", files=[("files", ("empty.zip", buffer.getvalue()))],
                           data={"split": "train"})
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "— loose or in a .zip" in detail
    assert "โ€" not in detail
