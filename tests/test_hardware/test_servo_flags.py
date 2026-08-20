"""Tests for per-axis servo flag construction."""

from kalib.hardware.pi_stage_xy import SERVO_AXES, servo_flags


def test_three_axis_controller_leaves_the_spare_channel_off():
    """The E-725 here reports three axes for a two-axis stage."""
    assert servo_flags(3) == [1, 1, 0]


def test_two_axis_controller_gets_no_trailing_zero():
    """A two-axis controller must not receive a third flag."""
    assert servo_flags(2) == [1, 1]


def test_four_channel_controller_has_every_spare_channel_off():
    """Channels beyond the stage stay off, however many there are."""
    assert servo_flags(4) == [1, 1, 0, 0]


def test_flag_count_always_matches_the_axis_count():
    """SVO requires one flag per axis; a mismatch fails at the controller."""
    for n in range(2, 9):
        assert len(servo_flags(n)) == n


def test_only_the_stage_axes_are_enabled():
    """Enabling an unconnected channel would drive its piezo to the rail."""
    for n in range(2, 9):
        flags = servo_flags(n)
        assert sum(flags) == min(SERVO_AXES, n)
        assert flags[:SERVO_AXES] == [1] * min(SERVO_AXES, n)
