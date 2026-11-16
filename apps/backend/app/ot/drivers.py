"""Industrial transports for the binary reject signal.

The signal is deliberately one bit: asserted = reject/actuate, released = the fail-safe
(de-energised) state. Each driver raises :class:`DriverError` only with a controlled message;
the caller logs unexpected exceptions and reports "driver error" without echoing payloads.

No driver is opened at import time. Tests replace :func:`write` or the socket factory; the
deployment decides which addresses are reachable. Modbus and MQTT are implemented on the
standard library (one TCP connection per write, bounded by ``TIMEOUT_S``) so the demo installs
without an industrial SDK. OPC-UA uses the optional ``asyncua`` package via its synchronous
client; without it the output fails safe with a clear reason. GPIO writes the sysfs value file
below ``LD_GPIO_ROOT`` (default ``/sys/class/gpio``) and never accepts a caller-supplied path.
"""
from __future__ import annotations

import logging
import os
import socket
import struct
from pathlib import Path

log = logging.getLogger("labeldesk.ot")

TIMEOUT_S = 2.0
MQTT_KEEPALIVE_S = 30
MAX_GPIO_LINE = 1023


class DriverError(RuntimeError):
    """A transport failure whose message is safe to store and show as the output status."""


def _tcp(host: str, port: int, timeout: float) -> socket.socket:
    try:
        return socket.create_connection((host, port), timeout=timeout)
    except OSError as e:
        raise DriverError("connection failed") from e


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        try:
            chunk = sock.recv(remaining)
        except OSError as e:
            raise DriverError("connection failed") from e
        if not chunk:
            raise DriverError("connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _modbus(endpoint: dict, asserted: bool, timeout: float) -> None:
    """Modbus TCP write-single-coil (FC5) or write-single-register (FC6), value 1/0."""
    unit = endpoint["unit_id"]
    address = endpoint["address"]
    if endpoint["register"] == "coil":
        pdu = struct.pack(">BHH", 5, address, 0xFF00 if asserted else 0x0000)
    else:
        pdu = struct.pack(">BHH", 6, address, 1 if asserted else 0)
    transaction = 1
    frame = struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu

    sock = _tcp(endpoint["host"], endpoint["port"], timeout)
    try:
        try:
            sock.sendall(frame)
        except OSError as e:
            raise DriverError("connection failed") from e
        header = _recv_exact(sock, 7)
        r_transaction, r_protocol, r_length, r_unit = struct.unpack(">HHHB", header)
        if not 2 <= r_length <= 254:                 # unit id + a PDU no larger than the protocol allows
            raise DriverError("modbus response mismatch")
        body = _recv_exact(sock, r_length - 1)
    finally:
        sock.close()

    if r_transaction != transaction or r_protocol != 0 or r_unit != unit:
        raise DriverError("modbus response mismatch")
    function = body[0]
    if function & 0x80:
        raise DriverError(f"modbus exception {body[1] if len(body) > 1 else 0}")
    if function != pdu[0] or body[1:] != pdu[1:]:
        raise DriverError("modbus response mismatch")


def _mqtt_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value % 128
        value //= 128
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _mqtt_string(value: bytes) -> bytes:
    return struct.pack(">H", len(value)) + value


def _mqtt(endpoint: dict, asserted: bool, timeout: float) -> None:
    """MQTT 3.1.1, clean session, QoS 0 publish of "1"/"0" to one topic.

    The release (``0``) is published retained: if the API crashes or reconnects, the broker
    hands a subscriber the safe level rather than a latched reject. OT brokers normally sit on
    an isolated network; TLS and broker credentials are deliberately out of scope for this
    build, so a deployment exposes the broker only to the API host.
    """
    sock = _tcp(endpoint["host"], endpoint["port"], timeout)
    try:
        client_id = ("labeldesk-ot-" + os.urandom(4).hex()).encode()
        payload = _mqtt_string(b"MQTT") + bytes([4, 0x02]) + struct.pack(">H", MQTT_KEEPALIVE_S)
        payload += _mqtt_string(client_id)
        connect = b"\x10" + _mqtt_varint(len(payload)) + payload
        try:
            sock.sendall(connect)
        except OSError as e:
            raise DriverError("connection failed") from e
        connack = _recv_exact(sock, 4)
        if connack[0] != 0x20 or connack[1] != 2 or connack[3] != 0:
            raise DriverError("mqtt connect refused")

        topic = endpoint["topic"].encode("utf-8")
        body = _mqtt_string(topic) + (b"1" if asserted else b"0")
        header = 0x30 if asserted else 0x31          # bit 0 = retain on the release only
        publish = bytes([header]) + _mqtt_varint(len(body)) + body
        try:
            sock.sendall(publish)
        except OSError as e:
            raise DriverError("connection failed") from e
    finally:
        sock.close()


def _opcua(endpoint: dict, asserted: bool, timeout: float) -> None:
    """Write a boolean to one node through the optional synchronous OPC-UA client."""
    try:
        from asyncua.sync import Client
    except ImportError as e:
        raise DriverError("OPC-UA driver not installed") from e
    try:
        with Client(endpoint["endpoint_url"], timeout=timeout) as client:
            client.get_node(endpoint["node_id"]).write_value(bool(asserted))
    except DriverError:
        raise
    except Exception as e:
        raise DriverError("OPC-UA write failed") from e


def _gpio(endpoint: dict, asserted: bool, _timeout: float) -> None:
    """Write the sysfs value file; ``active_high`` maps the logical bit to the electrical level."""
    line = endpoint["line"]
    if isinstance(line, bool) or not isinstance(line, int) or not 0 <= line <= MAX_GPIO_LINE:
        raise DriverError("invalid GPIO line")
    root = Path(os.environ.get("LD_GPIO_ROOT", "/sys/class/gpio")).resolve()
    path = (root / f"gpio{line}" / "value").resolve()
    if root not in path.parents:
        raise DriverError("GPIO line is outside the configured root")
    level = "1" if bool(asserted) == bool(endpoint.get("active_high", True)) else "0"
    try:
        path.write_text(level)
    except OSError as e:
        raise DriverError("GPIO write failed") from e


DRIVERS = {"modbus": _modbus, "opcua": _opcua, "mqtt": _mqtt, "gpio": _gpio}


def write(protocol: str, endpoint: dict, asserted: bool, timeout: float | None = None) -> None:
    """Assert or release one output; the only function the dispatcher calls.

    ``timeout`` caps connection and response waits; the dispatcher passes the remaining
    latency budget so a slow PLC cannot actuate a part that has already passed the gate.
    """
    try:
        driver = DRIVERS[protocol]
    except KeyError:
        raise DriverError(f"unknown protocol: {protocol}") from None
    driver(endpoint, bool(asserted), timeout or TIMEOUT_S)
