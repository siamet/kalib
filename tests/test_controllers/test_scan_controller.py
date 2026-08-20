"""Regression tests for ScanController's scan thread lifecycle."""

import time

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.scan_controller import ScanController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.models import XYScanParameters


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def scan_controller():
    """A ScanController wired to simulated, connected hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    factory.world.width, factory.world.height = 64, 64
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    return ScanController(camera_controller=camera, stage_controller=stage)


def test_cancelling_a_scan_emits_scan_cancelled_and_frees_the_thread(
        scan_controller, qapp):
    """Cancelling a running scan must fire scan_cancelled and quit its thread.

    Regression test for a defect where ScanWorker's cancelled branch called
    scan_model.cancel_scan() but emitted no signal at all. ScanController
    only reaches _cleanup_thread() (thread.quit() + thread.wait()) from its
    scan_completed/scan_error handlers, so a cancelled scan's QThread never
    quit: the documented scan_cancelled signal never fired for any
    connected GUI code, and the leaked, still-running QThread aborted the
    process with SIGABRT the moment the ScanController was garbage
    collected.
    """
    scan_controller.configure_xy_scan(XYScanParameters(
        start_x=0.0, start_y=0.0, end_x=5.0, end_y=5.0,
        step_x=1.0, step_y=1.0,
    ))
    assert scan_controller.start_scan(save_path=None) is True

    received = []
    scan_controller.scan_cancelled.connect(lambda: received.append(True))

    assert scan_controller.cancel_scan() is True

    deadline = time.monotonic() + 5.0
    while not received and time.monotonic() < deadline:
        qapp.processEvents()

    assert received, "scan_cancelled was never emitted"
    assert scan_controller.is_scanning is False
    assert scan_controller._scan_thread is None
