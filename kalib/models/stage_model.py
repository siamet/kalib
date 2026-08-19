"""Stage model for position tracking and limits.

Manages XY and Z stage positions, limits, and movement history.
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
import numpy as np


@dataclass
class Position3D:
    """3D position coordinates."""
    x: float
    y: float
    z: float
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_tuple(self) -> Tuple[float, float, float]:
        """Convert to tuple."""
        return (self.x, self.y, self.z)

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([self.x, self.y, self.z])


@dataclass
class StageLimits:
    """Stage movement limits."""
    x_min: float = 0.0
    x_max: float = 100.0
    y_min: float = 0.0
    y_max: float = 100.0
    z_min: float = 0.0
    z_max: float = 10.0

    def is_within_limits(self, x: float, y: float, z: float) -> bool:
        """Check if position is within limits.

        Args:
            x: X position
            y: Y position
            z: Z position

        Returns:
            True if within limits
        """
        return (
            self.x_min <= x <= self.x_max and
            self.y_min <= y <= self.y_max and
            self.z_min <= z <= self.z_max
        )

    def clamp(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Clamp position to limits.

        Args:
            x: X position
            y: Y position
            z: Z position

        Returns:
            Clamped (x, y, z) tuple
        """
        x_clamped = max(self.x_min, min(self.x_max, x))
        y_clamped = max(self.y_min, min(self.y_max, y))
        z_clamped = max(self.z_min, min(self.z_max, z))
        return (x_clamped, y_clamped, z_clamped)


class StageModel:
    """Stage data model.

    Manages stage positions, limits, and movement history for
    XY and Z stages.
    """

    def __init__(self, limits: Optional[StageLimits] = None):
        """Initialize stage model.

        Args:
            limits: Stage movement limits
        """
        self.limits = limits or StageLimits()
        self._current_position = Position3D(0.0, 0.0, 0.0)
        self._target_position: Optional[Position3D] = None
        self._position_history: List[Position3D] = []
        self._max_history_size = 1000

        self._xy_connected = False
        self._z_connected = False
        self._is_moving = False

    def set_xy_connected(self, connected: bool) -> None:
        """Set XY stage connection state."""
        self._xy_connected = connected

    def set_z_connected(self, connected: bool) -> None:
        """Set Z stage connection state."""
        self._z_connected = connected

    @property
    def is_connected(self) -> bool:
        """Check if any stage is connected."""
        return self._xy_connected or self._z_connected

    @property
    def is_fully_connected(self) -> bool:
        """Check if all stages are connected."""
        return self._xy_connected and self._z_connected

    def update_position(self, x: Optional[float] = None,
                       y: Optional[float] = None,
                       z: Optional[float] = None) -> None:
        """Update current position.

        Args:
            x: X position (None to keep current)
            y: Y position (None to keep current)
            z: Z position (None to keep current)
        """
        new_x = x if x is not None else self._current_position.x
        new_y = y if y is not None else self._current_position.y
        new_z = z if z is not None else self._current_position.z

        self._current_position = Position3D(new_x, new_y, new_z)

        # Add to history
        self._position_history.append(self._current_position)
        if len(self._position_history) > self._max_history_size:
            self._position_history.pop(0)

    def set_target_position(self, x: float, y: float, z: float) -> None:
        """Set target position for movement.

        Args:
            x: Target X position
            y: Target Y position
            z: Target Z position
        """
        self._target_position = Position3D(x, y, z)
        self._is_moving = True

    def clear_target_position(self) -> None:
        """Clear target position (movement complete)."""
        self._target_position = None
        self._is_moving = False

    def get_position(self) -> Position3D:
        """Get current position.

        Returns:
            Current position
        """
        return self._current_position

    def get_position_tuple(self) -> Tuple[float, float, float]:
        """Get current position as tuple.

        Returns:
            (x, y, z) tuple
        """
        return self._current_position.to_tuple()

    def get_xy_position(self) -> Tuple[float, float]:
        """Get current XY position.

        Returns:
            (x, y) tuple
        """
        return (self._current_position.x, self._current_position.y)

    def get_z_position(self) -> float:
        """Get current Z position.

        Returns:
            Z position
        """
        return self._current_position.z

    def get_target_position(self) -> Optional[Position3D]:
        """Get target position.

        Returns:
            Target position or None
        """
        return self._target_position

    def get_position_history(self) -> List[Position3D]:
        """Get position history.

        Returns:
            List of historical positions
        """
        return self._position_history.copy()

    def get_position_history_array(self) -> np.ndarray:
        """Get position history as numpy array.

        Returns:
            Nx3 array of positions
        """
        if not self._position_history:
            return np.array([]).reshape(0, 3)

        return np.array([pos.to_array() for pos in self._position_history])

    def clear_history(self) -> None:
        """Clear position history."""
        self._position_history.clear()

    def is_within_limits(self, x: float, y: float, z: float) -> bool:
        """Check if position is within limits.

        Args:
            x: X position
            y: Y position
            z: Z position

        Returns:
            True if within limits
        """
        return self.limits.is_within_limits(x, y, z)

    def validate_and_clamp(self, x: float, y: float, z: float
                          ) -> Tuple[float, float, float]:
        """Validate and clamp position to limits.

        Args:
            x: X position
            y: Y position
            z: Z position

        Returns:
            Clamped (x, y, z) tuple
        """
        return self.limits.clamp(x, y, z)

    def get_distance_to_target(self) -> Optional[float]:
        """Get Euclidean distance to target position.

        Returns:
            Distance in mm or None if no target
        """
        if self._target_position is None:
            return None

        current = self._current_position.to_array()
        target = self._target_position.to_array()
        return float(np.linalg.norm(target - current))

    @property
    def is_moving(self) -> bool:
        """Check if stage is moving to target."""
        return self._is_moving

    def export_history_csv(self, filepath: str) -> None:
        """Export position history to CSV file.

        Args:
            filepath: Output CSV file path
        """
        import csv

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'X', 'Y', 'Z'])

            for pos in self._position_history:
                writer.writerow([
                    pos.timestamp.isoformat(),
                    pos.x,
                    pos.y,
                    pos.z
                ])

    def import_history_csv(self, filepath: str) -> None:
        """Import position history from CSV file.

        Args:
            filepath: Input CSV file path
        """
        import csv

        self._position_history.clear()

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pos = Position3D(
                    x=float(row['X']),
                    y=float(row['Y']),
                    z=float(row['Z']),
                    timestamp=datetime.fromisoformat(row['Timestamp'])
                )
                self._position_history.append(pos)

    def to_dict(self) -> dict:
        """Convert model to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'current_position': self._current_position.to_tuple(),
            'target_position': (
                self._target_position.to_tuple()
                if self._target_position else None
            ),
            'is_moving': self._is_moving,
            'xy_connected': self._xy_connected,
            'z_connected': self._z_connected,
            'limits': {
                'x': [self.limits.x_min, self.limits.x_max],
                'y': [self.limits.y_min, self.limits.y_max],
                'z': [self.limits.z_min, self.limits.z_max],
            }
        }
