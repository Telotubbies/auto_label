"""One request id from the browser to the API to the worker, one JSON object per log line.

The shape under test is MONITORING-PLAN §4.1: `X-Request-Id` honoured when it is 8..64 chars of
[A-Za-z0-9_-], minted otherwise, echoed on the response, carried in a contextvar and injected into
every record; a job is joined by `job_id` on the worker's claim and terminal lines.
"""
import io
import json
import logging
import re
import uuid

import anyio
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PImage

from app import logging_setup, worker
from app.bootstrap import DEMO_EMAIL, DEMO_PW
from app.db import SessionLocal
from app.main import app
from app.models import Job, Workspace
from conftest import login

# §4.1: every line carries exactly these keys, "" when the field does not apply.
KEYS = {"ts", "level", "logger", "msg", "request_id", "user_id", "workspace_id",
        "method", "route", "status", "duration_ms", "job_id", "worker_id"}
GENERATED = re.compile(r"[0-9a-f]{16}")
WS = "labeldesk-demo"


def _handler() -> logging.Handler:
    """The handler `install()` put on the root logger."""
    return next(h for h in logging.getLogger().handlers if h.name == "labeldesk")


@pytest.fixture
def logbuf(monkeypatch):
    """Capture the installed handler's own output, so the test reads what a deployment writes."""
    buf = io.StringIO()
    monkeypatch.setattr(_handler(), "stream", buf)
    return buf


def _lines(buf) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]


def _get(path: str = "/api/health", headers: list[tuple[bytes, bytes]] | None = None):
    """One request straight through the ASGI app: httpx refuses an illegal header value, the app must not."""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "headers": [(b"host", b"testserver"), *(headers or [])],
             "server": ("testserver", 80), "client": ("testclient", 50000)}
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    async def run():
        await app(scope, receive, send)

    anyio.run(run)
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], dict(start["headers"])


def test_supplied_request_id_is_echoed(logbuf):
    status, headers = _get(headers=[(b"x-request-id", b"abc12345")])
    assert status == 200
    assert headers[b"x-request-id"] == b"abc12345"
    line = next(r for r in _lines(logbuf) if r["msg"] == "http.request")
    assert line["request_id"] == "abc12345"
    assert (line["method"], line["route"], line["status"]) == ("GET", "/api/health", 200)


def test_the_log_labels_the_route_template_not_the_path(logbuf):
    _get("/api/images/img_secret_123")
    line = next(r for r in _lines(logbuf) if r["msg"] == "http.request")
    assert line["route"] == "/api/images/{image_id}"
    assert "img_secret_123" not in logbuf.getvalue()


def test_an_authenticated_request_names_the_user_and_workspace(logbuf):
    c = TestClient(app)
    c.get(f"/api/ws/{WS}/projects", headers=login(c))
    line = next(r for r in _lines(logbuf) if r["route"].endswith("/projects"))
    assert line["user_id"] and line["workspace_id"], "the deps layer fills the context for the line"


def test_uvicorn_access_is_quiet_for_api_only():
    """The middleware writes the richer line; uvicorn keeps its own line for non-API paths."""
    flt = next(f for f in logging.getLogger("uvicorn.access").filters
               if isinstance(f, logging_setup._ApiAccessOnly))

    def access(path: str) -> logging.LogRecord:
        return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                                 '%s - "%s %s HTTP/%s" %d',
                                 ("1.2.3.4:5", "GET", path, "1.1", 200), None)

    assert not flt.filter(access("/api/ws/labeldesk-demo/projects?limit=5"))
    assert flt.filter(access("/index.html"))


@pytest.mark.parametrize("bad", [None, b"short", b"has space", b"a" * 2000, b"a\nb"])
def test_request_id_is_generated_when_absent_or_invalid(bad, logbuf):
    headers = [] if bad is None else [(b"x-request-id", bad)]
    status, out = _get(headers=headers)
    assert status == 200
    rid = out[b"x-request-id"].decode()
    assert GENERATED.fullmatch(rid), rid
    assert _lines(logbuf)[0]["request_id"] == rid
    if bad is not None:
        assert bad.decode("latin-1") not in logbuf.getvalue(), "a bad header must never reach the log"


