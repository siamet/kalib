"""Tests for the simulated LED controller."""

import pytest

from kalib.hardware.base import CommandError
from kalib.hardware.sim.sim_led import SimLED
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld()


def test_set_brightness_updates_world(world):
    """Brightness set on the LED is visible in the shared world."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(128)
    assert world.led_brightness == 128
    assert led.get_brightness() == 128


def test_brightness_outside_range_is_rejected(world):
    """Out-of-range brightness raises rather than clamping."""
    led = SimLED(world, brightness_range=(0, 255))
    led.connect()
    with pytest.raises(CommandError):
        led.set_brightness(300)


def test_turn_off_sets_zero(world):
    """turn_off drives brightness to zero."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(200)
    led.turn_off()
    assert led.get_brightness() == 0


def test_percent_round_trips(world):
    """Percentage helpers agree with raw values."""
    led = SimLED(world, brightness_range=(0, 200))
    led.connect()
    led.set_brightness_percent(50.0)
    assert led.get_brightness() == 100
    assert led.get_brightness_percent() == pytest.approx(50.0)
