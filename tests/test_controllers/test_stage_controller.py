"""Tests for StageController against simulated stages."""

import pytest

from kalib.controllers.stage_controller import StageController
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(x=50.0, y=50.0, z=5.0)


@pytest.fixture
def controller(world):
    """A controller driving injected simulated stages."""
    return StageController(
        xy_device=SimStageXY(world),
        z_device=SimStageZ(world),
    )


def test_connect_uses_injected_devices(controller):
    """Connecting succeeds with no real controllers present."""
    assert controller.connect_xy_stage() is True
    assert controller.connect_z_stage() is True


def test_xy_move_reaches_the_requested_position(controller, world):
    """An XY move through the controller updates the simulated world."""
    controller.connect_xy_stage()
    controller.move_absolute(x=10.0, y=20.0)
    assert (world.x, world.y) == (pytest.approx(10.0), pytest.approx(20.0))


def test_z_move_reaches_the_requested_position(controller, world):
    """A Z move through the controller updates the simulated world."""
    controller.connect_z_stage()
    controller.move_absolute(z=7.0)
    assert world.z == pytest.approx(7.0)


def test_connect_xy_without_device_id_or_injection_fails():
    """The real-hardware path still refuses to connect with no device ID."""
    controller = StageController()
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.connect_xy_stage() is False
    assert errors == ["No XY stage device ID configured"]


def test_connect_z_without_device_id_or_injection_fails():
    """The real-hardware path still refuses to connect with no device ID."""
    controller = StageController()
    errors = []
    controller.error_occurred.connect(errors.append)

    assert controller.connect_z_stage() is False
    assert errors == ["No Z stage device ID configured"]

def test_z_move_beyond_the_limit_is_refused_not_clamped(controller, world):
    """A move outside travel must fail loudly rather than land somewhere else.

    The hardware clamps and logs a warning, so a caller that trusts its own
    commanded positions builds a stack whose axis is wrong at the ends with
    nothing raised. Refuse the move instead, and leave the stage where it was.
    """
    controller.connect_z_stage()
    controller.move_absolute(z=5.0)
    assert controller.move_absolute(z=99.0) is False
    assert world.z == pytest.approx(5.0)


def test_xy_move_beyond_the_limit_is_refused_not_clamped(controller, world):
    """Same contract on the XY axes."""
    controller.connect_xy_stage()
    controller.move_absolute(x=10.0, y=20.0)
    assert controller.move_absolute(x=500.0, y=20.0) is False
    assert (world.x, world.y) == (pytest.approx(10.0), pytest.approx(20.0))


def test_a_move_inside_the_limits_still_succeeds(controller, world):
    """The guard must not reject legitimate moves."""
    controller.connect_z_stage()
    assert controller.move_absolute(z=9.5) is True
    assert world.z == pytest.approx(9.5)
