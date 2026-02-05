"""LED Light driver with serial communication.

Provides high-level interface to LED illumination system via serial port
with brightness control and state persistence.
"""

from typing import Optional, List
import time

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    serial = None

from kalib.hardware.base import (
    HardwareDevice,
    ConnectionError,
    CommandError,
    ConfigurationError,
    TimeoutError
)


def _encode_led_value(value: int) -> bytes:
    """Encode LED brightness value for serial transmission.

    This is a placeholder implementation. The actual encoding should match
    the LED controller's protocol. Based on observed usage, it appears to
    send a formatted command to set brightness.

    Args:
        value: Brightness value (0-4096)

    Returns:
        Encoded command bytes

    Note:
        If the original utility.LLencode function is available, this should
        be replaced with the actual implementation.
    """
    # Basic implementation - sends value as string
    # Adjust based on actual LED controller protocol
    command = f"SET:{value}\r\n"
    return command.encode('ascii')


class LEDDriver(HardwareDevice):
    """LED Light controller via serial communication.

    Provides brightness control for LED illumination system with
    connection management and state persistence.

    Example:
        led = LEDDriver(port='COM7', brightness_range=(0, 4096))
        led.connect()
        led.set_brightness(2048)
        brightness = led.get_brightness()
        led.disconnect()

    Or with context manager:
        with LEDDriver(port='COM7') as led:
            led.set_brightness(2048)
    """

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        brightness_range: tuple = (0, 4096),
        default_brightness: int = 2048,
        state_file: Optional[str] = None,
        name: Optional[str] = None
    ):
        """Initialize LED driver.

        Args:
            port: Serial port (e.g., 'COM7', '/dev/ttyUSB0', or 'auto' to detect)
            baud_rate: Serial baud rate (default: 115200)
            brightness_range: Tuple of (min, max) brightness values
            default_brightness: Default brightness on connect
            state_file: File to save/restore brightness state
            name: Custom name for the device
        """
        if not SERIAL_AVAILABLE:
            raise ImportError(
                "pyserial not available. Install with: pip install pyserial"
            )

        super().__init__(device_id=port, name=name or "LED_Controller")

        self._port = port
        self._baud_rate = baud_rate
        self._brightness_range = brightness_range
        self._current_brightness = default_brightness
        self._state_file = state_file or 'LLpos.txt'
        self._serial: Optional[serial.Serial] = None

    def _do_connect(self) -> None:
        """Connect to LED controller via serial port.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Auto-detect port if needed
            if self._port is None or self._port.lower() == 'auto':
                self._port = self._auto_detect_port()
                if self._port is None:
                    raise ConnectionError("No serial ports found")

            self._logger.info(f"Connecting to LED controller on {self._port}")

            # Open serial connection
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0
            )

            # Small delay for connection to stabilize
            time.sleep(0.1)

            # Send start command and wait for ready response
            self._serial.write(b'Start')
            self._serial.flush()

            # Wait for "Ready\r\n" response
            start_time = time.time()
            response = b''
            while time.time() - start_time < 2.0:
                if self._serial.in_waiting > 0:
                    response += self._serial.read(self._serial.in_waiting)
                    if b"Ready" in response:
                        break
                time.sleep(0.01)

            if b"Ready" not in response:
                self._logger.warning(
                    f"Did not receive 'Ready' response. Got: {response}"
                )
                # Continue anyway - some controllers may not send this

            self._device_info = {
                'port': self._port,
                'baud_rate': self._baud_rate,
                'brightness_range': self._brightness_range
            }

            self._logger.info(f"LED controller connected on {self._port}")

        except serial.SerialException as e:
            self._logger.error(f"Serial connection failed: {e}")
            raise ConnectionError(f"Failed to connect to {self._port}: {e}") from e
        except Exception as e:
            self._logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Connection failed: {e}") from e

    def _do_initialize(self) -> None:
        """Initialize LED controller after connection.

        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            # Load saved brightness if state file exists
            try:
                with open(self._state_file, 'r') as f:
                    saved_brightness = int(f.readline().strip())
                    self._current_brightness = saved_brightness
                    self._logger.debug(
                        f"Loaded saved brightness: {saved_brightness}"
                    )
            except (FileNotFoundError, ValueError) as e:
                self._logger.debug(
                    f"No saved state found, using default: {self._current_brightness}"
                )

            # Set initial brightness
            self.set_brightness(self._current_brightness)

            self._logger.info("LED controller initialized")

        except Exception as e:
            self._logger.error(f"Initialization failed: {e}")
            raise ConfigurationError(f"Initialization failed: {e}") from e

    def _do_disconnect(self) -> None:
        """Disconnect from LED controller."""
        try:
            # Save current brightness to state file
            try:
                with open(self._state_file, 'w') as f:
                    f.write(str(self._current_brightness))
                self._logger.debug(
                    f"Saved brightness state: {self._current_brightness}"
                )
            except Exception as e:
                self._logger.warning(f"Could not save state: {e}")

            # Close serial connection
            if self._serial is not None and self._serial.is_open:
                self._serial.close()
                self._logger.info("LED controller disconnected")

            self._serial = None

        except Exception as e:
            self._logger.error(f"Error during disconnect: {e}")
            raise

    def _auto_detect_port(self) -> Optional[str]:
        """Auto-detect serial port.

        Returns:
            Detected port name or None if not found
        """
        ports = serial.tools.list_ports.comports()

        if not ports:
            self._logger.warning("No serial ports found")
            return None

        # Return first available port
        # In production, you might want to filter by vendor ID or description
        port = ports[0].device
        self._logger.info(f"Auto-detected port: {port}")
        return port

    def _validate_brightness(self, brightness: int) -> int:
        """Validate and clamp brightness value.

        Args:
            brightness: Brightness value

        Returns:
            Validated brightness value
        """
        min_val, max_val = self._brightness_range

        # Clamp value
        brightness_clamped = max(min_val, min(max_val, int(brightness)))

        # Warn if clamping occurred
        if brightness != brightness_clamped:
            self._logger.warning(
                f"Brightness {brightness} clamped to {brightness_clamped}. "
                f"Valid range: [{min_val}, {max_val}]"
            )

        return brightness_clamped

    def set_brightness(self, brightness: int) -> None:
        """Set LED brightness.

        Args:
            brightness: Brightness value (within configured range)

        Raises:
            CommandError: If setting brightness fails
        """
        self._check_connected()

        # Validate brightness
        brightness = self._validate_brightness(brightness)

        try:
            # Encode and send command
            command = _encode_led_value(brightness)
            self._serial.write(command)
            self._serial.flush()

            # Update current brightness
            self._current_brightness = brightness

            # Calculate current in mA (based on observed formula: value/4096*293)
            current_ma = brightness / 4096 * 293
            self._logger.debug(
                f"Brightness set to {brightness} (~{current_ma:.2f} mA)"
            )

        except Exception as e:
            self._logger.error(f"Failed to set brightness: {e}")
            raise CommandError(f"Failed to set brightness: {e}") from e

    def get_brightness(self) -> int:
        """Get current brightness value.

        Returns:
            Current brightness value
        """
        return self._current_brightness

    def set_brightness_percent(self, percent: float) -> None:
        """Set brightness as percentage.

        Args:
            percent: Brightness percentage (0-100)

        Raises:
            CommandError: If setting fails
        """
        min_val, max_val = self._brightness_range
        brightness = int(min_val + (max_val - min_val) * (percent / 100.0))
        self.set_brightness(brightness)

    def get_brightness_percent(self) -> float:
        """Get brightness as percentage.

        Returns:
            Brightness percentage (0-100)
        """
        min_val, max_val = self._brightness_range
        return (self._current_brightness - min_val) / (max_val - min_val) * 100.0

    def get_current_ma(self) -> float:
        """Get estimated LED current in milliamps.

        Returns:
            Estimated current in mA (based on brightness/4096*293)
        """
        return self._current_brightness / 4096 * 293

    def turn_off(self) -> None:
        """Turn LED off (set to minimum brightness).

        Raises:
            CommandError: If command fails
        """
        min_val = self._brightness_range[0]
        self.set_brightness(min_val)
        self._logger.info("LED turned off")

    def turn_on(self, brightness: Optional[int] = None) -> None:
        """Turn LED on to specified or previous brightness.

        Args:
            brightness: Target brightness (None to use current/default)

        Raises:
            CommandError: If command fails
        """
        if brightness is None:
            brightness = self._current_brightness

        self.set_brightness(brightness)
        self._logger.info(f"LED turned on at brightness {brightness}")

    @staticmethod
    def list_ports() -> List[str]:
        """List available serial ports.

        Returns:
            List of available port names
        """
        if not SERIAL_AVAILABLE:
            return []

        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    @property
    def brightness_range(self) -> tuple:
        """Get brightness range."""
        return self._brightness_range

    @property
    def port(self) -> Optional[str]:
        """Get serial port name."""
        return self._port
