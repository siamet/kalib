"""Calibration model for storing calibration data and state.

Manages tilt calibration, magnetic calibration, and autofocus data.
"""

from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import json


@dataclass
class TiltCalibration:
    """Tilt calibration data."""
    corner_positions: List[Tuple[float, float, float]] = field(default_factory=list)
    corner_sharpness: List[float] = field(default_factory=list)
    plane_coefficients: Optional[Tuple[float, float, float]] = None
    tilt_angle_x: Optional[float] = None
    tilt_angle_y: Optional[float] = None
    calibration_date: Optional[datetime] = None
    is_valid: bool = False

    def calculate_plane(self) -> bool:
        """Calculate tilt plane from corner positions.

        Returns:
            True if calculation successful
        """
        if len(self.corner_positions) < 3:
            return False

        try:
            # Extract positions
            positions = np.array(self.corner_positions)
            x = positions[:, 0]
            y = positions[:, 1]
            z = positions[:, 2]

            # Fit plane: z = ax + by + c
            A = np.column_stack([x, y, np.ones_like(x)])
            coeffs, _, _, _ = np.linalg.lstsq(A, z, rcond=None)

            self.plane_coefficients = tuple(coeffs)

            # Calculate tilt angles
            a, b, _ = coeffs
            self.tilt_angle_x = np.arctan(a) * 180 / np.pi
            self.tilt_angle_y = np.arctan(b) * 180 / np.pi

            self.is_valid = True
            self.calibration_date = datetime.now()
            return True

        except Exception:
            return False

    def get_z_correction(self, x: float, y: float) -> Optional[float]:
        """Get Z correction for given XY position.

        Args:
            x: X position
            y: Y position

        Returns:
            Z correction value or None if not calibrated
        """
        if not self.is_valid or self.plane_coefficients is None:
            return None

        a, b, c = self.plane_coefficients
        return a * x + b * y + c


@dataclass
class MagneticCalibration:
    """Magnetic calibration data."""
    calibration_positions: List[Tuple[float, float, float]] = field(default_factory=list)
    reference_position: Optional[Tuple[float, float, float]] = None
    fitting_function: Optional[callable] = None
    calibration_date: Optional[datetime] = None
    is_valid: bool = False

    def add_calibration_point(self, x: float, y: float, z: float) -> None:
        """Add calibration point.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.calibration_positions.append((x, y, z))

    def set_reference_position(self, x: float, y: float, z: float) -> None:
        """Set reference position.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.reference_position = (x, y, z)

    def clear_calibration(self) -> None:
        """Clear calibration data."""
        self.calibration_positions.clear()
        self.reference_position = None
        self.fitting_function = None
        self.is_valid = False


@dataclass
class AutofocusData:
    """Autofocus data and settings."""
    best_focus_z: Optional[float] = None
    peak_sharpness: Optional[float] = None
    search_positions: List[float] = field(default_factory=list)
    sharpness_values: List[float] = field(default_factory=list)
    search_range: float = 1.0
    step_size: float = 0.05
    timestamp: Optional[datetime] = None

    def update_focus(self, z_positions: List[float],
                    sharpness_values: List[float]) -> bool:
        """Update autofocus data from search.

        Args:
            z_positions: List of Z positions searched
            sharpness_values: Corresponding sharpness values

        Returns:
            True if best focus found
        """
        if not z_positions or not sharpness_values:
            return False

        self.search_positions = z_positions.copy()
        self.sharpness_values = sharpness_values.copy()

        # Find peak sharpness
        peak_idx = np.argmax(sharpness_values)
        self.best_focus_z = z_positions[peak_idx]
        self.peak_sharpness = sharpness_values[peak_idx]
        self.timestamp = datetime.now()

        return True


