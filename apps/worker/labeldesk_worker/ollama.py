"""T-1023: the Ollama engine's health check, on the worker's loopback only.

The hub never calls this endpoint. The worker probes ``GET /api/version`` before it runs a pull, so
a stopped Ollama server fails the job with one sentence instead of a CLI stack trace.
"""
import json
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_URL = "http://127.0.0.1:11434/api/version"


class OllamaUnreachable(RuntimeError):
    """Nothing answered the loopback health check."""


def version(url: str = DEFAULT_URL, timeout: float = 2.0) -> str:
    """The server version from ``/api/version``, or ``OllamaUnreachable`` naming the URL."""
    try:
        with urlopen(url, timeout=timeout) as response:      # noqa: S310 - loopback only
            body = json.load(response)
    except (OSError, URLError, ValueError) as exc:
        raise OllamaUnreachable(f"ollama_unreachable: no answer from {url} ({exc})") from None
    return str(body.get("version") or "")
