"""I2 regression: media egress must survive a redirect/rebinding attempt and a DNS blip.

The review probe for `oc-nogo-streams` showed that checking the source hostname once is
not enough: FFmpeg resolves it again and follows a 302 into the internal network. These
tests pin the two halves of the fix:

* HTTP(S) capture goes through the loopback guard, which refuses a redirect to a
  private host instead of letting libavformat follow it.
* A resolver failure on a reconnect is transient (`reconnecting`), while a resolved
  address that is forbidden is still a fatal stream error.
"""

import http.server
import io
import ipaddress
import socket
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import pytest
from PIL import Image as PImage
from sqlalchemy import select

from app import config
from app.db import SessionLocal
from app.models import Project, Stream
from app.services.safefetch import BlockedURL, UnresolvableHost
from app.streams import manager as mgr

_JPEG = io.BytesIO()
PImage.new("RGB", (64, 64), (200, 30, 30)).save(_JPEG, "JPEG")
_JPEG = _JPEG.getvalue()


class _Target(http.server.BaseHTTPRequestHandler):
    hits: list[str] = []

    def do_GET(self):
        type(self).hits.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(_JPEG)))
        self.end_headers()
        self.wfile.write(_JPEG)

    def log_message(self, *args):
        pass


class _Redirect(http.server.BaseHTTPRequestHandler):
    location = ""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", type(self).location)
        self.end_headers()

    def log_message(self, *args):
        pass


def _serve(handler) -> tuple[http.server.ThreadingHTTPServer, int]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


class _OpenableCap:
    def __init__(self):
        self.reads = 0

    def isOpened(self):
        return True

    def read(self):
        self.reads += 1
        return self.reads < 2, np.zeros((8, 8, 3), np.uint8)

    def get(self, _prop):
        return 10.0

    def set(self, *_args):
        return True

    def release(self):
        pass


def test_guarded_proxy_refuses_a_redirect_to_a_private_host(monkeypatch):
    target, target_port = _serve(_Target)
    _Redirect.location = f"http://internal.test:{target_port}/secret"
    redirect, redirect_port = _serve(_Redirect)
    _Target.hits = []

    def public_only(host, _port):
        if host == "public.test":
            return "127.0.0.1"
        raise BlockedURL("URL points to a private or reserved address")

    monkeypatch.setattr(mgr, "_public_ip", public_only)
    proxy = mgr.GuardedMediaProxy(f"http://public.test:{redirect_port}/live", ip="127.0.0.1")
    url = proxy.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(url, timeout=5).read()
        assert caught.value.code == 403
    finally:
        proxy.stop()
        redirect.shutdown()
        redirect.server_close()
        target.shutdown()
        target.server_close()
    assert _Target.hits == [], "the private redirect target was contacted"


def test_http_source_is_opened_through_the_loopback_guard(monkeypatch):
    opened: list[str] = []

    def capture(url, *_args, **_kwargs):
        opened.append(url)
        return _OpenableCap()

    monkeypatch.setattr(mgr.cv2, "VideoCapture", capture)
    monkeypatch.setattr(mgr, "_public_ip", lambda _host, _port: "8.8.8.8")
    worker = mgr._Worker(Stream(
        id="guard-open", workspace_id="w", project_id="p", name="guard",
        source="http://camera.example.test/live", model_ref="ultralytics:yolo11n"))
    cap = worker._open()
    try:
        assert cap is not None
        assert opened
        assert opened[0].startswith("http://127.0.0.1:")
        assert "camera.example.test" not in opened[0]
    finally:
        if cap is not None:
            cap.release()
        worker._close_proxy()


