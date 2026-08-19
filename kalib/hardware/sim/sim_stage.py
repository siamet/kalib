"""Simulated XY and Z stages acting on a shared SimWorld."""

from typing import List, Optional, Tuple

from kalib.hardware.base import CommandError, HardwareDevice
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

    def _check_range(self, value: float, limits: Tuple[float, float],
                     axis: str) -> None:
        """Raise if a target lies outside the permitted travel.

        Args:
            value: Requested position in mm
            limits: (minimum, maximum) in mm
            axis: Axis name, for the error message

        Raises:
            CommandError: If the target is out of range
        """
        low, high = limits
        if not low <= value <= high:
            raise CommandError(
                f"{axis} target {value} outside range [{low}, {high}]")

    def move_absolute(self, x: Optional[float] = None,
                      y: Optional[float] = None, wait: bool = True) -> None:
        """Move to an absolute position.

        Args:
            x: Target X in mm; unchanged if None
            y: Target Y in mm; unchanged if None
            wait: Accepted for API parity; simulated moves are instant

        Raises:
            CommandError: If a target is out of range
        """
        self._check_connected()
        if x is not None:
            self._check_range(x, self._x_range, "X")
        if y is not None:
            self._check_range(y, self._y_range, "Y")
        if x is not None:
            self._world.x = float(x)
        if y is not None:
            self._world.y = float(y)

    def move_relative(self, dx: float = 0.0, dy: float = 0.0,
                      wait: bool = True) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(x=self._world.x + dx, y=self._world.y + dy, wait=wait)

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

    def move_absolute(self, z: float, wait: bool = True) -> None:
        """Move to an absolute Z position in mm.

        Args:
            z: Target Z in mm
            wait: Accepted for API parity; simulated moves are instant

        Raises:
            CommandError: If the target is out of range
        """
        self._check_connected()
        low, high = self._z_range
        if not low <= z <= high:
            raise CommandError(f"Z target {z} outside range [{low}, {high}]")
        self._world.z = float(z)

    def move_relative(self, dz: float, wait: bool = True) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(self._world.z + dz, wait=wait)

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
