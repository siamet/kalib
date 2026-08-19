"""Simulated XY and Z stages acting on a shared SimWorld."""

from typing import List, Optional, Tuple

from kalib.hardware.base import HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimStageXY(HardwareDevice):
    """XY stage simulator mirroring the public API of PIStageXY.

    Moves are instantaneous, so is_on_target is always True.

    Example:
        stage = SimStageXY(SimWorld())
        stage.connect()
        stage.move_absolute(x=10.0, y=20.0)
    """

    def __init__(self, world: SimWorld, device_id: Optional[str] = None,
                 name: Optional[str] = None,
                 x_range: Tuple[float, float] = (0.0, 100.0),
                 y_range: Tuple[float, float] = (0.0, 100.0)):
        """Initialize the simulated XY stage.

        Args:
            world: Shared simulated instrument state
            device_id: Present for parity with PIStageXY
            name: Human-readable device name
            x_range: Permitted X travel in mm
            y_range: Permitted Y travel in mm
        """
        super().__init__(device_id=device_id or "SIM-XY", name=name or "Sim_XY")
        self._world = world
        self._x_range = x_range
        self._y_range = y_range
        self._velocity = 10.0

    def _do_connect(self) -> None:
        """Connect to the simulated stage."""
        self._device_info = {'model': 'SimStageXY', 'serial': self._device_id}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated stage."""

    def _do_initialize(self) -> None:
        """Initialize the simulated stage."""

    def _validate_position(self, x: float, y: float) -> Tuple[float, float]:
        """Validate and clamp position to limits.

        Args:
            x: X position in mm
            y: Y position in mm

        Returns:
            Tuple of clamped (x, y) positions
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

    def move_absolute(self, x: Optional[float] = None,
                      y: Optional[float] = None, wait: bool = True,
                      timeout: float = 30.0) -> None:
        """Move to an absolute position.

        Args:
            x: Target X in mm; unchanged if None
            y: Target Y in mm; unchanged if None
            wait: Accepted for API parity; simulated moves are instant
            timeout: Accepted for API parity; simulated moves are instant
        """
        self._check_connected()

        # Get current position if needed
        current = self.get_position()

        target_x = x if x is not None else current[0]
        target_y = y if y is not None else current[1]

        # Validate and clamp position
        target_x, target_y = self._validate_position(target_x, target_y)

        self._world.x = float(target_x)
        self._world.y = float(target_y)

    def move_relative(self, dx: float = 0.0, dy: float = 0.0,
                      wait: bool = True, timeout: float = 30.0) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(x=self._world.x + dx, y=self._world.y + dy,
                           wait=wait, timeout=timeout)

    def get_position(self) -> Tuple[float, float]:
        """Return current position as (x, y) in mm."""
        self._check_connected()
        return (self._world.x, self._world.y)

    def is_on_target(self) -> bool:
        """Return True; simulated moves complete immediately."""
        self._check_connected()
        return True

    def stop(self) -> None:
        """Stop motion. A no-op, since simulated moves are instant."""
        self._check_connected()

    def set_velocity(self, velocity: float) -> None:
        """Set velocity in mm/s."""
        self._check_connected()
        self._velocity = float(velocity)

    def get_velocity(self) -> Tuple[float, float]:
        """Return velocity for both axes in mm/s."""
        self._check_connected()
        return (self._velocity, self._velocity)

    @property
    def x_range(self) -> Tuple[float, float]:
        """Permitted X travel in mm."""
        return self._x_range

    @property
    def y_range(self) -> Tuple[float, float]:
        """Permitted Y travel in mm."""
        return self._y_range

    @property
    def axes(self) -> List[str]:
        """Axis names."""
        return ['X', 'Y']


class SimStageZ(HardwareDevice):
    """Z stage simulator mirroring the public API of PIStageZ.

    Example:
        stage = SimStageZ(SimWorld())
        stage.connect()
        stage.move_absolute(5.0)
    """

    def __init__(self, world: SimWorld, device_id: Optional[str] = None,
                 name: Optional[str] = None,
                 z_range: Tuple[float, float] = (0.0, 10.0)):
        """Initialize the simulated Z stage.

        Args:
            world: Shared simulated instrument state
            device_id: Present for parity with PIStageZ
            name: Human-readable device name
            z_range: Permitted Z travel in mm
        """
        super().__init__(device_id=device_id or "SIM-Z", name=name or "Sim_Z")
        self._world = world
        self._z_range = z_range
        self._velocity = 1.0
        self._referenced = True

    def _do_connect(self) -> None:
        """Connect to the simulated stage."""
        self._device_info = {'model': 'SimStageZ', 'serial': self._device_id}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated stage."""

    def _do_initialize(self) -> None:
        """Initialize the simulated stage."""

    def _validate_position(self, z: float) -> float:
        """Validate and clamp position to limits.

        Args:
            z: Z position in mm

        Returns:
            Clamped Z position
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
        """Move to an absolute Z position in mm.

        Args:
            z: Target Z in mm
            wait: Accepted for API parity; simulated moves are instant
            timeout: Accepted for API parity; simulated moves are instant
        """
        self._check_connected()

        # Validate and clamp position
        z = self._validate_position(z)

        self._world.z = float(z)

    def move_relative(self, dz: float, wait: bool = True,
                      timeout: float = 30.0) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(self._world.z + dz, wait=wait, timeout=timeout)

    def get_position(self) -> float:
        """Return current Z position in mm."""
        self._check_connected()
        return self._world.z

    def is_on_target(self) -> bool:
        """Return True; simulated moves complete immediately."""
        self._check_connected()
        return True

    def stop(self) -> None:
        """Stop motion. A no-op, since simulated moves are instant."""
        self._check_connected()

    def set_velocity(self, velocity: float) -> None:
        """Set velocity in mm/s."""
        self._check_connected()
        self._velocity = float(velocity)

    def get_velocity(self) -> float:
        """Return velocity in mm/s."""
        self._check_connected()
        return self._velocity

    def reference(self) -> None:
        """Reference the axis. Always succeeds in simulation."""
        self._check_connected()
        self._referenced = True

    @property
    def z_range(self) -> Tuple[float, float]:
        """Permitted Z travel in mm."""
        return self._z_range

    @property
    def axis(self) -> str:
        """Axis name."""
        return 'Z'

    @property
    def is_referenced(self) -> bool:
        """Whether the axis has been referenced."""
        return self._referenced
