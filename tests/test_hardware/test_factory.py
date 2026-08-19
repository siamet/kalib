"""Tests for the hardware factory."""

import pytest

from kalib.hardware.factory import HardwareFactory
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.sim_led import SimLED


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def sim_settings():
    return FakeSettings({'hardware.backend': 'sim'})


def test_sim_backend_builds_simulated_devices(sim_settings):
    """With backend 'sim', every device is a simulator."""
    factory = HardwareFactory(sim_settings)
    assert isinstance(factory.create_camera(), SimCamera)
    assert isinstance(factory.create_stage_xy(), SimStageXY)
    assert isinstance(factory.create_stage_z(), SimStageZ)
    assert isinstance(factory.create_led(), SimLED)


def test_sim_devices_share_one_world(sim_settings):
    """All simulated devices from one factory act on the same world."""
    factory = HardwareFactory(sim_settings)
    xy = factory.create_stage_xy()
    camera = factory.create_camera()
    xy.connect()
    xy.move_absolute(x=12.0, y=0.0)
    assert factory.world.x == pytest.approx(12.0)


def test_backend_defaults_to_real():
    """Absent configuration, the factory targets real hardware."""
    factory = HardwareFactory(FakeSettings({}))
    assert factory.backend == 'real'


def test_unknown_backend_is_rejected():
    """A misspelled backend fails loudly at construction."""
    from kalib.hardware.base import ConfigurationError
    with pytest.raises(ConfigurationError):
        HardwareFactory(FakeSettings({'hardware.backend': 'pretend'}))


def test_create_led_uses_configured_brightness_scale(sim_settings):
    """The sim LED starts from the same configured scale as the real one."""
    sim_settings._values['led.brightness_range'] = [0, 4096]
    sim_settings._values['led.default_brightness'] = 2048
    factory = HardwareFactory(sim_settings)
    led = factory.create_led()
    led.connect()
    assert led.brightness_range == (0, 4096)
    assert led.get_brightness() == 2048
