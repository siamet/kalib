"""Tests for the simulated instrument world."""

import pytest
from kalib.hardware.sim.world import SimWorld


def test_focus_plane_is_tilted():
    """Focal height varies with position when tilt coefficients are non-zero."""
    world = SimWorld(tilt_a=0.01, tilt_b=0.02, tilt_c=5.0)
    assert world.focus_z(0.0, 0.0) == pytest.approx(5.0)
    assert world.focus_z(100.0, 0.0) == pytest.approx(6.0)
    assert world.focus_z(0.0, 100.0) == pytest.approx(7.0)


def test_defocus_is_zero_on_the_focal_plane():
    """Defocus is zero when z sits exactly on the focal plane."""
    world = SimWorld(x=10.0, y=20.0, tilt_a=0.01, tilt_b=0.02, tilt_c=5.0)
    world.z = world.focus_z()
    assert world.defocus() == pytest.approx(0.0)


def test_defocus_grows_with_distance_from_plane():
    """Defocus is the absolute distance from the focal plane."""
    world = SimWorld(x=0.0, y=0.0, tilt_a=0.0, tilt_b=0.0, tilt_c=5.0)
    world.z = 5.5
    assert world.defocus() == pytest.approx(0.5)
    world.z = 4.5
    assert world.defocus() == pytest.approx(0.5)
