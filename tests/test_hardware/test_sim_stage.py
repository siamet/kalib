"""Tests for the simulated stages."""

import pytest

from kalib.hardware.base import ConnectionError
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(x=50.0, y=50.0, z=5.0)


def test_xy_absolute_move_updates_world(world):
    """Moving the simulated XY stage moves the shared world."""
    stage = SimStageXY(world)
    stage.connect()
    stage.move_absolute(x=10.0, y=20.0)
    assert world.x == pytest.approx(10.0)
    assert world.y == pytest.approx(20.0)
    assert stage.get_position() == (pytest.approx(10.0), pytest.approx(20.0))


def test_xy_relative_move_is_additive(world):
    """Relative moves add to the current position."""
    stage = SimStageXY(world)
    stage.connect()
    stage.move_absolute(x=10.0, y=10.0)
    stage.move_relative(dx=2.5, dy=-3.0)
    assert stage.get_position() == (pytest.approx(12.5), pytest.approx(7.0))


def test_xy_move_clamps_out_of_range(world):
    """Out-of-range moves are clamped to the valid range."""
    stage = SimStageXY(world, x_range=(0.0, 100.0), y_range=(0.0, 100.0))
    stage.connect()
    # Move beyond upper limit
    stage.move_absolute(x=150.0)
    assert stage.get_position()[0] == pytest.approx(100.0)
    # Move beyond lower limit
    stage.move_absolute(x=-10.0)
    assert stage.get_position()[0] == pytest.approx(0.0)


def test_z_move_updates_world(world):
    """Moving the simulated Z stage moves the shared world."""
    stage = SimStageZ(world)
    stage.connect()
    stage.move_absolute(7.5)
    assert world.z == pytest.approx(7.5)
    assert stage.get_position() == pytest.approx(7.5)


def test_z_move_clamps_out_of_range(world):
    """Out-of-range Z moves are clamped to the valid range."""
    stage = SimStageZ(world, z_range=(0.0, 10.0))
    stage.connect()
    # Move beyond upper limit
    stage.move_absolute(20.0)
    assert stage.get_position() == pytest.approx(10.0)
    # Move beyond lower limit
    stage.move_absolute(-5.0)
    assert stage.get_position() == pytest.approx(0.0)


def test_stages_share_one_world(world):
    """XY and Z stages act on the same world object."""
    xy = SimStageXY(world)
    z = SimStageZ(world)
    xy.connect()
    z.connect()
    xy.move_absolute(x=1.0, y=2.0)
    z.move_absolute(3.0)
    assert (world.x, world.y, world.z) == (
        pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0))


def test_xy_operations_require_connection(world):
    """XY stage operations raise ConnectionError when not connected."""
    stage = SimStageXY(world)
    with pytest.raises(ConnectionError):
        stage.stop()


def test_z_reference_requires_connection(world):
    """Z stage reference() raises ConnectionError when not connected."""
    stage = SimStageZ(world)
    with pytest.raises(ConnectionError):
        stage.reference()
