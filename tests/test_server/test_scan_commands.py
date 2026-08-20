"""Tests for scan job commands."""

import time

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.scan_controller import ScanController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _pump_until(qapp, predicate, timeout=5.0):
    """Drain the Qt event queue until predicate() is true or timeout elapses.

    ScanController's worker-to-controller cleanup handlers are reached via
    a queued cross-thread signal, which is only delivered once something
    drains the event queue on the thread that owns the ScanController.
    Without this, a completed or cancelled scan's QThread never quits, and
    Qt aborts the process when that QThread is later garbage collected.

    Args:
        qapp: The QCoreApplication whose event queue is drained
        predicate: Callable returning True once the wait is over
        timeout: Maximum seconds to wait

    Returns:
        Whether predicate() became true before the timeout
    """
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
    return predicate()


def _drain_scan_thread(registry, qapp, timeout=5.0):
    """Let a started scan finish or be cancelled, and its thread quit.

    Called at the end of any test that started a real scan, so the
    ScanController is safe to garbage collect at fixture teardown instead
    of aborting the process.
    """
    scan = registry.scan
    if scan is not None:
        _pump_until(qapp, lambda: scan._scan_thread is None, timeout=timeout)


@pytest.fixture
def registry():
    """A registry with a scan controller over simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    factory.world.width, factory.world.height = 64, 64
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    scan = ScanController(camera_controller=camera, stage_controller=stage)
    return CommandRegistry(camera=camera, stage=stage, scan=scan,
                           calibration=None)


def test_scan_xy_returns_a_job_id_without_blocking(registry, qapp):
    """Starting a scan returns immediately with an identifier."""
    result = registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 2.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    assert result["started"] is True
    assert isinstance(result["job_id"], str) and result["job_id"]
    _drain_scan_thread(registry, qapp)


def test_job_status_reports_the_running_job(registry, qapp):
    """job_status reports scanning state and progress."""
    registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 2.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    status = registry.dispatch("job_status", {})
    assert set(status) >= {"job_id", "scanning", "progress"}
    _drain_scan_thread(registry, qapp)


def test_job_cancel_stops_the_scan(registry, qapp):
    """A running scan can be cancelled."""
    registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 5.0, "end_y": 5.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    assert registry.dispatch("job_cancel", {})["cancelled"] is True
    _drain_scan_thread(registry, qapp)


def test_job_status_with_no_job_reports_idle(registry):
    """Asking for status before any scan is not an error."""
    status = registry.dispatch("job_status", {})
    assert status["scanning"] is False
    assert status["job_id"] is None


def test_scan_requires_a_scan_controller(registry):
    """A registry built without a scan controller says so."""
    bare = CommandRegistry(camera=registry.camera, stage=registry.stage,
                           scan=None, calibration=None)
    with pytest.raises(CommandError):
        bare.dispatch("scan_xy", {})
