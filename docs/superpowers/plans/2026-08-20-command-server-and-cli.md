# Command Server and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the microscope from the Linux development machine by embedding a command server in the Kalib GUI on the instrument machine and talking to it over SSH through a thin CLI.

**Architecture:** A `QTcpServer` bound to 127.0.0.1 runs inside the existing Qt event loop, so command handlers call the controllers directly on the main thread with no cross-thread marshalling. Commands are newline-delimited JSON. Long scans reuse `ScanController`'s existing `QThread` and progress signals rather than introducing new threading. SSH provides the network hop and authentication; the server never faces the network.

**Tech Stack:** Python 3.12, PySide6 6.8.0.2 (`QTcpServer`/`QTcpSocket`), NumPy 2.2.6, OpenCV headless 4.14, pytest 9.1.1, uv.

**Spec:** `docs/superpowers/specs/2026-08-19-remote-operation-design.md`

## How This Plan Diverges From the Spec, and Why

The spec was written before the controller code was read closely. Three of its
assumptions do not survive contact with the source. Each divergence below is
deliberate.

| Spec says | Source says | This plan does |
|---|---|---|
| Commands arrive on a socket thread and must hop to the Qt main thread via `QMetaObject.invokeMethod` | `QTcpServer` delivers `newConnection`/`readyRead` **on the Qt event loop already** | Use `QTcpServer`; no marshalling layer at all. This removes the spec's single riskiest component. |
| `autofocus` and `calibrate_tilt` are background jobs | `CalibrationController` is **not threaded**: `quick_autofocus` blocks (~1-3 s for 20 steps), and tilt calibration is a manual three-call sequence (`start_tilt_calibration` → `measure_tilt_corner` per corner → `complete_tilt_calibration`) | `autofocus` is an immediate blocking command. Tilt calibration is exposed as its three separate immediate commands. Only scans are jobs. |
| Command set includes `set_led` | There is **no LED controller** — `LEDDriver`/`SimLED` have no consumer anywhere in the application | `set_led` is out of scope. Adding it means building an LED controller first, which is its own piece of work. |

Only `scan_xy` and `scan_z` are jobs, and they are jobs because
`ScanController` already runs them on a `QThread` with `progress_updated`,
`scan_completed`, `scan_cancelled` and `scan_error` signals. This plan observes
that machinery; it does not build new threading.

**A blocking command blocks the server.** With `autofocus` running (~seconds),
no other command is answered until it returns. The spec puts multi-client access
out of scope — one operator at a time — so this is acceptable. If it becomes
painful, moving autofocus onto a worker thread is a later change.

## Global Constraints

- Python 3.12; dependencies installed with `uv pip sync requirements.lock`.
- Run everything through the project venv: `.venv/bin/python`.
- `PySide6==6.8.0.2` and `opencv-python-headless>=4.7.0,<5` are pinned. Do not change them.
- Files under 500 lines; functions under 50 lines; classes under 100 lines.
- Google-style docstrings and type annotations on all public APIs, per `docs/ENGINEERING-STANDARDS.md`.
- The server binds **127.0.0.1 only**. It implements no authentication — SSH provides it. Binding any other interface is a defect.
- Protocol version is `1`. Every request and response carries `"v": 1`.
- Error `type` values reuse the existing exception names from `kalib/hardware/base.py`: `ConnectionError`, `CommandError`, `TimeoutError`, `ConfigurationError`, `HardwareError`.
- **Full-resolution images never travel on the command channel.** A frame is 4000×3000×3 = 36 MB. `snap` writes to disk and returns a path; only `preview` returns pixels, downscaled and JPEG-compressed with a hard size cap.
- Never modify `config/config.yaml`.
- All work is testable against the simulated backend from the previous plan: `HardwareFactory(settings)` with `hardware.backend` set to `sim`.

## Verified Interfaces (do not re-derive)

Read from source on 2026-08-20. Where a task's code disagrees with these, these win.

```python
# CameraController
connect_camera() -> bool ; disconnect_camera() -> bool
start_acquisition() -> bool ; stop_acquisition() -> bool
capture_image(timeout_ms: int = 1000) -> Optional[np.ndarray]
get_current_settings() -> dict
@property is_connected -> bool ; @property is_acquiring -> bool
model.state.is_connected / .is_acquiring / .resolution

# StageController
connect_xy_stage(device_id=None) -> bool ; connect_z_stage(device_id=None) -> bool
move_absolute(x=None, y=None, z=None, wait=True) -> bool
move_relative(dx=0.0, dy=0.0, dz=0.0, wait=True) -> bool
get_position() -> Tuple[float, float, float]
stop_movement() -> bool
@property is_xy_connected -> bool ; @property is_z_connected -> bool

# ScanController  (already threaded — QThread + worker)
configure_xy_scan(params: XYScanParameters) -> None
configure_z_stack(params: ZStackParameters) -> None
start_scan(save_path: Optional[str] = None) -> bool
cancel_scan() -> bool
@property is_scanning -> bool ; @property scan_progress -> float
signals: scan_started(str), scan_completed(), scan_cancelled(), scan_error(str),
         progress_updated(int, int)

# CalibrationController  (NOT threaded — these block)
quick_autofocus(num_steps: int = 20, search_range: float = 2.0) -> Optional[float]
autofocus_at_position(search_range=1.0, step_size=0.05, method="sobel") -> Optional[float]
start_tilt_calibration(num_corners: int = 4) -> bool
measure_tilt_corner(corner_idx: int, ...) -> bool
complete_tilt_calibration() -> bool

# models
XYScanParameters(start_x, start_y, end_x, end_y, step_x, step_y, num_steps_x=None, num_steps_y=None)
ZStackParameters(start_z, end_z, step_z, num_steps=None)

# utils
save_image(image: np.ndarray, filepath: str, format: str = 'tiff') -> None
resize_image(image, ...) ; create_thumbnail(image, ...)
gradient_sharpness(image, roi=None) -> float
```

---
### Task 1: Wire protocol

**Files:**
- Create: `kalib/server/__init__.py`
- Create: `kalib/server/protocol.py`
- Test: `tests/test_server/__init__.py`, `tests/test_server/test_protocol.py`

