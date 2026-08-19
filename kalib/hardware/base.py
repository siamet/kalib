"""Base hardware interface for Kalib devices.

Provides abstract base class and common functionality for all hardware devices.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any
from kalib.utils.logger import get_logger


class ConnectionState(Enum):
    """Hardware connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class HardwareError(Exception):
    """Base exception for hardware-related errors."""
    pass


class ConnectionError(HardwareError):
    """Device connection failed."""
    pass


class CommandError(HardwareError):
    """Command execution failed."""
    pass


class ConfigurationError(HardwareError):
    """Device configuration invalid or failed."""
    pass


class TimeoutError(HardwareError):
    """Operation timed out."""
    pass


class HardwareDevice(ABC):
    """Abstract base class for hardware devices.

    Provides common functionality for device lifecycle management,
    error handling, and state tracking.
    """

    def __init__(self, device_id: Optional[str] = None, name: Optional[str] = None):
        """Initialize hardware device.

        Args:
            device_id: Unique device identifier (serial number, etc.)
            name: Human-readable device name
        """
        self._device_id = device_id
        self._name = name or self.__class__.__name__
        self._state = ConnectionState.DISCONNECTED
        self._logger = get_logger(f"{__name__}.{self._name}")
        self._device_info: Dict[str, Any] = {}

    @property
    def device_id(self) -> Optional[str]:
        """Get device ID."""
        return self._device_id

    @property
    def name(self) -> str:
        """Get device name."""
        return self._name

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def device_info(self) -> Dict[str, Any]:
        """Get device information."""
        return self._device_info.copy()

    @abstractmethod
    def _do_connect(self) -> None:
        """Perform device-specific connection.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def _do_disconnect(self) -> None:
        """Perform device-specific disconnection."""
        pass

    @abstractmethod
    def _do_initialize(self) -> None:
        """Perform device-specific initialization after connection.

        Raises:
            ConfigurationError: If initialization fails
        """
        pass

    def connect(self) -> None:
        """Connect to device.

        Raises:
            ConnectionError: If already connected or connection fails
        """
        if self._state == ConnectionState.CONNECTED:
            raise ConnectionError(f"{self._name} is already connected")

        self._logger.info(f"Connecting to {self._name} (ID: {self._device_id})")
        self._state = ConnectionState.CONNECTING

        try:
            self._do_connect()
            self._do_initialize()
            self._state = ConnectionState.CONNECTED
            self._logger.info(f"{self._name} connected successfully")

        except Exception as e:
            self._state = ConnectionState.ERROR
            self._logger.error(f"Failed to connect to {self._name}: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from device."""
        if self._state == ConnectionState.DISCONNECTED:
            self._logger.warning(f"{self._name} is already disconnected")
            return

        self._logger.info(f"Disconnecting from {self._name}")

        try:
            self._do_disconnect()
            self._state = ConnectionState.DISCONNECTED
            self._logger.info(f"{self._name} disconnected successfully")

        except Exception as e:
            self._state = ConnectionState.ERROR
            self._logger.error(f"Error during disconnect: {e}")
            raise HardwareError(f"Disconnect failed: {e}") from e

    def reconnect(self) -> None:
        """Reconnect to device.

        Raises:
            ConnectionError: If reconnection fails
        """
        self._logger.info(f"Reconnecting to {self._name}")

        if self._state == ConnectionState.CONNECTED:
            self.disconnect()

        self.connect()

    def _check_connected(self) -> None:
        """Check if device is connected and raise error if not.

        Raises:
            ConnectionError: If device is not connected
        """
        if not self.is_connected:
            raise ConnectionError(
                f"{self._name} is not connected. Call connect() first."
            )

    def _execute_command(self, command_func, *args, **kwargs) -> Any:
        """Execute a command with error handling.

        Args:
            command_func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of command function

        Raises:
            ConnectionError: If device not connected
            CommandError: If command execution fails
        """
        self._check_connected()

        try:
            return command_func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(command_func, '__name__', 'unknown')
            self._logger.error(
                f"Command failed on {self._name}: {func_name}: {e}"
            )
            raise CommandError(
                f"Command '{func_name}' failed: {e}"
            ) from e

    def cleanup(self) -> None:
        """Cleanup resources and disconnect.

        Safe to call even if not connected.
        """
        try:
            if self.is_connected:
                self.disconnect()
        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"{self.__class__.__name__}(name='{self._name}', "
            f"device_id='{self._device_id}', state={self._state.value})"
        )
