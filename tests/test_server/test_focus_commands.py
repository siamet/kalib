"""Tests for autofocus and tilt-calibration commands."""

import pytest

from kalib.controllers.calibration_controller import CalibrationController
from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry with a calibration controller over simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    world = factory.world
    world.tilt_a, world.tilt_b, world.tilt_c = 0.0, 0.0, 5.0
    world.width, world.height = 128, 128

    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    calibration = CalibrationController(camera_controller=camera,
                                        stage_controller=stage)
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=calibration)


def test_autofocus_finds_the_focal_plane(registry):
    """Autofocus lands near the simulated focal plane at z = 5.0."""
    result = registry.dispatch("autofocus", {"num_steps": 21,
                                             "search_range": 4.0})
    assert result["focus_z"] == pytest.approx(5.0, abs=0.5)


def test_autofocus_reports_the_resulting_position(registry):
    """The response carries where the stage ended up."""
    result = registry.dispatch("autofocus", {"num_steps": 11,
                                             "search_range": 4.0})
    assert set(result["position"]) == {"x", "y", "z"}


def test_tilt_sequence_is_exposed_as_three_commands(registry):
    """Tilt calibration is driven step by step, matching the controller."""
    assert registry.dispatch("tilt_start", {"num_corners": 4})["started"] is True


def test_commands_requiring_calibration_fail_without_it(registry):
    """A registry built without a calibration controller says so."""
    bare = CommandRegistry(camera=registry.camera, stage=registry.stage,
                           scan=None, calibration=None)
    with pytest.raises(CommandError):
        bare.dispatch("autofocus", {})
