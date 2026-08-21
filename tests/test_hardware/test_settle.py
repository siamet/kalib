"""Tests for waiting on position rather than the on-target flag.

The E-816 reports qONT True before the actuator has moved at all, measured on
the bench: at t=0.00 the flag was True with the stage 4.94 um short of target.
Waiting on the flag is therefore a no-op, so the wait is done on position.
"""

import pytest

from kalib.hardware.base import TimeoutError as StageTimeoutError
from kalib.hardware.pi_stage_z import wait_until_settled


class FakeClock:
    """A clock that only advances when sleep() is called."""

    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, dt):
        self.t += dt


def test_returns_once_the_reading_reaches_the_target():
    """A stage that arrives immediately does not delay the caller."""
    clock = FakeClock()
    got = wait_until_settled(lambda: 5.0, target=5.0, tolerance=0.1,
                             timeout=1.0, now=clock.now, sleep=clock.sleep)
    assert got == pytest.approx(5.0)


def test_waits_while_the_stage_is_still_travelling():
    """It must not return on the first reading the way qONT did."""
    clock = FakeClock()
    readings = iter([0.2, 1.4, 3.1, 4.6, 5.02])
    got = wait_until_settled(lambda: next(readings), target=5.0,
                             tolerance=0.1, timeout=1.0,
                             now=clock.now, sleep=clock.sleep)
    assert got == pytest.approx(5.02)
    assert clock.t > 0.0, "returned without ever waiting"


def test_a_steady_state_offset_inside_tolerance_counts_as_arrived():
    """The servo settles ~40 nm off target; that is arrival, not failure."""
    clock = FakeClock()
    got = wait_until_settled(lambda: 5.042, target=5.0, tolerance=0.1,
                             timeout=1.0, now=clock.now, sleep=clock.sleep)
    assert got == pytest.approx(5.042)


def test_raises_when_the_stage_never_arrives():
    """A stage that cannot reach the target must fail loudly, not hang."""
    clock = FakeClock()
    with pytest.raises(StageTimeoutError) as excinfo:
        wait_until_settled(lambda: 0.0, target=5.0, tolerance=0.1,
                           timeout=0.5, now=clock.now, sleep=clock.sleep)
    assert "5.0" in str(excinfo.value)
    assert "0.0" in str(excinfo.value), "the error should report where it got to"


def test_approaching_from_above_settles_too():
    """Tolerance is symmetric; overshoot is as valid as undershoot."""
    clock = FakeClock()
    readings = iter([9.0, 6.0, 5.05])
    got = wait_until_settled(lambda: next(readings), target=5.0,
                             tolerance=0.1, timeout=1.0,
                             now=clock.now, sleep=clock.sleep)
    assert got == pytest.approx(5.05)
