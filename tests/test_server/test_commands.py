"""Tests for the command registry and immediate commands."""

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


def test_command_names_are_listed(registry):
    """The registry can enumerate what it accepts."""
    names = registry.command_names()
    assert "status" in names
    assert "move_xy" in names
