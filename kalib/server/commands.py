"""Command registry mapping wire command names onto controller calls.

The handler functions themselves live in kalib.server.handlers; this module
owns only the dispatch table and the registry that walks it, so that new
commands can be added there -- one function plus one `_handlers` entry --
without growing this file.
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from kalib.hardware.base import CommandError
from kalib.server.handlers import (
    _autofocus,
    _connect,
    _disconnect,
    _get_position,
    _job_cancel,
    _job_status,
    _move_rel,
    _move_xy,
    _move_z,
    _preview,
    _scan_xy,
    _scan_z,
    _snap,
    _start_acquisition,
    _status,
    _stop,
    _stop_acquisition,
    _tilt_complete,
    _tilt_measure,
    _tilt_start,
)
from kalib.utils.logger import get_logger

if TYPE_CHECKING:
    from kalib.controllers.calibration_controller import CalibrationController
    from kalib.controllers.camera_controller import CameraController
    from kalib.controllers.scan_controller import ScanController
    from kalib.controllers.stage_controller import StageController


class UnknownCommand(CommandError):
    """Raised when a request names a command the server does not have."""


class CommandRegistry:
    """Dispatch table from command names to controller calls.

    Example:
        registry = CommandRegistry(camera, stage, scan, calibration)
        registry.dispatch("move_xy", {"x": 1.0, "y": 2.0})
    """

    def __init__(self, camera: "CameraController", stage: "StageController",
                 scan: Optional["ScanController"] = None,
                 calibration: Optional["CalibrationController"] = None):
        """Initialize the registry.

        Args:
            camera: CameraController instance
            stage: StageController instance
            scan: ScanController instance, or None if scans are unavailable
            calibration: CalibrationController instance, or None
        """
        self._logger = get_logger(__name__)
        self.camera: "CameraController" = camera
        self.stage: "StageController" = stage
        self.scan: Optional["ScanController"] = scan
        self.calibration: Optional["CalibrationController"] = calibration
        self._job_id: Optional[str] = None
        self._handlers: Dict[str, Callable[["CommandRegistry", Dict[str, Any]], Any]] = {
            "status": _status,
            "connect": _connect,
            "disconnect": _disconnect,
            "get_position": _get_position,
            "move_xy": _move_xy,
            "move_z": _move_z,
            "move_rel": _move_rel,
            "stop": _stop,
            "start_acquisition": _start_acquisition,
            "stop_acquisition": _stop_acquisition,
            "snap": _snap,
            "preview": _preview,
            "autofocus": _autofocus,
            "tilt_start": _tilt_start,
            "tilt_measure": _tilt_measure,
            "tilt_complete": _tilt_complete,
            "scan_xy": _scan_xy,
            "scan_z": _scan_z,
            "job_status": _job_status,
            "job_cancel": _job_cancel,
        }

    def command_names(self) -> List[str]:
        """Return the names this registry accepts, sorted."""
        return sorted(self._handlers)

    def dispatch(self, cmd: str, args: Dict[str, Any]) -> Any:
        """Run one command.

        Args:
            cmd: Command name
            args: Command arguments

        Returns:
            A JSON-serialisable result

        Raises:
            UnknownCommand: If the name is not registered
        """
        handler = self._handlers.get(cmd)
        if handler is None:
            raise UnknownCommand(
                f"Unknown command '{cmd}'. Known: {', '.join(self.command_names())}"
            )
        self._logger.debug(f"dispatch {cmd} {args}")
        return handler(self, args)
