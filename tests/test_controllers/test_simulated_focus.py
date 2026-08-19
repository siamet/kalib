"""End-to-end checks that the simulator reproduces focus behaviour."""

import pytest

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _sim_rig(tilt_a=0.0, tilt_b=0.0, tilt_c=5.0):
    """Build connected controllers over a shared simulated world.

    Args:
        tilt_a: Focal plane gradient along X
        tilt_b: Focal plane gradient along Y
        tilt_c: Focal plane height at the origin

    Returns:
        Tuple of (camera controller, stage controller, world)
    """
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    world = factory.world
    world.tilt_a, world.tilt_b, world.tilt_c = tilt_a, tilt_b, tilt_c
    world.width, world.height = 128, 128

    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    return camera, stage, world


def test_sharpness_peaks_at_the_focal_plane():
    """Sweeping z through focus produces a peak at the plane."""
    camera, stage, world = _sim_rig(tilt_c=5.0)

    heights = [3.0, 4.0, 5.0, 6.0, 7.0]
    scores = []
    for z in heights:
        stage.move_absolute(z=z)
        scores.append(gradient_sharpness(camera.capture_image()))

    assert heights[scores.index(max(scores))] == pytest.approx(5.0)


def _sharpness_peak_z(camera, stage, x, y, heights):
    """Move to (x, y), sweep z, and return the height with peak sharpness.

    Args:
        camera: Connected, acquiring CameraController
        stage: Connected StageController
        x: X position to measure at
        y: Y position to measure at
        heights: Candidate Z heights to sweep through

    Returns:
        The height in `heights` at which captured-image sharpness peaks
    """
    stage.move_absolute(x=x, y=y)
    scores = []
    for z in heights:
        stage.move_absolute(z=z)
        scores.append(gradient_sharpness(camera.capture_image()))
    return heights[scores.index(max(scores))]


def test_focal_height_shifts_with_xy_when_the_sample_is_tilted():
    """A tilted sample focuses at different z depending on position.

    This is the behaviour tilt calibration exists to measure, so it must be
    observed through the camera - a simulator whose camera ignored focus
    entirely would still pass a test that only checked the world's dataclass
    arithmetic (that arithmetic is covered separately in
    tests/test_hardware/test_sim_world.py).
    """
    camera, stage, world = _sim_rig(tilt_a=0.01, tilt_c=5.0)

    # The sharpness peak is roughly 44x its neighbours one mm away (measured
    # with this pattern and this tilt), so a 1 mm sweep resolution finds it
    # reliably without flakiness.
    peak_at_origin = _sharpness_peak_z(camera, stage, x=0.0, y=0.0,
                                       heights=[3.0, 4.0, 5.0, 6.0, 7.0])
    peak_at_far_x = _sharpness_peak_z(camera, stage, x=100.0, y=0.0,
                                      heights=[4.0, 5.0, 6.0, 7.0, 8.0])

    expected_shift = world.focus_z(100.0, 0.0) - world.focus_z(0.0, 0.0)
    assert peak_at_far_x - peak_at_origin == pytest.approx(expected_shift)
