"""Command registry mapping wire command names onto controller calls.

Handlers run on the Qt main thread, so they may call the controllers
directly. A handler returns a JSON-serialisable result or raises one of the
exceptions from kalib.hardware.base, which the protocol turns into an error
response.

Handlers are module-level functions, not methods, so that Tasks 3-5 can add
new commands by writing one function plus one `_handlers` table entry
without growing `CommandRegistry` itself.
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from kalib.hardware.base import CommandError
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
        self._handlers: Dict[str, Callable[["CommandRegistry", Dict[str, Any]], Any]] = {
            "status": _status,
            "connect": _connect,
            "disconnect": _disconnect,
            "get_position": _get_position,
            "move_xy": _move_xy,
            "move_z": _move_z,
            "move_rel": _move_rel,
            "stop": _stop,
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


def _position_dict(reg: CommandRegistry) -> Dict[str, float]:
    """Return the current stage position as a dict."""
    x, y, z = reg.stage.get_position()
    return {"x": x, "y": y, "z": z}


def _status(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Report the connection state of every device."""
    return {
        "camera": {"connected": reg.camera.is_connected,
                   "acquiring": reg.camera.is_acquiring},
        "stage_xy": {"connected": reg.stage.is_xy_connected},
        "stage_z": {"connected": reg.stage.is_z_connected},
        "scanning": bool(reg.scan and reg.scan.is_scanning),
    }


def _connect(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Connect every device, reporting which succeeded."""
    return {
        "camera": reg.camera.connect_camera(),
        "stage_xy": reg.stage.connect_xy_stage(),
        "stage_z": reg.stage.connect_z_stage(),
    }


def _disconnect(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Disconnect the camera and stages."""
    return {
        "camera": reg.camera.disconnect_camera(),
        "stage_xy": reg.stage.disconnect_xy_stage(),
        "stage_z": reg.stage.disconnect_z_stage(),
    }


def _get_position(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, float]:
    """Report the current stage position."""
    return _position_dict(reg)


def _move_xy(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, float]:
    """Move the XY stage to an absolute position."""
    reg.stage.move_absolute(x=_require(args, "x"), y=_require(args, "y"))
    return _position_dict(reg)


def _move_z(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, float]:
    """Move the Z stage to an absolute position."""
    reg.stage.move_absolute(z=_require(args, "z"))
    return _position_dict(reg)


def _move_rel(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, float]:
    """Move all axes by a relative offset."""
    reg.stage.move_relative(dx=args.get("dx", 0.0),
                            dy=args.get("dy", 0.0),
                            dz=args.get("dz", 0.0))
    return _position_dict(reg)


def _stop(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Stop stage motion immediately."""
    return {"stopped": reg.stage.stop_movement()}
