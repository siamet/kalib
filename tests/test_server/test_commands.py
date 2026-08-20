"""Tests for the command registry and immediate commands."""

from pathlib import Path

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry, UnknownCommand


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _FailingCameraDevice:
    """A stub whose connect() raises an exception connect_camera() does
    not catch internally, standing in for IDSCamera's constructor raising
    ImportError when the vendor SDK is not installed -- without a real
    CameraController ever touching the vendor SDK or the real hardware.

    Deliberately NOT kalib.hardware.base.ConnectionError: connect_camera()
    already catches that one internally and returns False cleanly, which
    would not exercise fix 3's per-device isolation at all -- the whole
    point of this stub is an exception type that escapes connect_camera()
    uncaught, the same way ImportError does for a real IDSCamera.
    """

    def connect(self) -> None:
        raise RuntimeError("simulated device failure")


@pytest.fixture
def registry():
    """A registry over connected simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=None)


def test_unknown_command_is_rejected(registry):
    """An unregistered name fails as a CommandError, not a KeyError."""
    with pytest.raises(UnknownCommand):
        registry.dispatch("teleport", {})


def test_unknown_command_is_a_command_error(registry):
    """UnknownCommand is catchable as CommandError for the wire taxonomy."""
    assert issubclass(UnknownCommand, CommandError)


def test_status_reports_connection_state(registry):
    """status reports each device's connection state."""
    result = registry.dispatch("status", {})
    assert result["camera"]["connected"] is True
    assert result["stage_xy"]["connected"] is True
    assert result["stage_z"]["connected"] is True


def test_status_reports_not_scanning_when_no_scan_controller(registry):
    """status reports scanning=False when no ScanController is wired up."""
    result = registry.dispatch("status", {})
    assert result["scanning"] is False


def test_connect_reports_each_device(registry):
    """connect works against already-connected hardware and reports a
    per-device result rather than raising."""
    result = registry.dispatch("connect", {})
    assert set(result) == {"camera", "stage_xy", "stage_z"}
    assert all(isinstance(v, bool) for v in result.values())


def test_connect_succeeds_on_fresh_hardware():
    """connect reports success when the devices were not yet connected."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    fresh_registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                                     calibration=None)
    result = fresh_registry.dispatch("connect", {})
    assert result["camera"] is True
    assert result["stage_xy"] is True
    assert result["stage_z"] is True


def test_connect_isolates_a_camera_that_fails_outside_its_own_try_except():
    """One device failing to connect must not prevent the others.

    connect_camera() only catches kalib.hardware.base.ConnectionError
    internally; any other exception raised while connecting -- e.g.
    IDSCamera's constructor raising a plain ImportError when the vendor
    SDK is not installed -- used to propagate out of the `connect` command
    before the stages were ever attempted, since it evaluated a plain
    dict literal left to right. connect must evaluate each device in its
    own try so the stages still connect regardless.

    Uses a stub device (_FailingCameraDevice) rather than a real,
    uninjected CameraController(). A prior version of this test built a
    real IDSCamera and relied on ImportError because the vendor SDK
    happens not to be installed in this dev environment -- but on the
    Windows instrument machine, exactly where this suite would run to
    validate a deployment, the SDK *is* installed, so that version would
    have gone on to actually open the real camera hardware. The stub
    reaches connect_camera()'s same uncaught-exception path with no
    hardware access at all.
    """
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=_FailingCameraDevice())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)

    result = registry.dispatch("connect", {})

    assert result["stage_xy"] is True
    assert result["stage_z"] is True
    assert result["camera"] is not True


def test_disconnect_reports_each_device(registry):
    """disconnect reports a result per device."""
    result = registry.dispatch("disconnect", {})
    assert result["camera"] is True
    assert result["stage_xy"] is True
    assert result["stage_z"] is True


def test_stop_halts_stage_motion(registry):
    """stop reports that the stage was halted."""
    result = registry.dispatch("stop", {})
    assert result == {"stopped": True}


def test_get_position_returns_all_three_axes(registry):
    """get_position reports x, y and z."""
    result = registry.dispatch("get_position", {})
    assert set(result) == {"x", "y", "z"}


def test_move_xy_changes_position(registry):
    """move_xy moves the stage and reports where it ended up."""
    result = registry.dispatch("move_xy", {"x": 12.0, "y": 34.0})
    assert result["x"] == pytest.approx(12.0)
    assert result["y"] == pytest.approx(34.0)


def test_move_z_changes_position(registry):
    """move_z moves the Z axis only."""
    before = registry.dispatch("get_position", {})
    registry.dispatch("move_z", {"z": 7.0})
    after = registry.dispatch("get_position", {})
    assert after["z"] == pytest.approx(7.0)
    assert after["x"] == pytest.approx(before["x"])


def test_move_rel_is_additive(registry):
    """move_rel offsets from the current position."""
    registry.dispatch("move_xy", {"x": 10.0, "y": 10.0})
    result = registry.dispatch("move_rel", {"dx": 2.0, "dy": -3.0})
    assert result["x"] == pytest.approx(12.0)
    assert result["y"] == pytest.approx(7.0)


def test_missing_required_argument_is_a_command_error(registry):
    """A command called without its required argument fails cleanly."""
    with pytest.raises(CommandError):
        registry.dispatch("move_z", {})


def test_move_xy_on_an_unconnected_stage_raises_instead_of_reporting_ok():
    """StageController.move_absolute used to return True having done
    nothing when the targeted stage was never connected, so move_xy before
    connect reported ok:true with a stale position and nothing moved. It
    must now raise CommandError instead."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController()  # No injected or configured devices.
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    with pytest.raises(CommandError):
        registry.dispatch("move_xy", {"x": 1.0, "y": 2.0})


