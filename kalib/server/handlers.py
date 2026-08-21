"""Status, connection and motion command handlers dispatched by
CommandRegistry.

Handlers run on the Qt main thread, so they may call the controllers
directly. A handler returns a JSON-serialisable result or raises one of the
exceptions from kalib.hardware.base, which the protocol turns into an error
response.

Handlers are module-level functions, not methods, so that new commands can
be added by writing one function here plus one `_handlers` table entry in
kalib.server.commands, without growing `CommandRegistry` itself. Split out
of kalib.server.commands to keep that file under the project's line cap;
CommandRegistry imports these by name and owns the dispatch table. The
autofocus, tilt-calibration and scan-job handlers live in the sibling
kalib.server.handlers_scan for the same reason -- this module was itself
approaching the cap -- and import `_require`/`_position_dict` back from
here.
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import cv2
import numpy as np

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.hardware.base import CommandError
from kalib.utils.image_utils import save_image

if TYPE_CHECKING:
    from kalib.server.commands import CommandRegistry

PREVIEW_DEFAULT_PX = 1024
PREVIEW_MAX_BYTES = 400_000
PREVIEW_JPEG_QUALITY = 80


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


def _position_dict(reg: "CommandRegistry") -> Dict[str, float]:
    """Return the current stage position as a dict."""
    x, y, z = reg.stage.get_position()
    return {"x": x, "y": y, "z": z}


def _status(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Report the connection state of every device."""
    return {
        "camera": {"connected": reg.camera.is_connected,
                   "acquiring": reg.camera.is_acquiring},
        "stage_xy": {"connected": reg.stage.is_xy_connected},
        "stage_z": {"connected": reg.stage.is_z_connected},
        "scanning": bool(reg.scan and reg.scan.is_scanning),
    }


def _try_connect(connect_fn) -> Any:
    """Call a controller connect method, isolating its failure.

    connect_camera()/connect_xy_stage()/connect_z_stage() already turn a
    ConnectionError into a returned `False`, but IDSCamera's constructor
    raises a plain ImportError when the vendor SDK is not installed, which
    is not caught inside connect_camera. Evaluating each device's connect
    call separately, and catching here, keeps that from aborting the
    whole `connect` command before the stages are ever attempted.

    Args:
        connect_fn: A zero-arg controller connect method

    Returns:
        Whatever connect_fn returns, or a short error string if it raised
        an exception the controller itself did not catch.
    """
    try:
        return connect_fn()
    except Exception as exc:
        return f"error: {exc}"


def _connect(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Connect every device, reporting which succeeded.

    Each device is connected in its own try so that one failing -- most
    commonly the camera, on a machine without the vendor SDK installed --
    never prevents the others from being attempted.
    """
    return {
        "camera": _try_connect(reg.camera.connect_camera),
        "stage_xy": _try_connect(reg.stage.connect_xy_stage),
        "stage_z": _try_connect(reg.stage.connect_z_stage),
    }


def _disconnect(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Disconnect the camera and stages."""
    return {
        "camera": reg.camera.disconnect_camera(),
        "stage_xy": reg.stage.disconnect_xy_stage(),
        "stage_z": reg.stage.disconnect_z_stage(),
    }


def _get_position(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, float]:
    """Report the current stage position."""
    return _position_dict(reg)


def _move_xy(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, float]:
    """Move the XY stage to an absolute position.

    Raises:
        CommandError: If the move fails, e.g. the stage is not connected
    """
    ok = reg.stage.move_absolute(x=float(_require(args, "x")),
                                 y=float(_require(args, "y")))
    reg.require_ok(ok, "Move failed")
    return _position_dict(reg)


def _move_z(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, float]:
    """Move the Z stage to an absolute position.

    Raises:
        CommandError: If the move fails, e.g. the stage is not connected
    """
    ok = reg.stage.move_absolute(z=float(_require(args, "z")))
    reg.require_ok(ok, "Move failed")
    return _position_dict(reg)


def _move_rel(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, float]:
    """Move all axes by a relative offset.

    Raises:
        CommandError: If the move fails, e.g. the stage is not connected
    """
    ok = reg.stage.move_relative(dx=float(args.get("dx", 0.0)),
                                 dy=float(args.get("dy", 0.0)),
                                 dz=float(args.get("dz", 0.0)))
    reg.require_ok(ok, "Move failed")
    return _position_dict(reg)


def _stop(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Stop stage motion immediately.

    Raises:
        CommandError: If the stop itself fails
    """
    ok = reg.stage.stop_movement()
    reg.require_ok(ok, "Failed to stop stage")
    return {"stopped": True}


def _start_acquisition(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Start camera acquisition so captures can succeed.

    snap and preview both require acquisition to already be running;
    without a remote way to start it, an operator connecting only over
    SSH would have no path to a working snap/preview.

    Args:
        reg: The registry whose camera controller is started
        args: Unused

    Returns:
        The resulting acquisition state

    Raises:
        CommandError: If the camera fails to start, e.g. not connected
    """
    ok = reg.camera.start_acquisition()
    reg.require_ok(ok, "Failed to start acquisition")
    return {"acquiring": reg.camera.is_acquiring}


def _stop_acquisition(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Stop camera acquisition.

    Args:
        reg: The registry whose camera controller is stopped
        args: Unused

    Returns:
        The resulting acquisition state

    Raises:
        CommandError: If the camera fails to stop
    """
    ok = reg.camera.stop_acquisition()
    reg.require_ok(ok, "Failed to stop acquisition")
    return {"acquiring": reg.camera.is_acquiring}


def _capture(reg: "CommandRegistry") -> np.ndarray:
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


def _snap(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
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
    # save_image() already creates the parent directory.
    save_image(frame, str(path), format=path.suffix.lstrip("."))

    settings = reg.camera.get_current_settings()
    meta = {
        "path": str(path),
        "width": int(frame.shape[1]),
        "height": int(frame.shape[0]),
        "dtype": str(frame.dtype),
        "position": _position_dict(reg),
        # Exposure and gain make the capture reproducible. A frame whose
        # exposure is unrecorded cannot be compared against another frame,
        # matched to a master dark, or re-shot.
        "exposure_time": settings.get("exposure_time"),
        "gain": settings.get("gain"),
        "sharpness": float(gradient_sharpness(frame)),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return meta


def _preview(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
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

