"""Camera controller for managing camera operations.

Coordinates camera hardware with camera model and provides
workflow management for image capture operations.
"""

from typing import Optional
from PySide6.QtCore import QObject, Signal
import numpy as np

from kalib.hardware import IDSCamera, ConnectionError, CommandError
from kalib.models import CameraModel, CameraSettings
from kalib.utils.logger import get_logger


class CameraController(QObject):
    """Camera controller.

    Manages camera lifecycle, settings, and image capture operations
    with Qt signal/slot integration.
    """

    # Qt Signals
    connected = Signal()
    disconnected = Signal()
    acquisition_started = Signal()
    acquisition_stopped = Signal()
    image_captured = Signal(object)  # np.ndarray
    error_occurred = Signal(str)
    settings_changed = Signal(dict)

    def __init__(self,
                 device_idx: int = 0,
                 settings: Optional[CameraSettings] = None):
        """Initialize camera controller.

        Args:
            device_idx: Camera device index
            settings: Initial camera settings
        """
        super().__init__()

        self._logger = get_logger(__name__)
        self._device_idx = device_idx

        # Models and hardware
        self.model = CameraModel(settings or CameraSettings())
        self._camera: Optional[IDSCamera] = None

    def connect_camera(self) -> bool:
        """Connect to camera.

        Returns:
            True if connection successful

        Emits:
            connected: On successful connection
            error_occurred: On connection failure
        """
        try:
            self._logger.info(f"Connecting to camera {self._device_idx}")

            # Create camera instance
            pixel_format = (8, "RGB")  # TODO: Get from settings
            self._camera = IDSCamera(
                device_idx=self._device_idx,
                pixel_format=pixel_format
            )

            # Connect
            self._camera.connect()

            # Update model
            self.model.set_connected(True)
            width, height = self._camera.get_resolution()
            self.model.set_resolution(width, height)

            # Apply initial settings
            self._apply_settings()

            self._logger.info("Camera connected successfully")
            self.connected.emit()
            return True

        except ConnectionError as e:
            error_msg = f"Camera connection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def disconnect_camera(self) -> bool:
        """Disconnect from camera.

        Returns:
            True if disconnection successful

        Emits:
            disconnected: On successful disconnection
        """
        try:
            if self._camera is None:
                return True

            self._logger.info("Disconnecting camera")

            # Stop acquisition if running
            if self.model.state.is_acquiring:
                self.stop_acquisition()

            # Disconnect
            self._camera.disconnect()
            self._camera = None

            # Update model
            self.model.set_connected(False)

            self._logger.info("Camera disconnected")
            self.disconnected.emit()
            return True

        except Exception as e:
            error_msg = f"Camera disconnection failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def start_acquisition(self) -> bool:
        """Start image acquisition.

        Returns:
            True if acquisition started

        Emits:
            acquisition_started: On successful start
            error_occurred: On failure
        """
        if self._camera is None:
            self.error_occurred.emit("Camera not connected")
            return False

        try:
            self._logger.info("Starting acquisition")
            self._camera.start_acquisition()

            self.model.set_acquiring(True)

            self._logger.info("Acquisition started")
            self.acquisition_started.emit()
            return True

        except CommandError as e:
            error_msg = f"Failed to start acquisition: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def stop_acquisition(self) -> bool:
        """Stop image acquisition.

        Returns:
            True if acquisition stopped

        Emits:
            acquisition_stopped: On successful stop
        """
        if self._camera is None:
            return True

        try:
            self._logger.info("Stopping acquisition")
            self._camera.stop_acquisition()

            self.model.set_acquiring(False)

            self._logger.info("Acquisition stopped")
            self.acquisition_stopped.emit()
            return True

        except Exception as e:
            error_msg = f"Failed to stop acquisition: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def capture_image(self, timeout_ms: int = 1000) -> Optional[np.ndarray]:
        """Capture single image.

        Args:
            timeout_ms: Capture timeout in milliseconds

        Returns:
            Captured image or None on failure

        Emits:
            image_captured: On successful capture
            error_occurred: On capture failure
        """
        if self._camera is None:
            self.error_occurred.emit("Camera not connected")
            return None

        if not self.model.state.is_acquiring:
            self.error_occurred.emit("Acquisition not running")
            return None

        try:
            # Capture image
            image = self._camera.capture(timeout_ms=timeout_ms)

            # Update model
            self.model.add_image(image)

            # Emit signal
            self.image_captured.emit(image)

            return image

        except Exception as e:
            error_msg = f"Image capture failed: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            self.model.increment_error_count()
            return None

    def set_exposure_time(self, exposure_us: float) -> bool:
        """Set exposure time.

        Args:
            exposure_us: Exposure time in microseconds

        Returns:
            True if successful

        Emits:
            settings_changed: On successful change
        """
        if self._camera is None:
            self.error_occurred.emit("Camera not connected")
            return False

        try:
            self._camera.set_exposure_time(exposure_us)
            self.model.update_settings(exposure_time=exposure_us)

            self.settings_changed.emit({'exposure_time': exposure_us})
            return True

        except CommandError as e:
            error_msg = f"Failed to set exposure: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def set_gain(self, gain: float) -> bool:
        """Set camera gain.

        Args:
            gain: Gain value

        Returns:
            True if successful

        Emits:
            settings_changed: On successful change
        """
        if self._camera is None:
            self.error_occurred.emit("Camera not connected")
            return False

        try:
            self._camera.set_gain(gain)
            self.model.update_settings(gain=gain)

            self.settings_changed.emit({'gain': gain})
            return True

        except CommandError as e:
            error_msg = f"Failed to set gain: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def set_fps(self, fps: float) -> bool:
        """Set frames per second.

        Args:
            fps: Target FPS

        Returns:
            True if successful

        Emits:
            settings_changed: On successful change
        """
        if self._camera is None:
            self.error_occurred.emit("Camera not connected")
            return False

        try:
            self._camera.set_fps(fps)
            self.model.update_settings(fps=fps)

            self.settings_changed.emit({'fps': fps})
            return True

        except CommandError as e:
            error_msg = f"Failed to set FPS: {e}"
            self._logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False

    def get_current_settings(self) -> dict:
        """Get current camera settings.

        Returns:
            Dictionary of current settings
        """
        if self._camera is None:
            return {}

        try:
            settings = {
                'exposure_time': self._camera.get_exposure_time(),
                'gain': self._camera.get_gain(),
                'fps': self._camera.get_fps(),
                'resolution': self._camera.get_resolution(),
            }
            return settings

        except Exception as e:
            self._logger.error(f"Failed to get settings: {e}")
            return {}

    def _apply_settings(self) -> None:
        """Apply model settings to hardware."""
        if self._camera is None:
            return

        try:
            settings = self.model.settings
            self._camera.set_exposure_time(settings.exposure_time)
            self._camera.set_gain(settings.gain)
            self._camera.set_fps(settings.fps)

            self._logger.debug("Applied camera settings")

        except Exception as e:
            self._logger.error(f"Failed to apply settings: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if camera is connected."""
        return self.model.state.is_connected

    @property
    def is_acquiring(self) -> bool:
        """Check if acquisition is running."""
        return self.model.state.is_acquiring

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.disconnect_camera()
