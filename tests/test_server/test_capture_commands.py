"""Tests for the snap and preview commands."""

import base64
import json
from pathlib import Path

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import PREVIEW_MAX_BYTES, CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry over connected, acquiring simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=None)


def test_snap_writes_a_file_and_returns_its_path(registry, tmp_path):
    """snap saves to disk rather than returning pixels."""
    target = tmp_path / "shot.tiff"
    result = registry.dispatch("snap", {"path": str(target)})
    assert Path(result["path"]).exists()
    assert result["width"] > 0 and result["height"] > 0


def test_snap_writes_a_metadata_sidecar(registry, tmp_path):
    """Each capture gets a JSON sidecar carrying acquisition context."""
    target = tmp_path / "shot.tiff"
    registry.dispatch("snap", {"path": str(target)})
    sidecar = target.with_suffix(".json")
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text())
    assert set(meta) >= {"position", "sharpness", "timestamp", "width", "height"}


def test_snap_records_the_position_it_was_taken_at(registry, tmp_path):
    """The sidecar's position matches where the stage actually was."""
    registry.dispatch("move_xy", {"x": 11.0, "y": 22.0})
    target = tmp_path / "shot.tiff"
    result = registry.dispatch("snap", {"path": str(target)})
    assert result["position"]["x"] == pytest.approx(11.0)
    assert result["position"]["y"] == pytest.approx(22.0)


def test_snap_response_carries_no_pixel_data(registry, tmp_path):
    """A 36 MB frame must never travel on the command channel."""
    result = registry.dispatch("snap", {"path": str(tmp_path / "s.tiff")})
    assert len(json.dumps(result)) < 2000


def test_preview_returns_base64_jpeg_within_the_cap(registry):
    """preview returns pixels, downscaled and size-capped."""
    result = registry.dispatch("preview", {"max_px": 256})
    raw = base64.b64decode(result["jpeg_base64"])
    assert raw[:2] == b"\xff\xd8"          # JPEG SOI marker
    assert result["bytes"] == len(raw)
    assert len(raw) <= PREVIEW_MAX_BYTES


def test_preview_downscales_to_the_requested_size(registry):
    """The long edge is reduced to max_px."""
    result = registry.dispatch("preview", {"max_px": 128})
    assert max(result["width"], result["height"]) <= 128


def test_preview_reports_sharpness(registry):
    """preview carries a focus metric so focusing needs no eyes."""
    result = registry.dispatch("preview", {})
    assert isinstance(result["sharpness"], float)


def test_capture_without_acquisition_fails_cleanly(tmp_path):
    """Capturing before start_acquisition is a CommandError, not a crash."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    with pytest.raises(CommandError):
        registry.dispatch("snap", {"path": str(tmp_path / "x.tiff")})