def test_open_refuses_a_redirect_to_a_private_host_end_to_end(monkeypatch):
    target, target_port = _serve(_Target)
    _Redirect.location = f"http://internal.test:{target_port}/secret"
    redirect, redirect_port = _serve(_Redirect)
    _Target.hits = []

    def public_only(host, _port):
        if host == "public.test":
            return "127.0.0.1"
        raise BlockedURL("URL points to a private or reserved address")

    monkeypatch.setattr(mgr, "_public_ip", public_only)
    worker = mgr._Worker(Stream(
        id="guard-redirect", workspace_id="w", project_id="p", name="guard",
        source=f"http://public.test:{redirect_port}/live", model_ref="ultralytics:yolo11n"))
    cap = None
    try:
        cap = worker._open()
        if cap is not None:                       # some builds open before the 403 response lands
            assert cap.read()[0] is False
            assert worker._active_proxy is not None
            assert "private or reserved" in worker._active_proxy.error
    finally:
        if cap is not None:
            cap.release()
        worker._close_proxy()
        redirect.shutdown()
        redirect.server_close()
        target.shutdown()
        target.server_close()
    assert _Target.hits == [], "OpenCV/FFmpeg followed the private redirect"


def test_rtsp_source_is_pinned_to_the_vetted_ip(monkeypatch):
    opened: list[str] = []

    def capture(url, *_args, **_kwargs):
        opened.append(url)
        return _OpenableCap()

    monkeypatch.setattr(mgr.cv2, "VideoCapture", capture)
    monkeypatch.setattr(mgr, "_public_ip", lambda _host, _port: "203.0.113.10")
    worker = mgr._Worker(Stream(
        id="pinned", workspace_id="w", project_id="p", name="pinned",
        source="rtsp://alice:secret@camera.example.test:554/live",
        model_ref="ultralytics:yolo11n"))
    cap = worker._open()
    try:
        assert opened == ["rtsp://alice:secret@203.0.113.10:554/live"]
    finally:
        if cap is not None:
            cap.release()
        worker._close_proxy()


def test_check_source_marks_an_unresolvable_host_as_transient(monkeypatch):
    def cannot_resolve(_host, _port):
        raise UnresolvableHost("cannot resolve cam.example.test")

    monkeypatch.setattr(mgr, "_public_ip", cannot_resolve)
    with pytest.raises(mgr.SourceTransient):
        mgr.check_source("http://cam.example.test/live")


def _worker_row(name: str) -> Stream:
    with SessionLocal() as db:
        project = db.scalar(select(Project).where(Project.slug == "ppe-detection"))
        row = Stream(workspace_id=project.workspace_id, project_id=project.id, name=name,
                     source="http://camera.example.test/live", model_ref="ultralytics:yolo11n",
                     status="stopped")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def _run_grab(worker) -> threading.Thread:
    thread = threading.Thread(target=worker._guard, args=(worker._grab,), daemon=True)
    thread.start()
    return thread


def _wait_for(predicate, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_transient_resolution_failure_reconnects_instead_of_failing(monkeypatch):
    row = _worker_row("flaky DNS")
    answers = {"n": 0}

    def flaky(host, _port):
        answers["n"] += 1
        if answers["n"] == 1:
            return "8.8.8.8"
        raise UnresolvableHost(f"cannot resolve {host}")

    monkeypatch.setattr(mgr, "_public_ip", flaky)
    monkeypatch.setattr(mgr.cv2, "VideoCapture", lambda *_a, **_k: _OpenableCap())
    worker = mgr._Worker(row)
    thread = _run_grab(worker)
    try:
        assert _wait_for(lambda: "cannot resolve" in worker.last_error)
        assert worker.status == "reconnecting", (worker.status, worker.last_error)
        assert not worker.fatal
    finally:
        worker._stop.set()
        thread.join(5)
        with SessionLocal() as db:
            db.delete(db.get(Stream, row.id))
            db.commit()


def test_forbidden_rebinding_is_a_fatal_stream_error(monkeypatch):
    row = _worker_row("rebinding")
    answers = {"n": 0}

    def rebinding(host, _port):
        answers["n"] += 1
        if answers["n"] == 1:
            return "8.8.8.8"
        raise BlockedURL(f"URL points to a private or reserved address ({host})")

    monkeypatch.setattr(mgr, "_public_ip", rebinding)
    monkeypatch.setattr(mgr.cv2, "VideoCapture", lambda *_a, **_k: _OpenableCap())
    worker = mgr._Worker(row)
    thread = _run_grab(worker)
    try:
        assert _wait_for(lambda: worker.status == "error")
        assert worker.fatal
        assert "private or reserved" in worker.last_error
    finally:
        worker._stop.set()
        thread.join(5)
        with SessionLocal() as db:
            db.delete(db.get(Stream, row.id))
            db.commit()


# ---------------------------------------------------------------------------
# I-3: LAN cameras are private by definition, so the operator may name the exact
# networks the stream egress may reach. The allowlist is empty by default and a
# name is only allowed when *every* address it resolves to is inside it.
# ---------------------------------------------------------------------------


def _answer(ip: str, port: int = 554):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]


