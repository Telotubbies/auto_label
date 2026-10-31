"""Fetch a user-supplied image URL without exposing the internal network (SSRF guard).

Only http/https, only public unicast addresses, every redirect hop re-checked,
connection pinned to the vetted IP (no DNS-rebinding window), size and time capped.
"""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 20 * 1024 * 1024
TIMEOUT = 10


class BlockedURL(ValueError):
    pass


def _public_ip(host: str, port: int) -> str:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise BlockedURL(f"cannot resolve {host}") from e
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if not ip.is_global or ip.is_multicast:
            raise BlockedURL("URL points to a private or reserved address")
    return infos[0][4][0]


def fetch(url: str, max_redirects: int = 3) -> bytes:
    for _ in range(max_redirects + 1):
        u = urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise BlockedURL("only http(s) URLs are allowed")
        port = u.port or (443 if u.scheme == "https" else 80)
        ip = _public_ip(u.hostname, port)
        if u.scheme == "https":
            conn = http.client.HTTPSConnection(ip, port, timeout=TIMEOUT, context=ssl.create_default_context())
            conn._tunnel_host = None
            # connect to the vetted IP but validate the certificate for the real hostname
            conn.sock = ssl.create_default_context().wrap_socket(
                socket.create_connection((ip, port), timeout=TIMEOUT), server_hostname=u.hostname)
        else:
            conn = http.client.HTTPConnection(ip, port, timeout=TIMEOUT)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        conn.request("GET", path, headers={"Host": u.netloc, "User-Agent": "LabelDesk/1.0"})
        r = conn.getresponse()
        if r.status in (301, 302, 303, 307, 308) and r.getheader("Location"):
            url = urljoin(url, r.getheader("Location")); conn.close(); continue
        if r.status != 200:
            raise BlockedURL(f"image URL returned HTTP {r.status}")
        data = r.read(MAX_BYTES + 1)
        conn.close()
        if len(data) > MAX_BYTES:
            raise BlockedURL("image larger than 20 MB")
        return data
    raise BlockedURL("too many redirects")
