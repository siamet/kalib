"""Simulated LED controller acting on a shared SimWorld."""

from typing import Optional, Tuple

from kalib.hardware.base import HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimLED(HardwareDevice):
    """LED simulator mirroring the public API of LEDDriver.

    Example:
        led = SimLED(SimWorld())
        led.connect()
        led.set_brightness(128)
    """

    def __init__(self, world: SimWorld, port: Optional[str] = None,
                 name: Optional[str] = None,
                 brightness_range: Tuple[int, int] = (0, 255),
                 default_brightness: int = 128):
        """Initialize the simulated LED controller.

        Args:
            world: Shared simulated instrument state
            port: Present for parity with LEDDriver
            name: Human-readable device name
            brightness_range: (minimum, maximum) brightness in device units
            default_brightness: Brightness set on initialize, mirroring
                LEDDriver's default_brightness
        """
        super().__init__(device_id=port or "SIM-LED", name=name or "Sim_LED")
        self._world = world
        self._port = port or "SIM-LED"
        self._range = brightness_range
        self._default_brightness = default_brightness

    def _do_connect(self) -> None:
        """Connect to the simulated LED controller."""
        self._device_info = {'model': 'SimLED', 'port': self._port}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated LED controller."""

    def _do_initialize(self) -> None:
        """Initialize the simulated LED controller."""
        self._world.led_brightness = self._default_brightness

    def set_brightness(self, brightness: int) -> None:
        """Set brightness in raw device units.

        Args:
            brightness: Target brightness (clamped to configured range)
        """
        self._check_connected()
        low, high = self._range
        brightness_int = int(brightness)
        brightness_clamped = max(low, min(high, brightness_int))
        if brightness_int != brightness_clamped:
            self._logger.warning(
                f"Brightness {brightness_int} clamped to {brightness_clamped}. "
                f"Valid range: [{low}, {high}]"
            )
        self._world.led_brightness = brightness_clamped

    def get_brightness(self) -> int:
        """Return brightness in raw device units."""
        return self._world.led_brightness

    def set_brightness_percent(self, percent: float) -> None:
        """Set brightness as a percentage of the configured range."""
        low, high = self._range
        self.set_brightness(int(low + (high - low) * percent / 100.0))

    def get_brightness_percent(self) -> float:
        """Return brightness as a percentage of the configured range."""
        low, high = self._range
        return (self.get_brightness() - low) / (high - low) * 100.0

    def get_current_ma(self) -> float:
        """Return estimated drive current in milliamps.

        Uses the same formula as LEDDriver.get_current_ma so calibration
        performed in simulation matches the instrument.
        """
        return self.get_brightness() / 4096 * 293

    def turn_off(self) -> None:
        """Switch the LED off."""
        self.set_brightness(self._range[0])

    def turn_on(self, brightness: Optional[int] = None) -> None:
        """Switch the LED on.

        Args:
            brightness: Level to use; defaults to the current brightness
        """
        self.set_brightness(self.get_brightness() if brightness is None else brightness)

    @property
    def brightness_range(self) -> Tuple[int, int]:
        """Configured brightness range."""
        return self._range

    @property
    def port(self) -> Optional[str]:
        """Simulated port name."""
        return self._port
