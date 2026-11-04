"""Audit log: filters, CSV/JSON export with formula guard and BOM, and stream-view auditing."""
import csv
import io
import os
import secrets
import tempfile

os.environ.setdefault("LD_DATA_DIR", tempfile.mkdtemp(prefix="ld-audit-"))
os.environ["LD_EMBEDDED_WORKER"] = "1"
os.environ["LD_WORKER_TOKEN"] = "test-worker-token-0123456789abcdef"
os.environ["LD_SAM_ENABLED"] = "0"
os.environ.pop("LD_SUPERADMINS", None)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Audit, User, Workspace, now

WS = "labeldesk-demo"
EXPORT = f"/api/ws/{WS}/audit/export"
PW = "demo1234"


def login(email: str = "demo@labeldesk.dev", pw: str = PW) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


@pytest.fixture(scope="module", autouse=True)
def _started():
    with TestClient(app):
        yield


@pytest.fixture(scope="module")
def admin():
    with TestClient(app):
        yield login()


@pytest.fixture(scope="module")
def ids():
    with SessionLocal() as db:
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        demo = db.scalar(select(User).where(User.email == "demo@labeldesk.dev"))
        labeler = db.scalar(select(User).where(User.email == "labeler@labeldesk.dev"))
        return {"ws": ws.id, "demo": demo.id, "labeler": labeler.id}


@pytest.fixture
def marker():
    return f"audit-{secrets.token_hex(5)}"


def add(ws_id: str, uid: str | None, action: str, target: str, **kw) -> str:
    with SessionLocal() as db:
        row = Audit(workspace_id=ws_id, user_id=uid, action=action, target=target, **kw)
        db.add(row)
        db.commit()
        return row.id


def drop(*row_ids: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(Audit).where(Audit.id.in_(row_ids)))
        db.commit()


def test_csv_export_has_header_bom_and_row(admin, ids, marker):
    rid = add(ids["ws"], ids["labeler"], "member.invite", f"{marker}-thai", meta={"role": "annotator"})
    try:
        r = admin.get(EXPORT, params={"format": "csv", "q": marker})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "text/csv; charset=utf-8"
        assert 'attachment; filename="audit-' in r.headers["content-disposition"]
        assert r.content.startswith(b"\xef\xbb\xbf")                      # UTF-8 BOM for Excel/Thai
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert rows[0] == ["id", "created", "user", "action", "target", "meta"]
        assert len(rows) >= 2
        mine = [row for row in rows[1:] if row[0] == rid]
        assert mine and mine[0][3] == "member.invite"
        assert mine[0][4] == f"{marker}-thai"
        assert float(mine[0][1]) > 0                                      # epoch, not an ISO string
    finally:
        drop(rid)


def test_csv_guards_formula_cells(admin, ids, marker):
    rid = add(ids["ws"], ids["demo"], "formula.test", "=cmd")
    try:
        r = admin.get(EXPORT, params={"format": "csv", "q": "=cmd", "action": "formula"})
        assert r.status_code == 200, r.text
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert [row for row in rows[1:] if row[0] == rid][0][4] == "'=cmd"
    finally:
        drop(rid)


def test_json_export_shape(admin, ids, marker):
    rid = add(ids["ws"], ids["labeler"], "workspace.update", f"{marker}-json", meta={"note": "x"})
    try:
        r = admin.get(EXPORT, params={"format": "json", "action": "workspace.update", "q": marker})
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list) and len(body) == 1
        row = body[0]
        assert set(row) == {"id", "action", "target", "meta", "created", "user"}
        assert row["id"] == rid and row["meta"] == {"note": "x"}
        assert row["user"] == "Lee Labeler" and isinstance(row["created"], float)
    finally:
        drop(rid)


