"""Tests for the simulated camera."""

import numpy as np
import pytest

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.hardware.base import ConnectionError
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    """A flat sample focused at z = 5.0."""
    return SimWorld(x=0.0, y=0.0, z=5.0, tilt_a=0.0, tilt_b=0.0, tilt_c=5.0,
                    width=256, height=256)


@pytest.fixture
def camera(world):
    """A connected, acquiring simulated camera."""
    cam = SimCamera(world)
    cam.connect()
    cam.start_acquisition()
    return cam


def test_capture_returns_frame_of_configured_size(camera, world):
    """Captured frames match the world's sensor dimensions."""
    frame = camera.capture()
    assert frame.shape[0] == world.height
    assert frame.shape[1] == world.width
    assert frame.dtype == np.uint8


def test_capture_requires_acquisition_started(world):
    """Capturing before acquisition starts is an error, as on real hardware."""
    cam = SimCamera(world)
    cam.connect()
    with pytest.raises(ConnectionError):
        cam.capture()


def test_image_is_sharper_at_focus_than_away_from_it(camera, world):
    """Defocus blurs the frame. This is what makes autofocus testable."""
    world.z = world.focus_z()
    sharp = gradient_sharpness(camera.capture())

    world.z = world.focus_z() + 1.0
    blurred = gradient_sharpness(camera.capture())

    assert sharp > blurred


def test_frames_are_repeatable_for_a_given_state(camera, world):
    """The same world state produces the same frame, so tests are deterministic."""
    world.z = 5.0
    first = camera.capture()
    second = camera.capture()
    assert np.array_equal(first, second)


def test_resolution_matches_world(camera, world):
    """get_resolution reports the simulated sensor size."""
    assert camera.get_resolution() == (world.width, world.height)


def test_exposure_round_trips(camera):
    """Exposure set on the simulator is reported back."""
    camera.set_exposure_time(20000.0)
    assert camera.get_exposure_time() == pytest.approx(20000.0)
