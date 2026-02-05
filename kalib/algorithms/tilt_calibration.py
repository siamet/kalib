"""Tilt calibration algorithms.

Implements tilt plane fitting from corner measurements for
surface tilt compensation.
"""

from typing import List, Tuple, Optional
import numpy as np


def fit_plane_lstsq(points: np.ndarray) -> Tuple[float, float, float]:
    """Fit a plane to 3D points using least squares.

    Fits plane equation: z = ax + by + c

    Args:
        points: Nx3 array of (x, y, z) coordinates

    Returns:
        Tuple of (a, b, c) plane coefficients

    Raises:
        ValueError: If insufficient points provided
    """
    if len(points) < 3:
        raise ValueError("At least 3 points required for plane fitting")

    # Extract coordinates
    x = points[:, 0]
    y = points[:, 1]
    z = points[:, 2]

    # Construct matrix A = [x, y, ones]
    A = np.column_stack([x, y, np.ones_like(x)])

    # Solve least squares: Az = b
    coeffs, residuals, rank, s = np.linalg.lstsq(A, z, rcond=None)

    a, b, c = coeffs

    return float(a), float(b), float(c)


def calculate_tilt_angles(a: float, b: float) -> Tuple[float, float]:
    """Calculate tilt angles from plane coefficients.

    Args:
        a: X coefficient from plane equation z = ax + by + c
        b: Y coefficient from plane equation

    Returns:
        Tuple of (tilt_x_degrees, tilt_y_degrees)
    """
    # Tilt angle in X direction (radians)
    tilt_x_rad = np.arctan(a)
    tilt_x_deg = np.degrees(tilt_x_rad)

    # Tilt angle in Y direction (radians)
    tilt_y_rad = np.arctan(b)
    tilt_y_deg = np.degrees(tilt_y_rad)

    return float(tilt_x_deg), float(tilt_y_deg)


def get_z_correction(x: float, y: float,
                    a: float, b: float, c: float) -> float:
    """Get Z correction for given XY position.

    Args:
        x: X position
        y: Y position
        a: X coefficient from plane equation
        b: Y coefficient from plane equation
        c: Z offset from plane equation

    Returns:
        Z correction value
    """
    z_correction = a * x + b * y + c
    return float(z_correction)


def calibrate_tilt_from_corners(corner_positions: List[Tuple[float, float, float]]
                                ) -> dict:
    """Perform tilt calibration from corner measurements.

    Args:
        corner_positions: List of (x, y, z) corner positions

    Returns:
        Dictionary containing:
            - 'plane_coefficients': (a, b, c) tuple
            - 'tilt_angles': (tilt_x_deg, tilt_y_deg) tuple
            - 'residuals': RMS error of fit
            - 'num_points': Number of points used

    Raises:
        ValueError: If insufficient corner positions
    """
    if len(corner_positions) < 3:
        raise ValueError("At least 3 corner positions required")

    # Convert to numpy array
    points = np.array(corner_positions)

    # Fit plane
    a, b, c = fit_plane_lstsq(points)

    # Calculate tilt angles
    tilt_x_deg, tilt_y_deg = calculate_tilt_angles(a, b)

    # Calculate residuals (fit quality)
    z_predicted = points[:, 0] * a + points[:, 1] * b + c
    z_actual = points[:, 2]
    residuals = np.sqrt(np.mean((z_predicted - z_actual) ** 2))

    result = {
        'plane_coefficients': (a, b, c),
        'tilt_angles': (tilt_x_deg, tilt_y_deg),
        'residuals': float(residuals),
        'num_points': len(corner_positions)
    }

    return result


def generate_corner_positions(x_range: Tuple[float, float],
                              y_range: Tuple[float, float],
                              num_corners: int = 4
                              ) -> List[Tuple[float, float]]:
    """Generate corner positions for tilt calibration.

    Args:
        x_range: (x_min, x_max) range
        y_range: (y_min, y_max) range
        num_corners: Number of corners (4 or 9)

    Returns:
        List of (x, y) corner positions

    Raises:
        ValueError: If unsupported number of corners
    """
    x_min, x_max = x_range
    y_min, y_max = y_range

    if num_corners == 4:
        # Four corners
        corners = [
            (x_min, y_min),  # Bottom-left
            (x_max, y_min),  # Bottom-right
            (x_min, y_max),  # Top-left
            (x_max, y_max),  # Top-right
        ]
    elif num_corners == 9:
        # Nine points (corners + edges + center)
        x_mid = (x_min + x_max) / 2
        y_mid = (y_min + y_max) / 2
        corners = [
            (x_min, y_min),  # Bottom-left
            (x_mid, y_min),  # Bottom-center
            (x_max, y_min),  # Bottom-right
            (x_min, y_mid),  # Middle-left
            (x_mid, y_mid),  # Center
            (x_max, y_mid),  # Middle-right
            (x_min, y_max),  # Top-left
            (x_mid, y_max),  # Top-center
            (x_max, y_max),  # Top-right
        ]
    else:
        raise ValueError(f"Unsupported number of corners: {num_corners}. Use 4 or 9.")

    return corners


