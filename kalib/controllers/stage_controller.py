"""Stage controller for managing XY and Z stage operations.

Coordinates stage hardware with stage model and provides
workflow management for positioning operations.
"""

from typing import Optional, Tuple
from PySide6.QtCore import QObject, Signal

from kalib.hardware import PIStageXY, PIStageZ, ConnectionError, CommandError, HardwareDevice
from kalib.models import StageModel, StageLimits
from kalib.utils.logger import get_logger


class StageController(QObject):
    """Stage controller.

    Manages XY and Z stage lifecycle, positioning, and movement coordination
    with Qt signal/slot integration.
    """

    # Qt Signals
    xy_connected = Signal()
    xy_disconnected = Signal()
    z_connected = Signal()
    z_disconnected = Signal()
    position_changed = Signal(float, float, float)  # x, y, z
    movement_started = Signal()
    movement_completed = Signal()
    error_occurred = Signal(str)

    def __init__(self,
                 xy_device_id: Optional[str] = None,
                 z_device_id: Optional[str] = None,
                 limits: Optional[StageLimits] = None,
                 xy_device: Optional[HardwareDevice] = None,
                 z_device: Optional[HardwareDevice] = None):
        """Initialize stage controller.

        Args:
            xy_device_id: XY stage device ID
            z_device_id: Z stage device ID
            limits: Stage movement limits
            xy_device: Pre-built XY stage to use instead of a PIStageXY
            z_device: Pre-built Z stage to use instead of a PIStageZ
        """
        super().__init__()

        self._logger = get_logger(__name__)

        # Models and hardware
        self.model = StageModel(limits or StageLimits())
        self._xy_stage: Optional[HardwareDevice] = None
        self._z_stage: Optional[HardwareDevice] = None

        # Device IDs
        self._xy_device_id = xy_device_id
        self._z_device_id = z_device_id

        # Injected devices (used in place of constructing PIStageXY/PIStageZ)
        self._injected_xy = xy_device
        self._injected_z = z_device

    def connect_xy_stage(self, device_id: Optional[str] = None) -> bool:
        """Connect to XY stage.

        Args:
            device_id: Device ID (None to use configured ID)

        Returns:
            True if connection successful

        Emits:
            xy_connected: On successful connection
            error_occurred: On connection failure
        """
        device_id = device_id or self._xy_device_id
        if device_id is None and self._injected_xy is None:
            self.error_occurred.emit("No XY stage device ID configured")
            return False

        try:
            self._logger.info(f"Connecting to XY stage: {device_id}")

            # Create stage instance
            if self._injected_xy is not None:
                self._xy_stage = self._injected_xy
            else:
                self._xy_stage = PIStageXY(
                    device_id=device_id,
                    x_range=(self.model.limits.x_min, self.model.limits.x_max),
                    y_range=(self.model.limits.y_min, self.model.limits.y_max)
                )

            # Connect
            self._xy_stage.connect()

            # Update model
            self.model.set_xy_connected(True)

            # Read initial position
            x, y = self._xy_stage.get_position()
            self.model.update_position(x=x, y=y)

            self._logger.info(f"XY stage connected at position: ({x}, {y})")
            self.xy_connected.emit()
            self._emit_position()
            return True

        except ConnectionError as e:
            error_msg = f"XY stage connection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def disconnect_xy_stage(self) -> bool:
        """Disconnect from XY stage.

        Returns:
            True if disconnection successful

        Emits:
            xy_disconnected: On successful disconnection
        """
        try:
            if self._xy_stage is None:
                return True

            self._logger.info("Disconnecting XY stage")

            # Disconnect
            self._xy_stage.disconnect()
            self._xy_stage = None

            # Update model
            self.model.set_xy_connected(False)

            self._logger.info("XY stage disconnected")
            self.xy_disconnected.emit()
            return True

        except Exception as e:
            error_msg = f"XY stage disconnection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def connect_z_stage(self, device_id: Optional[str] = None) -> bool:
        """Connect to Z stage.

        Args:
            device_id: Device ID (None to use configured ID)

        Returns:
            True if connection successful

        Emits:
            z_connected: On successful connection
            error_occurred: On connection failure
        """
        device_id = device_id or self._z_device_id
        if device_id is None and self._injected_z is None:
            self.error_occurred.emit("No Z stage device ID configured")
            return False

        try:
            self._logger.info(f"Connecting to Z stage: {device_id}")

            # Create stage instance
            if self._injected_z is not None:
                self._z_stage = self._injected_z
            else:
                self._z_stage = PIStageZ(
                    device_id=device_id,
                    z_range=(self.model.limits.z_min, self.model.limits.z_max)
                )

            # Connect
            self._z_stage.connect()

            # Update model
            self.model.set_z_connected(True)

            # Read initial position
            z = self._z_stage.get_position()
            self.model.update_position(z=z)

            self._logger.info(f"Z stage connected at position: {z}")
            self.z_connected.emit()
            self._emit_position()
            return True

        except ConnectionError as e:
            error_msg = f"Z stage connection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def disconnect_z_stage(self) -> bool:
        """Disconnect from Z stage.

        Returns:
            True if disconnection successful

        Emits:
            z_disconnected: On successful disconnection
        """
        try:
            if self._z_stage is None:
                return True

            self._logger.info("Disconnecting Z stage")

            # Disconnect
            self._z_stage.disconnect()
            self._z_stage = None

            # Update model
            self.model.set_z_connected(False)

            self._logger.info("Z stage disconnected")
            self.z_disconnected.emit()
            return True

        except Exception as e:
            error_msg = f"Z stage disconnection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def _require_within_limits(self, x: Optional[float] = None,
                               y: Optional[float] = None,
                               z: Optional[float] = None) -> None:
        """Reject a target outside the configured travel.

        The hardware layer clamps out-of-range targets and logs a warning, so
        a caller that trusts its own commanded positions gets a stack whose
        axis is silently wrong at the ends. Fail before moving instead, and
        leave the stage where it was.

        Args:
            x: Target X in um, or None to keep the current value
            y: Target Y in um, or None to keep the current value
            z: Target Z in um, or None to keep the current value

        Raises:
            CommandError: If any supplied axis lies outside its travel
        """
        limits = self.model.limits
        for axis, value, low, high in (
            ("x", x, limits.x_min, limits.x_max),
            ("y", y, limits.y_min, limits.y_max),
            ("z", z, limits.z_min, limits.z_max),
        ):
            if value is not None and not low <= value <= high:
                raise CommandError(
                    f"{axis}={value} um is outside the stage travel "
                    f"[{low}, {high}] um"
                )

    def move_absolute(self, x: Optional[float] = None,
                     y: Optional[float] = None,
                     z: Optional[float] = None,
                     wait: bool = True) -> bool:
        """Move to absolute position.

        Args:
            x: Target X position (None to keep current)
            y: Target Y position (None to keep current)
            z: Target Z position (None to keep current)
            wait: Wait for movement to complete

        Returns:
            True if movement successful; emits movement_started,
            position_changed and (if wait) movement_completed on success,
            or error_occurred on failure (e.g. the targeted stage isn't
            connected).
        """
        try:
            self._require_within_limits(x=x, y=y, z=z)
            self.movement_started.emit()

            # Move XY if specified
            if x is not None or y is not None:
                if self._xy_stage is None:
                    raise CommandError("XY stage not connected")
                current_x, current_y = self._xy_stage.get_position()
                target_x = x if x is not None else current_x
                target_y = y if y is not None else current_y
                self._xy_stage.move_absolute(x=target_x, y=target_y, wait=wait)
                self.model.update_position(x=target_x, y=target_y)

            # Move Z if specified
            if z is not None:
                if self._z_stage is None:
                    raise CommandError("Z stage not connected")
                self._z_stage.move_absolute(z, wait=wait)
                self.model.update_position(z=z)

            self._emit_position()
            if wait:
                self.movement_completed.emit()
            return True

        except CommandError as e:
            error_msg = f"Movement failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def move_relative(self, dx: float = 0.0,
                     dy: float = 0.0,
                     dz: float = 0.0,
                     wait: bool = True) -> bool:
        """Move relative to current position.

        Args:
            dx: Relative X movement
            dy: Relative Y movement
            dz: Relative Z movement
            wait: Wait for movement to complete

        Returns:
            True if movement successful; emits movement_started,
            position_changed and (if wait) movement_completed on success,
            or error_occurred on failure (e.g. the targeted stage isn't
            connected).
        """
        try:
            current = self.model.get_position()
            self._require_within_limits(
                x=current.x + dx if dx else None,
                y=current.y + dy if dy else None,
                z=current.z + dz if dz else None,
            )
            self.movement_started.emit()

            # Move XY if specified
            if dx != 0.0 or dy != 0.0:
                if self._xy_stage is None:
                    raise CommandError("XY stage not connected")
                self._xy_stage.move_relative(dx=dx, dy=dy, wait=wait)
                x, y = self._xy_stage.get_position()
                self.model.update_position(x=x, y=y)

            # Move Z if specified
            if dz != 0.0:
                if self._z_stage is None:
                    raise CommandError("Z stage not connected")
                self._z_stage.move_relative(dz=dz, wait=wait)
                z = self._z_stage.get_position()
                self.model.update_position(z=z)

            self._emit_position()

            if wait:
                self.movement_completed.emit()

            return True

        except CommandError as e:
            error_msg = f"Relative movement failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def get_position(self) -> Tuple[float, float, float]:
        """Get current position.

        Returns:
            Tuple of (x, y, z) positions
        """
        # Update from hardware if connected
        try:
            if self._xy_stage is not None:
                x, y = self._xy_stage.get_position()
                self.model.update_position(x=x, y=y)

            if self._z_stage is not None:
                z = self._z_stage.get_position()
                self.model.update_position(z=z)

        except Exception as e:
            self._logger.warning(f"Failed to update position from hardware: {e}")

        return self.model.get_position_tuple()

    def stop_movement(self) -> bool:
        """Stop all stage movement.

        Returns:
            True if stop successful

        Emits:
            error_occurred: On failure
        """
        try:
            if self._xy_stage is not None:
                self._xy_stage.stop()

            if self._z_stage is not None:
                self._z_stage.stop()

            self._logger.info("Stage movement stopped")
            return True

        except CommandError as e:
            error_msg = f"Failed to stop stage: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def _emit_position(self) -> None:
        """Emit current position signal."""
        x, y, z = self.model.get_position_tuple()
        self.position_changed.emit(x, y, z)

    @property
    def is_xy_connected(self) -> bool:
        """Check if XY stage is connected."""
        return self.model._xy_connected

    @property
    def is_z_connected(self) -> bool:
        """Check if Z stage is connected."""
        return self.model._z_connected

    @property
    def is_connected(self) -> bool:
        """Check if any stage is connected."""
        return self.model.is_connected

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.disconnect_xy_stage()
        self.disconnect_z_stage()