**Interfaces:**
- Consumes: `HardwareError` and subclasses from `kalib/hardware/base.py`.
- Produces: `PROTOCOL_VERSION = 1`; `encode_request(cmd: str, args: dict, request_id: str) -> bytes`; `encode_ok(request_id: str, result: Any) -> bytes`; `encode_error(request_id: str, exc: Exception) -> bytes`; `decode_message(line: bytes) -> dict`; `ProtocolError(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_protocol.py
"""Tests for the command wire protocol."""

import json
import pytest

from kalib.hardware.base import CommandError, ConnectionError
from kalib.server.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_message,
    encode_error,
    encode_ok,
    encode_request,
)


def test_request_round_trips():
    """A request encodes to one JSON line and decodes back."""
    raw = encode_request("move_xy", {"x": 1.0, "y": 2.0}, "abc")
    assert raw.endswith(b"\n")
    msg = decode_message(raw)
    assert msg == {"v": PROTOCOL_VERSION, "id": "abc", "cmd": "move_xy",
                   "args": {"x": 1.0, "y": 2.0}}


def test_ok_response_carries_result():
    """A success response reports ok and the result payload."""
    msg = decode_message(encode_ok("abc", {"x": 1.0}))
    assert msg["ok"] is True
    assert msg["result"] == {"x": 1.0}
    assert msg["id"] == "abc"


def test_error_response_uses_the_exception_class_name():
    """Error type reuses the project's exception taxonomy."""
    msg = decode_message(encode_error("abc", CommandError("nope")))
    assert msg["ok"] is False
    assert msg["error"]["type"] == "CommandError"
    assert msg["error"]["message"] == "nope"


def test_error_distinguishes_exception_types():
    """A different exception class produces a different type field."""
    msg = decode_message(encode_error("abc", ConnectionError("down")))
    assert msg["error"]["type"] == "ConnectionError"


def test_encoded_message_is_a_single_line():
    """Multi-line content must not break the newline framing."""
    raw = encode_error("abc", CommandError("line one\nline two"))
    assert raw.count(b"\n") == 1


def test_decode_rejects_malformed_json():
    """Garbage on the wire raises ProtocolError, not a bare JSONDecodeError."""
    with pytest.raises(ProtocolError):
        decode_message(b"{not json\n")


def test_decode_rejects_wrong_version():
    """A mismatched protocol version fails loudly rather than strangely."""
    bad = json.dumps({"v": 99, "id": "a", "cmd": "status", "args": {}}).encode()
    with pytest.raises(ProtocolError):
        decode_message(bad + b"\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/server/__init__.py
"""Command server for driving Kalib remotely over a local socket."""
```

```python
# kalib/server/protocol.py
"""Newline-delimited JSON wire protocol for the command server.

Every message is one JSON object on one line. Requests carry a command name
and arguments; responses carry either a result or an error whose type is the
name of the exception class that produced it, so the existing exception
taxonomy in kalib.hardware.base doubles as the wire taxonomy.
"""

import json
from typing import Any, Dict

PROTOCOL_VERSION = 1


class ProtocolError(Exception):
    """Raised when a message cannot be parsed or has the wrong version."""


def encode_request(cmd: str, args: Dict[str, Any], request_id: str) -> bytes:
    """Encode a command request.

    Args:
        cmd: Command name
        args: Command arguments
        request_id: Caller-chosen identifier echoed in the response

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "cmd": cmd,
                  "args": args})


def encode_ok(request_id: str, result: Any) -> bytes:
    """Encode a success response.

    Args:
        request_id: Identifier from the request being answered
        result: JSON-serialisable payload

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "ok": True,
                  "result": result})


def encode_error(request_id: str, exc: Exception) -> bytes:
    """Encode a failure response.

    Args:
        request_id: Identifier from the request being answered
        exc: The exception that caused the failure

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "ok": False,
                  "error": {"type": type(exc).__name__, "message": str(exc)}})


def decode_message(line: bytes) -> Dict[str, Any]:
    """Decode one wire message.

    Args:
        line: A single newline-terminated JSON line

    Returns:
        The decoded message

    Raises:
        ProtocolError: If the line is not valid JSON or carries an
            unsupported protocol version
    """
    try:
        msg = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError(f"Malformed message: {exc}") from exc

    if not isinstance(msg, dict):
        raise ProtocolError("Message must be a JSON object")

    version = msg.get("v")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
            f"Unsupported protocol version {version}; "
            f"this server speaks {PROTOCOL_VERSION}"
        )
    return msg


def _line(payload: Dict[str, Any]) -> bytes:
    """Serialise a payload to one newline-terminated JSON line."""
    return (json.dumps(payload) + "\n").encode("utf-8")
```

Create `tests/test_server/__init__.py` as an empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_protocol.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/server/ tests/test_server/
git commit -m "feat: add wire protocol for the command server"
```

---

### Task 2: Command registry and the immediate device commands

**Files:**
- Create: `kalib/server/commands.py`
- Test: `tests/test_server/test_commands.py`

**Interfaces:**
- Consumes: protocol from Task 1; `CameraController`, `StageController` from `kalib.controllers`.
- Produces: `CommandRegistry(camera, stage, scan, calibration)` with `dispatch(cmd: str, args: dict) -> Any` and `command_names() -> List[str]`. Raises `UnknownCommand(CommandError)` for an unregistered name. Registers: `status`, `connect`, `disconnect`, `get_position`, `move_xy`, `move_z`, `move_rel`, `stop`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_commands.py
"""Tests for the command registry and immediate commands."""

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry, UnknownCommand


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry over connected simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=None)


def test_unknown_command_is_rejected(registry):
    """An unregistered name fails as a CommandError, not a KeyError."""
    with pytest.raises(UnknownCommand):
        registry.dispatch("teleport", {})


def test_unknown_command_is_a_command_error(registry):
    """UnknownCommand is catchable as CommandError for the wire taxonomy."""
    assert issubclass(UnknownCommand, CommandError)


def test_status_reports_connection_state(registry):
    """status reports each device's connection state."""
    result = registry.dispatch("status", {})
    assert result["camera"]["connected"] is True
    assert result["stage_xy"]["connected"] is True
    assert result["stage_z"]["connected"] is True


def test_get_position_returns_all_three_axes(registry):
    """get_position reports x, y and z."""
    result = registry.dispatch("get_position", {})
    assert set(result) == {"x", "y", "z"}


def test_move_xy_changes_position(registry):
    """move_xy moves the stage and reports where it ended up."""
    result = registry.dispatch("move_xy", {"x": 12.0, "y": 34.0})
    assert result["x"] == pytest.approx(12.0)
    assert result["y"] == pytest.approx(34.0)


def test_move_z_changes_position(registry):
    """move_z moves the Z axis only."""
    before = registry.dispatch("get_position", {})
    registry.dispatch("move_z", {"z": 7.0})
    after = registry.dispatch("get_position", {})
    assert after["z"] == pytest.approx(7.0)
    assert after["x"] == pytest.approx(before["x"])


def test_move_rel_is_additive(registry):
    """move_rel offsets from the current position."""
    registry.dispatch("move_xy", {"x": 10.0, "y": 10.0})
    result = registry.dispatch("move_rel", {"dx": 2.0, "dy": -3.0})
    assert result["x"] == pytest.approx(12.0)
    assert result["y"] == pytest.approx(7.0)


def test_missing_required_argument_is_a_command_error(registry):
    """A command called without its required argument fails cleanly."""
    with pytest.raises(CommandError):
        registry.dispatch("move_z", {})


def test_command_names_are_listed(registry):
    """The registry can enumerate what it accepts."""
    names = registry.command_names()
    assert "status" in names
    assert "move_xy" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_commands.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.server.commands'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/server/commands.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_commands.py -v`
Expected: PASS, 9 tests

Then the full suite: `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add kalib/server/commands.py tests/test_server/test_commands.py
git commit -m "feat: add command registry with stage and status commands"
```

---
### Task 3: Capture commands — `snap` and `preview`

