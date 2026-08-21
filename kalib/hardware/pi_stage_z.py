"""PI E-816.DB Z Stage driver with hardware abstraction.

Provides high-level interface to Physik Instrumente E-816.DB Z motion stage
for focus control with position tracking and error handling.
"""

from typing import Optional, Tuple
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


class PIStageZ(HardwareDevice):
    """PI E-816.DB Z Stage driver.

    Provides position control for Z-axis motion stage (focus control)
    with position tracking, soft limits, and movement validation.

    Example:
        stage = PIStageZ(device_id='112064239')
        stage.connect()
        stage.move_absolute(5.0)
        z = stage.get_position()
        stage.disconnect()

    Or with context manager:
        with PIStageZ(device_id='112064239') as stage:
            stage.move_absolute(5.0)
    """

    def __init__(
        self,
        device_id: str,
        z_range: Tuple[float, float] = (0.0, 10.0),
        velocity: float = 1.0,
        axis: str = 'A',
        name: Optional[str] = None
    ):
        """Initialize PI Z stage.

        Args:
            device_id: USB device serial number
            z_range: Z-axis range (min, max) in um
            velocity: Default velocity in um/s
            axis: Axis identifier (default: 'A')
            name: Custom name for the stage
        """
        if not PI_AVAILABLE:
            raise ImportError(
                "pipython not available. Install with: pip install pipython"
            )

        super().__init__(device_id=device_id, name=name or "PI_E816_Z")

        self._gcs_device = None
        self._axis = axis
        self._z_range = z_range
        self._velocity = velocity
        self._position: Optional[float] = None

    def _do_connect(self) -> None:
        """Connect to PI Z stage.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Create GCS device
            self._gcs_device = GCSDevice('E-816.DB')
            self._logger.debug(f"Created GCS device controller for E-816.DB")

            # Connect via USB
            self._gcs_device.ConnectUSB(self._device_id)
            self._logger.info(f"Connected to PI Z stage via USB: {self._device_id}")

            # Get device info
            try:
                idn = self._gcs_device.qIDN()
                self._device_info = {
                    'model': 'E-816.DB',
                    'serial': self._device_id,
                    'idn': idn.strip() if idn else 'N/A'
                }
                self._logger.info(f"Device ID: {idn}")
            except Exception as e:
                self._logger.warning(f"Could not query device info: {e}")

        except Exception as e:
            self._logger.error(f"Failed to connect to PI Z stage: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e

    def _do_initialize(self) -> None:
        """Initialize stage after connection.

        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            # Initialize stage using pitools
            # stages=None uses default stage for this controller
            # refmodes=None uses default reference mode
            pitools.startup(self._gcs_device, stages=None, refmodes=None)
            self._logger.debug("PI Z stage startup completed")

            # Set velocity if supported
            try:
                self._gcs_device.VEL(self._axis, self._velocity)
                self._logger.debug(f"Velocity set to {self._velocity} um/s")
            except Exception as e:
                self._logger.warning(f"Could not set velocity: {e}")

            # Read initial position
            self._update_position()

            self._logger.info("PI Z stage initialized successfully")

        except Exception as e:
            self._logger.error(f"Initialization failed: {e}")
            raise ConfigurationError(f"Initialization failed: {e}") from e

    def _do_disconnect(self) -> None:
        """Disconnect from PI stage."""
        try:
            if self._gcs_device is not None:
                # Close connection
                self._gcs_device.CloseConnection()
                self._logger.info("PI Z stage disconnected")

            self._gcs_device = None
            self._position = None

        except Exception as e:
            self._logger.error(f"Error during disconnect: {e}")
            raise

    def _update_position(self) -> None:
        """Update current position from hardware."""
        if self._gcs_device is not None:
            try:
                pos = self._gcs_device.qPOS(self._axis)
                self._position = pos[self._axis]
            except Exception as e:
                self._logger.warning(f"Could not update position: {e}")

    def _validate_position(self, z: float) -> float:
        """Validate and clamp position to limits.

        Args:
            z: Z position in um

        Returns:
            The position clamped into range.

        Note:
            This clamps and warns; it does not raise. It is the last-resort
            guard, not the validation. StageController refuses an
            out-of-range target before it reaches this layer, so a clamp
            here means something bypassed the controller.
        """
        z_min, z_max = self._z_range

        # Clamp value
        z_clamped = max(z_min, min(z_max, z))

        # Warn if clamping occurred
        if z != z_clamped:
            self._logger.warning(
                f"Position {z} clamped to {z_clamped}. "
                f"Valid range: [{z_min}, {z_max}]"
            )

        return z_clamped

    def move_absolute(self, z: float, wait: bool = True,
                     timeout: float = 30.0) -> None:
        """Move to absolute Z position.

        Args:
            z: Target Z position in um
            wait: Wait for movement to complete
            timeout: Timeout in seconds for movement

        Raises:
            CommandError: If movement fails
            TimeoutError: If movement times out
        """
        self._check_connected()

        # Validate position
        z = self._validate_position(z)

        try:
            # Move Z axis
            self._gcs_device.MOV(self._axis, z)
            self._logger.debug(f"Moving Z to {z} um")

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
            self._logger.info(f"Moved to Z position: {z} um")

        except TimeoutError:
            raise
        except Exception as e:
            self._logger.error(f"Movement failed: {e}")
            raise CommandError(f"Movement failed: {e}") from e

    def move_relative(self, dz: float, wait: bool = True,
                     timeout: float = 30.0) -> None:
        """Move relative to current Z position.

        Args:
            dz: Relative Z movement in um
            wait: Wait for movement to complete
            timeout: Timeout in seconds

        Raises:
            CommandError: If movement fails
        """
        current_z = self.get_position()
        target_z = current_z + dz

        self.move_absolute(target_z, wait=wait, timeout=timeout)

    def get_position(self) -> float:
        """Get current Z position.

        Returns:
            Z position in um

        Raises:
            CommandError: If position query fails
        """
        self._check_connected()

        try:
            pos = self._gcs_device.qPOS(self._axis)
            z = pos[self._axis]
            self._position = z
            return z

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
            # Query on-target status
            on_target = self._gcs_device.qONT(self._axis)
            return on_target[self._axis]

        except Exception as e:
            self._logger.warning(f"Could not check on-target status: {e}")
            return False

    def stop(self) -> None:
        """Stop motion immediately.

        Raises:
            CommandError: If stop fails
        """
        self._check_connected()

        try:
            self._gcs_device.STP()
            self._logger.info("Z stage motion stopped")

        except Exception as e:
            self._logger.error(f"Failed to stop stage: {e}")
            raise CommandError(f"Stop failed: {e}") from e

    def set_velocity(self, velocity: float) -> None:
        """Set movement velocity.

        Args:
            velocity: Velocity in um/s

        Raises:
            CommandError: If setting fails
        """
        self._check_connected()

        try:
            self._gcs_device.VEL(self._axis, velocity)
            self._velocity = velocity
            self._logger.debug(f"Velocity set to {velocity} um/s")

        except Exception as e:
            self._logger.error(f"Failed to set velocity: {e}")
            raise CommandError(f"Velocity setting failed: {e}") from e

    def get_velocity(self) -> float:
        """Get current velocity setting.

        Returns:
            Velocity in um/s

        Raises:
            CommandError: If query fails
        """
        self._check_connected()

        try:
            vel = self._gcs_device.qVEL(self._axis)[self._axis]
            return vel

        except Exception as e:
            self._logger.error(f"Failed to get velocity: {e}")
            raise CommandError(f"Velocity query failed: {e}") from e

    def reference(self) -> None:
        """Perform reference move (homing).

        Raises:
            CommandError: If referencing fails
        """
        self._check_connected()

        try:
            self._logger.info("Starting reference move...")
            self._gcs_device.FRF(self._axis)

            # Wait for reference move to complete
            start_time = time.time()
            timeout = 60.0  # Reference can take longer

            while not self._gcs_device.qFRF(self._axis)[self._axis]:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Reference timeout after {timeout}s")
                time.sleep(0.1)

            self._update_position()
            self._logger.info("Reference move completed")

        except TimeoutError:
            raise
        except Exception as e:
            self._logger.error(f"Reference move failed: {e}")
            raise CommandError(f"Reference move failed: {e}") from e

    @property
    def z_range(self) -> Tuple[float, float]:
        """Get Z-axis range limits."""
        return self._z_range

    @property
    def axis(self) -> str:
        """Get axis identifier."""
        return self._axis

    @property
    def is_referenced(self) -> bool:
        """Check if stage is referenced.

        Returns:
            True if referenced, False otherwise
        """
        self._check_connected()

        try:
            return self._gcs_device.qFRF(self._axis)[self._axis]
        except Exception:
            return False