def test_action_filter_matches_prefix_or_exact(admin, ids, marker):
    prefix = add(ids["ws"], ids["demo"], "member.invite", f"{marker}-a")
    exact = add(ids["ws"], ids["demo"], "member", f"{marker}-b")
    other = add(ids["ws"], ids["demo"], "workspace.update", f"{marker}-c")
    try:
        rows = admin.get(EXPORT, params={"format": "json", "action": "member", "q": marker}).json()
        got = {r["id"] for r in rows}
        assert got == {prefix, exact}
        rows = admin.get(EXPORT, params={"format": "json", "action": "member.invite", "q": marker}).json()
        assert {r["id"] for r in rows} == {prefix}
    finally:
        drop(prefix, exact, other)


def test_user_filter_matches_name_email_and_api(admin, ids, marker):
    mine = add(ids["ws"], ids["labeler"], "member.role", f"{marker}-u")
    api = add(ids["ws"], None, "job.run", f"{marker}-api")
    try:
        rows = admin.get(EXPORT, params={"format": "json", "user": "lee", "q": marker}).json()
        assert {r["id"] for r in rows} == {mine}
        rows = admin.get(EXPORT, params={"format": "json", "user": "labeler@labeldesk", "q": marker}).json()
        assert {r["id"] for r in rows} == {mine}
        rows = admin.get(EXPORT, params={"format": "json", "user": "api", "q": marker}).json()
        assert {r["id"] for r in rows} == {api}
    finally:
        drop(mine, api)


def test_since_and_until_window(admin, ids, marker):
    old = add(ids["ws"], ids["demo"], "version.create", f"{marker}-old", created=now() - 10_000)
    fresh = add(ids["ws"], ids["demo"], "version.create", f"{marker}-new", created=now())
    try:
        rows = admin.get(EXPORT, params={"format": "json", "q": marker, "since": now() - 100}).json()
        assert {r["id"] for r in rows} == {fresh}
        rows = admin.get(EXPORT, params={"format": "json", "q": marker, "until": now() - 100}).json()
        assert {r["id"] for r in rows} == {old}
    finally:
        drop(old, fresh)


def test_q_searches_target_and_meta(admin, ids, marker):
    meta_hit = add(ids["ws"], ids["demo"], "member.invite", f"{marker}-meta",
                   meta={"email": f"needle-{marker}@example.com"})
    try:
        rows = admin.get(EXPORT, params={"format": "json", "q": f"needle-{marker}"}).json()
        assert {r["id"] for r in rows} == {meta_hit}
    finally:
        drop(meta_hit)


def test_limit_and_offset_page_newest_first(admin, ids, marker):
    a = add(ids["ws"], ids["demo"], "export.create", f"{marker}-1", created=now() - 3)
    b = add(ids["ws"], ids["demo"], "export.create", f"{marker}-2", created=now() - 2)
    c = add(ids["ws"], ids["demo"], "export.create", f"{marker}-3", created=now() - 1)
    try:
        rows = admin.get(EXPORT, params={"format": "json", "q": marker, "limit": 1, "offset": 1}).json()
        assert [r["id"] for r in rows] == [b]
        rows = admin.get(EXPORT, params={"format": "json", "q": marker, "limit": 2}).json()
        assert [r["id"] for r in rows] == [c, b]
    finally:
        drop(a, b, c)


def test_annotator_cannot_export():
    labeler = login("labeler@labeldesk.dev")
    r = labeler.get(EXPORT, params={"format": "json"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "requires workspace.audit"


def test_labeler_cannot_list_audit():
    """I1: the list endpoint carries the same workspace.audit check as the export."""
    labeler = login("labeler@labeldesk.dev")
    r = labeler.get(f"/api/ws/{WS}/audit")
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "requires workspace.audit"


def test_billing_cannot_list_audit():
    from app.models import Member

    email = f"billing-audit-{secrets.token_hex(4)}@example.test"
    c = TestClient(app)
    assert c.post("/api/auth/signup", json={"name": "Bill Ing", "email": email,
                                            "password": "longpassword1"}).status_code == 200
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == email))
        ws = db.scalar(select(Workspace).where(Workspace.slug == WS))
        db.add(Member(workspace_id=ws.id, user_id=uid, role="billing"))
        db.commit()
    try:
        bill = login(email, "longpassword1")
        r = bill.get(f"/api/ws/{WS}/audit")
        assert r.status_code == 403, r.text
        assert r.json()["detail"] == "requires workspace.audit"
    finally:
        with SessionLocal() as db:
            db.execute(delete(Member).where(Member.user_id == uid))
            db.commit()


