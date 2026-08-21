"""Tests for KalibApplication's hardware wiring helpers.

These exercise _build_sim_devices and _build_stage_limits directly, without
running KalibApplication.__init__ (which loads config files and sets up
logging). The controllers involved are QObject-based and construct fine
without a QApplication.
"""

from config import Settings
from kalib.hardware.factory import HardwareFactory
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.main import KalibApplication


def _bare_app(settings: Settings) -> KalibApplication:
    """Build a KalibApplication without running __init__.

    Args:
        settings: Settings instance the app should use

    Returns:
        A KalibApplication with only .settings set
    """
    app = object.__new__(KalibApplication)
    app.settings = settings
    return app


def test_build_sim_devices_returns_none_for_real_backend():
    """Real backend: devices stay lazy, constructed later at connect time.

    This pins the guard that exists specifically so real drivers are never
    constructed eagerly - doing so raises ImportError on machines without
    the vendor SDKs, which would crash the app on the instrument.
    """
    app = _bare_app(Settings({'hardware': {'backend': 'real'}}))
    factory = HardwareFactory(app.settings)
    limits = app._build_stage_limits()

    devices = app._build_sim_devices(factory, 'xy-id', 'z-id', limits)

    assert devices == (None, None, None)


def test_build_sim_devices_returns_simulators_for_sim_backend():
    """Sim backend: all three devices are built eagerly as simulators."""
    app = _bare_app(Settings({'hardware': {'backend': 'sim'}}))
    factory = HardwareFactory(app.settings)
    limits = app._build_stage_limits()

    camera, xy, z = app._build_sim_devices(factory, 'xy-id', 'z-id', limits)

    assert isinstance(camera, SimCamera)
    assert isinstance(xy, SimStageXY)
    assert isinstance(z, SimStageZ)


def test_build_stage_limits_reads_configured_ranges():
    """A non-default configured range reaches StageLimits.

    Settings.get splits only on '.', so a key like 'x_range[0]' never
    matches - this pins the fix that indexes the list instead.
    """
    app = _bare_app(Settings({
        'stages': {
            'xy': {'x_range': [1.0, 42.0], 'y_range': [2.0, 43.0]},
            'z': {'z_range': [0.5, 9.5]},
        }
    }))

    limits = app._build_stage_limits()

    assert (limits.x_min, limits.x_max) == (1.0, 42.0)
    assert (limits.y_min, limits.y_max) == (2.0, 43.0)
    assert (limits.z_min, limits.z_max) == (0.5, 9.5)


def test_build_stage_limits_falls_back_to_defaults_when_unconfigured():
    """Absent configuration, the standard XY/Z ranges are used."""
    app = _bare_app(Settings({}))

    limits = app._build_stage_limits()

    assert (limits.x_min, limits.x_max) == (0.0, 100.0)
    assert (limits.y_min, limits.y_max) == (0.0, 100.0)
    assert (limits.z_min, limits.z_max) == (0.0, 400.0)
