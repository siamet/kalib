"""Pytest configuration and shared fixtures."""

import pytest
import sys
from pathlib import Path

# Add kalib directory to path for imports
kalib_root = Path(__file__).parent.parent
sys.path.insert(0, str(kalib_root))


@pytest.fixture
def mock_hardware():
    """Fixture to mock hardware devices for testing."""
    # Will be expanded as hardware classes are created
    pass


@pytest.fixture
def test_config():
    """Fixture to provide test configuration."""
    return {
        'camera': {
            'exposure_time_min': 100,
            'exposure_time_max': 100000,
            'default_exposure': 15000,
        },
        'stages': {
            'xy': {
                'device_id': 'TEST_XY',
                'x_range': [0, 100],
                'y_range': [0, 100],
            },
            'z': {
                'device_id': 'TEST_Z',
                'z_range': [0, 10],
            }
        }
    }