def test_log_line_is_one_json_object(logbuf):
    _get(headers=[(b"x-request-id", b"shape0001")])
    text = logbuf.getvalue().strip()
    assert "\n" not in text, "one JSON object per line"
    line = json.loads(text)
    assert set(line) == KEYS
    assert line["level"] == "INFO" and line["logger"] == "labeldesk.request"
    assert isinstance(line["status"], int) and isinstance(line["duration_ms"], (int, float))
    assert line["job_id"] == "" and line["worker_id"] == ""


def test_no_secret_in_the_log_line(logbuf):
    body = io.BytesIO()
    PImage.new("RGB", (32, 32), (9, 9, 9)).save(body, "PNG")
    marker = "secret-body-marker"
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PW})
    token = r.json()["token"]
    auth = {"Authorization": f"Bearer {token}"}
    # A fresh workspace, so the demo one's credit allowance (spent by other modules) cannot 402 this.
    ws = c.post("/api/workspaces", json={"name": f"log-check {uuid.uuid4().hex[:8]}"}, headers=auth).json()["slug"]
    project = c.post(f"/api/ws/{ws}/projects", json={"name": f"log-check-{marker[:6]}",
                                                     "classes": ["person"]}, headers=auth).json()
    c.post(f"/api/ws/{ws}/projects/{project['slug']}/upload", headers=auth,
           files={"files": (f"{marker}.png", body.getvalue(), "image/png")})
    key = c.post(f"/api/ws/{ws}/keys", json={"name": "log-check"}, headers=auth).json()["key"]

    text = logbuf.getvalue()
    for secret in (DEMO_PW, token, key, marker):
        assert secret not in text, "a log line must never carry a credential or a body"
    for word in ("password", "api_key", "token"):
        assert word not in text


def test_a_500_carries_the_traceback_on_the_same_request_id(logbuf):
    async def boom():
        raise ZeroDivisionError("t1300")

    app.add_api_route("/api/_t1300_boom", boom)
    try:
        r = TestClient(app).get("/api/_t1300_boom", headers={"X-Request-Id": "boom0001"})
    finally:
        app.router.routes = [x for x in app.router.routes if getattr(x, "path", "") != "/api/_t1300_boom"]
    assert r.status_code == 500
    assert r.headers["X-Request-Id"] == "boom0001"
    line = next(x for x in _lines(logbuf) if x["msg"].startswith("http.request"))
    assert line["request_id"] == "boom0001"
    assert line["status"] == 500
    assert "Traceback" in line["msg"] and "ZeroDivisionError" in line["msg"]


def test_text_format_still_available(monkeypatch):
    root = logging.getLogger()
    saved, level = list(root.handlers), root.level
    monkeypatch.setenv("LD_LOG_JSON", "0")
    monkeypatch.setattr(logging_setup, "_installed", False)
    try:
        logging_setup.install()
        fmt = _handler().formatter
        assert not isinstance(fmt, logging_setup.JsonFormatter)
        record = logging.LogRecord("labeldesk.test", logging.INFO, __file__, 1, "hello", (), None)
        assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} INFO labeldesk.test: hello", fmt.format(record))
    finally:
        root.handlers[:] = saved
        root.setLevel(level)


def test_worker_job_lines_carry_job_id(logbuf, monkeypatch):
    with SessionLocal() as db:
        ws = db.query(Workspace).filter_by(slug=WS).one()
        job = Job(workspace_id=ws.id, kind="export", params={}, created=-1e9)
        db.add(job)
        db.commit()
        jid = job.id
    monkeypatch.setitem(worker.HANDLERS, "export", lambda j: {"status": "done"})
    claimed = worker._claim()
    assert claimed == jid, "the test's job is the oldest queued one"
    worker.run_one(jid)

    lines = [x for x in _lines(logbuf) if x["job_id"] == jid]
    assert any(x["msg"].startswith("job.claim") and "export" in x["msg"] for x in lines), "claim line"
    assert any(x["msg"].startswith("job.done") for x in lines), "terminal line"
    assert all(x["worker_id"] for x in lines), "every job line names the worker"