def apply_tilt_correction(positions: np.ndarray,
                         plane_coefficients: Tuple[float, float, float]
                         ) -> np.ndarray:
    """Apply tilt correction to a set of XYZ positions.

    Args:
        positions: Nx3 array of (x, y, z) positions
        plane_coefficients: (a, b, c) from plane fit

    Returns:
        Nx3 array of corrected (x, y, z_corrected) positions
    """
    a, b, c = plane_coefficients

    # Calculate reference plane at origin
    z_reference = c

    # Apply correction to each position
    corrected = positions.copy()
    for i in range(len(positions)):
        x, y, z = positions[i]

        # Calculate expected Z from tilt plane
        z_expected = a * x + b * y + c

        # Correction is difference from reference
        z_correction = z_expected - z_reference

        # Apply correction
        corrected[i, 2] = z - z_correction

    return corrected


def validate_calibration(corner_positions: List[Tuple[float, float, float]],
                        plane_coefficients: Tuple[float, float, float],
                        max_residual: float = 0.1
                        ) -> bool:
    """Validate tilt calibration quality.

    Args:
        corner_positions: List of (x, y, z) corner positions
        plane_coefficients: (a, b, c) from plane fit
        max_residual: Maximum acceptable RMS residual

    Returns:
        True if calibration is valid
    """
    points = np.array(corner_positions)
    a, b, c = plane_coefficients

    # Calculate residuals
    z_predicted = points[:, 0] * a + points[:, 1] * b + c
    z_actual = points[:, 2]
    rms_residual = np.sqrt(np.mean((z_predicted - z_actual) ** 2))

    return rms_residual <= max_residual


class TiltCalibrator:
    """Tilt calibration helper class.

    Provides stateful tilt calibration with corner measurement tracking.
    """

    def __init__(self, x_range: Tuple[float, float],
                 y_range: Tuple[float, float],
                 num_corners: int = 4):
        """Initialize tilt calibrator.

        Args:
            x_range: (x_min, x_max) range
            y_range: (y_min, y_max) range
            num_corners: Number of calibration corners
        """
        self.x_range = x_range
        self.y_range = y_range
        self.num_corners = num_corners

        self.target_corners = generate_corner_positions(x_range, y_range, num_corners)
        self.measured_corners: List[Tuple[float, float, float]] = []
        self.plane_coefficients: Optional[Tuple[float, float, float]] = None
        self.tilt_angles: Optional[Tuple[float, float]] = None

    def add_corner_measurement(self, x: float, y: float, z: float) -> None:
        """Add corner measurement.

        Args:
            x: X position
            y: Y position
            z: Z position (measured at best focus)
        """
        self.measured_corners.append((x, y, z))

    def is_complete(self) -> bool:
        """Check if all corners measured.

        Returns:
            True if all corners measured
        """
        return len(self.measured_corners) >= self.num_corners

    def calculate(self) -> bool:
        """Calculate tilt calibration from measurements.

        Returns:
            True if calibration successful
        """
        if not self.is_complete():
            return False

        try:
            result = calibrate_tilt_from_corners(self.measured_corners)
            self.plane_coefficients = result['plane_coefficients']
            self.tilt_angles = result['tilt_angles']
            return True
        except Exception:
            return False

    def get_correction(self, x: float, y: float) -> Optional[float]:
        """Get Z correction for position.

        Args:
            x: X position
            y: Y position

        Returns:
            Z correction or None if not calibrated
        """
        if self.plane_coefficients is None:
            return None

        a, b, c = self.plane_coefficients
        return get_z_correction(x, y, a, b, c)

    def reset(self) -> None:
        """Reset calibration measurements."""
        self.measured_corners.clear()
        self.plane_coefficients = None
        self.tilt_angles = None