**Files:**
- Modify: `kalib/server/commands.py` (register two handlers)
- Test: `tests/test_server/test_capture_commands.py`

**Interfaces:**
- Consumes: `CommandRegistry` from Task 2; `save_image` from `kalib.utils.image_utils`; `gradient_sharpness` from `kalib.algorithms.sharpness`.
- Produces: commands `snap` and `preview`. `snap(args: {"path": str|None}) -> {"path", "width", "height", "dtype", "position", "sharpness", "timestamp"}`. `preview(args: {"max_px": int}) -> {"jpeg_base64", "width", "height", "sharpness", "bytes"}`. Adds `PREVIEW_MAX_BYTES = 400_000` and `PREVIEW_DEFAULT_PX = 1024` as module constants.

**Why this shape:** a full frame is 36 MB. `snap` writes it to the instrument's
disk and returns a path plus a metadata sidecar; the operator fetches pixels
deliberately with `scp`. `preview` is the only command returning image data, and
it is downscaled, JPEG-compressed and size-capped.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_capture_commands.py
"""Tests for the snap and preview commands."""

import base64
import json
from pathlib import Path

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import PREVIEW_MAX_BYTES, CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry over connected, acquiring simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=None)


def test_snap_writes_a_file_and_returns_its_path(registry, tmp_path):
    """snap saves to disk rather than returning pixels."""
    target = tmp_path / "shot.tiff"
    result = registry.dispatch("snap", {"path": str(target)})
    assert Path(result["path"]).exists()
    assert result["width"] > 0 and result["height"] > 0


def test_snap_writes_a_metadata_sidecar(registry, tmp_path):
    """Each capture gets a JSON sidecar carrying acquisition context."""
    target = tmp_path / "shot.tiff"
    registry.dispatch("snap", {"path": str(target)})
    sidecar = target.with_suffix(".json")
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text())
    assert set(meta) >= {"position", "sharpness", "timestamp", "width", "height"}


def test_snap_records_the_position_it_was_taken_at(registry, tmp_path):
    """The sidecar's position matches where the stage actually was."""
    registry.dispatch("move_xy", {"x": 11.0, "y": 22.0})
    target = tmp_path / "shot.tiff"
    result = registry.dispatch("snap", {"path": str(target)})
    assert result["position"]["x"] == pytest.approx(11.0)
    assert result["position"]["y"] == pytest.approx(22.0)


def test_snap_response_carries_no_pixel_data(registry, tmp_path):
    """A 36 MB frame must never travel on the command channel."""
    result = registry.dispatch("snap", {"path": str(tmp_path / "s.tiff")})
    assert len(json.dumps(result)) < 2000


def test_preview_returns_base64_jpeg_within_the_cap(registry):
    """preview returns pixels, downscaled and size-capped."""
    result = registry.dispatch("preview", {"max_px": 256})
    raw = base64.b64decode(result["jpeg_base64"])
    assert raw[:2] == b"\xff\xd8"          # JPEG SOI marker
    assert result["bytes"] == len(raw)
    assert len(raw) <= PREVIEW_MAX_BYTES


def test_preview_downscales_to_the_requested_size(registry):
    """The long edge is reduced to max_px."""
    result = registry.dispatch("preview", {"max_px": 128})
    assert max(result["width"], result["height"]) <= 128


def test_preview_reports_sharpness(registry):
    """preview carries a focus metric so focusing needs no eyes."""
    result = registry.dispatch("preview", {})
    assert isinstance(result["sharpness"], float)


