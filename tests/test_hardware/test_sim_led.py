"""Tests for the simulated LED controller."""

import pytest

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


def test_brightness_clamps_to_range(world):
    """Out-of-range brightness is clamped to the configured range."""
    led = SimLED(world, brightness_range=(0, 255))
    led.connect()
    led.set_brightness(300)
    assert led.get_brightness() == 255
    led.set_brightness(-50)
    assert led.get_brightness() == 0


def test_turn_off_sets_zero(world):
    """turn_off drives brightness to zero."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(200)
    led.turn_off()
    assert led.get_brightness() == 0


def test_turn_on_with_explicit_brightness(world):
    """turn_on with explicit brightness sets that value."""
    led = SimLED(world)
    led.connect()
    led.turn_off()
    assert led.get_brightness() == 0
    led.turn_on(128)
    assert led.get_brightness() == 128


def test_turn_on_no_args_restores_off_state(world):
    """turn_on() with no argument after turn_off() keeps LED off."""
    led = SimLED(world, brightness_range=(0, 255))
    led.connect()
    led.set_brightness(200)
    led.turn_off()
    assert led.get_brightness() == 0
    led.turn_on()
    assert led.get_brightness() == 0


def test_turn_on_no_args_remembers_brightness(world):
    """turn_on() with no argument remembers the current brightness level."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(180)
    led.turn_on()
    assert led.get_brightness() == 180


def test_percent_round_trips(world):
    """Percentage helpers agree with raw values."""
    led = SimLED(world, brightness_range=(0, 200))
    led.connect()
    led.set_brightness_percent(50.0)
    assert led.get_brightness() == 100
    assert led.get_brightness_percent() == pytest.approx(50.0)


def test_current_ma_matches_led_driver_formula(world):
    """get_current_ma uses the same brightness/4096*293 formula as LEDDriver.

    A 7x divergence here would mean code calibrated in simulation is wrong
    on the instrument, so this pins the two formulas together.
    """
    led = SimLED(world, brightness_range=(0, 4096))
    led.connect()
    led.set_brightness(2048)
    assert led.get_current_ma() == pytest.approx(2048 / 4096 * 293)


def test_connect_applies_default_brightness(world):
    """Connecting sets brightness to the configured default, like LEDDriver."""
    led = SimLED(world, default_brightness=64)
    led.connect()
    assert led.get_brightness() == 64
