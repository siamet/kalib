"""Command registry mapping wire command names onto controller calls.

Handlers run on the Qt main thread, so they may call the controllers
directly. A handler returns a JSON-serialisable result or raises one of the
exceptions from kalib.hardware.base, which the protocol turns into an error
response.
"""

from typing import Any, Callable, Dict, List, Optional

from kalib.hardware.base import CommandError
from kalib.utils.logger import get_logger


class UnknownCommand(CommandError):
    """Raised when a request names a command the server does not have."""


class CommandRegistry:
    """Dispatch table from command names to controller calls.

    Example:
        registry = CommandRegistry(camera, stage, scan, calibration)
        registry.dispatch("move_xy", {"x": 1.0, "y": 2.0})
    """

    def __init__(self, camera, stage, scan=None, calibration=None):
        """Initialize the registry.

        Args:
            camera: CameraController instance
            stage: StageController instance
            scan: ScanController instance, or None if scans are unavailable
            calibration: CalibrationController instance, or None
        """
        self._logger = get_logger(__name__)
        self.camera = camera
        self.stage = stage
        self.scan = scan
        self.calibration = calibration
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "status": self._status,
            "connect": self._connect,
            "disconnect": self._disconnect,
            "get_position": self._get_position,
            "move_xy": self._move_xy,
            "move_z": self._move_z,
            "move_rel": self._move_rel,
            "stop": self._stop,
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
        return handler(args)

    @staticmethod
    def _require(args: Dict[str, Any], name: str) -> Any:
        """Return a required argument or raise.

        Args:
            args: Supplied arguments
            name: Argument name that must be present

        Returns:
            The argument's value

        Raises:
            CommandError: If the argument is absent
        """
        if name not in args:
            raise CommandError(f"Missing required argument '{name}'")
        return args[name]

    def _position_dict(self) -> Dict[str, float]:
        """Return the current stage position as a dict."""
        x, y, z = self.stage.get_position()
        return {"x": x, "y": y, "z": z}

    def _status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Report the connection state of every device."""
        return {
            "camera": {"connected": self.camera.is_connected,
                       "acquiring": self.camera.is_acquiring},
            "stage_xy": {"connected": self.stage.is_xy_connected},
            "stage_z": {"connected": self.stage.is_z_connected},
            "scanning": bool(self.scan and self.scan.is_scanning),
        }

    def _connect(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Connect every device, reporting which succeeded."""
        return {
            "camera": self.camera.connect_camera(),
            "stage_xy": self.stage.connect_xy_stage(),
            "stage_z": self.stage.connect_z_stage(),
        }

    def _disconnect(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Disconnect the camera and stages."""
        return {
            "camera": self.camera.disconnect_camera(),
            "stage_xy": self.stage.disconnect_xy_stage(),
            "stage_z": self.stage.disconnect_z_stage(),
        }

    def _get_position(self, args: Dict[str, Any]) -> Dict[str, float]:
        """Report the current stage position."""
        return self._position_dict()

    def _move_xy(self, args: Dict[str, Any]) -> Dict[str, float]:
        """Move the XY stage to an absolute position."""
        self.stage.move_absolute(x=self._require(args, "x"),
                                 y=self._require(args, "y"))
        return self._position_dict()

    def _move_z(self, args: Dict[str, Any]) -> Dict[str, float]:
        """Move the Z stage to an absolute position."""
        self.stage.move_absolute(z=self._require(args, "z"))
        return self._position_dict()

    def _move_rel(self, args: Dict[str, Any]) -> Dict[str, float]:
        """Move all axes by a relative offset."""
        self.stage.move_relative(dx=args.get("dx", 0.0),
                                 dy=args.get("dy", 0.0),
                                 dz=args.get("dz", 0.0))
        return self._position_dict()

    def _stop(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Stop stage motion immediately."""
        return {"stopped": self.stage.stop_movement()}
