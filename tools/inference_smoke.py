"""Smoke-check a running LabelDesk inference container: /healthz, /models and /predict.

Usage:
    python tools/inference_smoke.py --url http://localhost:8010
    python tools/inference_smoke.py --url http://localhost:8010 --image photo.jpg --model ppe/best.onnx

Prints one PASS/FAIL line per check and exits non-zero on the first failed check.
Only the standard library is used, so this runs on any machine with Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path

REQUIRED_KEYS = {"class", "class_id", "confidence", "x", "y", "width", "height"}


def _png(width: int = 64, height: int = 64) -> bytes:
    """A tiny red RGB PNG, so the smoke check needs no sample file."""
    row = b"\x00" + b"\xff\x00\x00" * width
    raw = row * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _request(
    url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 60
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        return 0, f"cannot reach {url}: {error.reason}".encode()


def _multipart(fields: dict[str, str], filename: str, content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = "----labeldesk-" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _report(ok: bool, label: str, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'} {label}{': ' + detail if detail else ''}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-check a running LabelDesk inference container.")
    parser.add_argument("--url", default="http://127.0.0.1:8010", help="base URL of the service")
    parser.add_argument("--image", type=Path, help="image to POST (default: a generated 64x64 PNG)")
    parser.add_argument("--model", help="model name from GET /models; omit for a single-model mount")
    parser.add_argument("--confidence", type=float, default=0.25, help="confidence sent to /predict")
    parser.add_argument("--timeout", type=float, default=60, help="per-request timeout in seconds")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    status, body = _request(f"{base}/healthz", timeout=args.timeout)
    try:
        health = json.loads(body)
    except json.JSONDecodeError:
        health = {}
    ok = _report(
        status == 200 and health.get("status") == "ok",
        "healthz",
        f"HTTP {status}, {health.get('models', {}).get('count', '?')} model(s), "
        f"backends {health.get('backends')}, versions {health.get('versions')}"
        if status
        else body.decode(errors="replace"),
    )
    if not ok:
        return 1

    status, body = _request(f"{base}/models", timeout=args.timeout)
    try:
        parsed = json.loads(body)
        catalog = parsed.get("models", []) if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        catalog = []
    ok = _report(
        status == 200 and bool(catalog) and all({"name", "backend", "available"} <= set(row) for row in catalog),
        "models",
        f"HTTP {status}, {[row.get('name') for row in catalog]}",
    )
    if not ok:
        return 1

    if args.image:
        content, filename, content_type = args.image.read_bytes(), args.image.name, "application/octet-stream"
    else:
        content, filename, content_type = _png(), "smoke.png", "image/png"
    fields = {"confidence": str(args.confidence)}
    if args.model:
        fields["model"] = args.model
    payload, boundary = _multipart(fields, filename, content, content_type)

    status, body = _request(f"{base}/predict", data=payload, headers={"Content-Type": boundary}, timeout=args.timeout)
    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        result = {}
    predictions = result.get("predictions") if isinstance(result, dict) else None
    shape_ok = (
        isinstance(predictions, list)
        and isinstance(result.get("image"), dict)
        and isinstance(result["image"].get("width"), int)
        and isinstance(result["image"].get("height"), int)
        and all(isinstance(p, dict) and REQUIRED_KEYS <= set(p) for p in predictions)
    )
    if not _report(
        status == 200 and isinstance(predictions, list) and shape_ok,
        "predict",
        f"HTTP {status}, model={result.get('model')!r}, {len(predictions or [])} prediction(s)"
        if status == 200
        else f"HTTP {status}: {body[:300]!r}",
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
