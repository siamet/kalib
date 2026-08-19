"""Calibration controller for managing calibration operations.

Coordinates camera and stage controllers to perform tilt calibration,
magnetic calibration, and autofocus operations.
"""

from typing import List, Tuple, Optional
from PySide6.QtCore import QObject, Signal
import time

from kalib.models import CalibrationModel
from kalib.algorithms import (
    calibrate_tilt_from_corners,
    TiltCalibrator,
    autofocus_search,
    autofocus_iterative,
    calculate_sharpness
)
from kalib.utils.logger import get_logger


class CalibrationController(QObject):
    """Calibration controller.

    Manages calibration workflows including tilt calibration,
    magnetic calibration, and autofocus.
    """

    # Qt Signals
    calibration_started = Signal(str)  # calibration type
    calibration_completed = Signal(str)  # calibration type
    calibration_error = Signal(str)
    progress_updated = Signal(int, int)  # current, total
    corner_measured = Signal(int, int)  # current corner, total corners
    focus_found = Signal(float)  # best focus Z position

    def __init__(self, camera_controller, stage_controller):
        """Initialize calibration controller.

        Args:
            camera_controller: Camera controller instance
            stage_controller: Stage controller instance
        """
        super().__init__()

        self._logger = get_logger(__name__)

        # Controllers
        self.camera = camera_controller
        self.stage = stage_controller

        # Model
        self.model = CalibrationModel()

        # Tilt calibrator helper
        self._tilt_calibrator: Optional[TiltCalibrator] = None

    def start_tilt_calibration(self, num_corners: int = 4) -> bool:
        """Start tilt calibration process.

        Args:
            num_corners: Number of calibration corners (4 or 9)

        Returns:
            True if calibration started

        Emits:
            calibration_started: When calibration begins
        """
        if not self.camera.is_acquiring or not self.stage.is_connected:
            self.calibration_error.emit("Camera or stage not ready")
            return False

        try:
            self._logger.info(f"Starting tilt calibration with {num_corners} corners")

            # Create tilt calibrator
            x_range = (self.stage.model.limits.x_min, self.stage.model.limits.x_max)
            y_range = (self.stage.model.limits.y_min, self.stage.model.limits.y_max)

            self._tilt_calibrator = TiltCalibrator(
                x_range=x_range,
                y_range=y_range,
                num_corners=num_corners
            )

            self.calibration_started.emit("tilt")
            return True

        except Exception as e:
            error_msg = f"Failed to start tilt calibration: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return False

    def measure_tilt_corner(self, corner_idx: int,
                           autofocus: bool = True) -> bool:
        """Measure tilt calibration corner.

        Args:
            corner_idx: Index of corner to measure
            autofocus: Perform autofocus at corner

        Returns:
            True if measurement successful

        Emits:
            corner_measured: When corner measured
            focus_found: When autofocus completes (if enabled)
        """
        if self._tilt_calibrator is None:
            self.calibration_error.emit("Tilt calibration not started")
            return False

        try:
            # Get target corner position
            target_corners = self._tilt_calibrator.target_corners
            if corner_idx >= len(target_corners):
                self.calibration_error.emit("Invalid corner index")
                return False

            x, y = target_corners[corner_idx]

            self._logger.info(f"Measuring corner {corner_idx + 1} at ({x}, {y})")

            # Move to corner
            self.stage.move_absolute(x=x, y=y, wait=True)
            time.sleep(0.2)

            # Autofocus if requested
            if autofocus:
                z = self.autofocus_at_position()
                if z is None:
                    self.calibration_error.emit("Autofocus failed")
                    return False
                self.focus_found.emit(z)
            else:
                z = self.stage.model.get_z_position()

            # Add measurement
            self._tilt_calibrator.add_corner_measurement(x, y, z)

            self._logger.info(f"Corner measured: ({x}, {y}, {z})")
            self.corner_measured.emit(
                len(self._tilt_calibrator.measured_corners),
                self._tilt_calibrator.num_corners
            )

            return True

        except Exception as e:
            error_msg = f"Corner measurement failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return False

    def complete_tilt_calibration(self) -> bool:
        """Complete tilt calibration and calculate plane.

        Returns:
            True if calibration successful

        Emits:
            calibration_completed: When calibration completes
        """
        if self._tilt_calibrator is None:
            self.calibration_error.emit("Tilt calibration not started")
            return False

        try:
            # Check if all corners measured
            if not self._tilt_calibrator.is_complete():
                self.calibration_error.emit(
                    f"Not all corners measured: "
                    f"{len(self._tilt_calibrator.measured_corners)}/"
                    f"{self._tilt_calibrator.num_corners}"
                )
                return False

            # Calculate calibration
            success = self._tilt_calibrator.calculate()
            if not success:
                self.calibration_error.emit("Tilt calibration calculation failed")
                return False

            # Update model
            corners = self._tilt_calibrator.measured_corners
            self.model.set_tilt_corners(corners)

            self._logger.info(
                f"Tilt calibration complete: "
                f"angles=({self._tilt_calibrator.tilt_angles[0]:.3f}, "
                f"{self._tilt_calibrator.tilt_angles[1]:.3f}) degrees"
            )

            self.calibration_completed.emit("tilt")
            return True

        except Exception as e:
            error_msg = f"Tilt calibration failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return False

    def autofocus_at_position(self,
                             search_range: float = 1.0,
                             step_size: float = 0.05,
                             method: str = "sobel") -> Optional[float]:
        """Perform autofocus at current position.

        Args:
            search_range: Z search range in mm
            step_size: Initial step size in mm
            method: Sharpness calculation method

        Returns:
            Best focus Z position or None on failure

        Emits:
            focus_found: When focus found
        """
        if not self.camera.is_acquiring:
            self.calibration_error.emit("Camera not acquiring")
            return None

        try:
            current_z = self.stage.model.get_z_position()

            self._logger.info(f"Starting autofocus at Z={current_z}")

            # Capture function for autofocus
            def capture_at_z(z: float):
                self.stage.move_absolute(z=z, wait=True)
                time.sleep(0.1)
                image = self.camera.capture_image()
                return image

            # Perform iterative autofocus
            best_z, peak_sharpness = autofocus_iterative(
                current_z=current_z,
                capture_func=capture_at_z,
                step_size=step_size,
                tolerance=0.01,
                method=method
            )

            # Move to best focus
            self.stage.move_absolute(z=best_z, wait=True)

            # Update model
            self.model.autofocus_data.best_focus_z = best_z
            self.model.autofocus_data.peak_sharpness = peak_sharpness

            self._logger.info(
                f"Autofocus complete: Z={best_z:.3f}, "
                f"sharpness={peak_sharpness:.2f}"
            )

            self.focus_found.emit(best_z)
            return best_z

        except Exception as e:
            error_msg = f"Autofocus failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return None

    def quick_autofocus(self, num_steps: int = 20,
                       search_range: float = 2.0) -> Optional[float]:
        """Perform quick autofocus scan.

        This implements the getSharp() method from original Ui.py.

        Args:
            num_steps: Number of Z steps
            search_range: Total search range in mm

        Returns:
            Best focus Z position or None on failure
        """
        if not self.camera.is_acquiring:
            self.calibration_error.emit("Camera not acquiring")
            return None

        try:
            current_z = self.stage.model.get_z_position()
            start_z = current_z - search_range / 2

            self._logger.info(f"Quick autofocus: {num_steps} steps over {search_range}mm")

            z_positions = []
            images = []

            # Capture images at each Z position
            for i in range(num_steps):
                z = start_z + (i * search_range / num_steps)
                self.stage.move_absolute(z=z, wait=True)
                time.sleep(0.05)

                image = self.camera.capture_image()
                if image is not None:
                    z_positions.append(z)
                    images.append(image)

                self.progress_updated.emit(i + 1, num_steps)

            # Find best focus
            if not z_positions:
                self.calibration_error.emit("No images captured")
                return None

            best_z, sharpness_values = autofocus_search(
                z_positions,
                images,
                method="sobel"
            )

            # Move to best focus
            self.stage.move_absolute(z=best_z, wait=True)

            # Update model
            self.model.update_autofocus(z_positions, sharpness_values)

            self._logger.info(f"Quick autofocus complete: Z={best_z:.3f}")

            self.focus_found.emit(best_z)
            return best_z

        except Exception as e:
            error_msg = f"Quick autofocus failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return None

    def enable_tilt_correction(self, enabled: bool) -> None:
        """Enable/disable tilt correction.

        Args:
            enabled: True to enable tilt correction
        """
        self.model.enable_tilt_correction(enabled)
        self._logger.info(f"Tilt correction {'enabled' if enabled else 'disabled'}")

    def get_tilt_correction(self, x: float, y: float) -> float:
        """Get tilt correction for position.

        Args:
            x: X position
            y: Y position

        Returns:
            Z correction value
        """
        return self.model.get_tilt_correction(x, y)

    def add_magnetic_calibration_point(self, x: float, y: float, z: float) -> None:
        """Add magnetic calibration point.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.model.add_magnetic_position(x, y, z)
        self._logger.debug(f"Added magnetic calibration point: ({x}, {y}, {z})")

    def export_calibration(self, filepath: str) -> bool:
        """Export calibration data to file.

        Args:
            filepath: Output file path

        Returns:
            True if export successful
        """
        try:
            self.model.export_calibration(filepath)
            self._logger.info(f"Calibration exported to {filepath}")
            return True
        except Exception as e:
            error_msg = f"Calibration export failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return False

    def import_calibration(self, filepath: str) -> bool:
        """Import calibration data from file.

        Args:
            filepath: Input file path

        Returns:
            True if import successful
        """
        try:
            success = self.model.import_calibration(filepath)
            if success:
                self._logger.info(f"Calibration imported from {filepath}")
            else:
                self.calibration_error.emit("Failed to import calibration")
            return success
        except Exception as e:
            error_msg = f"Calibration import failed: {e}"
            self._logger.error(error_msg)
            self.calibration_error.emit(error_msg)
            return False

    @property
    def is_tilt_calibrated(self) -> bool:
        """Check if tilt calibration is valid."""
        return self.model.tilt_calibration.is_valid

    @property
    def is_tilt_enabled(self) -> bool:
        """Check if tilt correction is enabled."""
        return self.model.tilt_enabled

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._tilt_calibrator = None
