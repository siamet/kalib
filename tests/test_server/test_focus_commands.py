"""Tests for autofocus and tilt-calibration commands."""

import pytest

from kalib.controllers.calibration_controller import CalibrationController
from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry
from kalib.server.handlers_scan import AUTOFOCUS_MAX_STEPS, AUTOFOCUS_MIN_STEPS


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


def test_autofocus_num_steps_is_clamped_to_the_configured_range(registry, monkeypatch):
    """quick_autofocus retains every captured frame until the sweep ends;
    at 36 MB/frame on real hardware an unclamped num_steps is an easy way
    to exhaust memory (the default 20 steps is 720 MB, --num_steps 500 is
    18 GB). The handler must clamp before the controller ever sees it, on
    both ends of the range.

    Stubs quick_autofocus rather than running a real sweep, since this is
    testing the handler's clamp, not the controller's search -- a real
    200-step sweep would also make this test unnecessarily slow.
    """
    captured = {}

    def fake_quick_autofocus(num_steps, search_range):
        captured["num_steps"] = num_steps
        return 5.0

    monkeypatch.setattr(registry.calibration, "quick_autofocus", fake_quick_autofocus)

    registry.dispatch("autofocus", {"num_steps": 5000, "search_range": 2.0})
    assert captured["num_steps"] == AUTOFOCUS_MAX_STEPS

    registry.dispatch("autofocus", {"num_steps": 0, "search_range": 2.0})
    assert captured["num_steps"] == AUTOFOCUS_MIN_STEPS


def test_tilt_sequence_is_exposed_as_three_commands(registry):
    """Tilt calibration is driven step by step, matching the controller:
    tilt_start, then tilt_measure once per corner, then tilt_complete.

    Drives the real sequence end to end rather than only checking
    tilt_start, since tilt_measure and tilt_complete were otherwise the
    only two of twenty commands with zero coverage.
    """
    start = registry.dispatch("tilt_start", {"num_corners": 4})
    assert start["started"] is True

    for corner_idx in range(4):
        measured = registry.dispatch("tilt_measure", {"corner_idx": corner_idx})
        assert measured["measured"] is True
        assert measured["corner_idx"] == corner_idx

    complete = registry.dispatch("tilt_complete", {})
    assert complete["completed"] is True


def test_commands_requiring_calibration_fail_without_it(registry):
    """A registry built without a calibration controller says so."""
    bare = CommandRegistry(camera=registry.camera, stage=registry.stage,
                           scan=None, calibration=None)
    with pytest.raises(CommandError):
        bare.dispatch("autofocus", {})
