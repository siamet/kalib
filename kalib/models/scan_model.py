"""Scan model for scanning operations and state management.

Manages scan parameters, state machine, and progress tracking
for XY, Z-stack, and SFF scanning.
"""

from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import numpy as np


class ScanType(Enum):
    """Types of scanning operations."""
    XY_SCAN = "xy_scan"
    Z_STACK = "z_stack"
    XY_CALIBRATION = "xy_calibration"
    SFF_SCAN = "sff_scan"


class ScanState(Enum):
    """Scan state machine states."""
    IDLE = "idle"
    CONFIGURING = "configuring"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class XYScanParameters:
    """Parameters for XY area scanning."""
    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 10.0
    end_y: float = 10.0
    step_x: float = 1.0
    step_y: float = 1.0
    num_steps_x: Optional[int] = None
    num_steps_y: Optional[int] = None

    def __post_init__(self):
        """Calculate number of steps if not provided."""
        if self.num_steps_x is None:
            self.num_steps_x = int((self.end_x - self.start_x) / self.step_x) + 1
        if self.num_steps_y is None:
            self.num_steps_y = int((self.end_y - self.start_y) / self.step_y) + 1

    @property
    def total_positions(self) -> int:
        """Total number of scan positions."""
        return self.num_steps_x * self.num_steps_y


@dataclass
class ZStackParameters:
    """Parameters for Z-stack scanning."""
    start_z: float = 0.0
    end_z: float = 5.0
    step_z: float = 0.1
    num_steps: Optional[int] = None

    def __post_init__(self):
        """Calculate number of steps if not provided."""
        if self.num_steps is None:
            self.num_steps = int((self.end_z - self.start_z) / self.step_z) + 1

    @property
    def total_positions(self) -> int:
        """Total number of scan positions."""
        return self.num_steps


@dataclass
class SFFScanParameters:
    """Parameters for Shape from Focus scanning."""
    xy_params: XYScanParameters
    z_params: ZStackParameters
    sharpness_metric: str = "gradient"

    @property
    def total_positions(self) -> int:
        """Total number of scan positions."""
        return self.xy_params.total_positions * self.z_params.total_positions


