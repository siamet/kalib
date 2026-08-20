"""IDS Camera driver with hardware abstraction.

Refactored from interface.py with improved error handling,
logging, and integration with hardware base class.
"""

import re
from typing import Optional, List, Tuple, Dict, Any
import numpy as np

try:
    from ids_peak import ids_peak
    from ids_peak_ipl import ids_peak_ipl
    from ids_peak import ids_peak_ipl_extension
    IDS_AVAILABLE = True
except ImportError:
    IDS_AVAILABLE = False
    ids_peak = None
    ids_peak_ipl = None
    ids_peak_ipl_extension = None

from kalib.hardware.base import (
    HardwareDevice,
    ConnectionError,
    CommandError,
    ConfigurationError,
    TimeoutError
)


VALID_BIT_RATES = (8, 10, 12)


def parse_pixel_format(name: str) -> Tuple[int, Optional[str]]:
    """Parse a configured pixel format name into driver arguments.

    "auto" asks the camera for its own native colour mode, which avoids
    converting a monochrome sensor's frames up to RGB and tripling them for
    no added information. Explicit names override that.

    Args:
        name: Format name such as "auto", "Mono8", "RGB8" or "Mono12"

    Returns:
        Tuple of (bit_rate, colorness), where colorness is None for "auto"

    Raises:
        ConfigurationError: If the name is not a recognised format
    """
    text = (name or "auto").strip()
    if text.lower() in ("auto", "native"):
        return (8, None)

    match = re.fullmatch(r"(Mono|RGB)(\d+)", text, flags=re.IGNORECASE)
    if not match:
        raise ConfigurationError(
            f"Unrecognised pixel format '{name}'. "
            f"Use 'auto', or a name like 'Mono8', 'Mono12' or 'RGB8'."
        )

    colorness = "Mono" if match.group(1).lower() == "mono" else "RGB"
    bit_rate = int(match.group(2))
    if bit_rate not in VALID_BIT_RATES:
        raise ConfigurationError(
            f"Bit rate {bit_rate} not supported. Valid: {list(VALID_BIT_RATES)}"
        )
    return (bit_rate, colorness)