def test_export_is_itself_audited(admin, ids, marker):
    rid = add(ids["ws"], ids["demo"], "workspace.update", f"{marker}-self")
    try:
        assert admin.get(EXPORT, params={"format": "json", "q": marker}).status_code == 200
        with SessionLocal() as db:
            row = db.scalar(select(Audit).where(Audit.action == "audit.export").order_by(Audit.created.desc()))
            assert row is not None
            assert row.workspace_id == ids["ws"] and row.user_id == ids["demo"]
            assert row.target == "format=json" and row.meta["rows"] >= 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(Audit).where(Audit.action == "audit.export"))
            db.commit()
        drop(rid)


# A real stream row and frame: the Task 10b routes own the footage paths this module used to stub.
@pytest.fixture
def stream_id(ids):
    from app.models import Project, Stream

    with SessionLocal() as db:
        pid = db.scalar(select(Project.id).where(Project.slug == "ppe-detection"))
        row = Stream(workspace_id=ids["ws"], project_id=pid, name="audit view",
                     source="rtsp://cam.local/live", model_ref="ultralytics:yolo11n")
        db.add(row)
        db.commit()
        sid = row.id
    yield sid
    with SessionLocal() as db:
        db.execute(delete(Stream).where(Stream.id == sid))
        db.commit()


@pytest.fixture
def live_frame(monkeypatch):
    """A frame without threads: the route only needs `manager.latest_jpeg` to answer."""
    from app.routers import streams as stream_routes

    monkeypatch.setattr(stream_routes.manager, "latest_jpeg", lambda _sid: b"\xff\xd8\xff\xd9")


def _frame_url(sid: str, viewer: str) -> str:
    from app.security import sign_query

    rel = f"ws/{WS}/projects/ppe-detection/streams/{sid}/frame"
    return f"/api/{rel}?{sign_query(rel, viewer=viewer)}"


def test_stream_view_is_audited(admin, ids, stream_id, live_frame):
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.email == "demo@labeldesk.dev"))
        db.execute(delete(Audit).where(Audit.action == "stream.view"))
        db.commit()
    r = admin.get(_frame_url(stream_id, uid))
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "stream.view").order_by(Audit.created.desc()))
        assert row is not None
        assert row.workspace_id == ids["ws"] and row.target == stream_id
        assert row.user_id == uid
        assert row.meta["via"] == "frame" and row.meta["project"] == "ppe-detection"


def test_failed_stream_request_is_not_audited(admin, ids, live_frame):
    missing = "stream404" + secrets.token_hex(3)
    with SessionLocal() as db:
        db.execute(delete(Audit).where(Audit.target == missing))
        db.commit()
    assert admin.get(_frame_url(missing, ids["demo"])).status_code == 404
    with SessionLocal() as db:
        assert db.scalar(select(Audit.id).where(Audit.target == missing)) is None


def test_signed_stream_url_records_the_bound_viewer(ids, stream_id, live_frame):
    """I8: a signed frame URL names its viewer; the middleware must attribute the view to them."""
    with SessionLocal() as db:
        db.execute(delete(Audit).where(Audit.action == "stream.view"))
        db.commit()
    url = _frame_url(stream_id, ids["labeler"])
    raw = TestClient(app)                                  # no bearer token: viewer comes from the signature
    assert raw.get(url).status_code == 200
    with SessionLocal() as db:
        row = db.scalar(select(Audit).where(Audit.action == "stream.view").order_by(Audit.created.desc()))
        assert row is not None and row.user_id == ids["labeler"]

    # Tampering with the viewer invalidates the signature, so nothing is attributed to anyone else.
    tampered = url.replace(f"viewer={ids['labeler']}", f"viewer={ids['demo']}")
    assert raw.get(tampered).status_code == 403
    with SessionLocal() as db:
        rows = db.scalars(select(Audit).where(Audit.action == "stream.view")).all()
        assert [r.user_id for r in rows] == [ids["labeler"]]

