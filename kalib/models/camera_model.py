"""Camera model for state management and configuration.

Manages camera state, settings, and image buffer.
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass
class CameraSettings:
    """Camera configuration settings."""
    exposure_time: float = 15000.0  # microseconds
    gain: float = 1.0
    fps: float = 30.0
    pixel_format: str = "RGB8"
    auto_exposure: bool = False


@dataclass
class CameraState:
    """Camera operational state."""
    is_connected: bool = False
    is_acquiring: bool = False
    frame_count: int = 0
    error_count: int = 0
    last_capture_time: Optional[datetime] = None
    resolution: Optional[Tuple[int, int]] = None


class CameraModel:
    """Camera data model.

    Manages camera state, settings, and provides access to
    captured images.
    """

    def __init__(self, settings: Optional[CameraSettings] = None):
        """Initialize camera model.

        Args:
            settings: Initial camera settings
        """
        self.settings = settings or CameraSettings()
        self.state = CameraState()
        self._current_image: Optional[np.ndarray] = None
        self._image_buffer: List[np.ndarray] = []
        self._max_buffer_size = 100

    def update_settings(self, **kwargs) -> None:
        """Update camera settings.

        Args:
            **kwargs: Setting name-value pairs
        """
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

    def set_connected(self, connected: bool) -> None:
        """Set connection state."""
        self.state.is_connected = connected
        if not connected:
            self.state.is_acquiring = False

    def set_acquiring(self, acquiring: bool) -> None:
        """Set acquisition state."""
        self.state.is_acquiring = acquiring

    def add_image(self, image: np.ndarray) -> None:
        """Add captured image to buffer.

        Args:
            image: Captured image as numpy array
        """
        self._current_image = image
        self.state.frame_count += 1
        self.state.last_capture_time = datetime.now()

        # Add to buffer with size limit
        self._image_buffer.append(image)
        if len(self._image_buffer) > self._max_buffer_size:
            self._image_buffer.pop(0)

    def get_current_image(self) -> Optional[np.ndarray]:
        """Get most recent captured image.

        Returns:
            Current image or None if no image captured
        """
        return self._current_image

    def get_image_buffer(self) -> List[np.ndarray]:
        """Get list of buffered images.

        Returns:
            List of captured images
        """
        return self._image_buffer.copy()

    def clear_buffer(self) -> None:
        """Clear image buffer."""
        self._image_buffer.clear()

    def increment_error_count(self) -> None:
        """Increment error counter."""
        self.state.error_count += 1

    def reset_counters(self) -> None:
        """Reset frame and error counters."""
        self.state.frame_count = 0
        self.state.error_count = 0

    def set_resolution(self, width: int, height: int) -> None:
        """Set camera resolution.

        Args:
            width: Image width in pixels
            height: Image height in pixels
        """
        self.state.resolution = (width, height)

    def get_fps_actual(self) -> float:
        """Calculate actual FPS from capture times.

        Returns:
            Actual frames per second
        """
        if self.state.frame_count < 2:
            return 0.0

        # Calculate from last N frames
        # This is a simplified calculation
        return self.settings.fps  # TODO: Calculate from timestamps

    @property
    def is_ready(self) -> bool:
        """Check if camera is ready to capture.

        Returns:
            True if connected and acquiring
        """
        return self.state.is_connected and self.state.is_acquiring

    def to_dict(self) -> dict:
        """Convert model to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'settings': {
                'exposure_time': self.settings.exposure_time,
                'gain': self.settings.gain,
                'fps': self.settings.fps,
                'pixel_format': self.settings.pixel_format,
            },
            'state': {
                'is_connected': self.state.is_connected,
                'is_acquiring': self.state.is_acquiring,
                'frame_count': self.state.frame_count,
                'error_count': self.state.error_count,
                'resolution': self.state.resolution,
            }
        }