class CalibrationModel:
    """Calibration data model.

    Manages calibration data for tilt correction, magnetic calibration,
    and autofocus.
    """

    def __init__(self):
        """Initialize calibration model."""
        self.tilt_calibration = TiltCalibration()
        self.magnetic_calibration = MagneticCalibration()
        self.autofocus_data = AutofocusData()

        # Calibration settings
        self.tilt_enabled = False
        self.magnetic_enabled = False
        self.autofocus_enabled = False

    def set_tilt_corners(self, corners: List[Tuple[float, float, float]],
                        sharpness: Optional[List[float]] = None) -> bool:
        """Set tilt calibration corner positions.

        Args:
            corners: List of (x, y, z) corner positions
            sharpness: Optional sharpness values at corners

        Returns:
            True if calibration successful
        """
        self.tilt_calibration.corner_positions = corners.copy()

        if sharpness:
            self.tilt_calibration.corner_sharpness = sharpness.copy()

        # Calculate plane
        success = self.tilt_calibration.calculate_plane()

        if success:
            self.tilt_enabled = True

        return success

    def get_tilt_correction(self, x: float, y: float) -> float:
        """Get tilt correction for position.

        Args:
            x: X position
            y: Y position

        Returns:
            Z correction value (0 if not calibrated)
        """
        if not self.tilt_enabled:
            return 0.0

        correction = self.tilt_calibration.get_z_correction(x, y)
        return correction if correction is not None else 0.0

    def enable_tilt_correction(self, enabled: bool) -> None:
        """Enable/disable tilt correction.

        Args:
            enabled: True to enable
        """
        if enabled and not self.tilt_calibration.is_valid:
            return  # Cannot enable if not calibrated

        self.tilt_enabled = enabled

    def add_magnetic_position(self, x: float, y: float, z: float) -> None:
        """Add magnetic calibration position.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.magnetic_calibration.add_calibration_point(x, y, z)

    def set_magnetic_reference(self, x: float, y: float, z: float) -> None:
        """Set magnetic calibration reference position.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.magnetic_calibration.set_reference_position(x, y, z)

    def update_autofocus(self, z_positions: List[float],
                        sharpness_values: List[float]) -> bool:
        """Update autofocus data.

        Args:
            z_positions: Z positions searched
            sharpness_values: Sharpness values

        Returns:
            True if best focus found
        """
        success = self.autofocus_data.update_focus(z_positions, sharpness_values)

        if success:
            self.autofocus_enabled = True

        return success

    def get_best_focus_z(self) -> Optional[float]:
        """Get best focus Z position.

        Returns:
            Best focus Z or None if not available
        """
        return self.autofocus_data.best_focus_z

    def clear_all_calibrations(self) -> None:
        """Clear all calibration data."""
        self.tilt_calibration = TiltCalibration()
        self.magnetic_calibration = MagneticCalibration()
        self.autofocus_data = AutofocusData()
        self.tilt_enabled = False
        self.magnetic_enabled = False
        self.autofocus_enabled = False

    def export_calibration(self, filepath: str) -> None:
        """Export calibration data to JSON file.

        Args:
            filepath: Output JSON file path
        """
        data = {
            'tilt': {
                'corner_positions': self.tilt_calibration.corner_positions,
                'corner_sharpness': self.tilt_calibration.corner_sharpness,
                'plane_coefficients': self.tilt_calibration.plane_coefficients,
                'tilt_angle_x': self.tilt_calibration.tilt_angle_x,
                'tilt_angle_y': self.tilt_calibration.tilt_angle_y,
                'is_valid': self.tilt_calibration.is_valid,
                'enabled': self.tilt_enabled,
            },
            'magnetic': {
                'positions': self.magnetic_calibration.calibration_positions,
                'reference': self.magnetic_calibration.reference_position,
                'is_valid': self.magnetic_calibration.is_valid,
                'enabled': self.magnetic_enabled,
            },
            'autofocus': {
                'best_focus_z': self.autofocus_data.best_focus_z,
                'peak_sharpness': self.autofocus_data.peak_sharpness,
                'search_range': self.autofocus_data.search_range,
                'step_size': self.autofocus_data.step_size,
                'enabled': self.autofocus_enabled,
            }
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def import_calibration(self, filepath: str) -> bool:
        """Import calibration data from JSON file.

        Args:
            filepath: Input JSON file path

        Returns:
            True if import successful
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Load tilt calibration
            tilt = data.get('tilt', {})
            self.tilt_calibration.corner_positions = tilt.get('corner_positions', [])
            self.tilt_calibration.corner_sharpness = tilt.get('corner_sharpness', [])
            self.tilt_calibration.plane_coefficients = tilt.get('plane_coefficients')
            self.tilt_calibration.tilt_angle_x = tilt.get('tilt_angle_x')
            self.tilt_calibration.tilt_angle_y = tilt.get('tilt_angle_y')
            self.tilt_calibration.is_valid = tilt.get('is_valid', False)
            self.tilt_enabled = tilt.get('enabled', False)

            # Load magnetic calibration
            mag = data.get('magnetic', {})
            self.magnetic_calibration.calibration_positions = mag.get('positions', [])
            self.magnetic_calibration.reference_position = mag.get('reference')
            self.magnetic_calibration.is_valid = mag.get('is_valid', False)
            self.magnetic_enabled = mag.get('enabled', False)

            # Load autofocus data
            af = data.get('autofocus', {})
            self.autofocus_data.best_focus_z = af.get('best_focus_z')
            self.autofocus_data.peak_sharpness = af.get('peak_sharpness')
            self.autofocus_data.search_range = af.get('search_range', 1.0)
            self.autofocus_data.step_size = af.get('step_size', 0.05)
            self.autofocus_enabled = af.get('enabled', False)

            return True

        except Exception:
            return False

    def to_dict(self) -> dict:
        """Convert model to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'tilt': {
                'enabled': self.tilt_enabled,
                'is_valid': self.tilt_calibration.is_valid,
                'num_corners': len(self.tilt_calibration.corner_positions),
                'tilt_angles': (
                    self.tilt_calibration.tilt_angle_x,
                    self.tilt_calibration.tilt_angle_y
                ),
            },
            'magnetic': {
                'enabled': self.magnetic_enabled,
                'is_valid': self.magnetic_calibration.is_valid,
                'num_positions': len(self.magnetic_calibration.calibration_positions),
            },
            'autofocus': {
                'enabled': self.autofocus_enabled,
                'best_focus_z': self.autofocus_data.best_focus_z,
                'peak_sharpness': self.autofocus_data.peak_sharpness,
            }
        }