def test_capture_without_acquisition_fails_cleanly(tmp_path):
    """Capturing before start_acquisition is a CommandError, not a crash."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    with pytest.raises(CommandError):
        registry.dispatch("snap", {"path": str(tmp_path / "x.tiff")})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_capture_commands.py -v`
Expected: FAIL with `ImportError: cannot import name 'PREVIEW_MAX_BYTES'`

- [ ] **Step 3: Write minimal implementation**

Add to the imports at the top of `kalib/server/commands.py`:

```python
import base64
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.utils.image_utils import save_image
```

Add module constants below the imports:

```python
PREVIEW_DEFAULT_PX = 1024
PREVIEW_MAX_BYTES = 400_000
PREVIEW_JPEG_QUALITY = 80
```

Register the handlers in `__init__`'s `_handlers` dict:

```python
            "snap": self._snap,
            "preview": self._preview,
```

And add the methods:

```python
    def _capture(self) -> np.ndarray:
        """Capture one frame or raise.

        Returns:
            The captured frame

        Raises:
            CommandError: If no frame could be captured
        """
        frame = self.camera.capture_image()
        if frame is None:
            raise CommandError(
                "Capture failed. Is acquisition started? Call start_acquisition."
            )
        return frame

    def _snap(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Capture at full resolution, write it to disk, return its path.

        Pixels are deliberately not returned: a full frame is 36 MB and the
        command channel is for control, not bulk data.

        Args:
            args: Optional "path"; a timestamped default is used when absent

        Returns:
            The file path plus acquisition metadata
        """
        frame = self._capture()
        path = Path(args.get("path") or self._default_capture_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        save_image(frame, str(path), format=path.suffix.lstrip(".") or "tiff")

        meta = {
            "path": str(path),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "dtype": str(frame.dtype),
            "position": self._position_dict(),
            "sharpness": float(gradient_sharpness(frame)),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        return meta

    @staticmethod
    def _default_capture_path() -> str:
        """Return a timestamped default capture path under ./data."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return str(Path("data") / f"snap_{stamp}.tiff")

    def _preview(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Capture a downscaled, compressed frame for a quick look.

        Args:
            args: Optional "max_px" long-edge target

        Returns:
            Base64 JPEG plus its dimensions and a sharpness metric

        Raises:
            CommandError: If the encoded image exceeds the size cap
        """
        frame = self._capture()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_capture_commands.py -v`
Expected: PASS, 8 tests. Then `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add kalib/server/commands.py tests/test_server/test_capture_commands.py
git commit -m "feat: add snap and preview capture commands"
```

---

### Task 4: Focus and tilt-calibration commands

**Files:**
- Modify: `kalib/server/commands.py`
- Test: `tests/test_server/test_focus_commands.py`

**Interfaces:**
- Consumes: `CommandRegistry` from Task 2; `CalibrationController`.
- Produces: commands `autofocus`, `tilt_start`, `tilt_measure`, `tilt_complete`. `autofocus(args: {"num_steps": int, "search_range": float}) -> {"focus_z": float, "position": {...}}`.

**Note:** these block the server for their duration because
`CalibrationController` is not threaded. `quick_autofocus` with 20 steps is
roughly 1-3 seconds. That is accepted; see the plan's divergence table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_focus_commands.py
"""Tests for autofocus and tilt-calibration commands."""

import pytest

from kalib.controllers.calibration_controller import CalibrationController
from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry with a calibration controller over simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    world = factory.world
    world.tilt_a, world.tilt_b, world.tilt_c = 0.0, 0.0, 5.0
    world.width, world.height = 128, 128

    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    calibration = CalibrationController(camera_controller=camera,
                                        stage_controller=stage)
    return CommandRegistry(camera=camera, stage=stage, scan=None,
                           calibration=calibration)


def test_autofocus_finds_the_focal_plane(registry):
    """Autofocus lands near the simulated focal plane at z = 5.0."""
    result = registry.dispatch("autofocus", {"num_steps": 21,
                                             "search_range": 4.0})
    assert result["focus_z"] == pytest.approx(5.0, abs=0.5)


def test_autofocus_reports_the_resulting_position(registry):
    """The response carries where the stage ended up."""
    result = registry.dispatch("autofocus", {"num_steps": 11,
                                             "search_range": 4.0})
    assert set(result["position"]) == {"x", "y", "z"}


def test_tilt_sequence_is_exposed_as_three_commands(registry):
    """Tilt calibration is driven step by step, matching the controller."""
    assert registry.dispatch("tilt_start", {"num_corners": 4})["started"] is True


def test_commands_requiring_calibration_fail_without_it(registry):
    """A registry built without a calibration controller says so."""
    bare = CommandRegistry(camera=registry.camera, stage=registry.stage,
                           scan=None, calibration=None)
    with pytest.raises(CommandError):
        bare.dispatch("autofocus", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_focus_commands.py -v`
Expected: FAIL — `UnknownCommand: Unknown command 'autofocus'`

- [ ] **Step 3: Write minimal implementation**

Register in `_handlers`:

```python
            "autofocus": self._autofocus,
            "tilt_start": self._tilt_start,
            "tilt_measure": self._tilt_measure,
            "tilt_complete": self._tilt_complete,
```

Add the methods:

```python
    def _need_calibration(self):
        """Return the calibration controller or raise.

        Returns:
            The calibration controller

        Raises:
            CommandError: If the server was built without one
        """
        if self.calibration is None:
            raise CommandError("No calibration controller is available")
        return self.calibration

    def _autofocus(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run a quick autofocus sweep.

        This blocks until focus is found, because CalibrationController is
        not threaded. Expect roughly one to three seconds for 20 steps.

        Args:
            args: Optional "num_steps" and "search_range"

        Returns:
            The focus height found and the resulting stage position

        Raises:
            CommandError: If autofocus does not converge
        """
        calibration = self._need_calibration()
        focus_z = calibration.quick_autofocus(
            num_steps=int(args.get("num_steps", 20)),
            search_range=float(args.get("search_range", 2.0)),
        )
        if focus_z is None:
            raise CommandError("Autofocus failed to find a focus position")
        return {"focus_z": float(focus_z), "position": self._position_dict()}

    def _tilt_start(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Begin a tilt calibration sequence."""
        started = self._need_calibration().start_tilt_calibration(
            num_corners=int(args.get("num_corners", 4))
        )
        return {"started": bool(started)}

    def _tilt_measure(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Measure one tilt-calibration corner."""
        measured = self._need_calibration().measure_tilt_corner(
            int(self._require(args, "corner_idx"))
        )
        return {"measured": bool(measured),
                "corner_idx": int(args["corner_idx"])}

    def _tilt_complete(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Finish the tilt calibration and fit the plane."""
        return {"completed": bool(self._need_calibration()
                                  .complete_tilt_calibration())}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_focus_commands.py -v`
Expected: PASS, 4 tests. Then `.venv/bin/python -m pytest tests/ -q`

If `test_autofocus_finds_the_focal_plane` fails, do NOT widen the tolerance to
make it green — report the sharpness values across the sweep so the cause can be
established. The simulator's peak is roughly 44x above its neighbours, so
autofocus should converge easily.

- [ ] **Step 5: Commit**

```bash
git add kalib/server/commands.py tests/test_server/test_focus_commands.py
git commit -m "feat: add autofocus and tilt calibration commands"
```

---

### Task 5: Scan job commands

**Files:**
- Modify: `kalib/server/commands.py`
- Test: `tests/test_server/test_scan_commands.py`

**Interfaces:**
- Consumes: `CommandRegistry`; `ScanController`; `XYScanParameters`, `ZStackParameters` from `kalib.models`.
- Produces: commands `scan_xy`, `scan_z`, `job_status`, `job_cancel`. `scan_xy` and `scan_z` return `{"job_id": str, "started": bool}` immediately. `job_status() -> {"job_id", "scanning", "progress"}`. `job_cancel() -> {"cancelled": bool}`.

**Why there is only ever one job:** `ScanController` owns a single scan thread
and `is_scanning`/`cancel_scan()` refer to it. Modelling a job queue would
invent state the controller does not have. Starting a scan while one runs is
rejected.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_scan_commands.py
"""Tests for scan job commands."""

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.scan_controller import ScanController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.base import CommandError
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def registry():
    """A registry with a scan controller over simulated hardware."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    factory.world.width, factory.world.height = 64, 64
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    scan = ScanController(camera_controller=camera, stage_controller=stage)
    return CommandRegistry(camera=camera, stage=stage, scan=scan,
                           calibration=None)


def test_scan_xy_returns_a_job_id_without_blocking(registry):
    """Starting a scan returns immediately with an identifier."""
    result = registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 2.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    assert result["started"] is True
    assert isinstance(result["job_id"], str) and result["job_id"]


def test_job_status_reports_the_running_job(registry):
    """job_status reports scanning state and progress."""
    registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 2.0, "end_y": 2.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    status = registry.dispatch("job_status", {})
    assert set(status) >= {"job_id", "scanning", "progress"}


def test_job_cancel_stops_the_scan(registry):
    """A running scan can be cancelled."""
    registry.dispatch("scan_xy", {
        "start_x": 0.0, "start_y": 0.0, "end_x": 5.0, "end_y": 5.0,
        "step_x": 1.0, "step_y": 1.0,
    })
    assert registry.dispatch("job_cancel", {})["cancelled"] is True


def test_job_status_with_no_job_reports_idle(registry):
    """Asking for status before any scan is not an error."""
    status = registry.dispatch("job_status", {})
    assert status["scanning"] is False
    assert status["job_id"] is None


def test_scan_requires_a_scan_controller(registry):
    """A registry built without a scan controller says so."""
    bare = CommandRegistry(camera=registry.camera, stage=registry.stage,
                           scan=None, calibration=None)
    with pytest.raises(CommandError):
        bare.dispatch("scan_xy", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_scan_commands.py -v`
Expected: FAIL — `UnknownCommand: Unknown command 'scan_xy'`

- [ ] **Step 3: Write minimal implementation**

Add to imports:

```python
import uuid

from kalib.models import XYScanParameters, ZStackParameters
```

Add `self._job_id: Optional[str] = None` to `__init__`, and register:

```python
            "scan_xy": self._scan_xy,
            "scan_z": self._scan_z,
            "job_status": self._job_status,
            "job_cancel": self._job_cancel,
```

Add the methods:

```python
    def _need_scan(self):
        """Return the scan controller or raise.

        Returns:
            The scan controller

        Raises:
            CommandError: If the server was built without one
        """
        if self.scan is None:
            raise CommandError("No scan controller is available")
        return self.scan

    def _start_job(self, save_path: Optional[str]) -> Dict[str, Any]:
        """Start the configured scan and register it as the current job.

        Args:
            save_path: Directory for scan output, or None for the default

        Returns:
            The new job id and whether the scan started

        Raises:
            CommandError: If a scan is already running
        """
        scan = self._need_scan()
        if scan.is_scanning:
            raise CommandError(
                f"A scan is already running (job {self._job_id}). "
                f"Cancel it first."
            )
        started = scan.start_scan(save_path=save_path)
        self._job_id = uuid.uuid4().hex[:8] if started else None
        return {"job_id": self._job_id, "started": bool(started)}

    def _scan_xy(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Configure and start an XY grid scan."""
        scan = self._need_scan()
        scan.configure_xy_scan(XYScanParameters(
            start_x=float(args.get("start_x", 0.0)),
            start_y=float(args.get("start_y", 0.0)),
            end_x=float(args.get("end_x", 10.0)),
            end_y=float(args.get("end_y", 10.0)),
            step_x=float(args.get("step_x", 1.0)),
            step_y=float(args.get("step_y", 1.0)),
        ))
        return self._start_job(args.get("save_path"))

    def _scan_z(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Configure and start a Z-stack scan."""
        scan = self._need_scan()
        scan.configure_z_stack(ZStackParameters(
            start_z=float(args.get("start_z", 0.0)),
            end_z=float(args.get("end_z", 5.0)),
            step_z=float(args.get("step_z", 0.1)),
        ))
        return self._start_job(args.get("save_path"))

    def _job_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Report the current scan job, if any."""
        scan = self._need_scan()
        scanning = scan.is_scanning
        if not scanning:
            self._job_id = None
        return {"job_id": self._job_id, "scanning": bool(scanning),
                "progress": float(scan.scan_progress)}

    def _job_cancel(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel the running scan."""
        cancelled = self._need_scan().cancel_scan()
        if cancelled:
            self._job_id = None
        return {"cancelled": bool(cancelled)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_scan_commands.py -v`
Expected: PASS, 5 tests. Then `.venv/bin/python -m pytest tests/ -q`

A scan runs on a `QThread`, so these tests need a running Qt event loop only if
they wait for completion — they do not. If a test hangs, report it rather than
adding sleeps.

- [ ] **Step 5: Commit**

```bash
git add kalib/server/commands.py tests/test_server/test_scan_commands.py
git commit -m "feat: add scan job commands"
```

---
### Task 6: The daemon — a QTcpServer on 127.0.0.1

**Files:**
- Create: `kalib/server/daemon.py`
- Test: `tests/test_server/test_daemon.py`

**Interfaces:**
- Consumes: `protocol` (Task 1) and `CommandRegistry` (Tasks 2-5).
- Produces: `CommandDaemon(registry, port: int = 8765, host: str = "127.0.0.1")`, a `QObject` with `start() -> int` (returns the bound port), `stop() -> None`, `is_listening() -> bool`, and the signal `command_served = Signal(str, bool)` (command name, ok).

**Why `QTcpServer`:** it delivers `newConnection` and `readyRead` on the Qt
event loop, so handlers run on the main thread with the controllers and need no
marshalling. This is the whole reason the spec's `QMetaObject.invokeMethod`
layer is absent.

**Binding:** `QHostAddress.SpecialAddress.LocalHost` only. SSH provides the
network hop and authentication. Binding anything else is a defect.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_daemon.py
"""Tests for the command daemon."""

import socket

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry
from kalib.server.daemon import CommandDaemon
from kalib.server.protocol import decode_message, encode_request


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def daemon(qapp):
    """A listening daemon over simulated hardware, stopped after the test."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    server = CommandDaemon(registry, port=0)
    server.start()
    yield server
    server.stop()


def _round_trip(daemon, qapp, cmd, args):
    """Send one command over a real socket and return the decoded reply.

    Args:
        daemon: The listening CommandDaemon
        qapp: The Qt application, pumped while waiting
        cmd: Command name
        args: Command arguments

    Returns:
        The decoded response message
    """
    with socket.create_connection(("127.0.0.1", daemon.port), timeout=5) as sock:
        sock.sendall(encode_request(cmd, args, "t1"))
        sock.settimeout(5)
        buf = b""
        while not buf.endswith(b"\n"):
            qapp.processEvents()
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
        return decode_message(buf)


def test_daemon_listens_on_localhost(daemon):
    """The daemon binds and reports a port."""
    assert daemon.is_listening() is True
    assert daemon.port > 0


def test_daemon_binds_loopback_only(daemon):
    """Binding must be loopback — the server never faces the network."""
    assert daemon.host_address() == "127.0.0.1"


def test_command_round_trips_over_a_real_socket(daemon, qapp):
    """A request on the wire produces a matching response."""
    msg = _round_trip(daemon, qapp, "get_position", {})
    assert msg["ok"] is True
    assert set(msg["result"]) == {"x", "y", "z"}
    assert msg["id"] == "t1"


def test_unknown_command_returns_an_error_response(daemon, qapp):
    """An unknown command produces an error, not a dropped connection."""
    msg = _round_trip(daemon, qapp, "teleport", {})
    assert msg["ok"] is False
    assert msg["error"]["type"] == "UnknownCommand"


def test_stop_releases_the_port(daemon):
    """After stop the daemon is no longer listening."""
    daemon.stop()
    assert daemon.is_listening() is False
```

Add this fixture to `tests/conftest.py` (it is shared by later tasks):

```python
@pytest.fixture(scope="session")
def qapp():
    """A QApplication for tests that need a Qt event loop."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_daemon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.server.daemon'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/server/daemon.py
"""A localhost command server embedded in the Kalib Qt application.

QTcpServer delivers its signals on the Qt event loop, so command handlers run
on the main thread alongside the controllers and need no cross-thread
marshalling. The server binds loopback only: SSH provides the network hop and
authentication, so the server implements none of its own.
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from kalib.server.commands import CommandRegistry
from kalib.server.protocol import (
    ProtocolError,
    decode_message,
    encode_error,
    encode_ok,
)
from kalib.utils.logger import get_logger

DEFAULT_PORT = 8765


class CommandDaemon(QObject):
    """Serve commands over a loopback TCP socket.

    Example:
        daemon = CommandDaemon(registry)
        daemon.start()
    """

    command_served = Signal(str, bool)  # command name, ok

    def __init__(self, registry: CommandRegistry, port: int = DEFAULT_PORT,
                 parent: Optional[QObject] = None):
        """Initialize the daemon.

        Args:
            registry: Command registry to dispatch into
            port: TCP port to bind; 0 asks the OS for a free one
            parent: Optional Qt parent
        """
        super().__init__(parent)
        self._logger = get_logger(__name__)
        self._registry = registry
        self._requested_port = port
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._buffers = {}

    @property
    def port(self) -> int:
        """The bound port, or 0 when not listening."""
        return int(self._server.serverPort())

    def host_address(self) -> str:
        """The bound address as a string."""
        return self._server.serverAddress().toString()

    def is_listening(self) -> bool:
        """Whether the server is accepting connections."""
        return bool(self._server.isListening())

    def start(self) -> int:
        """Begin listening on loopback.

        Returns:
            The bound port

        Raises:
            RuntimeError: If the port cannot be bound
        """
        if not self._server.listen(QHostAddress(
                QHostAddress.SpecialAddress.LocalHost), self._requested_port):
            raise RuntimeError(
                f"Could not bind 127.0.0.1:{self._requested_port}: "
                f"{self._server.errorString()}"
            )
        self._logger.info(f"Command server listening on 127.0.0.1:{self.port}")
        return self.port

    def stop(self) -> None:
        """Stop listening and drop any open connections."""
        for sock in list(self._buffers):
            sock.disconnectFromHost()
        self._buffers.clear()
        if self._server.isListening():
            self._server.close()
            self._logger.info("Command server stopped")

    def _on_new_connection(self) -> None:
        """Accept a pending connection and wire its signals."""
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_disconnected(s))
            self._logger.debug("Client connected")

    def _on_disconnected(self, sock: QTcpSocket) -> None:
        """Forget a client that has gone away."""
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock: QTcpSocket) -> None:
        """Consume whole lines from a client and answer each one."""
        self._buffers[sock] = self._buffers.get(sock, b"") + bytes(sock.readAll())
        while b"\n" in self._buffers[sock]:
            line, _, rest = self._buffers[sock].partition(b"\n")
            self._buffers[sock] = rest
            sock.write(self._handle_line(line + b"\n"))
            sock.flush()

    def _handle_line(self, line: bytes) -> bytes:
        """Decode, dispatch and encode one request.

        Args:
            line: One newline-terminated request

        Returns:
            The encoded response
        """
        request_id = "?"
        try:
            msg = decode_message(line)
            request_id = str(msg.get("id", "?"))
            cmd = msg.get("cmd", "")
            result = self._registry.dispatch(cmd, msg.get("args") or {})
            self.command_served.emit(cmd, True)
            return encode_ok(request_id, result)
        except ProtocolError as exc:
            self._logger.warning(f"Protocol error: {exc}")
            return encode_error(request_id, exc)
        except Exception as exc:
            self._logger.error(f"Command failed: {exc}", exc_info=True)
            self.command_served.emit(locals().get("cmd", ""), False)
            return encode_error(request_id, exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_daemon.py -v`
Expected: PASS, 5 tests. Then `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add kalib/server/daemon.py tests/test_server/test_daemon.py tests/conftest.py
git commit -m "feat: add localhost command daemon on QTcpServer"
```

---

### Task 7: `--serve` flag and application wiring

**Files:**
- Modify: `kalib/main.py` (`parse_arguments`, `KalibApplication.__init__`, `initialize`, `cleanup`)
- Test: `tests/test_server/test_serve_wiring.py`

**Interfaces:**
- Consumes: `CommandDaemon` (Task 6), `CommandRegistry` (Tasks 2-5).
- Produces: `--serve` and `--serve-port` flags; `KalibApplication(config_path=None, log_level=None, simulate=False, serve=False, serve_port=8765)`; attribute `self.daemon: Optional[CommandDaemon]`; method `_start_command_server() -> None`.

**Preserve the existing property:** real drivers stay lazily constructed. The
daemon must not cause any hardware to be built at startup — it only holds
references to the controllers.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_serve_wiring.py
"""Tests for the --serve flag and daemon wiring."""

from kalib.main import parse_arguments


def test_serve_defaults_to_off():
    """Without the flag no command server runs."""
    assert parse_arguments([]).serve is False


def test_serve_flag_enables_the_server():
    """--serve turns the command server on."""
    assert parse_arguments(["--serve"]).serve is True


def test_serve_port_has_a_default():
    """A default port is supplied when none is given."""
    assert parse_arguments(["--serve"]).serve_port == 8765


def test_serve_port_can_be_overridden():
    """--serve-port sets the bound port."""
    assert parse_arguments(["--serve", "--serve-port", "9100"]).serve_port == 9100


def test_existing_flags_still_parse():
    """Adding the flags does not disturb the existing ones."""
    args = parse_arguments(["--simulate", "--log-level", "DEBUG"])
    assert args.simulate is True
    assert args.log_level == "DEBUG"
    assert args.serve is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_serve_wiring.py -v`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'serve'`

- [ ] **Step 3: Write minimal implementation**

In `parse_arguments`, alongside the existing arguments:

```python
    parser.add_argument(
        '--serve',
        action='store_true',
        help="Run a localhost command server so the instrument can be driven remotely"
    )

    parser.add_argument(
        '--serve-port',
        type=int,
        default=8765,
        help="Port for the command server (default: 8765)"
    )
```

In `main()`:

```python
    app = KalibApplication(
        config_path=args.config,
        log_level=args.log_level,
        simulate=args.simulate,
        serve=args.serve,
        serve_port=args.serve_port
    )
```

In `KalibApplication.__init__`, add the parameters and store them, leaving the
rest of the body unchanged:

```python
    def __init__(self, config_path: str = None, log_level: str = None,
                 simulate: bool = False, serve: bool = False,
                 serve_port: int = 8765):
        """Initialize application.

        Args:
            config_path: Path to configuration file
            log_level: Logging level override
            simulate: Run against simulated hardware instead of the instrument
            serve: Run a localhost command server for remote operation
            serve_port: Port for the command server
        """
        self._simulate = simulate
        self._serve = serve
        self._serve_port = serve_port
        self.daemon = None
```

At the end of `initialize()`, immediately before `return True`:

```python
            if self._serve:
                self._start_command_server()
```

Add the method:

```python
    def _start_command_server(self) -> None:
        """Start the localhost command server.

        The daemon only holds references to the controllers; it constructs no
        hardware, so the real drivers stay lazily built as before.
        """
        from kalib.server.commands import CommandRegistry
        from kalib.server.daemon import CommandDaemon

        registry = CommandRegistry(
            camera=self.camera,
            stage=self.stage,
            scan=self.scan,
            calibration=self.calibration,
        )
        self.daemon = CommandDaemon(registry, port=self._serve_port)
        port = self.daemon.start()
        self._logger.info(
            f"Command server ready on 127.0.0.1:{port}. "
            f"Drive it over SSH with: ssh <host> kalib-cli <command>"
        )
```

In `cleanup()`, before the existing controller cleanup:

```python
            if self.daemon is not None:
                self.daemon.stop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_serve_wiring.py -v`
Expected: PASS, 5 tests

Then: `.venv/bin/python -m pytest tests/ -q` and
`.venv/bin/python -m kalib.main --help` — confirm `--serve` and `--serve-port`
are listed.

- [ ] **Step 5: Commit**

```bash
git add kalib/main.py tests/test_server/test_serve_wiring.py
git commit -m "feat: add --serve flag starting the command server"
```

---

### Task 8: The CLI client

**Files:**
- Create: `kalib/cli/__init__.py`, `kalib/cli/__main__.py`, `kalib/cli/client.py`
- Test: `tests/test_server/test_cli.py`

**Interfaces:**
- Consumes: `protocol` (Task 1); a running `CommandDaemon`.
- Produces: `send_command(cmd: str, args: dict, host: str = "127.0.0.1", port: int = 8765, timeout: float = 30.0) -> dict` raising `CommandFailed(RuntimeError)` on an error response; `build_parser() -> argparse.ArgumentParser`; `main(argv: Optional[List[str]] = None) -> int`.

**Usage from the development machine:**
`ssh winbox python -m kalib.cli move-xy --x 10 --y 20`

Command names are hyphenated on the CLI and underscored on the wire.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_cli.py
"""Tests for the command line client."""

import pytest

from kalib.cli.client import CommandFailed, build_parser, cli_to_wire


def test_parser_accepts_a_command_and_arguments():
    """The parser takes a command name and key/value arguments."""
    args = build_parser().parse_args(["move-xy", "--x", "1.5", "--y", "2.5"])
    assert args.command == "move-xy"
    assert args.x == 1.5
    assert args.y == 2.5


def test_parser_has_a_port_option():
    """The port is overridable for non-default deployments."""
    args = build_parser().parse_args(["status", "--port", "9100"])
    assert args.port == 9100


def test_cli_names_map_to_wire_names():
    """Hyphenated CLI names become underscored wire names."""
    assert cli_to_wire("move-xy") == "move_xy"
    assert cli_to_wire("job-status") == "job_status"
    assert cli_to_wire("status") == "status"


def test_command_failed_is_a_runtime_error():
    """Callers can catch failures without importing a bespoke base."""
    assert issubclass(CommandFailed, RuntimeError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/cli/__init__.py
"""Command line client for driving a running Kalib command server."""
```

```python
# kalib/cli/client.py
"""Talk to a running Kalib command server over a loopback socket.

Intended to be invoked over SSH from the development machine:

    ssh winbox python -m kalib.cli move-xy --x 10 --y 20

SSH carries the network hop and the authentication; this client only ever
connects to localhost on the machine it runs on.
"""

import argparse
import json
import socket
import sys
import uuid
from typing import Any, Dict, List, Optional

from kalib.server.protocol import decode_message, encode_request

DEFAULT_PORT = 8765


class CommandFailed(RuntimeError):
    """Raised when the server answers with an error response."""


def cli_to_wire(name: str) -> str:
    """Convert a hyphenated CLI command name to its wire form.

    Args:
        name: CLI command name, e.g. "move-xy"

    Returns:
        The wire command name, e.g. "move_xy"
    """
    return name.replace("-", "_")


def send_command(cmd: str, args: Dict[str, Any], host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT, timeout: float = 30.0) -> Any:
    """Send one command and return its result.

    Args:
        cmd: Wire command name
        args: Command arguments
        host: Server host; always loopback in normal use
        port: Server port
        timeout: Socket timeout in seconds

    Returns:
        The command's result payload

    Raises:
        CommandFailed: If the server answers with an error
    """
    request_id = uuid.uuid4().hex[:8]
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(encode_request(cmd, args, request_id))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                raise CommandFailed("Server closed the connection")
            buf += chunk

    msg = decode_message(buf)
    if not msg.get("ok"):
        error = msg.get("error", {})
        raise CommandFailed(f"{error.get('type', 'Error')}: "
                            f"{error.get('message', 'unknown')}")
    return msg.get("result")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        The configured parser
    """
    parser = argparse.ArgumentParser(
        prog="kalib.cli",
        description="Drive a running Kalib command server."
    )
    parser.add_argument("command", help="Command name, e.g. move-xy, snap, status")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Socket timeout in seconds (default: 30)")
    for name in ("x", "y", "z", "dx", "dy", "dz", "start_x", "start_y",
                 "end_x", "end_y", "step_x", "step_y", "start_z", "end_z",
                 "step_z", "search_range"):
        parser.add_argument(f"--{name}", type=float, default=None)
    for name in ("num_steps", "num_corners", "corner_idx", "max_px"):
        parser.add_argument(f"--{name}", type=int, default=None)
    for name in ("path", "save_path"):
        parser.add_argument(f"--{name}", type=str, default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run one command and print its result as JSON.

    Args:
        argv: Argument list; reads sys.argv when None

    Returns:
        Process exit code: 0 on success, 1 on a command error
    """
    args = build_parser().parse_args(argv)
    reserved = {"command", "port", "timeout"}
    payload = {k: v for k, v in vars(args).items()
               if k not in reserved and v is not None}
    try:
        result = send_command(cli_to_wire(args.command), payload,
                              port=args.port, timeout=args.timeout)
    except (CommandFailed, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
```

```python
# kalib/cli/__main__.py
"""Entry point for `python -m kalib.cli`."""

import sys

from kalib.cli.client import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_cli.py -v`
Expected: PASS, 4 tests. Then `.venv/bin/python -m pytest tests/ -q`

Also confirm the entry point loads: `.venv/bin/python -m kalib.cli --help`

- [ ] **Step 5: Commit**

```bash
git add kalib/cli/ tests/test_server/test_cli.py
git commit -m "feat: add CLI client for the command server"
```

---

### Task 9: End-to-end test and safe state on shutdown

**Files:**
- Modify: `kalib/server/daemon.py` (add `shutdown_safe_state`)
- Test: `tests/test_server/test_end_to_end.py`

**Interfaces:**
- Consumes: everything from Tasks 1-8.
- Produces: `CommandDaemon.shutdown_safe_state() -> dict`, called from `stop()`. Returns `{"acquisition_stopped": bool, "scan_cancelled": bool}`.

**Safe state, deliberately narrow:** stop acquisition and cancel any running
scan. **Stages are left exactly where they are and are never homed.** Homing a
microscopy stage unattended risks driving the objective into the sample; parking
is the safe failure mode and recovery is a human decision. This is a
requirement from the spec, not an implementation preference.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server/test_end_to_end.py
"""End-to-end tests driving simulated hardware through the wire protocol."""

import socket

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.server.commands import CommandRegistry
from kalib.server.daemon import CommandDaemon
from kalib.server.protocol import decode_message, encode_request


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def rig(qapp):
    """A daemon plus the controllers behind it."""
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    factory.world.width, factory.world.height = 64, 64
    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    registry = CommandRegistry(camera=camera, stage=stage, scan=None,
                               calibration=None)
    daemon = CommandDaemon(registry, port=0)
    daemon.start()
    yield daemon, camera, stage, factory.world
    daemon.stop()


def _send(daemon, qapp, cmd, args):
    """Send one command over a real socket and return the decoded reply."""
    with socket.create_connection(("127.0.0.1", daemon.port), timeout=5) as sock:
        sock.sendall(encode_request(cmd, args, "e2e"))
        sock.settimeout(5)
        buf = b""
        while not buf.endswith(b"\n"):
            qapp.processEvents()
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
        return decode_message(buf)


def test_moving_over_the_wire_moves_the_simulated_stage(rig, qapp):
    """A command on the socket reaches the hardware layer."""
    daemon, _camera, _stage, world = rig
    _send(daemon, qapp, "move_xy", {"x": 42.0, "y": 24.0})
    assert world.x == pytest.approx(42.0)
    assert world.y == pytest.approx(24.0)


def test_preview_over_the_wire_reflects_focus(rig, qapp):
    """Sharpness reported over the wire drops as the stage defocuses."""
    daemon, _camera, _stage, world = rig
    world.tilt_a = world.tilt_b = 0.0
    world.tilt_c = 5.0

    _send(daemon, qapp, "move_z", {"z": 5.0})
    focused = _send(daemon, qapp, "preview", {"max_px": 64})["result"]["sharpness"]

    _send(daemon, qapp, "move_z", {"z": 8.0})
    blurred = _send(daemon, qapp, "preview", {"max_px": 64})["result"]["sharpness"]

    assert focused > blurred


def test_snap_over_the_wire_writes_a_file(rig, qapp, tmp_path):
    """A capture requested over the wire lands on disk."""
    daemon, _camera, _stage, _world = rig
    target = tmp_path / "wire.tiff"
    msg = _send(daemon, qapp, "snap", {"path": str(target)})
    assert msg["ok"] is True
    assert target.exists()


def test_shutdown_stops_acquisition_but_leaves_the_stage(rig):
    """Safe state stops acquisition and never moves the stage."""
    daemon, camera, _stage, world = rig
    before = (world.x, world.y, world.z)

    result = daemon.shutdown_safe_state()

    assert result["acquisition_stopped"] is True
    assert camera.is_acquiring is False
    assert (world.x, world.y, world.z) == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server/test_end_to_end.py -v`
Expected: FAIL — `AttributeError: 'CommandDaemon' object has no attribute 'shutdown_safe_state'`

- [ ] **Step 3: Write minimal implementation**

Add to `CommandDaemon` in `kalib/server/daemon.py`:

```python
    def shutdown_safe_state(self) -> dict:
        """Put the instrument into a safe state.

        Stops acquisition and cancels any running scan. The stages are
        deliberately left exactly where they are and are never homed: homing
        a microscopy stage unattended risks driving the objective into the
        sample, so parking is the safe failure mode and recovery is a human
        decision.

        Returns:
            What was actually stopped
        """
        registry = self._registry
        acquisition_stopped = False
        scan_cancelled = False

        try:
            if registry.camera is not None and registry.camera.is_acquiring:
                acquisition_stopped = bool(registry.camera.stop_acquisition())
        except Exception as exc:
            self._logger.error(f"Could not stop acquisition: {exc}")

        try:
            if registry.scan is not None and registry.scan.is_scanning:
                scan_cancelled = bool(registry.scan.cancel_scan())
        except Exception as exc:
            self._logger.error(f"Could not cancel scan: {exc}")

        self._logger.info(
            f"Safe state: acquisition_stopped={acquisition_stopped}, "
            f"scan_cancelled={scan_cancelled}; stages left in place"
        )
        return {"acquisition_stopped": acquisition_stopped,
                "scan_cancelled": scan_cancelled}
```

And call it as the first statement of `stop()`:

```python
    def stop(self) -> None:
        """Stop listening, put the instrument in a safe state, drop clients."""
        self.shutdown_safe_state()
        for sock in list(self._buffers):
            sock.disconnectFromHost()
        self._buffers.clear()
        if self._server.isListening():
            self._server.close()
            self._logger.info("Command server stopped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_server/test_end_to_end.py -v`
Expected: PASS, 4 tests. Then `.venv/bin/python -m pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add kalib/server/daemon.py tests/test_server/test_end_to_end.py
git commit -m "feat: put the instrument in a safe state on server shutdown"
```

---

### Task 10: Document remote operation

**Files:**
- Modify: `README.md` (new "Operating the Instrument Remotely" section)
- Modify: `CLAUDE.md` (Development Commands)
- Create: `docs/REMOTE_OPERATION.md`

- [ ] **Step 1: Verify every documented command actually works**

Start a server against simulated hardware in one terminal:

```bash
.venv/bin/python -m kalib.main --simulate --serve
```

In another, exercise the commands you are about to document:

```bash
.venv/bin/python -m kalib.cli status
.venv/bin/python -m kalib.cli move-xy --x 10 --y 20
.venv/bin/python -m kalib.cli get-position
.venv/bin/python -m kalib.cli snap --path /tmp/shot.tiff
.venv/bin/python -m kalib.cli preview --max_px 256
```

Record the real output. Document nothing you have not run.

- [ ] **Step 2: Write `docs/REMOTE_OPERATION.md`**

Cover, in this order: the architecture in three sentences (server inside the
GUI, loopback only, SSH for transport and auth); prerequisites (OpenSSH Server
on the instrument machine); starting the server; the full command table with one
example each; how images come back (`snap` writes to the instrument's disk,
fetch with `scp`; `preview` is the only command returning pixels); scan jobs and
how to poll them; and the safe-state behaviour on shutdown, stating explicitly
that stages are never homed.

Include this note verbatim, because it is the thing most likely to surprise:

> Live preview renders on the instrument's own screen and never crosses the
> network. A full frame is 36 MB; a gigabit link carries about 118 MB/s, so
> streaming full-resolution video is not possible at any useful frame rate. Use
> `preview` for a quick look, and RDP to the instrument when you want to watch
> continuously.

- [ ] **Step 3: Add a short section to README.md and one line to CLAUDE.md**

README, in the Development section after "Running Without Hardware":

````markdown
### Operating the Instrument Remotely

Run Kalib on the instrument machine with a command server attached:

```bash
python -m kalib.main --serve
```

Then drive it from another machine over SSH:

```bash
ssh <instrument-host> python -m kalib.cli move-xy --x 10 --y 20
ssh <instrument-host> python -m kalib.cli snap --path C:\data\shot.tiff
```

See [docs/REMOTE_OPERATION.md](docs/REMOTE_OPERATION.md) for the full command
set. Live preview stays on the instrument's screen; only `preview` returns
image data, downscaled and compressed.
````

CLAUDE.md, under Development Commands:

```markdown
# Command server:      python -m kalib.main --serve
```

- [ ] **Step 4: Confirm links resolve and commit**

```bash
grep -o '](docs/[A-Za-z_]*\.md' README.md | sed 's/](//' | while read f; do
  test -f "$f" && echo "OK $f" || echo "BROKEN $f"; done
git add README.md CLAUDE.md docs/REMOTE_OPERATION.md
git commit -m "docs: document remote operation over SSH"
```

---

## Definition of Done

- [ ] `.venv/bin/python -m pytest tests/ -q` passes
- [ ] `python -m kalib.main --simulate --serve` starts and serves commands
- [ ] `python -m kalib.cli status` returns device state over a real socket
- [ ] The server binds 127.0.0.1 only, verified by a test
- [ ] No command returns full-resolution pixel data
- [ ] Shutdown stops acquisition and cancels scans, and never moves the stages
- [ ] Real drivers are still constructed lazily; `--serve` builds no hardware

## Out of Scope

- **`set_led`** — there is no LED controller in the application. Adding one is separate work.
- **Record/replay** — a separate plan; it needs no server.
- **Multi-client access** — one operator at a time, per the spec.
- **Authentication in the server** — SSH provides it.
- **Moving autofocus onto a worker thread** — revisit only if blocking proves painful in use.
