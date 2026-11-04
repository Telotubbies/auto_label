"""Operator allowlist for stream sources on a private network (I-3).

The SSRF guard in ``services.safefetch`` refuses every non-public address, but a CCTV
camera normally lives on a LAN and is private by definition. An operator can name those
exact networks in ``LD_STREAM_ALLOW_CIDR``; the list is empty by default and the strict
public-only check still runs for every address that is not in it.

A name is allowed only when *every* address it resolves to is inside the allowlist, so a
mixed public/private DNS answer cannot smuggle the private one through. This is checked
before the public-IP rejection in the stream resolve path and on every guarded HTTP
redirect hop.
"""
from __future__ import annotations

import ipaddress
import socket

from .. import config
from ..services.safefetch import NAT64


def _reserved(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_multicast or (ip.version == 6 and ip in NAT64)


def allowed_stream_ip(host: str, port: int) -> str | None:
    """Return the vetted address when every resolved address is operator-allowed.

    ``None`` means "not covered": the caller falls through to the normal public-IP
    check, which keeps both the rejection message and the default posture. A resolver
    failure is also ``None`` so that path reports the usual transient error.
    """
    allow = config.STREAM_ALLOW_CIDR
    if not allow:
        return None
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return None
    for *_, addr in infos:
        ip = ipaddress.ip_address(addr[0])
        if _reserved(ip) or not any(ip in net for net in allow):
            return None
    return infos[0][4][0]
