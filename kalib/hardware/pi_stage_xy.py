"""PI E-725 XY Stage driver with hardware abstraction.

Provides high-level interface to Physik Instrumente E-725 XY motion stage
with position tracking, validation, and error handling.
"""

from typing import Optional, Tuple, List, Dict
import time

try:
    from pipython import GCSDevice, pitools
    PI_AVAILABLE = True
except ImportError:
    PI_AVAILABLE = False
    GCSDevice = None
    pitools = None

from kalib.hardware.base import (
    HardwareDevice,
    ConnectionError,
    CommandError,
    ConfigurationError,
    TimeoutError
)


class PIStageXY(HardwareDevice):
    """PI E-725 XY Stage driver.

    Provides position control for XY motion stage with position tracking,
    soft limits, and movement validation.

    Example:
        stage = PIStageXY(device_id='113068710')
        stage.connect()
        stage.move_absolute(10.0, 20.0)
        x, y = stage.get_position()
        stage.disconnect()

    Or with context manager:
        with PIStageXY(device_id='113068710') as stage:
            stage.move_absolute(10.0, 20.0)
    """

    def __init__(
        self,
        device_id: str,
        x_range: Tuple[float, float] = (0.0, 100.0),
        y_range: Tuple[float, float] = (0.0, 100.0),
        velocity: float = 10.0,
        name: Optional[str] = None
    ):
        """Initialize PI XY stage.

        Args:
            device_id: USB device serial number
            x_range: X-axis range (min, max) in mm
            y_range: Y-axis range (min, max) in mm
            velocity: Default velocity in mm/s
            name: Custom name for the stage
        """
        if not PI_AVAILABLE:
            raise ImportError(
                "pipython not available. Install with: pip install pipython"
            )

        super().__init__(device_id=device_id, name=name or "PI_E725_XY")

        self._gcs_device = None
        self._axes: List[str] = []
        self._x_range = x_range
        self._y_range = y_range
        self._velocity = velocity
        self._position: Optional[Dict[str, float]] = None

    def _do_connect(self) -> None:
        """Connect to PI XY stage.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Create GCS device
            self._gcs_device = GCSDevice('E-725')
            self._logger.debug(f"Created GCS device controller for E-725")

            # Connect via USB
            self._gcs_device.ConnectUSB(self._device_id)
            self._logger.info(f"Connected to PI stage via USB: {self._device_id}")

            # Get device info
            try:
                idn = self._gcs_device.qIDN()
                self._device_info = {
                    'model': 'E-725',
                    'serial': self._device_id,
                    'idn': idn.strip() if idn else 'N/A'
                }
                self._logger.info(f"Device ID: {idn}")
            except Exception as e:
                self._logger.warning(f"Could not query device info: {e}")

        except Exception as e:
            self._logger.error(f"Failed to connect to PI stage: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e

    def _do_initialize(self) -> None:
        """Initialize stage after connection.

        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            # Get available axes
            self._axes = self._gcs_device.axes
            self._logger.info(f"Available axes: {self._axes}")

            if len(self._axes) < 2:
                raise ConfigurationError(
                    f"Expected at least 2 axes, found {len(self._axes)}"
                )

            # Enable servo for X and Y axes (axes[0] and axes[1])
            # Third axis (Z) is disabled with 0
            self._gcs_device.SVO(self._axes, [1, 1, 0])
            self._logger.debug("Servo enabled for X and Y axes")

            # Set velocity if supported
            try:
                self._gcs_device.VEL(self._axes[0], self._velocity)
                self._gcs_device.VEL(self._axes[1], self._velocity)
                self._logger.debug(f"Velocity set to {self._velocity} mm/s")
            except Exception as e:
                self._logger.warning(f"Could not set velocity: {e}")

            # Read initial position
            self._update_position()

            self._logger.info("PI XY stage initialized successfully")

        except Exception as e:
            self._logger.error(f"Initialization failed: {e}")
            raise ConfigurationError(f"Initialization failed: {e}") from e

    def _do_disconnect(self) -> None:
        """Disconnect from PI stage."""
        try:
            if self._gcs_device is not None:
                # Disable servo
                try:
                    self._gcs_device.SVO(self._axes, [0, 0, 0])
                    self._logger.debug("Servo disabled")
                except Exception as e:
                    self._logger.warning(f"Could not disable servo: {e}")

                # Close connection
                self._gcs_device.CloseConnection()
                self._logger.info("PI XY stage disconnected")

            self._gcs_device = None
            self._axes = []
            self._position = None

        except Exception as e:
            self._logger.error(f"Error during disconnect: {e}")
            raise

    def _update_position(self) -> None:
        """Update current position from hardware."""
        if self._gcs_device is not None and len(self._axes) >= 2:
            try:
                # Query positions for axes 1, 2, 3
                pos = self._gcs_device.qPOS([1, 2, 3])
                self._position = {
                    'x': pos[1],
                    'y': pos[2]
                }
            except Exception as e:
                self._logger.warning(f"Could not update position: {e}")

    def _validate_position(self, x: float, y: float) -> Tuple[float, float]:
        """Validate and clamp position to limits.

        Args:
            x: X position in mm
            y: Y position in mm

        Returns:
            Tuple of validated (x, y) positions

        Raises:
            ValueError: If position is outside valid range
        """
        x_min, x_max = self._x_range
        y_min, y_max = self._y_range

        # Clamp values
        x_clamped = max(x_min, min(x_max, x))
        y_clamped = max(y_min, min(y_max, y))

        # Warn if clamping occurred
        if x != x_clamped or y != y_clamped:
            self._logger.warning(
                f"Position ({x}, {y}) clamped to ({x_clamped}, {y_clamped}). "
                f"Valid range: X=[{x_min}, {x_max}], Y=[{y_min}, {y_max}]"
            )

        return x_clamped, y_clamped

    def move_absolute(self, x: Optional[float] = None, y: Optional[float] = None,
                     wait: bool = True, timeout: float = 30.0) -> None:
        """Move to absolute position.

        Args:
            x: Target X position in mm (None to keep current)
            y: Target Y position in mm (None to keep current)
            wait: Wait for movement to complete
            timeout: Timeout in seconds for movement

        Raises:
            CommandError: If movement fails
            TimeoutError: If movement times out
        """
        self._check_connected()

        # Get current position if needed
        current = self.get_position()

        target_x = x if x is not None else current[0]
        target_y = y if y is not None else current[1]

        # Validate position
        target_x, target_y = self._validate_position(target_x, target_y)

        try:
            # Move X axis
            if x is not None:
                self._gcs_device.MOV(self._axes[0], target_x)
                self._logger.debug(f"Moving X to {target_x} mm")

            # Move Y axis
            if y is not None:
                self._gcs_device.MOV(self._axes[1], target_y)
                self._logger.debug(f"Moving Y to {target_y} mm")

            # Wait for movement to complete
            if wait:
                start_time = time.time()
                while not self.is_on_target():
                    if time.time() - start_time > timeout:
                        raise TimeoutError(
                            f"Movement timeout after {timeout}s"
                        )
                    time.sleep(0.01)

            # Update position
            self._update_position()
            self._logger.info(f"Moved to position: X={target_x}, Y={target_y}")

        except TimeoutError:
            raise
        except Exception as e:
            self._logger.error(f"Movement failed: {e}")
            raise CommandError(f"Movement failed: {e}") from e

    def move_relative(self, dx: float = 0.0, dy: float = 0.0,
                     wait: bool = True, timeout: float = 30.0) -> None:
        """Move relative to current position.

        Args:
            dx: Relative X movement in mm
            dy: Relative Y movement in mm
            wait: Wait for movement to complete
            timeout: Timeout in seconds

        Raises:
            CommandError: If movement fails
        """
        current_x, current_y = self.get_position()
        target_x = current_x + dx
        target_y = current_y + dy

        self.move_absolute(target_x, target_y, wait=wait, timeout=timeout)

    def get_position(self) -> Tuple[float, float]:
        """Get current XY position.

        Returns:
            Tuple of (x, y) position in mm

        Raises:
            CommandError: If position query fails
        """
        self._check_connected()

        try:
            pos = self._gcs_device.qPOS([1, 2, 3])
            x = pos[1]
            y = pos[2]
            self._position = {'x': x, 'y': y}
            return x, y

        except Exception as e:
            self._logger.error(f"Failed to get position: {e}")
            raise CommandError(f"Position query failed: {e}") from e

    def is_on_target(self) -> bool:
        """Check if stage has reached target position.

        Returns:
            True if on target, False otherwise
        """
        self._check_connected()

        try:
            # Query on-target status for both axes
            on_target = self._gcs_device.qONT([1, 2])
            return on_target[1] and on_target[2]

        except Exception as e:
            self._logger.warning(f"Could not check on-target status: {e}")
            return False

    def stop(self) -> None:
        """Stop all motion immediately.

        Raises:
            CommandError: If stop fails
        """
        self._check_connected()

        try:
            self._gcs_device.STP()
            self._logger.info("Stage motion stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop stage: {e}")
            raise CommandError(f"Stop failed: {e}") from e

    def set_velocity(self, velocity: float) -> None:
        """Set movement velocity.

        Args:
            velocity: Velocity in mm/s

        Raises:
            CommandError: If setting fails
        """
        self._check_connected()

        try:
            self._gcs_device.VEL(self._axes[0], velocity)
            self._gcs_device.VEL(self._axes[1], velocity)
            self._velocity = velocity
            self._logger.debug(f"Velocity set to {velocity} mm/s")

        except Exception as e:
            self._logger.error(f"Failed to set velocity: {e}")
            raise CommandError(f"Velocity setting failed: {e}") from e

    def get_velocity(self) -> Tuple[float, float]:
        """Get current velocity settings.

        Returns:
            Tuple of (vx, vy) velocities in mm/s

        Raises:
            CommandError: If query fails
        """
        self._check_connected()

        try:
            vx = self._gcs_device.qVEL(self._axes[0])[self._axes[0]]
            vy = self._gcs_device.qVEL(self._axes[1])[self._axes[1]]
            return vx, vy

        except Exception as e:
            self._logger.error(f"Failed to get velocity: {e}")
            raise CommandError(f"Velocity query failed: {e}") from e

    @property
    def x_range(self) -> Tuple[float, float]:
        """Get X-axis range limits."""
        return self._x_range

    @property
    def y_range(self) -> Tuple[float, float]:
        """Get Y-axis range limits."""
        return self._y_range

    @property
    def axes(self) -> List[str]:
        """Get list of available axes."""
        return self._axes.copy()
