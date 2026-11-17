"""Fetch a user-supplied image URL without exposing the internal network (SSRF guard).

Only http/https, only public unicast addresses, every redirect hop re-checked,
connection pinned to the vetted IP (no DNS-rebinding window), size and time capped.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 10


class BlockedURL(ValueError):
    pass


class UnresolvableHost(BlockedURL):
    """Transient resolver failure (gaierror), distinct from a policy rejection."""


NAT64 = ipaddress.ip_network("64:ff9b::/96")       # IPv4-embedded IPv6: resolves to private v4 just as easily


def _public_ip(host: str, port: int) -> str:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnresolvableHost(f"cannot resolve {host}") from e
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if not ip.is_global or ip.is_multicast or (ip.version == 6 and ip in NAT64):
            raise BlockedURL("URL points to a private or reserved address")
    return infos[0][4][0]


def check_url(url: str) -> str:
    """Validate scheme/host and that every resolved address is public. Returns the URL unchanged."""
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise BlockedURL("only http(s) URLs are allowed")
    _public_ip(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    return url


def _host_header(u, port: int) -> str:
    """Host header without userinfo; IPv6 literals keep their brackets, non-default ports are kept."""
    host = u.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    if port != (443 if u.scheme == "https" else 80):
        host = f"{host}:{port}"
    return host


def _remaining(deadline: float) -> float:
    """Time left in the call's one total budget; never zero, so no socket call can block forever."""
    return max(0.001, deadline - time.monotonic())


def _arm(conn, deadline: float) -> None:
    """Give the next socket read what is left of the total budget; a spent budget fails the call."""
    left = deadline - time.monotonic()
    if left <= 0:
        conn.close()
        raise TimeoutError("safefetch total timeout exceeded")
    sock = getattr(conn, "sock", None)
    if sock is not None:
        sock.settimeout(left)


def _pinned_connection(u, ip: str, port: int, timeout: float):
    """Connect to the vetted IP while keeping Host/SNI for the real hostname."""
    if u.scheme == "https":
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(ip, port, timeout=timeout, context=context)
        conn.sock = context.wrap_socket(socket.create_connection((ip, port), timeout=timeout),
                                        server_hostname=u.hostname)
        return conn
    return http.client.HTTPConnection(ip, port, timeout=timeout)


def post(url: str, body: bytes, headers: dict, timeout: float = TIMEOUT) -> int:
    """POST JSON to a public http(s) endpoint, pinned to the vetted IP. Never follows redirects.

    Returns the HTTP status code only — callers must not read or store the response body.
    """
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise BlockedURL("only http(s) URLs are allowed")
    port = u.port or (443 if u.scheme == "https" else 80)
    deadline = time.monotonic() + timeout      # DNS is not interruptible, so it spends this budget too
    ip = _public_ip(u.hostname, port)
    conn = _pinned_connection(u, ip, port, _remaining(deadline))
    try:
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        conn.request("POST", path, body=body, headers={"Host": _host_header(u, port), **headers})
        _arm(conn, deadline)                       # the read shares the same total budget
        r = conn.getresponse()
        if r.status in (301, 302, 303, 307, 308):
            raise BlockedURL("webhook redirects are not followed")
        return int(r.status)
    finally:
        conn.close()


def _get(url: str, max_bytes: int, timeout: float, max_redirects: int) -> bytes:
    """GET a public URL, pinning the connection to the one vetted IP (I12: no rebinding window)."""
    deadline = time.monotonic() + timeout      # one budget for every hop and read, not one per hop
    for _ in range(max_redirects + 1):
        u = urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise BlockedURL("only http(s) URLs are allowed")
        port = u.port or (443 if u.scheme == "https" else 80)
        ip = _public_ip(u.hostname, port)
        conn = _pinned_connection(u, ip, port, _remaining(deadline))
        try:
            path = (u.path or "/") + (f"?{u.query}" if u.query else "")
            conn.request("GET", path, headers={"Host": _host_header(u, port), "User-Agent": "LabelDesk/1.0"})
            _arm(conn, deadline)
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308) and r.getheader("Location") and max_redirects:
                url = urljoin(url, r.getheader("Location"))
                continue
            if r.status != 200:
                raise BlockedURL(f"URL returned HTTP {r.status}")
            _arm(conn, deadline)
            data = bytearray()
            while len(data) <= max_bytes:
                _arm(conn, deadline)   # read1 does one recv, so the deadline is checked across the body
                chunk = r.read1(max_bytes + 1 - len(data))
                if not chunk:
                    break
                data += chunk
            if len(data) > max_bytes:
                raise BlockedURL(f"response larger than {max_bytes // (1024 * 1024)} MB")
            return bytes(data)
        finally:
            conn.close()
    raise BlockedURL("too many redirects")


def fetch(url: str, max_redirects: int = 3) -> bytes:
    return _get(url, MAX_BYTES, TIMEOUT, max_redirects)


def fetch_bytes(url: str, max_bytes: int = MAX_BYTES, timeout: float = TIMEOUT) -> bytes:
    """Download one object (up to ``max_bytes``) without following redirects."""
    return _get(url, max_bytes, timeout, 0)