def test_start_acquisition_on_a_disconnected_camera_raises_with_a_reason():
    """A bool-returning handler must surface why it failed, not just
    turn a controller's False into a bare JSON false."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())  # not connected
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    with pytest.raises(CommandError, match="not connected"):
        registry.dispatch("start_acquisition", {})


def test_status_reports_false_fields_as_data_without_raising():
    """status on disconnected hardware is a normal reply, not a failure:
    connected: false and acquiring: false are the answer, not an error."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    result = registry.dispatch("status", {})
    assert result["camera"]["connected"] is False
    assert result["stage_xy"]["connected"] is False
    assert result["stage_z"]["connected"] is False


def test_command_names_are_listed(registry):
    """The registry can enumerate what it accepts."""
    names = registry.command_names()
    assert "status" in names
    assert "move_xy" in names


def test_start_acquisition_makes_status_report_acquiring(registry):
    """start_acquisition brings the camera to acquiring=True."""
    result = registry.dispatch("start_acquisition", {})
    assert result == {"acquiring": True}
    status = registry.dispatch("status", {})
    assert status["camera"]["acquiring"] is True


def test_stop_acquisition_returns_to_not_acquiring(registry):
    """stop_acquisition reverses start_acquisition."""
    registry.dispatch("start_acquisition", {})
    result = registry.dispatch("stop_acquisition", {})
    assert result == {"acquiring": False}
    status = registry.dispatch("status", {})
    assert status["camera"]["acquiring"] is False


def test_snap_succeeds_after_connect_and_start_acquisition(tmp_path):
    """The remote-only path -- connect, then start_acquisition, then snap --
    must work with no local GUI interaction, since that is the whole point
    of exposing start_acquisition as a command. Uses fresh, unconnected
    hardware and drives every step through registry.dispatch, exactly as a
    real client would over the wire."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    fresh_registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                                     calibration=None)

    fresh_registry.dispatch("connect", {})
    fresh_registry.dispatch("start_acquisition", {})

    target = tmp_path / "shot.tiff"
    result = fresh_registry.dispatch("snap", {"path": str(target)})
    assert Path(result["path"]).exists()
    assert result["width"] > 0 and result["height"] > 0
