"""Tests for CameraController against a simulated camera."""

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(width=128, height=128)


@pytest.fixture
def controller(world):
    """A controller driving an injected simulated camera."""
    return CameraController(device=SimCamera(world))


def test_connect_uses_the_injected_device(controller):
    """Connecting succeeds with no real hardware present."""
    assert controller.connect_camera() is True
    assert controller.model.state.is_connected is True


def test_resolution_comes_from_the_injected_device(controller, world):
    """The controller reads resolution from the injected device."""
    controller.connect_camera()
    assert controller.model.state.resolution == (world.width, world.height)


def test_capture_returns_a_frame(controller, world):
    """A frame can be captured end to end through the controller."""
    controller.connect_camera()
    controller.start_acquisition()
    frame = controller.capture_image()
    assert frame is not None
    assert frame.shape[:2] == (world.height, world.width)
