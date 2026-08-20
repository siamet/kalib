"""Simulated camera producing synthetic frames that respond to focus."""

from typing import List, Optional, Tuple

import cv2
import numpy as np

from kalib.hardware.base import CommandError, ConnectionError, HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimCamera(HardwareDevice):
    """Camera simulator mirroring the public API of IDSCamera.

    Renders a fixed synthetic sample and blurs it in proportion to how far
    the simulated stage is from the focal plane, so focus-dependent code
    behaves as it would on the instrument.

    Example:
        world = SimWorld()
        camera = SimCamera(world)
        camera.connect()
        camera.start_acquisition()
        frame = camera.capture()
    """

    BLUR_PER_UM = 6.0  # Gaussian sigma in pixels per um of defocus

    def __init__(self, world: SimWorld, device_idx: int = 0,
                 name: Optional[str] = None):
        """Initialize the simulated camera.

        Args:
            world: Shared simulated instrument state
            device_idx: Present for parity with IDSCamera; unused
            name: Human-readable device name
        """
        super().__init__(device_id=f"SIM-CAM-{device_idx}",
                         name=name or "Sim_Camera")
        self._world = world
        self._device_idx = device_idx
        self._exposure_us = 15000.0
        self._gain = 1.0
        self._fps = 30.0
        self._acquiring = False
        self._pattern = self._make_pattern()

    def _make_pattern(self) -> np.ndarray:
        """Build a fixed high-frequency sample pattern.

        Returns:
            Greyscale image of shape (height, width), dtype uint8
        """
        rng = np.random.default_rng(self._world.seed)
        noise = rng.integers(0, 256,
                             size=(self._world.height, self._world.width),
                             dtype=np.uint8)
        return cv2.GaussianBlur(noise, (3, 3), 0.8)

    def _do_connect(self) -> None:
        """Connect to the simulated camera."""
        self._device_info = {'model': 'SimCamera', 'serial': self._device_id,
                             'index': self._device_idx}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated camera."""
        self._acquiring = False

    def _do_initialize(self) -> None:
        """Initialize the simulated camera after connection."""
        self._pattern = self._make_pattern()

    def start_acquisition(self) -> None:
        """Begin acquisition."""
        self._check_connected()
        self._acquiring = True

    def stop_acquisition(self) -> None:
        """End acquisition."""
        self._acquiring = False

    @property
    def is_acquisition_running(self) -> bool:
        """Return whether acquisition is active."""
        return self._acquiring

    def capture(self, timeout_ms: int = 1000,
                force_8bit: bool = False) -> np.ndarray:
        """Capture one synthetic frame.

        Args:
            timeout_ms: Accepted for API parity; the simulator never blocks
            force_8bit: Accepted for API parity; frames are always 8-bit

        Returns:
            Greyscale frame of shape (height, width), dtype uint8

        Raises:
            CommandError: If acquisition has not been started
            ConnectionError: If device is not connected
        """
        self._check_connected()
        if not self._acquiring:
            raise CommandError("Acquisition not ready. Call start_acquisition() first.")

        sigma = self._world.defocus() * self.BLUR_PER_UM
        frame = self._pattern
        if sigma > 0.05:
            frame = cv2.GaussianBlur(frame, (0, 0), sigma)

        scale = self._exposure_us / 15000.0 * self._gain
        return np.clip(frame.astype(np.float32) * scale, 0, 255).astype(np.uint8)

    def set_exposure_time(self, exposure_us: float) -> None:
        """Set exposure time in microseconds."""
        self._exposure_us = float(exposure_us)

    def get_exposure_time(self) -> float:
        """Return exposure time in microseconds."""
        return self._exposure_us

    def set_gain(self, gain: float) -> None:
        """Set analogue gain."""
        self._gain = float(gain)

    def get_gain(self) -> float:
        """Return analogue gain."""
        return self._gain

    def set_fps(self, fps: float) -> None:
        """Set target frame rate."""
        self._fps = float(fps)

    def get_fps(self) -> float:
        """Return target frame rate."""
        return self._fps

    def get_resolution(self) -> Tuple[int, int]:
        """Return sensor resolution as (width, height)."""
        return (self._world.width, self._world.height)

    def get_available_pixel_formats(self) -> List[str]:
        """Return supported pixel formats."""
        return ['Mono8']
