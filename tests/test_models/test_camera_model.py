"""Tests for camera model."""

import pytest
import numpy as np
from datetime import datetime

from kalib.models import CameraModel, CameraSettings, CameraState


class TestCameraModel:
    """Test CameraModel class."""

    def test_initialization(self):
        """Test model initialization."""
        model = CameraModel()

        assert model.settings.exposure_time == 15000.0
        assert model.settings.gain == 1.0
        assert model.state.is_connected == False
        assert model.state.frame_count == 0

    def test_update_settings(self):
        """Test settings update."""
        model = CameraModel()

        model.update_settings(exposure_time=20000.0, gain=2.0)

        assert model.settings.exposure_time == 20000.0
        assert model.settings.gain == 2.0

    def test_set_connected(self):
        """Test connection state."""
        model = CameraModel()

        model.set_connected(True)
        assert model.state.is_connected == True

        model.set_connected(False)
        assert model.state.is_connected == False
        assert model.state.is_acquiring == False

    def test_add_image(self):
        """Test adding image."""
        model = CameraModel()

        image = np.zeros((480, 640, 3), dtype=np.uint8)
        model.add_image(image)

        assert model.state.frame_count == 1
        assert model.get_current_image() is not None
        assert model.state.last_capture_time is not None

    def test_image_buffer(self):
        """Test image buffer management."""
        model = CameraModel()
        model._max_buffer_size = 3

        # Add 5 images
        for i in range(5):
            image = np.ones((10, 10), dtype=np.uint8) * i
            model.add_image(image)

        # Buffer should only keep last 3
        buffer = model.get_image_buffer()
        assert len(buffer) == 3

    def test_clear_buffer(self):
        """Test buffer clearing."""
        model = CameraModel()

        image = np.zeros((10, 10), dtype=np.uint8)
        model.add_image(image)

        model.clear_buffer()

        assert len(model.get_image_buffer()) == 0

    def test_is_ready(self):
        """Test ready state."""
        model = CameraModel()

        assert model.is_ready == False

        model.set_connected(True)
        model.set_acquiring(True)

        assert model.is_ready == True

    def test_to_dict(self):
        """Test dictionary conversion."""
        model = CameraModel()
        model.set_resolution(640, 480)

        data = model.to_dict()

        assert 'settings' in data
        assert 'state' in data
        assert data['state']['resolution'] == (640, 480)
