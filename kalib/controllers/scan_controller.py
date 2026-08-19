"""Scan controller for managing scanning operations.

Coordinates camera and stage controllers to perform XY scans,
Z-stacks, and SFF scanning using QThread for background processing.
"""

from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread
import time

from kalib.models import ScanModel, ScanType, ScanState, XYScanParameters, ZStackParameters
from kalib.algorithms import calculate_sharpness
from kalib.utils.logger import get_logger
from kalib.utils.image_utils import save_image


class ScanWorker(QObject):
    """Worker thread for scanning operations."""

    # Signals
    progress_updated = Signal(int, int)  # current, total
    position_reached = Signal(float, float, float)  # x, y, z
    image_captured = Signal(object)  # image
    scan_completed = Signal()
    scan_error = Signal(str)

    def __init__(self, scan_model: ScanModel,
                 camera_controller, stage_controller):
        """Initialize scan worker.

        Args:
            scan_model: Scan model with parameters
            camera_controller: Camera controller instance
            stage_controller: Stage controller instance
        """
        super().__init__()

        self.scan_model = scan_model
        self.camera = camera_controller
        self.stage = stage_controller
        self._logger = get_logger(__name__)
        self._cancel_requested = False

    def cancel(self) -> None:
        """Request scan cancellation."""
        self._cancel_requested = True

    def run_xy_scan(self) -> None:
        """Execute XY scan."""
        try:
            params = self.scan_model.xy_params
            if params is None:
                self.scan_error.emit("No XY scan parameters configured")
                return

            self._logger.info(
                f"Starting XY scan: {params.num_steps_x}x{params.num_steps_y}"
            )

            # Generate grid positions
            positions = self.scan_model.generate_xy_grid()

            # Scan loop
            for idx, (x, y) in enumerate(positions):
                if self._cancel_requested:
                    self._logger.info("Scan cancelled by user")
                    break

                # Move to position
                self.stage.move_absolute(x=x, y=y, wait=True)
                time.sleep(0.1)  # Small delay for stage to settle

                # Update progress
                self.position_reached.emit(x, y, self.stage.model.get_z_position())

                # Capture image
                image = self.camera.capture_image()
                if image is None:
                    self._logger.warning(f"Failed to capture at ({x}, {y})")
                    self.scan_model.increment_error_count()
                    continue

                # Calculate sharpness if needed
                sharpness = calculate_sharpness(image, method="gradient")

                # Save image if configured
                if self.scan_model.save_individual_frames and self.scan_model.save_path:
                    filename = f"{self.scan_model.save_path}/scan_{idx:04d}.tiff"
                    save_image(image, filename)

                # Add to model
                self.scan_model.add_scan_position(
                    position=(x, y),
                    image=image,
                    sharpness=sharpness
                )

                # Emit signals
                self.image_captured.emit(image)
                self.progress_updated.emit(idx + 1, len(positions))

            # Complete
            if not self._cancel_requested:
                self.scan_model.complete_scan()
                self._logger.info("XY scan completed")
                self.scan_completed.emit()
            else:
                self.scan_model.cancel_scan()

        except Exception as e:
            error_msg = f"XY scan error: {e}"
            self._logger.error(error_msg, exc_info=True)
            self.scan_model.error_scan()
            self.scan_error.emit(error_msg)

    def run_z_stack(self) -> None:
        """Execute Z-stack scan."""
        try:
            params = self.scan_model.z_params
            if params is None:
                self.scan_error.emit("No Z-stack parameters configured")
                return

            self._logger.info(f"Starting Z-stack: {params.num_steps} steps")

            # Generate Z positions
            z_positions = self.scan_model.generate_z_positions()

            # Get current XY position
            x, y, _ = self.stage.get_position()

            # Scan loop
            for idx, z in enumerate(z_positions):
                if self._cancel_requested:
                    self._logger.info("Scan cancelled by user")
                    break

                # Move to Z position
                self.stage.move_absolute(z=z, wait=True)
                time.sleep(0.1)

                # Update progress
                self.position_reached.emit(x, y, z)

                # Capture image
                image = self.camera.capture_image()
                if image is None:
                    self._logger.warning(f"Failed to capture at Z={z}")
                    self.scan_model.increment_error_count()
                    continue

                # Calculate sharpness
                sharpness = calculate_sharpness(image, method="sobel")

                # Save image if configured
                if self.scan_model.save_individual_frames and self.scan_model.save_path:
                    filename = f"{self.scan_model.save_path}/zstack_{idx:04d}.tiff"
                    save_image(image, filename)

                # Add to model
                self.scan_model.add_scan_position(
                    position=(x, y, z),
                    image=image,
                    sharpness=sharpness
                )

                # Emit signals
                self.image_captured.emit(image)
                self.progress_updated.emit(idx + 1, len(z_positions))

            # Complete
            if not self._cancel_requested:
                self.scan_model.complete_scan()
                self._logger.info("Z-stack completed")
                self.scan_completed.emit()
            else:
                self.scan_model.cancel_scan()

        except Exception as e:
            error_msg = f"Z-stack error: {e}"
            self._logger.error(error_msg, exc_info=True)
            self.scan_model.error_scan()
            self.scan_error.emit(error_msg)


