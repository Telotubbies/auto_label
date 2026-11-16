"""OT protocol drivers: exact frames for Modbus/MQTT and sysfs GPIO. No real equipment or network.

Every socket is a fake; the Modbus/MQTT tests assert the bytes a PLC or broker would receive,
including the length fields, so a truncated or mis-numbered frame fails here rather than on a line.
"""
import pytest

from app.ot import drivers


class FakeSocket:
    """Records every write and replays canned responses (one per recv)."""

    def __init__(self, responses=()):
        self.sent: list[bytes] = []
        self.responses = list(responses)
        self.closed = False
        self.timeout = None

    def sendall(self, data: bytes) -> None:
        self.sent.append(bytes(data))

    def recv(self, n: int) -> bytes:
        """Like a TCP socket: never return more than ``n`` bytes; keep the rest buffered."""
        if not self.responses:
            return b""
        chunk = self.responses[0]
        head, tail = chunk[:n], chunk[n:]
        if tail:
            self.responses[0] = tail
        else:
            self.responses.pop(0)
        return head

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def close(self) -> None:
        self.closed = True


def _fake_connection(monkeypatch, sock: FakeSocket) -> None:
    calls = []

    def connect(address, timeout=None):
        calls.append((address, timeout))
        return sock

    monkeypatch.setattr(drivers.socket, "create_connection", connect)
    return calls


def _mqtt_remaining(packet: bytes) -> int:
    """Decode the MQTT variable-length remaining-length field (at most four bytes)."""
    value, shift, index = 0, 0, 1
    while True:
        byte = packet[index]
        value |= (byte & 0x7F) << shift
        index += 1
        if not byte & 0x80:
            return value
        shift += 7


# --- Modbus TCP ----------------------------------------------------------------

def test_modbus_coil_pulses_on_then_off(monkeypatch):
    on = b"\x00\x01\x00\x00\x00\x06\x01\x05\x00\x0a\xff\x00"
    off = b"\x00\x01\x00\x00\x00\x06\x01\x05\x00\x0a\x00\x00"
    sock = FakeSocket([on, off])
    calls = _fake_connection(monkeypatch, sock)
    endpoint = {"host": "plc.example.test", "port": 502, "unit_id": 1, "register": "coil", "address": 10}

    drivers.write("modbus", endpoint, True)
    drivers.write("modbus", endpoint, False)

    assert sock.sent[0] == b"\x00\x01\x00\x00\x00\x06\x01\x05\x00\x0a\xff\x00"   # FC5, coil 10, ON
    assert sock.sent[1] == b"\x00\x01\x00\x00\x00\x06\x01\x05\x00\x0a\x00\x00"   # FC5, coil 10, OFF
    assert calls == [(("plc.example.test", 502), drivers.TIMEOUT_S)] * 2
    assert sock.closed


def test_modbus_holding_register_writes_one_and_zero(monkeypatch):
    on = b"\x00\x01\x00\x00\x00\x06\x07\x06\x00\x03\x00\x01"
    off = b"\x00\x01\x00\x00\x00\x06\x07\x06\x00\x03\x00\x00"
    sock = FakeSocket([on, off])
    _fake_connection(monkeypatch, sock)
    endpoint = {"host": "plc.example.test", "port": 1502, "unit_id": 7, "register": "holding", "address": 3}

    drivers.write("modbus", endpoint, True)
    drivers.write("modbus", endpoint, False)

    assert sock.sent[0] == b"\x00\x01\x00\x00\x00\x06\x07\x06\x00\x03\x00\x01"   # FC6, register 3 = 1
    assert sock.sent[1] == b"\x00\x01\x00\x00\x00\x06\x07\x06\x00\x03\x00\x00"   # FC6, register 3 = 0


def test_modbus_exception_response_is_a_driver_error(monkeypatch):
    # FC5 | 0x80, exception code 2 (illegal data address)
    sock = FakeSocket([b"\x00\x01\x00\x00\x00\x03\x01\x85\x02"])
    _fake_connection(monkeypatch, sock)
    endpoint = {"host": "plc.example.test", "port": 502, "unit_id": 1, "register": "coil", "address": 10}
    with pytest.raises(drivers.DriverError, match="modbus exception 2"):
        drivers.write("modbus", endpoint, True)


def test_modbus_refuses_an_unbounded_length(monkeypatch):
    sock = FakeSocket([b"\x00\x01\x00\x00\xff\xff\x01"])
    _fake_connection(monkeypatch, sock)
    endpoint = {"host": "plc.example.test", "port": 502, "unit_id": 1, "register": "coil", "address": 10}
    with pytest.raises(drivers.DriverError, match="response mismatch"):
        drivers.write("modbus", endpoint, True)


def test_modbus_refuses_a_truncated_response(monkeypatch):
    sock = FakeSocket([b"\x00\x01\x00\x00\x00"])
    _fake_connection(monkeypatch, sock)
    endpoint = {"host": "plc.example.test", "port": 502, "unit_id": 1, "register": "coil", "address": 10}
    with pytest.raises(drivers.DriverError):
        drivers.write("modbus", endpoint, True)


# --- MQTT 3.1.1 (QoS 0) --------------------------------------------------------

