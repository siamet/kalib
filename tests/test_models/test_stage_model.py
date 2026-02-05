"""Tests for stage model."""

import pytest
import numpy as np

from kalib.models import StageModel, Position3D, StageLimits


class TestStageLimits:
    """Test StageLimits class."""

    def test_is_within_limits(self):
        """Test limit checking."""
        limits = StageLimits(x_min=0, x_max=100, y_min=0, y_max=100, z_min=0, z_max=10)

        assert limits.is_within_limits(50, 50, 5) == True
        assert limits.is_within_limits(-1, 50, 5) == False
        assert limits.is_within_limits(50, 101, 5) == False
        assert limits.is_within_limits(50, 50, 15) == False

    def test_clamp(self):
        """Test position clamping."""
        limits = StageLimits(x_min=0, x_max=100, y_min=0, y_max=100, z_min=0, z_max=10)

        x, y, z = limits.clamp(50, 50, 5)
        assert (x, y, z) == (50, 50, 5)

        x, y, z = limits.clamp(-10, 150, 20)
        assert (x, y, z) == (0, 100, 10)


class TestStageModel:
    """Test StageModel class."""

    def test_initialization(self):
        """Test model initialization."""
        model = StageModel()

        assert model.is_connected == False
        x, y, z = model.get_position_tuple()
        assert (x, y, z) == (0.0, 0.0, 0.0)

    def test_connection_states(self):
        """Test connection state management."""
        model = StageModel()

        model.set_xy_connected(True)
        assert model.is_connected == True
        assert model.is_fully_connected == False

        model.set_z_connected(True)
        assert model.is_fully_connected == True

    def test_update_position(self):
        """Test position updates."""
        model = StageModel()

        model.update_position(x=10.0, y=20.0, z=5.0)

        x, y, z = model.get_position_tuple()
        assert (x, y, z) == (10.0, 20.0, 5.0)

        # Partial update
        model.update_position(z=7.0)
        x, y, z = model.get_position_tuple()
        assert (x, y, z) == (10.0, 20.0, 7.0)

    def test_position_history(self):
        """Test position history tracking."""
        model = StageModel()

        model.update_position(x=1.0, y=1.0, z=1.0)
        model.update_position(x=2.0, y=2.0, z=2.0)
        model.update_position(x=3.0, y=3.0, z=3.0)

        history = model.get_position_history()
        assert len(history) == 3

        history_array = model.get_position_history_array()
        assert history_array.shape == (3, 3)
        assert np.array_equal(history_array[-1], [3.0, 3.0, 3.0])

    def test_target_position(self):
        """Test target position management."""
        model = StageModel()

        assert model.get_target_position() is None
        assert model.is_moving == False

        model.set_target_position(10.0, 20.0, 5.0)

        assert model.is_moving == True
        target = model.get_target_position()
        assert target.x == 10.0

        model.clear_target_position()
        assert model.is_moving == False

    def test_validate_and_clamp(self):
        """Test position validation."""
        limits = StageLimits(x_min=0, x_max=100, y_min=0, y_max=100, z_min=0, z_max=10)
        model = StageModel(limits=limits)

        x, y, z = model.validate_and_clamp(50, 50, 5)
        assert (x, y, z) == (50, 50, 5)

        x, y, z = model.validate_and_clamp(-10, 150, 20)
        assert (x, y, z) == (0, 100, 10)

    def test_export_import_history_csv(self, tmp_path):
        """Test CSV export/import."""
        model = StageModel()

        model.update_position(x=1.0, y=2.0, z=3.0)
        model.update_position(x=4.0, y=5.0, z=6.0)

        filepath = tmp_path / "history.csv"
        model.export_history_csv(str(filepath))

        assert filepath.exists()

        # Import
        new_model = StageModel()
        new_model.import_history_csv(str(filepath))

        assert len(new_model.get_position_history()) == 2