class ScanController(QObject):
    """Scan controller.

    Manages scanning workflows (XY, Z-stack, SFF) by coordinating
    camera and stage controllers.
    """

    # Qt Signals
    scan_started = Signal(str)  # scan type
    scan_completed = Signal()
    scan_cancelled = Signal()
    scan_error = Signal(str)
    progress_updated = Signal(int, int)  # current, total
    position_reached = Signal(float, float, float)  # x, y, z
    image_captured = Signal(object)  # image

    def __init__(self, camera_controller, stage_controller):
        """Initialize scan controller.

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
        self.model = ScanModel()

        # Threading
        self._scan_thread: Optional[QThread] = None
        self._scan_worker: Optional[ScanWorker] = None

    def configure_xy_scan(self, params: XYScanParameters) -> None:
        """Configure XY scan.

        Args:
            params: XY scan parameters
        """
        self.model.configure_xy_scan(params)
        self._logger.info(f"Configured XY scan: {params.total_positions} positions")

    def configure_z_stack(self, params: ZStackParameters) -> None:
        """Configure Z-stack scan.

        Args:
            params: Z-stack parameters
        """
        self.model.configure_z_stack(params)
        self._logger.info(f"Configured Z-stack: {params.total_positions} positions")

    def start_scan(self, save_path: Optional[str] = None) -> bool:
        """Start configured scan.

        Args:
            save_path: Path to save images (None to not save)

        Returns:
            True if scan started

        Emits:
            scan_started: When scan begins
            scan_error: If scan cannot start
        """
        # Check prerequisites
        if not self.camera.is_acquiring:
            self.scan_error.emit("Camera acquisition not running")
            return False

        if not self.stage.is_connected:
            self.scan_error.emit("Stage not connected")
            return False

        if not self.model.can_start:
            self.scan_error.emit("Scan not properly configured")
            return False

        # Check if scan already running
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self.scan_error.emit("Scan already running")
            return False

        try:
            # Set save path
            self.model.save_path = save_path

            # Start scan
            self.model.start_scan()

            # Create worker and thread
            self._scan_worker = ScanWorker(self.model, self.camera, self.stage)
            self._scan_thread = QThread()

            # Move worker to thread
            self._scan_worker.moveToThread(self._scan_thread)

            # Connect signals
            self._scan_worker.progress_updated.connect(self.progress_updated.emit)
            self._scan_worker.position_reached.connect(self.position_reached.emit)
            self._scan_worker.image_captured.connect(self.image_captured.emit)
            self._scan_worker.scan_completed.connect(self._on_scan_completed)
            self._scan_worker.scan_error.connect(self._on_scan_error)

            # Connect thread signals
            if self.model.scan_type == ScanType.XY_SCAN:
                self._scan_thread.started.connect(self._scan_worker.run_xy_scan)
            elif self.model.scan_type == ScanType.Z_STACK:
                self._scan_thread.started.connect(self._scan_worker.run_z_stack)

            # Start thread
            self._scan_thread.start()

            self._logger.info(f"Started {self.model.scan_type.value} scan")
            self.scan_started.emit(self.model.scan_type.value)
            return True

        except Exception as e:
            error_msg = f"Failed to start scan: {e}"
            self._logger.error(error_msg)
            self.scan_error.emit(error_msg)
            return False

    def pause_scan(self) -> bool:
        """Pause running scan.

        Returns:
            True if paused
        """
        if self.model.is_running:
            self.model.pause_scan()
            self._logger.info("Scan paused")
            return True
        return False

    def resume_scan(self) -> bool:
        """Resume paused scan.

        Returns:
            True if resumed
        """
        if self.model.state == ScanState.PAUSED:
            self.model.resume_scan()
            self._logger.info("Scan resumed")
            return True
        return False

    def cancel_scan(self) -> bool:
        """Cancel running scan.

        Returns:
            True if cancelled

        Emits:
            scan_cancelled: When scan is cancelled
        """
        if self._scan_worker is not None:
            self._scan_worker.cancel()
            self._logger.info("Scan cancellation requested")
            return True
        return False

    def _on_scan_completed(self) -> None:
        """Handle scan completion."""
        self._cleanup_thread()
        self._logger.info("Scan completed successfully")
        self.scan_completed.emit()

    def _on_scan_error(self, error_msg: str) -> None:
        """Handle scan error.

        Args:
            error_msg: Error message
        """
        self._cleanup_thread()
        self._logger.error(f"Scan error: {error_msg}")
        self.scan_error.emit(error_msg)

    def _cleanup_thread(self) -> None:
        """Cleanup scan thread and worker."""
        if self._scan_thread is not None:
            self._scan_thread.quit()
            self._scan_thread.wait()
            self._scan_thread = None

        self._scan_worker = None

    @property
    def is_scanning(self) -> bool:
        """Check if scan is running."""
        return self.model.is_running

    @property
    def scan_progress(self) -> float:
        """Get scan progress percentage."""
        return self.model.progress.percent_complete

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.cancel_scan()
        self._cleanup_thread()
