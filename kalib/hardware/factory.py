"""Build real or simulated hardware devices according to configuration."""

from typing import Any, Optional, Tuple

from kalib.hardware.base import ConfigurationError, HardwareDevice
from kalib.hardware.sim.world import SimWorld

REAL = 'real'
SIM = 'sim'
BACKENDS = (REAL, SIM)


class HardwareFactory:
    """Construct hardware devices for the configured backend.

    With the 'sim' backend every device is a simulator, and all of them
    share one SimWorld so that moving a stage changes what the camera sees.

    Example:
        factory = HardwareFactory(settings)
        camera = factory.create_camera()
    """

    def __init__(self, settings: Any, world: Optional[SimWorld] = None):
        """Initialize the factory.

        Args:
            settings: Object with a get(key, default) method
            world: Shared simulated state; created automatically when omitted

        Raises:
            ConfigurationError: If the configured backend is not recognised
        """
        self._settings = settings
        self._backend = settings.get('hardware.backend', REAL)
        if self._backend not in BACKENDS:
            raise ConfigurationError(
                f"Unknown hardware backend '{self._backend}'. "
                f"Expected one of: {', '.join(BACKENDS)}")
        self._world = world or SimWorld()

    @property
    def backend(self) -> str:
        """Configured backend name."""
        return self._backend

    @property
    def world(self) -> SimWorld:
        """Shared simulated state, used only by the 'sim' backend."""
        return self._world

    def create_camera(self, device_idx: int = 0) -> HardwareDevice:
        """Build a camera for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_camera import SimCamera
            return SimCamera(self._world, device_idx=device_idx)
        from kalib.hardware.ids_camera import IDSCamera
        return IDSCamera(device_idx=device_idx, pixel_format=(8, "RGB"))

    def create_stage_xy(self, device_id: Optional[str] = None,
                        x_range: Optional[Tuple[float, float]] = None,
                        y_range: Optional[Tuple[float, float]] = None
                        ) -> HardwareDevice:
        """Build an XY stage for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_stage import SimStageXY
            return SimStageXY(self._world, device_id=device_id,
                              x_range=x_range or (0.0, 100.0),
                              y_range=y_range or (0.0, 100.0))
        from kalib.hardware.pi_stage_xy import PIStageXY
        kwargs = {}
        if x_range is not None:
            kwargs['x_range'] = x_range
        if y_range is not None:
            kwargs['y_range'] = y_range
        return PIStageXY(device_id=device_id, **kwargs)

    def create_stage_z(self, device_id: Optional[str] = None,
                       z_range: Optional[Tuple[float, float]] = None
                       ) -> HardwareDevice:
        """Build a Z stage for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_stage import SimStageZ
            return SimStageZ(self._world, device_id=device_id,
                             z_range=z_range or (0.0, 10.0))
        from kalib.hardware.pi_stage_z import PIStageZ
        kwargs = {}
        if z_range is not None:
            kwargs['z_range'] = z_range
        return PIStageZ(device_id=device_id, **kwargs)

    def create_led(self, port: Optional[str] = None) -> HardwareDevice:
        """Build an LED controller for the configured backend.

        Both backends are built from the same configured brightness range
        and default brightness, so code calibrated against one starts from
        the same scale on the other.
        """
        brightness_range = tuple(
            self._settings.get('led.brightness_range', (0, 255)))
        default_brightness = self._settings.get('led.default_brightness', 128)

        if self._backend == SIM:
            from kalib.hardware.sim.sim_led import SimLED
            return SimLED(self._world, port=port,
                          brightness_range=brightness_range,
                          default_brightness=default_brightness)
        from kalib.hardware.led_driver import LEDDriver
        return LEDDriver(port=port, brightness_range=brightness_range,
                         default_brightness=default_brightness)
