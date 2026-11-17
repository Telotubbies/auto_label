"""B2: a safefetch call must honour its connect/read/total timeout, or a slow host pins a worker."""
import socket
import threading
import time

import pytest

from app.services import safefetch


@pytest.fixture()
def silent_server():
    """A real loopback server that accepts the connection and never sends a byte."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    srv.settimeout(0.1)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            with conn:
                stop.wait()                   # hold it open, answer nothing

    threading.Thread(target=serve, daemon=True).start()
    try:
        yield srv.getsockname()[1]
    finally:
        stop.set()
        srv.close()


def test_post_honours_its_timeout(silent_server, monkeypatch):
    """The caller's timeout must reach the socket; a hardcoded 10 s is a worker hang."""
    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "127.0.0.1")
    started = time.monotonic()
    with pytest.raises(OSError):          # socket timeout
        safefetch.post(f"http://hooks.example.com:{silent_server}/x", b"{}", {}, timeout=0.3)
    assert time.monotonic() - started < 3


def test_fetch_bytes_honours_its_timeout(silent_server, monkeypatch):
    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "127.0.0.1")
    started = time.monotonic()
    with pytest.raises(OSError):
        safefetch.fetch_bytes(f"http://img.example.com:{silent_server}/x.jpg", max_bytes=10, timeout=0.3)
    assert time.monotonic() - started < 3


@pytest.fixture()
def trickle_server():
    """A loopback peer that sends headers, then one body byte per 0.1 s: a slow-drip body."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    srv.settimeout(0.1)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            try:
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n")
                for _ in range(1000):
                    if stop.is_set():
                        break
                    conn.sendall(b"x")
                    time.sleep(0.1)
            except OSError:                # the client hung up at its deadline
                pass
            finally:
                conn.close()

    threading.Thread(target=serve, daemon=True).start()
    try:
        yield srv.getsockname()[1]
    finally:
        stop.set()
        srv.close()


def test_total_timeout_bounds_a_slow_drip_body(trickle_server, monkeypatch):
    """Each read resets a per-read timeout, so the deadline must be re-checked across reads."""
    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "127.0.0.1")
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        safefetch.fetch_bytes(f"http://img.example.com:{trickle_server}/x.jpg", max_bytes=20, timeout=0.3)
    assert time.monotonic() - started < 2, "a byte per tick must not hold the call past its one deadline"


def test_total_budget_covers_every_redirect_hop(monkeypatch):
    """Each hop must spend the one budget the caller gave, not a fresh one (total timeout)."""
    seen: list[float] = []

    class Sock:
        def settimeout(self, t):
            pass

    class FakeConn:
        sock = Sock()

        def request(self, *a, **k):
            pass

        def getresponse(self):
            time.sleep(0.1)                 # each hop spends the caller's one budget
            class R:
                status = 302

                def getheader(self, name):
                    return "/next" if name == "Location" else None

            return R()

        def close(self):
            pass

    def fake_connection(*a, **k):
        seen.append(k.get("timeout"))
        return FakeConn()

    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "93.184.216.34")
    monkeypatch.setattr(safefetch.http.client, "HTTPConnection", fake_connection)
    with pytest.raises(safefetch.BlockedURL):
        safefetch._get("http://example.com/a", 10, 0.4, 3)
    assert len(seen) == 4                       # the first hop plus three redirects
    assert seen[0] <= 0.4
    assert seen[-1] < seen[0], "every hop got a fresh budget: the total timeout is not enforced"


def test_a_timeout_closes_the_connection(monkeypatch):
    """A timeout must not wait for the GC to close the socket."""
    closed: list[bool] = []

    class Sock:
        def settimeout(self, t):
            pass

    class FakeConn:
        sock = Sock()

        def request(self, *a, **k):
            pass

        def getresponse(self):
            raise TimeoutError("timed out")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(safefetch, "_public_ip", lambda host, port: "93.184.216.34")
    monkeypatch.setattr(safefetch.http.client, "HTTPConnection", lambda *a, **k: FakeConn())
    with pytest.raises(TimeoutError):
        safefetch._get("http://example.com/a", 10, 0.5, 0)
    assert closed, "the connection must be closed when a timeout unwinds the read"
