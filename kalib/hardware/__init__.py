"""Hardware module - Hardware abstraction layer for devices.

Provides unified interface to all hardware devices with proper
error handling and lifecycle management.
"""

from kalib.hardware.base import (
    HardwareDevice,
    HardwareError,
    ConnectionError,
    CommandError,
    ConfigurationError,
    TimeoutError,
    ConnectionState
)

from kalib.hardware.ids_camera import IDSCamera
from kalib.hardware.pi_stage_xy import PIStageXY
from kalib.hardware.pi_stage_z import PIStageZ
from kalib.hardware.led_driver import LEDDriver

__all__ = [
    # Base classes and exceptions
    'HardwareDevice',
    'HardwareError',
    'ConnectionError',
    'CommandError',
    'ConfigurationError',
    'TimeoutError',
    'ConnectionState',

    # Hardware drivers
    'IDSCamera',
    'PIStageXY',
    'PIStageZ',
    'LEDDriver',
]
