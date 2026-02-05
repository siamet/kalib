"""Tests for hardware base classes."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from kalib.hardware.base import (
    HardwareDevice,
    ConnectionState,
    HardwareError,
    ConnectionError,
    CommandError,
    ConfigurationError
)


class MockHardwareDevice(HardwareDevice):
    """Mock hardware device for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_called = False
        self.disconnect_called = False
        self.initialize_called = False

    def _do_connect(self):
        self.connect_called = True

    def _do_disconnect(self):
        self.disconnect_called = True

    def _do_initialize(self):
        self.initialize_called = True


class TestHardwareDevice:
    """Test HardwareDevice base class."""

    def test_initialization(self):
        """Test device initialization."""
        device = MockHardwareDevice(device_id="TEST123", name="TestDevice")

        assert device.device_id == "TEST123"
        assert device.name == "TestDevice"
        assert device.state == ConnectionState.DISCONNECTED
        assert not device.is_connected

    def test_connect_success(self):
        """Test successful connection."""
        device = MockHardwareDevice(device_id="TEST123")

        device.connect()

        assert device.connect_called
        assert device.initialize_called
        assert device.state == ConnectionState.CONNECTED
        assert device.is_connected

    def test_connect_already_connected(self):
        """Test connecting when already connected raises error."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        with pytest.raises(ConnectionError, match="already connected"):
            device.connect()

    def test_connect_failure(self):
        """Test connection failure."""
        device = MockHardwareDevice(device_id="TEST123")

        # Make _do_connect raise an exception
        device._do_connect = Mock(side_effect=Exception("Connection failed"))

        with pytest.raises(ConnectionError, match="Connection failed"):
            device.connect()

        assert device.state == ConnectionState.ERROR

    def test_disconnect(self):
        """Test disconnection."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        device.disconnect()

        assert device.disconnect_called
        assert device.state == ConnectionState.DISCONNECTED

    def test_disconnect_when_not_connected(self):
        """Test disconnecting when not connected (should not raise)."""
        device = MockHardwareDevice(device_id="TEST123")

        # Should log warning but not raise
        device.disconnect()

    def test_reconnect(self):
        """Test reconnect."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        device.reconnect()

        assert device.is_connected

    def test_check_connected(self):
        """Test connection check."""
        device = MockHardwareDevice(device_id="TEST123")

        # Should raise when not connected
        with pytest.raises(ConnectionError, match="not connected"):
            device._check_connected()

        # Should not raise when connected
        device.connect()
        device._check_connected()  # Should not raise

    def test_execute_command(self):
        """Test command execution."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        # Test successful command
        mock_func = Mock(return_value="success")
        result = device._execute_command(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    def test_execute_command_failure(self):
        """Test command execution failure."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        mock_func = Mock(side_effect=Exception("Command failed"))

        with pytest.raises(CommandError, match="Command failed"):
            device._execute_command(mock_func)

    def test_execute_command_not_connected(self):
        """Test command execution when not connected."""
        device = MockHardwareDevice(device_id="TEST123")

        mock_func = Mock()

        with pytest.raises(ConnectionError, match="not connected"):
            device._execute_command(mock_func)

    def test_context_manager(self):
        """Test context manager usage."""
        device = MockHardwareDevice(device_id="TEST123")

        with device:
            assert device.is_connected

        assert not device.is_connected
        assert device.disconnect_called

    def test_cleanup(self):
        """Test cleanup method."""
        device = MockHardwareDevice(device_id="TEST123")
        device.connect()

        device.cleanup()

        assert device.disconnect_called
        assert not device.is_connected

    def test_cleanup_when_not_connected(self):
        """Test cleanup when not connected (should not raise)."""
        device = MockHardwareDevice(device_id="TEST123")

        device.cleanup()  # Should not raise

    def test_repr(self):
        """Test string representation."""
        device = MockHardwareDevice(device_id="TEST123", name="TestDevice")

        repr_str = repr(device)

        assert "TestDevice" in repr_str
        assert "TEST123" in repr_str
        assert "disconnected" in repr_str