class IDSCamera(HardwareDevice):
    """IDS Camera interface with hardware abstraction.

    Provides high-level interface to IDS cameras with automatic
    memory management and configuration.

    Example:
        camera = IDSCamera()
        camera.connect()
        camera.set_exposure_time(15000)
        image = camera.capture()
        camera.disconnect()

    Or with context manager:
        with IDSCamera() as camera:
            image = camera.capture()
    """

    def __init__(
        self,
        device_idx: int = 0,
        pixel_format: Tuple[int, Optional[str]] = (8, None),
        name: Optional[str] = None
    ):
        """Initialize IDS camera interface.

        Args:
            device_idx: Camera device index (default: 0)
            pixel_format: Tuple of (bit_rate, colorness) e.g., (8, "RGB")
            name: Custom name for the camera
        """
        if not IDS_AVAILABLE:
            raise ImportError(
                "IDS peak SDK not available. Please install IDS peak SDK "
                "and Python bindings from https://en.ids-imaging.com/downloads.html"
            )

        super().__init__(device_id=str(device_idx), name=name or "IDSCamera")

        self._device_idx = device_idx
        self._device = None
        self._datastream = None
        self._nodemap = None
        self._acquisition_ready = False
        self._inner_pixel_format = None
        self._outer_pixel_format = None
        self._resolution: Optional[Tuple[int, int]] = None

        # Pixel format configuration
        self._bit_rate, self._colorness = pixel_format

        # Device manager (shared across all instances)
        self._device_manager = None

    def _do_connect(self) -> None:
        """Connect to IDS camera.

        Raises:
            ConnectionError: If camera not found or cannot be opened
        """
        try:
            # Initialize IDS library
            ids_peak.Library.Initialize()
            self._logger.debug("IDS library initialized")

            # Create device manager
            self._device_manager = ids_peak.DeviceManager.Instance()
            self._device_manager.Update()

            devices = self._device_manager.Devices()
            if devices.empty():
                raise ConnectionError("No IDS cameras found")

            self._logger.debug(f"Found {len(devices)} IDS camera(s)")

            # Get device
            try:
                device = devices[self._device_idx]
            except IndexError:
                raise ConnectionError(
                    f"Camera index {self._device_idx} not found. "
                    f"Available: 0-{len(devices) - 1}"
                )

            # Check if device can be opened
            if not device.IsOpenable():
                raise ConnectionError(
                    f"Camera {self._device_idx} cannot be opened. "
                    f"May be in use by another application."
                )

            # Open device
            self._device = device.OpenDevice(ids_peak.DeviceAccessType_Control)
            self._logger.info(f"Opened camera: {device.ModelName()}")

            # Store device info
            self._device_info = {
                'model': device.ModelName(),
                'serial': device.SerialNumber() if hasattr(device, 'SerialNumber') else 'N/A',
                'index': self._device_idx
            }

        except ids_peak.Exception as e:
            self._logger.error(f"IDS peak exception during connection: {e}")
            raise ConnectionError(f"Failed to connect to camera: {e}") from e
        except Exception as e:
            self._logger.error(f"Unexpected error during connection: {e}")
            raise ConnectionError(f"Failed to connect to camera: {e}") from e

    def _do_initialize(self) -> None:
        """Initialize camera after connection.

        Raises:
            ConfigurationError: If initialization fails
        """
        try:
            self._setup_datastream()
            self._configure_pixel_format()
            self._read_resolution()
            self._logger.info("Camera initialized successfully")

        except Exception as e:
            self._logger.error(f"Initialization failed: {e}")
            raise ConfigurationError(f"Camera initialization failed: {e}") from e

    def _do_disconnect(self) -> None:
        """Disconnect from camera."""
        try:
            # Stop acquisition if running
            if self._acquisition_ready:
                self.stop_acquisition()

            # Release datastream
            if self._datastream is not None:
                try:
                    self._datastream.KillWait()
                    self._datastream.StopAcquisition(ids_peak.AcquisitionStopMode_Default)
                    self._datastream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
                except Exception as e:
                    self._logger.warning(f"Error stopping datastream: {e}")

            # Unlock parameters
            if self._nodemap is not None:
                try:
                    self._nodemap.FindNode("TLParamsLocked").SetValue(0)
                except Exception:
                    pass

            # Close IDS library
            try:
                ids_peak.Library.Close()
            except Exception as e:
                self._logger.warning(f"Error closing IDS library: {e}")

            # Clear references
            self._device = None
            self._datastream = None
            self._nodemap = None
            self._acquisition_ready = False

        except Exception as e:
            self._logger.error(f"Error during disconnect: {e}")
            raise

    def _setup_datastream(self) -> None:
        """Setup datastream for image acquisition.

        Raises:
            ConfigurationError: If datastream setup fails
        """
        if self._device is None:
            raise ConfigurationError("Device not connected")

        # Get datastream
        datastreams = self._device.DataStreams()
        if datastreams.empty():
            raise ConfigurationError("Device has no DataStream")

        self._datastream = datastreams[0].OpenDataStream()

        # Get nodemap
        self._nodemap = self._device.RemoteDevice().NodeMaps()[0]

        # Load default settings
        try:
            self._nodemap.FindNode("UserSetSelector").SetCurrentEntry("Default")
            self._nodemap.FindNode("UserSetLoad").Execute()
            self._nodemap.FindNode("UserSetLoad").WaitUntilDone()
            self._logger.debug("Loaded default user set")
        except ids_peak.Exception:
            self._logger.debug("User set not available")

    def _configure_pixel_format(self) -> None:
        """Configure pixel format based on initialization parameters.

        Raises:
            ConfigurationError: If pixel format not supported
        """
        # Determine camera type (color or mono)
        model_name = self._device_info.get('model', '')
        is_color = model_name.endswith('C')
        cam_colorness = "RGB" if is_color else "Mono"

        self._logger.info(
            f"{model_name} is a {'color' if is_color else 'monochrome'} camera"
        )

        # Use camera's native mode if colorness not specified
        colorness = self._colorness or cam_colorness

        # Validate bit rate
        valid_bit_rates = [8, 10, 12]
        if self._bit_rate not in valid_bit_rates:
            raise ConfigurationError(
                f"Bit rate {self._bit_rate} not supported. "
                f"Valid: {valid_bit_rates}"
            )

        # Validate colorness
        if colorness not in ['Mono', 'RGB']:
            raise ConfigurationError(
                f"Color mode '{colorness}' not supported. Valid: Mono, RGB"
            )

        # Get available formats from camera
        available_formats = self.get_available_pixel_formats()
        
        # Auto-detect Bayer pattern for color cameras
        bayer_pattern = None
        if cam_colorness == "RGB":
            for pattern in ['RG', 'GR', 'GB', 'BG']:
                if any(f.startswith(f'Bayer{pattern}') for f in available_formats):
                    bayer_pattern = pattern
                    self._logger.debug(f"Detected Bayer pattern: {bayer_pattern}")
                    break
            
            if not bayer_pattern:
                raise ConfigurationError(
                    f"No Bayer pattern found in available formats: {available_formats}"
                )

        # Build format name candidates (try IDS-specific formats first, then standard)
        if cam_colorness == "Mono":
            # Mono format candidates
            inner_candidates = [
                f"Mono{self._bit_rate}g40IDS",
                f"Mono{self._bit_rate}g24IDS",
                f"Mono{self._bit_rate}"
            ]
        else:
            # Bayer format candidates for color cameras
            inner_candidates = [
                f"Bayer{bayer_pattern}{self._bit_rate}g40IDS",
                f"Bayer{bayer_pattern}{self._bit_rate}g24IDS",
                f"Bayer{bayer_pattern}{self._bit_rate}"
            ]
        
        # Find first available inner format
        inner_mode = None
        for candidate in inner_candidates:
            if candidate in available_formats:
                inner_mode = candidate
                break
        
        if not inner_mode:
            raise ConfigurationError(
                f"No suitable {cam_colorness} format with {self._bit_rate}-bit found. "
                f"Available: {available_formats}"
            )

        # Output format
        outer_modes = {
            "Mono": f"Mono{self._bit_rate}",
            "RGB": f"RGB{self._bit_rate}"
        }
        outer_mode = outer_modes[colorness]

        # Set pixel formats
        try:
            # Get the PixelFormatName enum values for IPL conversion
            self._inner_pixel_format = getattr(
                ids_peak_ipl, f"PixelFormatName_{inner_mode}"
            )
            self._outer_pixel_format = getattr(
                ids_peak_ipl, f"PixelFormatName_{outer_mode}"
            )

            # Apply to camera using string name (not enum value)
            self._nodemap.FindNode("PixelFormat").SetCurrentEntry(inner_mode)

            self._logger.info(
                f"Pixel format: {inner_mode} (internal) -> {outer_mode} (output)"
            )

        except AttributeError as e:
            raise ConfigurationError(
                f"Pixel format '{inner_mode}' not supported by IDS library. "
                f"Available: {available_formats}"
            ) from e
        except ids_peak.Exception as e:
            raise ConfigurationError(
                f"Failed to set pixel format '{inner_mode}'. Available: {available_formats}"
            ) from e

        # Allocate buffers
        payload_size = self._nodemap.FindNode("PayloadSize").Value()
        buffer_count = self._datastream.NumBuffersAnnouncedMinRequired()

        for i in range(buffer_count):
            buffer = self._datastream.AllocAndAnnounceBuffer(payload_size)
            self._datastream.QueueBuffer(buffer)

        self._logger.debug(f"Allocated {buffer_count} image buffers")

    def _read_resolution(self) -> None:
        """Read camera resolution."""
        try:
            width = self._nodemap.FindNode("Width").Value()
            height = self._nodemap.FindNode("Height").Value()
            self._resolution = (width, height)
            self._logger.debug(f"Resolution: {width}x{height}")
        except Exception as e:
            self._logger.warning(f"Could not read resolution: {e}")

    def start_acquisition(self) -> None:
        """Start image acquisition.

        Raises:
            CommandError: If acquisition start fails
        """
        self._check_connected()

        if self._acquisition_ready:
            self._logger.warning("Acquisition already running")
            return

        try:
            self._nodemap.FindNode("TLParamsLocked").SetValue(1)
            self._datastream.StartAcquisition()
            self._nodemap.FindNode("AcquisitionStart").Execute()
            self._nodemap.FindNode("AcquisitionStart").WaitUntilDone()

            self._acquisition_ready = True
            self._logger.info("Acquisition started")

        except ids_peak.Exception as e:
            self._logger.error(f"Failed to start acquisition: {e}")
            raise CommandError(f"Failed to start acquisition: {e}") from e

    def stop_acquisition(self) -> None:
        """Stop image acquisition.

        Raises:
            CommandError: If acquisition stop fails
        """
        if not self._acquisition_ready:
            self._logger.warning("Acquisition not running")
            return

        try:
            self._nodemap.FindNode("AcquisitionStop").Execute()
            self._nodemap.FindNode("AcquisitionStop").WaitUntilDone()
            self._datastream.StopAcquisition()
            self._nodemap.FindNode("TLParamsLocked").SetValue(0)

            self._acquisition_ready = False
            self._logger.info("Acquisition stopped")

        except ids_peak.Exception as e:
            self._logger.error(f"Failed to stop acquisition: {e}")
            raise CommandError(f"Failed to stop acquisition: {e}") from e

    def capture(self, timeout_ms: int = 1000, force_8bit: bool = False) -> np.ndarray:
        """Capture a single image.

        Args:
            timeout_ms: Timeout in milliseconds
            force_8bit: Force 8-bit output regardless of pixel format

        Returns:
            Captured image as numpy array

        Raises:
            CommandError: If capture fails
            TimeoutError: If capture times out
        """
        self._check_connected()

        if not self._acquisition_ready:
            raise CommandError(
                "Acquisition not ready. Call start_acquisition() first."
            )

        try:
            # Wait for frame
            buffer = self._datastream.WaitForFinishedBuffer(timeout_ms)

            # Convert to image
            ipl_image = ids_peak_ipl_extension.BufferToImage(buffer)
            converted_image = ipl_image.ConvertTo(self._outer_pixel_format)

            # Return buffer for reuse
            self._datastream.QueueBuffer(buffer)

            # Convert to numpy array
            pixel_format = converted_image.PixelFormat()
            num_channels = pixel_format.NumChannels()
            bits_per_channel = pixel_format.NumSignificantBitsPerChannel()

            if num_channels == 1:
                # Monochrome
                if bits_per_channel <= 8 or force_8bit:
                    image_array = converted_image.get_numpy_2D()
                else:
                    image_array = converted_image.get_numpy_2D_16()
            else:
                # Color
                if bits_per_channel <= 8 or force_8bit:
                    image_array = converted_image.get_numpy_3D()
                else:
                    image_array = converted_image.get_numpy_3D_16()

            return image_array.copy()

        except ids_peak.Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError(f"Capture timeout after {timeout_ms}ms") from e
            else:
                raise CommandError(f"Capture failed: {e}") from e

    # Camera parameter methods

    def set_exposure_time(self, exposure_us: float) -> None:
        """Set exposure time in microseconds.

        Args:
            exposure_us: Exposure time in microseconds

        Raises:
            CommandError: If setting fails
        """
        def _set_exposure():
            min_exp = self._nodemap.FindNode("ExposureTime").Minimum()
            max_exp = self._nodemap.FindNode("ExposureTime").Maximum()
            target = max(min_exp, min(max_exp, exposure_us))

            if target != exposure_us:
                self._logger.warning(
                    f"Exposure {exposure_us}us clamped to {target}us "
                    f"(range: {min_exp}-{max_exp})"
                )

            self._nodemap.FindNode("ExposureTime").SetValue(target)
            self._logger.debug(f"Exposure set to {target}us")

        self._execute_command(_set_exposure)

    def get_exposure_time(self) -> float:
        """Get current exposure time in microseconds.

        Returns:
            Exposure time in microseconds
        """
        def _get_exposure():
            return self._nodemap.FindNode("ExposureTime").Value()

        return self._execute_command(_get_exposure)

    def set_gain(self, gain: float) -> None:
        """Set camera gain.

        Args:
            gain: Gain value (must be >= 1.0)

        Raises:
            CommandError: If setting fails
        """
        def _set_gain():
            target_gain = max(gain, 1.0)
            if target_gain != gain:
                self._logger.warning(f"Gain {gain} clamped to {target_gain}")

            self._nodemap.FindNode("Gain").SetValue(target_gain)
            self._logger.debug(f"Gain set to {target_gain}")

        self._execute_command(_set_gain)

    def get_gain(self) -> float:
        """Get current gain value.

        Returns:
            Current gain value
        """
        def _get_gain():
            return self._nodemap.FindNode("Gain").Value()

        return self._execute_command(_get_gain)

    def set_fps(self, fps: float) -> None:
        """Set frames per second.

        Args:
            fps: Target frames per second

        Raises:
            CommandError: If setting fails
        """
        def _set_fps():
            # Adjust exposure if needed
            current_exp = self.get_exposure_time()
            max_exp_for_fps = 1e6 / fps

            if current_exp > max_exp_for_fps:
                self._logger.warning(
                    f"Reducing exposure from {current_exp}us to {max_exp_for_fps}us "
                    f"to achieve {fps} fps"
                )
                self.set_exposure_time(max_exp_for_fps)

            max_fps = self._nodemap.FindNode("AcquisitionFrameRate").Maximum()
            target_fps = min(max_fps, fps)

            if target_fps != fps:
                self._logger.warning(
                    f"FPS {fps} clamped to {target_fps} (max: {max_fps})"
                )

            self._nodemap.FindNode("AcquisitionFrameRate").SetValue(target_fps)
            self._logger.debug(f"FPS set to {target_fps}")

        self._execute_command(_set_fps)

    def get_fps(self) -> float:
        """Get current frames per second.

        Returns:
            Current FPS
        """
        def _get_fps():
            return self._nodemap.FindNode("AcquisitionFrameRate").Value()

        return self._execute_command(_get_fps)

    def get_resolution(self) -> Tuple[int, int]:
        """Get camera resolution.

        Returns:
            Tuple of (width, height) in pixels
        """
        if self._resolution is None:
            self._read_resolution()

        if self._resolution is None:
            raise CommandError("Could not read resolution")

        return self._resolution

    def get_available_pixel_formats(self) -> List[str]:
        """Get list of available pixel formats.

        Returns:
            List of supported pixel format names
        """
        # Check nodemap is available (works during initialization)
        if self._nodemap is None:
            raise ConnectionError(
                f"{self._name} nodemap not available. Ensure device is connected."
            )

        try:
            pixel_format_node = self._nodemap.FindNode("PixelFormat")
            current_format = pixel_format_node.CurrentEntry().StringValue()

            formats = []
            for entry in pixel_format_node.Entries():
                format_name = entry.StringValue()
                try:
                    pixel_format_node.SetCurrentEntry(entry.Value())
                    formats.append(format_name)
                except ids_peak.Exception:
                    pass

            # Restore original format
            pixel_format_node.SetCurrentEntry(current_format)

            return formats

        except Exception as e:
            self._logger.error(f"Failed to get pixel formats: {e}")
            return []

    @property
    def is_acquisition_running(self) -> bool:
        """Check if acquisition is running."""
        return self._acquisition_ready