@dataclass
class ScanProgress:
    """Scan progress tracking."""
    current_position: int = 0
    total_positions: int = 0
    images_captured: int = 0
    errors_encountered: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_positions == 0:
            return 0.0
        return (self.current_position / self.total_positions) * 100.0

    @property
    def elapsed_time(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        if self.current_position == 0 or self.elapsed_time is None:
            return None

        time_per_position = self.elapsed_time / self.current_position
        remaining_positions = self.total_positions - self.current_position
        return time_per_position * remaining_positions


class ScanModel:
    """Scan data model.

    Manages scan parameters, state, and progress tracking for
    various scanning operations.
    """

    def __init__(self, scan_type: ScanType = ScanType.XY_SCAN):
        """Initialize scan model.

        Args:
            scan_type: Type of scan to perform
        """
        self.scan_type = scan_type
        self.state = ScanState.IDLE

        # Parameters
        self.xy_params: Optional[XYScanParameters] = None
        self.z_params: Optional[ZStackParameters] = None
        self.sff_params: Optional[SFFScanParameters] = None

        # Progress
        self.progress = ScanProgress()

        # Data storage
        self._scan_positions: List[Tuple[float, ...]] = []
        self._scan_images: List[np.ndarray] = []
        self._sharpness_values: List[float] = []

        # Settings
        self.save_individual_frames = True
        self.save_path: Optional[str] = None

    def configure_xy_scan(self, params: XYScanParameters) -> None:
        """Configure XY scan parameters.

        Args:
            params: XY scan parameters
        """
        self.scan_type = ScanType.XY_SCAN
        self.xy_params = params
        self.progress.total_positions = params.total_positions
        self.state = ScanState.CONFIGURING

    def configure_z_stack(self, params: ZStackParameters) -> None:
        """Configure Z-stack scan parameters.

        Args:
            params: Z-stack parameters
        """
        self.scan_type = ScanType.Z_STACK
        self.z_params = params
        self.progress.total_positions = params.total_positions
        self.state = ScanState.CONFIGURING

    def configure_sff_scan(self, params: SFFScanParameters) -> None:
        """Configure SFF scan parameters.

        Args:
            params: SFF scan parameters
        """
        self.scan_type = ScanType.SFF_SCAN
        self.sff_params = params
        self.progress.total_positions = params.total_positions
        self.state = ScanState.CONFIGURING

    def start_scan(self) -> None:
        """Start scanning operation."""
        self.state = ScanState.RUNNING
        self.progress.start_time = datetime.now()
        self.progress.current_position = 0
        self.progress.images_captured = 0
        self.progress.errors_encountered = 0
        self._scan_positions.clear()
        self._scan_images.clear()
        self._sharpness_values.clear()

    def pause_scan(self) -> None:
        """Pause scanning operation."""
        if self.state == ScanState.RUNNING:
            self.state = ScanState.PAUSED

    def resume_scan(self) -> None:
        """Resume paused scan."""
        if self.state == ScanState.PAUSED:
            self.state = ScanState.RUNNING

    def cancel_scan(self) -> None:
        """Cancel scanning operation."""
        self.state = ScanState.CANCELLED
        self.progress.end_time = datetime.now()

    def complete_scan(self) -> None:
        """Mark scan as completed."""
        self.state = ScanState.COMPLETED
        self.progress.end_time = datetime.now()

    def error_scan(self) -> None:
        """Mark scan as error state."""
        self.state = ScanState.ERROR
        self.progress.end_time = datetime.now()

    def add_scan_position(self, position: Tuple[float, ...],
                         image: Optional[np.ndarray] = None,
                         sharpness: Optional[float] = None) -> None:
        """Add scan position and associated data.

        Args:
            position: Position coordinates (x, y) or (x, y, z)
            image: Captured image at this position
            sharpness: Sharpness value at this position
        """
        self._scan_positions.append(position)

        if image is not None:
            self._scan_images.append(image)
            self.progress.images_captured += 1

        if sharpness is not None:
            self._sharpness_values.append(sharpness)

        self.progress.current_position += 1

    def increment_error_count(self) -> None:
        """Increment error counter."""
        self.progress.errors_encountered += 1

    def get_scan_positions(self) -> List[Tuple[float, ...]]:
        """Get list of scan positions.

        Returns:
            List of position tuples
        """
        return self._scan_positions.copy()

    def get_scan_positions_array(self) -> np.ndarray:
        """Get scan positions as numpy array.

        Returns:
            Nx2 or Nx3 array of positions
        """
        if not self._scan_positions:
            return np.array([])
        return np.array(self._scan_positions)

    def get_scan_images(self) -> List[np.ndarray]:
        """Get list of captured images.

        Returns:
            List of images
        """
        return self._scan_images.copy()

    def get_sharpness_values(self) -> List[float]:
        """Get list of sharpness values.

        Returns:
            List of sharpness values
        """
        return self._sharpness_values.copy()

    def get_sharpness_array(self) -> np.ndarray:
        """Get sharpness values as numpy array.

        Returns:
            Array of sharpness values
        """
        return np.array(self._sharpness_values)

    def clear_data(self) -> None:
        """Clear scan data."""
        self._scan_positions.clear()
        self._scan_images.clear()
        self._sharpness_values.clear()
        self.progress = ScanProgress()

    def generate_xy_grid(self) -> List[Tuple[float, float]]:
        """Generate XY grid positions for scanning.

        Returns:
            List of (x, y) tuples
        """
        if self.xy_params is None:
            return []

        positions = []
        for i in range(self.xy_params.num_steps_x):
            x = self.xy_params.start_x + i * self.xy_params.step_x
            for j in range(self.xy_params.num_steps_y):
                y = self.xy_params.start_y + j * self.xy_params.step_y
                positions.append((x, y))

        return positions

    def generate_z_positions(self) -> List[float]:
        """Generate Z positions for scanning.

        Returns:
            List of Z positions
        """
        if self.z_params is None:
            return []

        positions = []
        for i in range(self.z_params.num_steps):
            z = self.z_params.start_z + i * self.z_params.step_z
            positions.append(z)

        return positions

    @property
    def is_running(self) -> bool:
        """Check if scan is running."""
        return self.state == ScanState.RUNNING

    @property
    def is_complete(self) -> bool:
        """Check if scan is complete."""
        return self.state == ScanState.COMPLETED

    @property
    def can_start(self) -> bool:
        """Check if scan can be started."""
        return self.state in [ScanState.IDLE, ScanState.CONFIGURING]

    def export_positions_csv(self, filepath: str) -> None:
        """Export scan positions to CSV file.

        Args:
            filepath: Output CSV file path
        """
        import csv

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Determine header based on position dimensions
            if self._scan_positions:
                num_dims = len(self._scan_positions[0])
                if num_dims == 2:
                    header = ['X', 'Y']
                elif num_dims == 3:
                    header = ['X', 'Y', 'Z']
                else:
                    header = [f'Dim{i}' for i in range(num_dims)]

                # Add sharpness column if available
                if len(self._sharpness_values) == len(self._scan_positions):
                    header.append('Sharpness')

                writer.writerow(header)

                # Write positions
                for i, pos in enumerate(self._scan_positions):
                    row = list(pos)
                    if i < len(self._sharpness_values):
                        row.append(self._sharpness_values[i])
                    writer.writerow(row)

    def to_dict(self) -> dict:
        """Convert model to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'scan_type': self.scan_type.value,
            'state': self.state.value,
            'progress': {
                'current': self.progress.current_position,
                'total': self.progress.total_positions,
                'percent': self.progress.percent_complete,
                'images_captured': self.progress.images_captured,
                'errors': self.progress.errors_encountered,
                'elapsed_time': self.progress.elapsed_time,
                'estimated_remaining': self.progress.estimated_time_remaining,
            },
            'num_positions': len(self._scan_positions),
            'num_images': len(self._scan_images),
        }
