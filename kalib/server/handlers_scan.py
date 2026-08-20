"""Autofocus, tilt-calibration and scan-job command handlers.

Split out of kalib.server.handlers -- which was itself already split out of
kalib.server.commands -- to keep each module under the project's line cap.
kalib.server.commands imports these by name exactly as it imports from
kalib.server.handlers; the split is by file only, not by behavior, and a
new command in this area is added the same way: one function here plus one
`_handlers` table entry in kalib.server.commands.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from kalib.hardware.base import CommandError
from kalib.models import XYScanParameters, ZStackParameters
from kalib.server.handlers import _position_dict, _require

if TYPE_CHECKING:
    from kalib.controllers.calibration_controller import CalibrationController
    from kalib.controllers.scan_controller import ScanController
    from kalib.server.commands import CommandRegistry

# A caller-supplied num_steps controls how many frames quick_autofocus
# keeps in memory at once (it retains every frame until the sweep ends);
# at 36 MB/frame an unclamped value is an easy way to exhaust memory.
AUTOFOCUS_MIN_STEPS = 1
AUTOFOCUS_MAX_STEPS = 200

# Caller-supplied scan geometry (start/end/step) can imply an arbitrarily
# large position count -- e.g. step_x=0.01 over 100 um is 1e8 positions.
# Reject anything past this before a scan is configured or started.
MAX_SCAN_POSITIONS = 10_000


def _need_calibration(reg: "CommandRegistry") -> "CalibrationController":
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


def _autofocus(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
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
    num_steps = max(AUTOFOCUS_MIN_STEPS,
                    min(AUTOFOCUS_MAX_STEPS, int(args.get("num_steps", 20))))
    focus_z = calibration.quick_autofocus(
        num_steps=num_steps,
        search_range=float(args.get("search_range", 2.0)),
    )
    if focus_z is None:
        raise CommandError("Autofocus failed to find a focus position")
    return {"focus_z": float(focus_z), "position": _position_dict(reg)}


def _tilt_start(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Begin a tilt calibration sequence.

    Args:
        reg: The registry whose calibration controller is used
        args: Optional "num_corners"

    Returns:
        Whether calibration started

    Raises:
        CommandError: If calibration fails to start, e.g. the camera is
            not acquiring or the stage is not connected
    """
    ok = _need_calibration(reg).start_tilt_calibration(
        num_corners=int(args.get("num_corners", 4))
    )
    reg.require_ok(ok, "Failed to start tilt calibration")
    return {"started": True}


def _tilt_measure(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Measure one tilt-calibration corner.

    Args:
        reg: The registry whose calibration controller is used
        args: Required "corner_idx"

    Returns:
        Whether the measurement succeeded and the corner it measured

    Raises:
        CommandError: If the measurement fails, e.g. an invalid corner
            index or a failed autofocus
    """
    corner_idx = int(_require(args, "corner_idx"))
    ok = _need_calibration(reg).measure_tilt_corner(corner_idx)
    reg.require_ok(ok, "Failed to measure tilt corner")
    return {"measured": True, "corner_idx": corner_idx}


def _tilt_complete(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Finish the tilt calibration and fit the plane.

    Args:
        reg: The registry whose calibration controller is used
        args: Unused

    Returns:
        Whether the calibration completed successfully

    Raises:
        CommandError: If the calibration is incomplete or the fit fails
    """
    ok = _need_calibration(reg).complete_tilt_calibration()
    reg.require_ok(ok, "Failed to complete tilt calibration")
    return {"completed": True}


def _need_scan(reg: "CommandRegistry") -> "ScanController":
    """Return the registry's scan controller or raise.

    Args:
        reg: The registry to check

    Returns:
        The scan controller

    Raises:
        CommandError: If the server was built without one
    """
    if reg.scan is None:
        raise CommandError("No scan controller is available")
    return reg.scan


def _start_job(reg: "CommandRegistry", save_path: Optional[str]) -> Dict[str, Any]:
    """Start the configured scan and register it as the current job.

    Args:
        reg: The registry whose scan controller performs the scan
        save_path: Directory for scan output, or None for the default

    Returns:
        The new job id and whether the scan started

    Raises:
        CommandError: If a scan is already running
    """
    scan = _need_scan(reg)
    if scan.is_scanning:
        raise CommandError(
            f"A scan is already running (job {reg.job_id}). "
            f"Cancel it first."
        )
    started = scan.start_scan(save_path=save_path)
    reg.job_id = uuid.uuid4().hex[:8] if started else None
    return {"job_id": reg.job_id, "started": bool(started)}


def _check_scan_size(total_positions: int) -> None:
    """Reject a scan whose position count would allocate unbounded memory.

    Args:
        total_positions: The position count the requested geometry implies

    Raises:
        CommandError: If total_positions exceeds MAX_SCAN_POSITIONS
    """
    if total_positions > MAX_SCAN_POSITIONS:
        raise CommandError(
            f"Scan would visit {total_positions} positions, over the "
            f"{MAX_SCAN_POSITIONS} limit. Use a larger step or a smaller "
            f"range."
        )


def _scan_xy(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Configure and start an XY grid scan.

    Raises:
        CommandError: If the requested geometry exceeds MAX_SCAN_POSITIONS
    """
    scan = _need_scan(reg)
    params = XYScanParameters(
        start_x=float(args.get("start_x", 0.0)),
        start_y=float(args.get("start_y", 0.0)),
        end_x=float(args.get("end_x", 10.0)),
        end_y=float(args.get("end_y", 10.0)),
        step_x=float(args.get("step_x", 1.0)),
        step_y=float(args.get("step_y", 1.0)),
    )
    _check_scan_size(params.total_positions)
    scan.configure_xy_scan(params)
    return _start_job(reg, args.get("save_path"))


def _scan_z(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Configure and start a Z-stack scan.

    Raises:
        CommandError: If the requested geometry exceeds MAX_SCAN_POSITIONS
    """
    scan = _need_scan(reg)
    params = ZStackParameters(
        start_z=float(args.get("start_z", 0.0)),
        end_z=float(args.get("end_z", 5.0)),
        step_z=float(args.get("step_z", 0.1)),
    )
    _check_scan_size(params.total_positions)
    scan.configure_z_stack(params)
    return _start_job(reg, args.get("save_path"))


def _job_status(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Report the current scan job, if any."""
    scan = _need_scan(reg)
    scanning = scan.is_scanning
    if not scanning:
        reg.job_id = None
    return {"job_id": reg.job_id, "scanning": bool(scanning),
            "progress": float(scan.scan_progress)}


def _job_cancel(reg: "CommandRegistry", args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel the running scan."""
    cancelled = _need_scan(reg).cancel_scan()
    if cancelled:
        reg.job_id = None
    return {"cancelled": bool(cancelled)}
