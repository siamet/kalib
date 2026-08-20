"""Command registry mapping wire command names onto controller calls.

Handlers run on the Qt main thread, so they may call the controllers
directly. A handler returns a JSON-serialisable result or raises one of the
exceptions from kalib.hardware.base, which the protocol turns into an error
response.

Handlers are module-level functions, not methods, so that Tasks 3-5 can add
new commands by writing one function plus one `_handlers` table entry
without growing `CommandRegistry` itself.
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import cv2
import numpy as np

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.hardware.base import CommandError
from kalib.utils.image_utils import save_image
from kalib.utils.logger import get_logger

if TYPE_CHECKING:
    from kalib.controllers.calibration_controller import CalibrationController
    from kalib.controllers.camera_controller import CameraController
    from kalib.controllers.scan_controller import ScanController
    from kalib.controllers.stage_controller import StageController

PREVIEW_DEFAULT_PX = 1024
PREVIEW_MAX_BYTES = 400_000
PREVIEW_JPEG_QUALITY = 80


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
            "snap": _snap,
            "preview": _preview,
            "autofocus": _autofocus,
            "tilt_start": _tilt_start,
            "tilt_measure": _tilt_measure,
            "tilt_complete": _tilt_complete,
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


def _capture(reg: CommandRegistry) -> np.ndarray:
    """Capture one frame or raise.

    Args:
        reg: The registry whose camera controller performs the capture

    Returns:
        The captured frame

    Raises:
        CommandError: If no frame could be captured
    """
    frame = reg.camera.capture_image()
    if frame is None:
        raise CommandError(
            "Capture failed. Is acquisition started? Call start_acquisition."
        )
    return frame


def _default_capture_path() -> str:
    """Return a timestamped default capture path under ./data."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return str(Path("data") / f"snap_{stamp}.tiff")


def _snap(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Capture at full resolution, write it to disk, return its path.

    Pixels are deliberately not returned: a full frame is 36 MB and the
    command channel is for control, not bulk data.

    Args:
        reg: The registry whose camera and stage controllers are used
        args: Optional "path"; a timestamped default is used when absent

    Returns:
        The file path plus acquisition metadata
    """
    frame = _capture(reg)
    path = Path(args.get("path") or _default_capture_path())
    if not path.suffix:
        path = path.with_suffix(".tiff")
    path.parent.mkdir(parents=True, exist_ok=True)
    save_image(frame, str(path), format=path.suffix.lstrip("."))

    meta = {
        "path": str(path),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "dtype": str(frame.dtype),
        "position": _position_dict(reg),
        "sharpness": float(gradient_sharpness(frame)),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return meta


def _preview(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Capture a downscaled, compressed frame for a quick look.

    Args:
        reg: The registry whose camera controller performs the capture
        args: Optional "max_px" long-edge target

    Returns:
        Base64 JPEG plus its dimensions and a sharpness metric

    Raises:
        CommandError: If the encoded image exceeds the size cap
    """
    frame = _capture(reg)
    sharpness = float(gradient_sharpness(frame))

    max_px = int(args.get("max_px", PREVIEW_DEFAULT_PX))
    height, width = frame.shape[:2]
    scale = min(1.0, max_px / max(height, width))
    if scale < 1.0:
        frame = cv2.resize(frame, (max(1, int(width * scale)),
                                   max(1, int(height * scale))),
                            interpolation=cv2.INTER_AREA)

    ok, buf = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), PREVIEW_JPEG_QUALITY]
    )
    if not ok:
        raise CommandError("Preview encoding failed")

    raw = buf.tobytes()
    if len(raw) > PREVIEW_MAX_BYTES:
        raise CommandError(
            f"Preview is {len(raw)} bytes, over the {PREVIEW_MAX_BYTES} cap. "
            f"Request a smaller max_px."
        )

    return {
        "jpeg_base64": base64.b64encode(raw).decode("ascii"),
        "bytes": len(raw),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "sharpness": sharpness,
    }


def _need_calibration(reg: CommandRegistry) -> "CalibrationController":
    """Return the registry's calibration controller or raise.

    Args:
        reg: The registry to check

    Returns:
        The calibration controller

    Raises:
        CommandError: If the server was built without one
    """
    if reg.calibration is None:
        raise CommandError("No calibration controller is available")
    return reg.calibration


def _autofocus(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a quick autofocus sweep.

    This blocks until focus is found, because CalibrationController is not
    threaded. Expect roughly one to three seconds for 20 steps.

    Args:
        reg: The registry whose calibration controller performs the sweep
        args: Optional "num_steps" and "search_range"

    Returns:
        The focus height found and the resulting stage position

    Raises:
        CommandError: If autofocus does not converge
    """
    calibration = _need_calibration(reg)
    focus_z = calibration.quick_autofocus(
        num_steps=int(args.get("num_steps", 20)),
        search_range=float(args.get("search_range", 2.0)),
    )
    if focus_z is None:
        raise CommandError("Autofocus failed to find a focus position")
    return {"focus_z": float(focus_z), "position": _position_dict(reg)}


def _tilt_start(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Begin a tilt calibration sequence.

    Args:
        reg: The registry whose calibration controller is used
        args: Optional "num_corners"

    Returns:
        Whether calibration started
    """
    started = _need_calibration(reg).start_tilt_calibration(
        num_corners=int(args.get("num_corners", 4))
    )
    return {"started": bool(started)}


def _tilt_measure(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Measure one tilt-calibration corner.

    Args:
        reg: The registry whose calibration controller is used
        args: Required "corner_idx"

    Returns:
        Whether the measurement succeeded and the corner it measured
    """
    corner_idx = int(_require(args, "corner_idx"))
    measured = _need_calibration(reg).measure_tilt_corner(corner_idx)
    return {"measured": bool(measured), "corner_idx": corner_idx}


def _tilt_complete(reg: CommandRegistry, args: Dict[str, Any]) -> Dict[str, Any]:
    """Finish the tilt calibration and fit the plane.

    Args:
        reg: The registry whose calibration controller is used
        args: Unused

    Returns:
        Whether the calibration completed successfully
    """
    return {"completed": bool(_need_calibration(reg).complete_tilt_calibration())}
