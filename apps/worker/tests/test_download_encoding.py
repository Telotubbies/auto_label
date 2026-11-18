"""The worker saves a dataset zip byte for byte, even when the server or a proxy gzips the response.

Found 2026-11-18: the API's GZipMiddleware compressed the zip and ``Server.download`` copied the raw
socket bytes, so every training job on a real worker died with ``BadZipFile``.
"""
import gzip
import io
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from labeldesk_worker.cli import Server


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("data.yaml", "names: [person]\n" * 200)
    return buf.getvalue()


def _serve(body: bytes, gzipped: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = gzip.compress(body) if gzipped else body
            self.send_response(200)
            self.send_header("Content-Type", "application/x-zip-compressed")
            if gzipped:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _download(tmp_path: Path, body: bytes, gzipped: bool) -> bytes:
    server = _serve(body, gzipped)
    try:
        dst = Server(f"http://127.0.0.1:{server.server_port}", "token").download("/ds.zip", tmp_path / "ds.zip")
        return dst.read_bytes()
    finally:
        server.shutdown()


def test_a_plain_zip_is_saved_unchanged(tmp_path):
    body = _zip_bytes()          # built once: a zip records the current time, so two builds can differ
    assert _download(tmp_path, body, gzipped=False) == body


def test_a_gzipped_response_is_decoded_before_it_is_saved(tmp_path):
    body = _zip_bytes()
    saved = _download(tmp_path, body, gzipped=True)

    assert saved == body
    assert zipfile.is_zipfile(io.BytesIO(saved))
