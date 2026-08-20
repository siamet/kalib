"""Tests for the command daemon."""

import json
import socket
import time

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry
from kalib.server.daemon import MAX_BUFFER_BYTES, CommandDaemon
from kalib.server.protocol import PROTOCOL_VERSION, decode_message, encode_request


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def daemon(qapp):
    """A listening daemon over simulated hardware, stopped after the test."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    server = CommandDaemon(registry, port=0)
    server.start()
    yield server
    server.stop()


# A single processEvents() pass per poll is not always enough to carry a
# connection all the way from accept through readyRead to a written reply
# (accepting and wiring the socket is one event-loop pass; noticing the
# already-buffered request and writing the response is another). Blocking on
# recv() with a long timeout after only one pump starves the loop of the
# further pumps it needs, so poll with a short per-attempt timeout and bound
# the total wait with a wall-clock deadline instead. This is still pumping
# with qapp.processEvents(), just at a granularity that actually lets the
# server run between polls.
_POLL_INTERVAL = 0.05
_POLL_DEADLINE = 5.0


def _round_trip(daemon, qapp, cmd, args):
    """Send one command over a real socket and return the decoded reply.

    Args:
        daemon: The listening CommandDaemon
        qapp: The Qt application, pumped while waiting
        cmd: Command name
        args: Command arguments

    Returns:
        The decoded response message
    """
    return _round_trip_raw(daemon, qapp, encode_request(cmd, args, "t1"))


def _round_trip_raw(daemon, qapp, payload_bytes):
    """Send raw bytes over a real socket and return the decoded reply.

    Args:
        daemon: The listening CommandDaemon
        qapp: The Qt application, pumped while waiting
        payload_bytes: Raw newline-terminated bytes to send

    Returns:
        The decoded response message
    """
    with socket.create_connection(("127.0.0.1", daemon.port), timeout=5) as sock:
        sock.sendall(payload_bytes)
        sock.settimeout(_POLL_INTERVAL)
        buf = b""
        deadline = time.monotonic() + _POLL_DEADLINE
        while not buf.endswith(b"\n") and time.monotonic() < deadline:
            qapp.processEvents()
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
        return decode_message(buf)


def test_daemon_listens_on_localhost(daemon):
    """The daemon binds and reports a port."""
    assert daemon.is_listening() is True
    assert daemon.port > 0


def test_daemon_binds_loopback_only(daemon):
    """Binding must be loopback — the server never faces the network."""
    assert daemon.host_address() == "127.0.0.1"


def test_command_round_trips_over_a_real_socket(daemon, qapp):
    """A request on the wire produces a matching response."""
    msg = _round_trip(daemon, qapp, "get_position", {})
    assert msg["ok"] is True
    assert set(msg["result"]) == {"x", "y", "z"}
    assert msg["id"] == "t1"


def test_unknown_command_returns_an_error_response(daemon, qapp):
    """An unknown command produces an error, not a dropped connection."""
    msg = _round_trip(daemon, qapp, "teleport", {})
    assert msg["ok"] is False
    assert msg["error"]["type"] == "UnknownCommand"


def test_stop_releases_the_port(daemon):
    """After stop the daemon is no longer listening."""
    daemon.stop()
    assert daemon.is_listening() is False


def test_unterminated_line_over_the_cap_closes_the_connection(daemon, qapp):
    """A client that never sends a newline cannot grow the server's
    per-socket buffer without limit; past MAX_BUFFER_BYTES the connection
    is closed instead of being buffered forever."""
    with socket.create_connection(("127.0.0.1", daemon.port), timeout=5) as sock:
        sock.sendall(b"x" * (MAX_BUFFER_BYTES + 1))
        sock.settimeout(_POLL_INTERVAL)
        deadline = time.monotonic() + _POLL_DEADLINE
        closed = False
        while not closed and time.monotonic() < deadline:
            qapp.processEvents()
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                closed = True
                break
            if chunk == b"":
                closed = True
                break
        assert closed is True


def test_missing_cmd_field_returns_a_clean_error(daemon, qapp):
    """A well-formed JSON message with no 'cmd' field errors cleanly."""
    payload = (json.dumps({"v": PROTOCOL_VERSION, "id": "t2"}) + "\n").encode("utf-8")
    msg = _round_trip_raw(daemon, qapp, payload)
    assert msg["ok"] is False
    assert msg["id"] == "t2"
    assert msg["error"]["type"] == "ProtocolError"


def test_non_string_cmd_field_returns_a_clean_error(daemon, qapp):
    """A well-formed JSON message with a non-string 'cmd' errors cleanly."""
    payload = (json.dumps({"v": PROTOCOL_VERSION, "id": "t3", "cmd": 42})
               + "\n").encode("utf-8")
    msg = _round_trip_raw(daemon, qapp, payload)
    assert msg["ok"] is False
    assert msg["id"] == "t3"
    assert msg["error"]["type"] == "ProtocolError"
