"""SSRF-safe egress for OpenCV/FFmpeg media sources.

Checking the source hostname once is not enough: libavformat resolves it again at
connect time (a DNS-rebinding window) and follows HTTP 3xx redirects itself (a
redirect SSRF).  For HTTP(S) sources the worker therefore gives OpenCV a loopback
reverse-proxy URL.  The proxy re-validates and pins every hop, refuses a redirect to
a non-public address, and keeps the real hostname and camera credentials away from
FFmpeg.  RTSP has no proxy support in libavformat, so the worker hands it the vetted
IP literal instead (DNS pinning); TLS sources keep their hostname so certificate
validation still applies.

The connection code is the same pinned `services.safefetch` path used for webhooks
and connector downloads.  A maintained proxy library (safehttpx/mitmproxy) cannot
intercept libavformat's own socket or stream a live feed without adding a much larger
runtime, so the small guard lives here.
"""
from __future__ import annotations

import base64
import http.client
import http.server
import threading
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from ..services.safefetch import BlockedURL, UnresolvableHost, _host_header, _pinned_connection, _public_ip
from .allowlist import allowed_stream_ip

_MAX_HOPS = 3
_CHUNK = 64 * 1024


class GuardedMediaProxy:
    """A one-stream loopback reverse proxy: vetted, pinned, redirect-safe."""

    def __init__(self, source: str, ip: str | None = None):
        u = urlsplit(source)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError("media guard only accepts http(s) URLs")
        self.source = source
        self._first_ip = ip
        self._lock = threading.Lock()
        self._closed = False
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.error = ""                 # last safe, user-facing reason
        self.transient = True           # policy rejections flip this to False

    def start(self) -> str:
        handler = type("_GuardedHandler", (_ProxyHandler,), {"proxy": self})
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True,
                                        name="stream-egress-guard")
        self._thread.start()
        u = urlsplit(self.source)
        return urlunsplit(("http", f"127.0.0.1:{self._server.server_address[1]}",
                           u.path or "/", u.query, ""))

    def stop(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        server, thread = self._server, self._thread
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(2.0)

    def _upstream(self, headers: dict[str, str]):
        """Open the first safe, non-redirect hop and return ``(connection, response)``."""
        url = self.source
        for hop in range(_MAX_HOPS + 1):
            u = urlsplit(url)
            if u.scheme not in ("http", "https") or not u.hostname:
                self._blocked("invalid media redirect")
                raise ValueError("invalid media redirect")
            port = u.port or (443 if u.scheme == "https" else 80)
            try:
                if hop == 0 and self._first_ip:
                    ip = self._first_ip
                else:
                    ip = allowed_stream_ip(u.hostname, port) or _public_ip(u.hostname, port)
            except UnresolvableHost as e:
                self.error, self.transient = str(e), True
                raise
            except BlockedURL as e:
                self._blocked(str(e))
                raise
            conn = _pinned_connection(u, ip, port)
            path = (u.path or "/") + (f"?{u.query}" if u.query else "")
            out = {"Host": _host_header(u, port), "User-Agent": headers.get("User-Agent", "LabelDesk/1.0")}
            for key in ("Range", "Accept", "If-None-Match", "If-Modified-Since"):
                if key in headers:
                    out[key] = headers[key]
            auth = self._basic_auth(u)
            if auth:
                out["Authorization"] = auth
            try:
                conn.request("GET", path, headers=out)
                response = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                conn.close()
                self.error, self.transient = f"media source unreachable ({type(e).__name__})", True
                raise
            if response.status in (301, 302, 303, 307, 308) and response.getheader("Location"):
                location = response.getheader("Location")
                response.close()
                conn.close()
                if hop >= _MAX_HOPS:
                    self._blocked("too many media redirects")
                    raise ValueError("too many media redirects")
                url = urljoin(url, location)
                continue
            if response.status not in (200, 206):
                response.close()
                conn.close()
                self.error = f"media source returned HTTP {response.status}"
                self.transient = True
                raise ValueError(self.error)
            return conn, response
        self._blocked("too many media redirects")
        raise ValueError("too many media redirects")

    def _blocked(self, message: str) -> None:
        self.error = message
        self.transient = False

    @staticmethod
    def _basic_auth(u) -> str:
        if "@" not in u.netloc:
            return ""
        userinfo = u.netloc.rpartition("@")[0]
        user, sep, password = userinfo.partition(":")
        if not sep:
            return ""
        raw = f"{unquote(user)}:{unquote(password)}".encode()
        return "Basic " + base64.b64encode(raw).decode()


class _ProxyHandler(http.server.BaseHTTPRequestHandler):
    proxy: GuardedMediaProxy
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            conn, response = self.proxy._upstream(self.headers)
        except Exception:
            try:
                self.send_error(403, "blocked by the stream egress guard")
            except OSError:
                pass
            return
        try:
            self.send_response(response.status)
            for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges",
                        "Last-Modified", "ETag", "Cache-Control"):
                value = response.getheader(key)
                if value:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while not self.proxy._closed:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            try:
                response.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