def test_private_source_is_rejected_by_default(monkeypatch):
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", ())
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: _answer("192.168.1.20"))
    with pytest.raises(ValueError, match="private or reserved"):
        mgr.resolve_source("rtsp://user:pass@192.168.1.20:554/stream1")


def test_private_source_is_allowed_when_its_cidr_is_configured(monkeypatch):
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", (ipaddress.ip_network("192.168.0.0/16"),))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: _answer("192.168.1.20"))
    source, ip = mgr.resolve_source("rtsp://user:pass@cam.lan:554/stream1")
    assert source == "rtsp://user:pass@cam.lan:554/stream1"
    assert ip == "192.168.1.20"


def test_address_outside_the_configured_cidr_is_still_rejected(monkeypatch):
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", (ipaddress.ip_network("10.0.0.0/8"),))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: _answer("192.168.1.20"))
    with pytest.raises(ValueError, match="private or reserved"):
        mgr.resolve_source("rtsp://cam.lan:554/stream1")


def test_a_name_mixing_allowed_and_forbidden_answers_is_rejected(monkeypatch):
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", (ipaddress.ip_network("192.168.1.20/32"),))
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_a, **_k: _answer("192.168.1.20") + _answer("10.0.0.9"))
    with pytest.raises(ValueError, match="private or reserved"):
        mgr.resolve_source("rtsp://cam.lan:554/stream1")


def test_invalid_allow_cidr_fails_loudly():
    with pytest.raises(RuntimeError, match="LD_STREAM_ALLOW_CIDR"):
        config.parse_cidrs("192.168.0.0/16,not-a-cidr")


def test_wildcard_allow_cidr_is_refused():
    with pytest.raises(RuntimeError, match="wildcard"):
        config.parse_cidrs("0.0.0.0/0")
    with pytest.raises(RuntimeError, match="wildcard"):
        config.parse_cidrs("::/0")


def test_allow_cidr_accepts_a_comma_separated_list():
    nets = config.parse_cidrs(" 192.168.0.0/16 , 10.0.0.0/8 ,")
    assert nets == (ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("10.0.0.0/8"))


def test_uploaded_video_needs_no_allowlist(monkeypatch):
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", ())
    assert mgr.resolve_source("file:videos/demo.mp4") == ("file:videos/demo.mp4", "")


def test_guard_follows_a_redirect_into_an_allowlisted_network(monkeypatch):
    target, target_port = _serve(_Target)
    _Redirect.location = f"http://internal.test:{target_port}/secret"
    redirect, redirect_port = _serve(_Redirect)
    _Target.hits = []
    monkeypatch.setattr(config, "STREAM_ALLOW_CIDR", (ipaddress.ip_network("127.0.0.0/8"),))
    monkeypatch.setattr(socket, "getaddrinfo", lambda _host, port, *_a, **_k: _answer("127.0.0.1", port))
    proxy = mgr.GuardedMediaProxy(f"http://public.test:{redirect_port}/live", ip="127.0.0.1")
    url = proxy.start()
    try:
        assert urllib.request.urlopen(url, timeout=5).read() == _JPEG
    finally:
        proxy.stop()
        redirect.shutdown()
        redirect.server_close()
        target.shutdown()
        target.server_close()
    assert _Target.hits == ["/secret"]