def test_mqtt_connects_then_publishes_on_and_retained_off(monkeypatch):
    sock = FakeSocket([b"\x20\x02\x00\x00", b"\x20\x02\x00\x00"])
    _fake_connection(monkeypatch, sock)
    endpoint = {"host": "broker.example.test", "port": 1883, "topic": "line1/reject"}

    drivers.write("mqtt", endpoint, True)
    drivers.write("mqtt", endpoint, False)

    connect, publish, connect2, release = sock.sent
    assert connect[0] == 0x10                                      # CONNECT
    level_at = connect.index(b"MQTT") + len(b"MQTT")                # protocol name followed by level
    assert connect[level_at] == 4                                  # 3.1.1
    assert publish[0] == 0x30                                       # PUBLISH, QoS 0, not retained
    assert _mqtt_remaining(publish) == len(publish) - 2 - 0         # length field covers topic + payload
    assert b"line1/reject" in publish
    assert publish.endswith(b"1")
    assert connect2[0] == 0x10
    assert release[0] == 0x31                                       # release is retained: reconnect sees safe
    assert release.endswith(b"0")
    assert sock.closed


def test_mqtt_rejected_connection_is_a_driver_error(monkeypatch):
    sock = FakeSocket([b"\x20\x02\x00\x05"])                        # CONNACK: not authorized
    _fake_connection(monkeypatch, sock)
    with pytest.raises(drivers.DriverError, match="mqtt connect refused"):
        drivers.write("mqtt", {"host": "broker.example.test", "port": 1883, "topic": "t"}, False)


# --- OPC-UA (optional client, faked module) -------------------------------------

def test_opcua_writes_boolean_through_the_optional_client(monkeypatch):
    import sys
    import types

    written = []

    class FakeClient:
        def __init__(self, url, timeout=None):
            self.url, self.timeout = url, timeout

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get_node(self, node_id):
            return types.SimpleNamespace(write_value=lambda value: written.append((node_id, value)))

    sync = types.ModuleType("asyncua.sync")
    sync.Client = FakeClient
    monkeypatch.setitem(sys.modules, "asyncua", types.ModuleType("asyncua"))
    monkeypatch.setitem(sys.modules, "asyncua.sync", sync)

    endpoint = {"endpoint_url": "opc.tcp://plc.example.test:4840", "node_id": "ns=2;s=Reject"}
    drivers.write("opcua", endpoint, True)
    drivers.write("opcua", endpoint, False)

    assert written == [("ns=2;s=Reject", True), ("ns=2;s=Reject", False)]


def test_opcua_without_the_optional_package_fails_safe(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "asyncua.sync", None)
    endpoint = {"endpoint_url": "opc.tcp://plc.example.test:4840", "node_id": "ns=2;s=Reject"}
    with pytest.raises(drivers.DriverError, match="not installed"):
        drivers.write("opcua", endpoint, True)


# --- GPIO via sysfs ------------------------------------------------------------

def _gpio_root(tmp_path, line: int = 17) -> tuple:
    root = tmp_path / "gpio"
    (root / f"gpio{line}").mkdir(parents=True)
    value = root / f"gpio{line}" / "value"
    value.write_text("0")
    return root, value


def test_gpio_active_high_writes_levels(tmp_path, monkeypatch):
    root, value = _gpio_root(tmp_path)
    monkeypatch.setenv("LD_GPIO_ROOT", str(root))

    drivers.write("gpio", {"line": 17, "active_high": True}, True)
    assert value.read_text() == "1"
    drivers.write("gpio", {"line": 17, "active_high": True}, False)
    assert value.read_text() == "0"


def test_gpio_active_low_inverts_the_level(tmp_path, monkeypatch):
    root, value = _gpio_root(tmp_path)
    monkeypatch.setenv("LD_GPIO_ROOT", str(root))

    drivers.write("gpio", {"line": 17, "active_high": False}, True)
    assert value.read_text() == "0"
    drivers.write("gpio", {"line": 17, "active_high": False}, False)
    assert value.read_text() == "1"


def test_gpio_symlink_escape_is_rejected(tmp_path, monkeypatch):
    """A symlinked value file must not let a config write outside the GPIO root."""
    root, value = _gpio_root(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("0")
    value.unlink()
    try:
        value.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("this platform does not allow unprivileged symlinks")
    monkeypatch.setenv("LD_GPIO_ROOT", str(root))
    with pytest.raises(drivers.DriverError, match="outside the configured root"):
        drivers.write("gpio", {"line": 17, "active_high": True}, True)
    assert outside.read_text() == "0"


def test_gpio_missing_line_is_a_driver_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LD_GPIO_ROOT", str(tmp_path / "gpio"))
    with pytest.raises(drivers.DriverError):
        drivers.write("gpio", {"line": 99, "active_high": True}, True)


def test_gpio_traversal_is_rejected(tmp_path, monkeypatch):
    """The line number is an int, so the resolved path must still stay under the configured root."""
    root, _value = _gpio_root(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("0")
    monkeypatch.setenv("LD_GPIO_ROOT", str(root))

    with pytest.raises(drivers.DriverError):
        drivers.write("gpio", {"line": "../outside", "active_high": True}, True)
