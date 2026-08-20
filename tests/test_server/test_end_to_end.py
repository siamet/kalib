"""End-to-end tests driving simulated hardware through the wire protocol."""

import socket
import time

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry
from kalib.server.daemon import CommandDaemon
from kalib.server.protocol import decode_message, encode_request


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def rig(qapp):
    """A daemon plus the controllers behind it."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    factory.world.width, factory.world.height = 64, 64
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    daemon = CommandDaemon(registry, port=0)
    daemon.start()
    yield daemon, camera, stage, factory.world
    daemon.stop()


# A single processEvents() pass per poll is not always enough to carry a
# connection all the way from accept through readyRead to a written reply
# (accepting and wiring the socket is one event-loop pass; noticing the
# already-buffered request and writing the response is another). Blocking on
# recv() with a long timeout after only one pump starves the loop of the
# further pumps it needs, so poll with a short per-attempt timeout and bound
# the total wait with a wall-clock deadline instead, matching
# tests/test_server/test_daemon.py's _round_trip.
_POLL_INTERVAL = 0.05
_POLL_DEADLINE = 5.0


def _send(daemon, qapp, cmd, args):
    """Send one command over a real socket and return the decoded reply."""
    with socket.create_connection(("127.0.0.1", daemon.port), timeout=5) as sock:
        sock.sendall(encode_request(cmd, args, "e2e"))
        sock.settimeout(_POLL_INTERVAL)
        buf = b""
        deadline = time.monotonic() + _POLL_DEADLINE
        while not buf.endswith(b"\n") and time.monotonic() < deadline:
            qapp.processEvents()
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
        return decode_message(buf)


def test_moving_over_the_wire_moves_the_simulated_stage(rig, qapp):
    """A command on the socket reaches the hardware layer."""
    daemon, _camera, _stage, world = rig
    _send(daemon, qapp, "move_xy", {"x": 42.0, "y": 24.0})
    assert world.x == pytest.approx(42.0)
    assert world.y == pytest.approx(24.0)


def test_preview_over_the_wire_reflects_focus(rig, qapp):
    """Sharpness reported over the wire drops as the stage defocuses."""
    daemon, _camera, _stage, world = rig
    world.tilt_a = world.tilt_b = 0.0
    world.tilt_c = 5.0

    _send(daemon, qapp, "move_z", {"z": 5.0})
    focused = _send(daemon, qapp, "preview", {"max_px": 64})["result"]["sharpness"]

    _send(daemon, qapp, "move_z", {"z": 8.0})
    blurred = _send(daemon, qapp, "preview", {"max_px": 64})["result"]["sharpness"]

    assert focused > blurred


def test_snap_over_the_wire_writes_a_file(rig, qapp, tmp_path):
    """A capture requested over the wire lands on disk."""
    daemon, _camera, _stage, _world = rig
    target = tmp_path / "wire.tiff"
    msg = _send(daemon, qapp, "snap", {"path": str(target)})
    assert msg["ok"] is True
    assert target.exists()


def test_shutdown_stops_acquisition_but_leaves_the_stage(rig):
    """Safe state stops acquisition and never moves the stage."""
    daemon, camera, _stage, world = rig
    before = (world.x, world.y, world.z)

    result = daemon.shutdown_safe_state()

    assert result["acquisition_stopped"] is True
    assert camera.is_acquiring is False
    assert (world.x, world.y, world.z) == before
