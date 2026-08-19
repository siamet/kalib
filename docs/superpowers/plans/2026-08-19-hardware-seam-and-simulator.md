# Hardware Seam and Simulation Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the hardware layer injectable and add a simulation backend, so the entire application can run and be tested on the Linux development machine with no instrument attached.

**Architecture:** Controllers currently construct their own concrete drivers, so there is no seam at which to substitute a simulator. Each controller gains an optional `device` parameter that takes precedence over building the real driver. A factory reads configuration and decides which to build. The simulators share a single `SimWorld` object holding virtual stage position, LED brightness, and a tilted focal plane, so that a simulated capture is genuinely blurrier away from focus - which is what makes autofocus and tilt calibration testable without hardware.

**Tech Stack:** Python 3.12, PySide6 6.8.0.2, NumPy 2.2.6, OpenCV (headless) 4.14, pytest 9.1.1, uv.

**Spec:** `docs/superpowers/specs/2026-08-19-remote-operation-design.md`

## Global Constraints

- Python 3.12; dependencies installed with `uv pip sync requirements.lock`.
- Run everything through the project venv: `.venv/bin/python`.
- `PySide6==6.8.0.2` and `opencv-python-headless>=4.7.0,<5` are pinned. Do not change them.
- Files under 500 lines; functions under 50 lines; classes under 100 lines.
- Google-style docstrings and type annotations on all public APIs, per `docs/ENGINEERING-STANDARDS.md`.
- Simulators must subclass `HardwareDevice` from `kalib/hardware/base.py` and implement `_do_connect`, `_do_disconnect`, `_do_initialize`.
- Simulators must not import `ids_peak`, `pipython`, or `serial`.
- Never modify `config/config.yaml` - it holds the instrument's own device IDs.

---

### Task 1: SimWorld - shared virtual instrument state

**Files:**
- Create: `kalib/hardware/sim/__init__.py`
- Create: `kalib/hardware/sim/world.py`
- Test: `tests/test_hardware/test_sim_world.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SimWorld` dataclass with fields `x, y, z, led_brightness, tilt_a, tilt_b, tilt_c, width, height, seed`; methods `focus_z(x=None, y=None) -> float` and `defocus() -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardware/test_sim_world.py
"""Tests for the simulated instrument world."""

import pytest
from kalib.hardware.sim.world import SimWorld


def test_focus_plane_is_tilted():
    """Focal height varies with position when tilt coefficients are non-zero."""
    world = SimWorld(tilt_a=0.01, tilt_b=0.02, tilt_c=5.0)
    assert world.focus_z(0.0, 0.0) == pytest.approx(5.0)
    assert world.focus_z(100.0, 0.0) == pytest.approx(6.0)
    assert world.focus_z(0.0, 100.0) == pytest.approx(7.0)


def test_defocus_is_zero_on_the_focal_plane():
    """Defocus is zero when z sits exactly on the focal plane."""
    world = SimWorld(x=10.0, y=20.0, tilt_a=0.01, tilt_b=0.02, tilt_c=5.0)
    world.z = world.focus_z()
    assert world.defocus() == pytest.approx(0.0)


def test_defocus_grows_with_distance_from_plane():
    """Defocus is the absolute distance from the focal plane."""
    world = SimWorld(x=0.0, y=0.0, tilt_a=0.0, tilt_b=0.0, tilt_c=5.0)
    world.z = 5.5
    assert world.defocus() == pytest.approx(0.5)
    world.z = 4.5
    assert world.defocus() == pytest.approx(0.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_world.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.hardware.sim'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/hardware/sim/__init__.py
"""Simulated hardware devices for development without an instrument."""

from kalib.hardware.sim.world import SimWorld

__all__ = ['SimWorld']
```

```python
# kalib/hardware/sim/world.py
"""Shared state for the simulated instrument.

All simulated devices read and write a single SimWorld, so that moving the
simulated stage changes what the simulated camera sees. This is what makes
autofocus and tilt calibration exercisable without hardware.
"""

from dataclasses import dataclass


@dataclass
class SimWorld:
    """State of the virtual instrument.

    The sample sits on a tilted plane, so the z height that is in focus
    depends on where the stage is in x and y:

        z_focus(x, y) = tilt_a * x + tilt_b * y + tilt_c

    Attributes:
        x: Stage X position in mm
        y: Stage Y position in mm
        z: Stage Z position in mm
        led_brightness: LED level in raw device units
        tilt_a: Focal plane gradient along X (mm of z per mm of x)
        tilt_b: Focal plane gradient along Y
        tilt_c: Focal plane height at the origin, in mm
        width: Simulated sensor width in pixels
        height: Simulated sensor height in pixels
        seed: Seed for the synthetic sample pattern, so frames are repeatable
    """

    x: float = 50.0
    y: float = 50.0
    z: float = 5.0
    led_brightness: int = 0
    tilt_a: float = 0.002
    tilt_b: float = -0.001
    tilt_c: float = 5.0
    width: int = 640
    height: int = 480
    seed: int = 1234

    def focus_z(self, x: float | None = None, y: float | None = None) -> float:
        """Return the in-focus z height at a position.

        Args:
            x: X position in mm; defaults to the current stage X
            y: Y position in mm; defaults to the current stage Y

        Returns:
            The z height in mm at which that position is in focus
        """
        x = self.x if x is None else x
        y = self.y if y is None else y
        return self.tilt_a * x + self.tilt_b * y + self.tilt_c

    def defocus(self) -> float:
        """Return absolute distance in mm between current z and focus.

        Returns:
            Distance from the focal plane; zero means perfectly focused
        """
        return abs(self.z - self.focus_z())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_world.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/hardware/sim/ tests/test_hardware/test_sim_world.py
git commit -m "feat: add SimWorld shared state for simulated hardware"
```

---

### Task 2: SimCamera - synthetic frames that respond to focus

**Files:**
- Create: `kalib/hardware/sim/sim_camera.py`
- Modify: `kalib/hardware/sim/__init__.py`
- Test: `tests/test_hardware/test_sim_camera.py`

**Interfaces:**
- Consumes: `SimWorld` from Task 1.
- Produces: `SimCamera(world: SimWorld, device_idx: int = 0, name: str | None = None)`. Mirrors the public API of `IDSCamera`: `start_acquisition() -> None`, `stop_acquisition() -> None`, `capture(timeout_ms: int = 1000, force_8bit: bool = False) -> np.ndarray`, `set_exposure_time(exposure_us: float) -> None`, `get_exposure_time() -> float`, `set_gain(gain: float) -> None`, `get_gain() -> float`, `set_fps(fps: float) -> None`, `get_fps() -> float`, `get_resolution() -> Tuple[int, int]`, `get_available_pixel_formats() -> List[str]`, `is_acquisition_running() -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardware/test_sim_camera.py
"""Tests for the simulated camera."""

import numpy as np
import pytest

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.hardware.base import ConnectionError
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    """A flat sample focused at z = 5.0."""
    return SimWorld(x=0.0, y=0.0, z=5.0, tilt_a=0.0, tilt_b=0.0, tilt_c=5.0,
                    width=256, height=256)


@pytest.fixture
def camera(world):
    """A connected, acquiring simulated camera."""
    cam = SimCamera(world)
    cam.connect()
    cam.start_acquisition()
    return cam


def test_capture_returns_frame_of_configured_size(camera, world):
    """Captured frames match the world's sensor dimensions."""
    frame = camera.capture()
    assert frame.shape[0] == world.height
    assert frame.shape[1] == world.width
    assert frame.dtype == np.uint8


def test_capture_requires_acquisition_started(world):
    """Capturing before acquisition starts is an error, as on real hardware."""
    cam = SimCamera(world)
    cam.connect()
    with pytest.raises(ConnectionError):
        cam.capture()


def test_image_is_sharper_at_focus_than_away_from_it(camera, world):
    """Defocus blurs the frame. This is what makes autofocus testable."""
    world.z = world.focus_z()
    sharp = gradient_sharpness(camera.capture())

    world.z = world.focus_z() + 1.0
    blurred = gradient_sharpness(camera.capture())

    assert sharp > blurred


def test_frames_are_repeatable_for_a_given_state(camera, world):
    """The same world state produces the same frame, so tests are deterministic."""
    world.z = 5.0
    first = camera.capture()
    second = camera.capture()
    assert np.array_equal(first, second)


def test_resolution_matches_world(camera, world):
    """get_resolution reports the simulated sensor size."""
    assert camera.get_resolution() == (world.width, world.height)


def test_exposure_round_trips(camera):
    """Exposure set on the simulator is reported back."""
    camera.set_exposure_time(20000.0)
    assert camera.get_exposure_time() == pytest.approx(20000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_camera.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.hardware.sim.sim_camera'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/hardware/sim/sim_camera.py
"""Simulated camera producing synthetic frames that respond to focus."""

from typing import List, Optional, Tuple

import cv2
import numpy as np

from kalib.hardware.base import ConnectionError, HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimCamera(HardwareDevice):
    """Camera simulator mirroring the public API of IDSCamera.

    Renders a fixed synthetic sample and blurs it in proportion to how far
    the simulated stage is from the focal plane, so focus-dependent code
    behaves as it would on the instrument.

    Example:
        world = SimWorld()
        camera = SimCamera(world)
        camera.connect()
        camera.start_acquisition()
        frame = camera.capture()
    """

    BLUR_PER_MM = 6.0  # Gaussian sigma in pixels per mm of defocus

    def __init__(self, world: SimWorld, device_idx: int = 0,
                 name: Optional[str] = None):
        """Initialize the simulated camera.

        Args:
            world: Shared simulated instrument state
            device_idx: Present for parity with IDSCamera; unused
            name: Human-readable device name
        """
        super().__init__(device_id=f"SIM-CAM-{device_idx}",
                         name=name or "Sim_Camera")
        self._world = world
        self._device_idx = device_idx
        self._exposure_us = 15000.0
        self._gain = 1.0
        self._fps = 30.0
        self._acquiring = False
        self._pattern = self._make_pattern()

    def _make_pattern(self) -> np.ndarray:
        """Build a fixed high-frequency sample pattern.

        Returns:
            Greyscale image of shape (height, width), dtype uint8
        """
        rng = np.random.default_rng(self._world.seed)
        noise = rng.integers(0, 256,
                             size=(self._world.height, self._world.width),
                             dtype=np.uint8)
        return cv2.GaussianBlur(noise, (3, 3), 0.8)

    def _do_connect(self) -> None:
        """Connect to the simulated camera."""
        self._device_info = {'model': 'SimCamera', 'serial': self._device_id,
                             'index': self._device_idx}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated camera."""
        self._acquiring = False

    def _do_initialize(self) -> None:
        """Initialize the simulated camera after connection."""
        self._pattern = self._make_pattern()

    def start_acquisition(self) -> None:
        """Begin acquisition."""
        self._check_connected()
        self._acquiring = True

    def stop_acquisition(self) -> None:
        """End acquisition."""
        self._acquiring = False

    def is_acquisition_running(self) -> bool:
        """Return whether acquisition is active."""
        return self._acquiring

    def capture(self, timeout_ms: int = 1000,
                force_8bit: bool = False) -> np.ndarray:
        """Capture one synthetic frame.

        Args:
            timeout_ms: Accepted for API parity; the simulator never blocks
            force_8bit: Accepted for API parity; frames are always 8-bit

        Returns:
            Greyscale frame of shape (height, width), dtype uint8

        Raises:
            ConnectionError: If acquisition has not been started
        """
        self._check_connected()
        if not self._acquiring:
            raise ConnectionError("Acquisition is not running")

        sigma = self._world.defocus() * self.BLUR_PER_MM
        frame = self._pattern
        if sigma > 0.05:
            frame = cv2.GaussianBlur(frame, (0, 0), sigma)

        scale = self._exposure_us / 15000.0 * self._gain
        return np.clip(frame.astype(np.float32) * scale, 0, 255).astype(np.uint8)

    def set_exposure_time(self, exposure_us: float) -> None:
        """Set exposure time in microseconds."""
        self._exposure_us = float(exposure_us)

    def get_exposure_time(self) -> float:
        """Return exposure time in microseconds."""
        return self._exposure_us

    def set_gain(self, gain: float) -> None:
        """Set analogue gain."""
        self._gain = float(gain)

    def get_gain(self) -> float:
        """Return analogue gain."""
        return self._gain

    def set_fps(self, fps: float) -> None:
        """Set target frame rate."""
        self._fps = float(fps)

    def get_fps(self) -> float:
        """Return target frame rate."""
        return self._fps

    def get_resolution(self) -> Tuple[int, int]:
        """Return sensor resolution as (width, height)."""
        return (self._world.width, self._world.height)

    def get_available_pixel_formats(self) -> List[str]:
        """Return supported pixel formats."""
        return ['Mono8']
```

Then add to `kalib/hardware/sim/__init__.py`:

```python
from kalib.hardware.sim.sim_camera import SimCamera

__all__ = ['SimWorld', 'SimCamera']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_camera.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/hardware/sim/ tests/test_hardware/test_sim_camera.py
git commit -m "feat: add SimCamera with focus-dependent synthetic frames"
```

---

### Task 3: SimStageXY and SimStageZ

**Files:**
- Create: `kalib/hardware/sim/sim_stage.py`
- Modify: `kalib/hardware/sim/__init__.py`
- Test: `tests/test_hardware/test_sim_stage.py`

**Interfaces:**
- Consumes: `SimWorld` from Task 1.
- Produces:
  - `SimStageXY(world, device_id=None, name=None)` with `move_absolute(x=None, y=None, wait=True) -> None`, `move_relative(dx=0.0, dy=0.0, wait=True) -> None`, `get_position() -> Tuple[float, float]`, `is_on_target() -> bool`, `stop() -> None`, `set_velocity(velocity: float) -> None`, `get_velocity() -> Tuple[float, float]`, properties `x_range`, `y_range`, `axes`.
  - `SimStageZ(world, device_id=None, name=None)` with `move_absolute(z, wait=True) -> None`, `move_relative(dz, wait=True) -> None`, `get_position() -> float`, `is_on_target() -> bool`, `stop() -> None`, `set_velocity(velocity: float) -> None`, `get_velocity() -> float`, `reference() -> None`, properties `z_range`, `axis`, `is_referenced`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardware/test_sim_stage.py
"""Tests for the simulated stages."""

import pytest

from kalib.hardware.base import CommandError
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(x=50.0, y=50.0, z=5.0)


def test_xy_absolute_move_updates_world(world):
    """Moving the simulated XY stage moves the shared world."""
    stage = SimStageXY(world)
    stage.connect()
    stage.move_absolute(x=10.0, y=20.0)
    assert world.x == pytest.approx(10.0)
    assert world.y == pytest.approx(20.0)
    assert stage.get_position() == (pytest.approx(10.0), pytest.approx(20.0))


def test_xy_relative_move_is_additive(world):
    """Relative moves add to the current position."""
    stage = SimStageXY(world)
    stage.connect()
    stage.move_absolute(x=10.0, y=10.0)
    stage.move_relative(dx=2.5, dy=-3.0)
    assert stage.get_position() == (pytest.approx(12.5), pytest.approx(7.0))


def test_xy_move_outside_range_is_rejected(world):
    """Out-of-range moves raise rather than silently clamping."""
    stage = SimStageXY(world, x_range=(0.0, 100.0), y_range=(0.0, 100.0))
    stage.connect()
    with pytest.raises(CommandError):
        stage.move_absolute(x=150.0)


def test_z_move_updates_world(world):
    """Moving the simulated Z stage moves the shared world."""
    stage = SimStageZ(world)
    stage.connect()
    stage.move_absolute(7.5)
    assert world.z == pytest.approx(7.5)
    assert stage.get_position() == pytest.approx(7.5)


def test_z_move_outside_range_is_rejected(world):
    """Z respects its configured range."""
    stage = SimStageZ(world, z_range=(0.0, 10.0))
    stage.connect()
    with pytest.raises(CommandError):
        stage.move_absolute(20.0)


def test_stages_share_one_world(world):
    """XY and Z stages act on the same world object."""
    xy = SimStageXY(world)
    z = SimStageZ(world)
    xy.connect()
    z.connect()
    xy.move_absolute(x=1.0, y=2.0)
    z.move_absolute(3.0)
    assert (world.x, world.y, world.z) == (
        pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_stage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.hardware.sim.sim_stage'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/hardware/sim/sim_stage.py
"""Simulated XY and Z stages acting on a shared SimWorld."""

from typing import List, Optional, Tuple

from kalib.hardware.base import CommandError, HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimStageXY(HardwareDevice):
    """XY stage simulator mirroring the public API of PIStageXY.

    Moves are instantaneous, so is_on_target is always True.

    Example:
        stage = SimStageXY(SimWorld())
        stage.connect()
        stage.move_absolute(x=10.0, y=20.0)
    """

    def __init__(self, world: SimWorld, device_id: Optional[str] = None,
                 name: Optional[str] = None,
                 x_range: Tuple[float, float] = (0.0, 100.0),
                 y_range: Tuple[float, float] = (0.0, 100.0)):
        """Initialize the simulated XY stage.

        Args:
            world: Shared simulated instrument state
            device_id: Present for parity with PIStageXY
            name: Human-readable device name
            x_range: Permitted X travel in mm
            y_range: Permitted Y travel in mm
        """
        super().__init__(device_id=device_id or "SIM-XY", name=name or "Sim_XY")
        self._world = world
        self._x_range = x_range
        self._y_range = y_range
        self._velocity = 10.0

    def _do_connect(self) -> None:
        """Connect to the simulated stage."""
        self._device_info = {'model': 'SimStageXY', 'serial': self._device_id}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated stage."""

    def _do_initialize(self) -> None:
        """Initialize the simulated stage."""

    def _check_range(self, value: float, limits: Tuple[float, float],
                     axis: str) -> None:
        """Raise if a target lies outside the permitted travel.

        Args:
            value: Requested position in mm
            limits: (minimum, maximum) in mm
            axis: Axis name, for the error message

        Raises:
            CommandError: If the target is out of range
        """
        low, high = limits
        if not low <= value <= high:
            raise CommandError(
                f"{axis} target {value} outside range [{low}, {high}]")

    def move_absolute(self, x: Optional[float] = None,
                      y: Optional[float] = None, wait: bool = True) -> None:
        """Move to an absolute position.

        Args:
            x: Target X in mm; unchanged if None
            y: Target Y in mm; unchanged if None
            wait: Accepted for API parity; simulated moves are instant

        Raises:
            CommandError: If a target is out of range
        """
        self._check_connected()
        if x is not None:
            self._check_range(x, self._x_range, "X")
        if y is not None:
            self._check_range(y, self._y_range, "Y")
        if x is not None:
            self._world.x = float(x)
        if y is not None:
            self._world.y = float(y)

    def move_relative(self, dx: float = 0.0, dy: float = 0.0,
                      wait: bool = True) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(x=self._world.x + dx, y=self._world.y + dy, wait=wait)

    def get_position(self) -> Tuple[float, float]:
        """Return current position as (x, y) in mm."""
        self._check_connected()
        return (self._world.x, self._world.y)

    def is_on_target(self) -> bool:
        """Return True; simulated moves complete immediately."""
        return True

    def stop(self) -> None:
        """Stop motion. A no-op, since simulated moves are instant."""

    def set_velocity(self, velocity: float) -> None:
        """Set velocity in mm/s."""
        self._velocity = float(velocity)

    def get_velocity(self) -> Tuple[float, float]:
        """Return velocity for both axes in mm/s."""
        return (self._velocity, self._velocity)

    @property
    def x_range(self) -> Tuple[float, float]:
        """Permitted X travel in mm."""
        return self._x_range

    @property
    def y_range(self) -> Tuple[float, float]:
        """Permitted Y travel in mm."""
        return self._y_range

    @property
    def axes(self) -> List[str]:
        """Axis names."""
        return ['X', 'Y']


class SimStageZ(HardwareDevice):
    """Z stage simulator mirroring the public API of PIStageZ.

    Example:
        stage = SimStageZ(SimWorld())
        stage.connect()
        stage.move_absolute(5.0)
    """

    def __init__(self, world: SimWorld, device_id: Optional[str] = None,
                 name: Optional[str] = None,
                 z_range: Tuple[float, float] = (0.0, 10.0)):
        """Initialize the simulated Z stage.

        Args:
            world: Shared simulated instrument state
            device_id: Present for parity with PIStageZ
            name: Human-readable device name
            z_range: Permitted Z travel in mm
        """
        super().__init__(device_id=device_id or "SIM-Z", name=name or "Sim_Z")
        self._world = world
        self._z_range = z_range
        self._velocity = 1.0
        self._referenced = True

    def _do_connect(self) -> None:
        """Connect to the simulated stage."""
        self._device_info = {'model': 'SimStageZ', 'serial': self._device_id}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated stage."""

    def _do_initialize(self) -> None:
        """Initialize the simulated stage."""

    def move_absolute(self, z: float, wait: bool = True) -> None:
        """Move to an absolute Z position in mm.

        Args:
            z: Target Z in mm
            wait: Accepted for API parity; simulated moves are instant

        Raises:
            CommandError: If the target is out of range
        """
        self._check_connected()
        low, high = self._z_range
        if not low <= z <= high:
            raise CommandError(f"Z target {z} outside range [{low}, {high}]")
        self._world.z = float(z)

    def move_relative(self, dz: float, wait: bool = True) -> None:
        """Move by a relative offset in mm."""
        self._check_connected()
        self.move_absolute(self._world.z + dz, wait=wait)

    def get_position(self) -> float:
        """Return current Z position in mm."""
        self._check_connected()
        return self._world.z

    def is_on_target(self) -> bool:
        """Return True; simulated moves complete immediately."""
        return True

    def stop(self) -> None:
        """Stop motion. A no-op, since simulated moves are instant."""

    def set_velocity(self, velocity: float) -> None:
        """Set velocity in mm/s."""
        self._velocity = float(velocity)

    def get_velocity(self) -> float:
        """Return velocity in mm/s."""
        return self._velocity

    def reference(self) -> None:
        """Reference the axis. Always succeeds in simulation."""
        self._referenced = True

    @property
    def z_range(self) -> Tuple[float, float]:
        """Permitted Z travel in mm."""
        return self._z_range

    @property
    def axis(self) -> str:
        """Axis name."""
        return 'Z'

    @property
    def is_referenced(self) -> bool:
        """Whether the axis has been referenced."""
        return self._referenced
```

Then extend `kalib/hardware/sim/__init__.py`:

```python
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ

__all__ = ['SimWorld', 'SimCamera', 'SimStageXY', 'SimStageZ']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_stage.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/hardware/sim/ tests/test_hardware/test_sim_stage.py
git commit -m "feat: add simulated XY and Z stages"
```

---

### Task 4: SimLED

**Files:**
- Create: `kalib/hardware/sim/sim_led.py`
- Modify: `kalib/hardware/sim/__init__.py`
- Test: `tests/test_hardware/test_sim_led.py`

**Interfaces:**
- Consumes: `SimWorld` from Task 1.
- Produces: `SimLED(world, port=None, name=None, brightness_range=(0, 255))` with `set_brightness(brightness: int) -> None`, `get_brightness() -> int`, `set_brightness_percent(percent: float) -> None`, `get_brightness_percent() -> float`, `get_current_ma() -> float`, `turn_off() -> None`, `turn_on(brightness: Optional[int] = None) -> None`, property `brightness_range`, property `port`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardware/test_sim_led.py
"""Tests for the simulated LED controller."""

import pytest

from kalib.hardware.base import CommandError
from kalib.hardware.sim.sim_led import SimLED
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld()


def test_set_brightness_updates_world(world):
    """Brightness set on the LED is visible in the shared world."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(128)
    assert world.led_brightness == 128
    assert led.get_brightness() == 128


def test_brightness_outside_range_is_rejected(world):
    """Out-of-range brightness raises rather than clamping."""
    led = SimLED(world, brightness_range=(0, 255))
    led.connect()
    with pytest.raises(CommandError):
        led.set_brightness(300)


def test_turn_off_sets_zero(world):
    """turn_off drives brightness to zero."""
    led = SimLED(world)
    led.connect()
    led.set_brightness(200)
    led.turn_off()
    assert led.get_brightness() == 0


def test_percent_round_trips(world):
    """Percentage helpers agree with raw values."""
    led = SimLED(world, brightness_range=(0, 200))
    led.connect()
    led.set_brightness_percent(50.0)
    assert led.get_brightness() == 100
    assert led.get_brightness_percent() == pytest.approx(50.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_led.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.hardware.sim.sim_led'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/hardware/sim/sim_led.py
"""Simulated LED controller acting on a shared SimWorld."""

from typing import Optional, Tuple

from kalib.hardware.base import CommandError, HardwareDevice
from kalib.hardware.sim.world import SimWorld


class SimLED(HardwareDevice):
    """LED simulator mirroring the public API of LEDDriver.

    Example:
        led = SimLED(SimWorld())
        led.connect()
        led.set_brightness(128)
    """

    def __init__(self, world: SimWorld, port: Optional[str] = None,
                 name: Optional[str] = None,
                 brightness_range: Tuple[int, int] = (0, 255)):
        """Initialize the simulated LED controller.

        Args:
            world: Shared simulated instrument state
            port: Present for parity with LEDDriver
            name: Human-readable device name
            brightness_range: (minimum, maximum) brightness in device units
        """
        super().__init__(device_id=port or "SIM-LED", name=name or "Sim_LED")
        self._world = world
        self._port = port or "SIM-LED"
        self._range = brightness_range

    def _do_connect(self) -> None:
        """Connect to the simulated LED controller."""
        self._device_info = {'model': 'SimLED', 'port': self._port}

    def _do_disconnect(self) -> None:
        """Disconnect from the simulated LED controller."""

    def _do_initialize(self) -> None:
        """Initialize the simulated LED controller."""
        self._world.led_brightness = 0

    def set_brightness(self, brightness: int) -> None:
        """Set brightness in raw device units.

        Args:
            brightness: Target brightness

        Raises:
            CommandError: If brightness is outside the configured range
        """
        self._check_connected()
        low, high = self._range
        if not low <= brightness <= high:
            raise CommandError(
                f"Brightness {brightness} outside range [{low}, {high}]")
        self._world.led_brightness = int(brightness)

    def get_brightness(self) -> int:
        """Return brightness in raw device units."""
        self._check_connected()
        return self._world.led_brightness

    def set_brightness_percent(self, percent: float) -> None:
        """Set brightness as a percentage of the configured range."""
        low, high = self._range
        self.set_brightness(int(low + (high - low) * percent / 100.0))

    def get_brightness_percent(self) -> float:
        """Return brightness as a percentage of the configured range."""
        low, high = self._range
        return (self.get_brightness() - low) / (high - low) * 100.0

    def get_current_ma(self) -> float:
        """Return a plausible drive current in milliamps."""
        return self.get_brightness() * 0.5

    def turn_off(self) -> None:
        """Switch the LED off."""
        self.set_brightness(self._range[0])

    def turn_on(self, brightness: Optional[int] = None) -> None:
        """Switch the LED on.

        Args:
            brightness: Level to use; defaults to the range maximum
        """
        self.set_brightness(self._range[1] if brightness is None else brightness)

    @property
    def brightness_range(self) -> Tuple[int, int]:
        """Configured brightness range."""
        return self._range

    @property
    def port(self) -> Optional[str]:
        """Simulated port name."""
        return self._port
```

Then extend `kalib/hardware/sim/__init__.py`:

```python
from kalib.hardware.sim.sim_led import SimLED

__all__ = ['SimWorld', 'SimCamera', 'SimStageXY', 'SimStageZ', 'SimLED']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_sim_led.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/hardware/sim/ tests/test_hardware/test_sim_led.py
git commit -m "feat: add simulated LED controller"
```

---

### Task 5: Hardware factory and configuration switch

**Files:**
- Create: `kalib/hardware/factory.py`
- Modify: `config/default_config.yaml` (add a `hardware:` section)
- Modify: `kalib/hardware/__init__.py` (export the factory)
- Test: `tests/test_hardware/test_factory.py`

**Interfaces:**
- Consumes: `SimWorld`, `SimCamera`, `SimStageXY`, `SimStageZ`, `SimLED` from Tasks 1-4.
- Produces: `HardwareFactory(settings, world=None)` with `backend -> str`, `create_camera(device_idx: int = 0)`, `create_stage_xy(device_id=None, x_range=None, y_range=None)`, `create_stage_z(device_id=None, z_range=None)`, `create_led(port=None)`. Each returns a `HardwareDevice`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hardware/test_factory.py
"""Tests for the hardware factory."""

import pytest

from kalib.hardware.factory import HardwareFactory
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.sim_led import SimLED


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


@pytest.fixture
def sim_settings():
    return FakeSettings({'hardware.backend': 'sim'})


def test_sim_backend_builds_simulated_devices(sim_settings):
    """With backend 'sim', every device is a simulator."""
    factory = HardwareFactory(sim_settings)
    assert isinstance(factory.create_camera(), SimCamera)
    assert isinstance(factory.create_stage_xy(), SimStageXY)
    assert isinstance(factory.create_stage_z(), SimStageZ)
    assert isinstance(factory.create_led(), SimLED)


def test_sim_devices_share_one_world(sim_settings):
    """All simulated devices from one factory act on the same world."""
    factory = HardwareFactory(sim_settings)
    xy = factory.create_stage_xy()
    camera = factory.create_camera()
    xy.connect()
    xy.move_absolute(x=12.0, y=0.0)
    assert camera._world.x == pytest.approx(12.0)


def test_backend_defaults_to_real():
    """Absent configuration, the factory targets real hardware."""
    factory = HardwareFactory(FakeSettings({}))
    assert factory.backend == 'real'


def test_unknown_backend_is_rejected():
    """A misspelled backend fails loudly at construction."""
    from kalib.hardware.base import ConfigurationError
    with pytest.raises(ConfigurationError):
        HardwareFactory(FakeSettings({'hardware.backend': 'pretend'}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kalib.hardware.factory'`

- [ ] **Step 3: Write minimal implementation**

```python
# kalib/hardware/factory.py
"""Build real or simulated hardware devices according to configuration."""

from typing import Any, Optional, Tuple

from kalib.hardware.base import ConfigurationError, HardwareDevice
from kalib.hardware.sim.world import SimWorld

REAL = 'real'
SIM = 'sim'
BACKENDS = (REAL, SIM)


class HardwareFactory:
    """Construct hardware devices for the configured backend.

    With the 'sim' backend every device is a simulator, and all of them
    share one SimWorld so that moving a stage changes what the camera sees.

    Example:
        factory = HardwareFactory(settings)
        camera = factory.create_camera()
    """

    def __init__(self, settings: Any, world: Optional[SimWorld] = None):
        """Initialize the factory.

        Args:
            settings: Object with a get(key, default) method
            world: Shared simulated state; created automatically when omitted

        Raises:
            ConfigurationError: If the configured backend is not recognised
        """
        self._settings = settings
        self._backend = settings.get('hardware.backend', REAL)
        if self._backend not in BACKENDS:
            raise ConfigurationError(
                f"Unknown hardware backend '{self._backend}'. "
                f"Expected one of: {', '.join(BACKENDS)}")
        self._world = world or SimWorld()

    @property
    def backend(self) -> str:
        """Configured backend name."""
        return self._backend

    @property
    def world(self) -> SimWorld:
        """Shared simulated state, used only by the 'sim' backend."""
        return self._world

    def create_camera(self, device_idx: int = 0) -> HardwareDevice:
        """Build a camera for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_camera import SimCamera
            return SimCamera(self._world, device_idx=device_idx)
        from kalib.hardware.ids_camera import IDSCamera
        return IDSCamera(device_idx=device_idx, pixel_format=(8, "RGB"))

    def create_stage_xy(self, device_id: Optional[str] = None,
                        x_range: Optional[Tuple[float, float]] = None,
                        y_range: Optional[Tuple[float, float]] = None
                        ) -> HardwareDevice:
        """Build an XY stage for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_stage import SimStageXY
            return SimStageXY(self._world, device_id=device_id,
                              x_range=x_range or (0.0, 100.0),
                              y_range=y_range or (0.0, 100.0))
        from kalib.hardware.pi_stage_xy import PIStageXY
        return PIStageXY(device_id=device_id)

    def create_stage_z(self, device_id: Optional[str] = None,
                       z_range: Optional[Tuple[float, float]] = None
                       ) -> HardwareDevice:
        """Build a Z stage for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_stage import SimStageZ
            return SimStageZ(self._world, device_id=device_id,
                             z_range=z_range or (0.0, 10.0))
        from kalib.hardware.pi_stage_z import PIStageZ
        return PIStageZ(device_id=device_id)

    def create_led(self, port: Optional[str] = None) -> HardwareDevice:
        """Build an LED controller for the configured backend."""
        if self._backend == SIM:
            from kalib.hardware.sim.sim_led import SimLED
            return SimLED(self._world, port=port)
        from kalib.hardware.led_driver import LEDDriver
        return LEDDriver(port=port)
```

Add to `config/default_config.yaml`, immediately after the `camera:` block:

```yaml
# Hardware Backend
hardware:
  backend: "real"                 # "real" for the instrument, "sim" for simulated devices
```

Add to `kalib/hardware/__init__.py`:

```python
from kalib.hardware.factory import HardwareFactory
```

and add `'HardwareFactory'` to `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_hardware/test_factory.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add kalib/hardware/factory.py kalib/hardware/__init__.py config/default_config.yaml tests/test_hardware/test_factory.py
git commit -m "feat: add hardware factory with real and sim backends"
```

---

### Task 6: Inject the device into CameraController

**Files:**
- Modify: `kalib/controllers/camera_controller.py:32-70`
- Test: `tests/test_controllers/test_camera_controller.py`
- Create: `tests/test_controllers/__init__.py`

**Interfaces:**
- Consumes: `HardwareFactory` from Task 5; `SimCamera`, `SimWorld` from Tasks 1-2.
- Produces: `CameraController(device_idx: int = 0, settings: Optional[CameraSettings] = None, device: Optional[HardwareDevice] = None)`. When `device` is given it is used verbatim and no real driver is constructed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_controllers/__init__.py
```

```python
# tests/test_controllers/test_camera_controller.py
"""Tests for CameraController against a simulated camera."""

import pytest

from kalib.controllers.camera_controller import CameraController
from kalib.hardware.sim.sim_camera import SimCamera
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(width=128, height=128)


@pytest.fixture
def controller(world):
    """A controller driving an injected simulated camera."""
    return CameraController(device=SimCamera(world))


def test_connect_uses_the_injected_device(controller):
    """Connecting succeeds with no real hardware present."""
    assert controller.connect_camera() is True
    assert controller.model.state.is_connected is True


def test_resolution_comes_from_the_injected_device(controller, world):
    """The controller reads resolution from the injected device."""
    controller.connect_camera()
    assert controller.model.state.resolution == (world.width, world.height)


def test_capture_returns_a_frame(controller, world):
    """A frame can be captured end to end through the controller."""
    controller.connect_camera()
    controller.start_acquisition()
    frame = controller.capture_image()
    assert frame is not None
    assert frame.shape[:2] == (world.height, world.width)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_camera_controller.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'device'`

- [ ] **Step 3: Write minimal implementation**

In `kalib/controllers/camera_controller.py`, change the constructor signature and store the injected device:

```python
    def __init__(self,
                 device_idx: int = 0,
                 settings: Optional[CameraSettings] = None,
                 device: Optional[HardwareDevice] = None):
        """Initialize camera controller.

        Args:
            device_idx: Camera device index
            settings: Initial camera settings
            device: Pre-built camera to use instead of constructing an
                IDSCamera. Supplying this is how the simulated backend and
                the tests avoid touching real hardware.
        """
        super().__init__()

        self._logger = get_logger(__name__)
        self._device_idx = device_idx
        self._injected_device = device
```

Add the import at the top of the file:

```python
from kalib.hardware import IDSCamera, ConnectionError, CommandError, HardwareDevice
```

Then in `connect_camera()` (line 50), replace the construction at line 65 with:

```python
            # Use the injected device when one was supplied, otherwise build
            # the real driver.
            if self._injected_device is not None:
                self._camera = self._injected_device
            else:
                pixel_format = (8, "RGB")
                self._camera = IDSCamera(
                    device_idx=self._device_idx,
                    pixel_format=pixel_format
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_camera_controller.py -v`
Expected: PASS, 3 tests

Then confirm nothing regressed: `.venv/bin/python -m pytest tests/ -q`
Expected: all previous tests still pass.

- [ ] **Step 5: Commit**

```bash
git add kalib/controllers/camera_controller.py tests/test_controllers/
git commit -m "feat: allow injecting a camera device into CameraController"
```

---

### Task 7: Inject devices into StageController

**Files:**
- Modify: `kalib/controllers/stage_controller.py:32-50,78,159`
- Test: `tests/test_controllers/test_stage_controller.py`

**Interfaces:**
- Consumes: `SimStageXY`, `SimStageZ`, `SimWorld` from Tasks 1 and 3.
- Produces: `StageController(xy_device_id=None, z_device_id=None, limits=None, xy_device=None, z_device=None)`. Supplied devices take precedence over constructing `PIStageXY` / `PIStageZ`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_controllers/test_stage_controller.py
"""Tests for StageController against simulated stages."""

import pytest

from kalib.controllers.stage_controller import StageController
from kalib.hardware.sim.sim_stage import SimStageXY, SimStageZ
from kalib.hardware.sim.world import SimWorld


@pytest.fixture
def world():
    return SimWorld(x=50.0, y=50.0, z=5.0)


@pytest.fixture
def controller(world):
    """A controller driving injected simulated stages."""
    return StageController(
        xy_device=SimStageXY(world),
        z_device=SimStageZ(world),
    )


def test_connect_uses_injected_devices(controller):
    """Connecting succeeds with no real controllers present."""
    assert controller.connect_xy_stage() is True
    assert controller.connect_z_stage() is True


def test_xy_move_reaches_the_requested_position(controller, world):
    """An XY move through the controller updates the simulated world."""
    controller.connect_xy_stage()
    controller.move_absolute(x=10.0, y=20.0)
    assert (world.x, world.y) == (pytest.approx(10.0), pytest.approx(20.0))


def test_z_move_reaches_the_requested_position(controller, world):
    """A Z move through the controller updates the simulated world."""
    controller.connect_z_stage()
    controller.move_absolute(z=7.0)
    assert world.z == pytest.approx(7.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_stage_controller.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'xy_device'`

- [ ] **Step 3: Write minimal implementation**

In `kalib/controllers/stage_controller.py`, extend the constructor:

```python
    def __init__(self,
                 xy_device_id: Optional[str] = None,
                 z_device_id: Optional[str] = None,
                 limits: Optional[StageLimits] = None,
                 xy_device: Optional[HardwareDevice] = None,
                 z_device: Optional[HardwareDevice] = None):
        """Initialize stage controller.

        Args:
            xy_device_id: XY stage device ID
            z_device_id: Z stage device ID
            limits: Stage movement limits
            xy_device: Pre-built XY stage to use instead of a PIStageXY
            z_device: Pre-built Z stage to use instead of a PIStageZ
        """
```

Store them alongside the existing assignments:

```python
        self._injected_xy = xy_device
        self._injected_z = z_device
```

Add `HardwareDevice` to the hardware import at the top of the file:

```python
from kalib.hardware import PIStageXY, PIStageZ, ConnectionError, CommandError, HardwareDevice
```

At line 78, replace the XY construction:

```python
            if self._injected_xy is not None:
                self._xy_stage = self._injected_xy
            else:
                self._xy_stage = PIStageXY(
                    device_id=self._xy_device_id
                )
```

At line 159, replace the Z construction:

```python
            if self._injected_z is not None:
                self._z_stage = self._injected_z
            else:
                self._z_stage = PIStageZ(
                    device_id=self._z_device_id
                )
```

Note: keep whatever additional keyword arguments the existing calls to
`PIStageXY(...)` and `PIStageZ(...)` already pass. Only the choice between
injected and constructed device is being added.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_stage_controller.py -v`
Expected: PASS, 3 tests

Then: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests still pass.

- [ ] **Step 5: Commit**

```bash
git add kalib/controllers/stage_controller.py tests/test_controllers/test_stage_controller.py
git commit -m "feat: allow injecting stage devices into StageController"
```

---

### Task 8: Wire the factory into main.py behind a --simulate flag

**Files:**
- Modify: `kalib/main.py:205-238` (`parse_arguments`), `kalib/main.py:241-250` (`main`), `kalib/main.py:32` (constructor), `kalib/main.py:111` (`_init_controllers`)
- Test: `tests/test_controllers/test_main_args.py`

**Interfaces:**
- Consumes: `HardwareFactory` from Task 5; injected constructors from Tasks 6-7.
- Produces: `parse_arguments(argv: Optional[List[str]] = None)` returning a namespace with a `simulate: bool` attribute, and `KalibApplication(config_path=None, log_level=None, simulate=False)`.

Note: `parse_arguments()` currently calls `parser.parse_args()` with no
argument, so it always reads `sys.argv` and cannot be tested. Task 8 makes
it accept an explicit argument list. `Settings.set(key_path, value)` already
exists at `config/settings.py:51`, so the backend override needs no new
configuration mechanism.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_controllers/test_main_args.py
"""Tests for command line argument handling."""

from kalib.main import parse_arguments


def test_simulate_defaults_to_false():
    """Without the flag the application targets real hardware."""
    args = parse_arguments([])
    assert args.simulate is False


def test_simulate_flag_sets_true():
    """The --simulate flag selects the simulated backend."""
    args = parse_arguments(['--simulate'])
    assert args.simulate is True


def test_existing_arguments_still_parse():
    """Adding the flag does not disturb the existing arguments."""
    args = parse_arguments(['--config', 'x.yaml', '--log-level', 'DEBUG'])
    assert args.config == 'x.yaml'
    assert args.log_level == 'DEBUG'
    assert args.simulate is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_main_args.py -v`
Expected: FAIL. `parse_arguments()` takes no positional argument, so
`parse_arguments([])` raises `TypeError: parse_arguments() takes 0 positional
arguments but 1 was given`.

- [ ] **Step 3: Write minimal implementation**

In `kalib/main.py`, make `parse_arguments` accept an argument list and add
the flag:

```python
def parse_arguments(argv: Optional[List[str]] = None):
    """Parse command line arguments.

    Args:
        argv: Argument list to parse; reads sys.argv when None

    Returns:
        Parsed arguments
    """
```

Add this alongside the existing `add_argument` calls:

```python
    parser.add_argument(
        '--simulate',
        action='store_true',
        help="Run against simulated hardware instead of the instrument"
    )
```

Change the final line of the function from `return parser.parse_args()` to:

```python
    return parser.parse_args(argv)
```

Add the import at the top of the file:

```python
from typing import List, Optional
```

Pass the flag through in `main()`:

```python
    app = KalibApplication(
        config_path=args.config,
        log_level=args.log_level,
        simulate=args.simulate
    )
```

Accept it on the constructor, adding this parameter and one assignment while
leaving the rest of the existing body unchanged:

```python
    def __init__(self, config_path: str = None, log_level: str = None,
                 simulate: bool = False):
        """Initialize application.

        Args:
            config_path: Path to configuration file
            log_level: Logging level override
            simulate: Run against simulated hardware instead of the instrument
        """
        self._simulate = simulate
```

Replace the body of `_init_controllers` with:

```python
    def _init_controllers(self) -> None:
        """Initialize controllers with dependency injection."""
        self._logger.info("Initializing controllers...")

        from kalib.hardware import HardwareFactory
        from kalib.models import StageLimits

        if self._simulate:
            self.settings.set('hardware.backend', 'sim')

        factory = HardwareFactory(self.settings)
        self._logger.info(f"Hardware backend: {factory.backend}")

        xy_device_id = self.settings.get('stages.xy.device_id')
        z_device_id = self.settings.get('stages.z.device_id')

        self.camera = CameraController(
            device_idx=0,
            device=factory.create_camera(device_idx=0)
        )

        limits = StageLimits(
            x_min=self.settings.get('stages.xy.x_range[0]', 0.0),
            x_max=self.settings.get('stages.xy.x_range[1]', 100.0),
            y_min=self.settings.get('stages.xy.y_range[0]', 0.0),
            y_max=self.settings.get('stages.xy.y_range[1]', 100.0),
            z_min=self.settings.get('stages.z.z_range[0]', 0.0),
            z_max=self.settings.get('stages.z.z_range[1]', 10.0)
        )

        self.stage = StageController(
            xy_device_id=xy_device_id,
            z_device_id=z_device_id,
            limits=limits,
            xy_device=factory.create_stage_xy(device_id=xy_device_id),
            z_device=factory.create_stage_z(device_id=z_device_id)
        )

        self.scan = ScanController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )

        self.calibration = CalibrationController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_main_args.py -v`
Expected: PASS, 3 tests

Then the whole suite: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass.

Then confirm the flag is registered: `.venv/bin/python -m kalib.main --help`
Expected: `--simulate` appears in the output.

- [ ] **Step 5: Commit**

```bash
git add kalib/main.py tests/test_controllers/test_main_args.py
git commit -m "feat: add --simulate flag selecting the simulated backend"
```

---

### Task 9: End-to-end check that focus behaves correctly in simulation

**Files:**
- Test: `tests/test_controllers/test_simulated_focus.py`

**Interfaces:**
- Consumes: `HardwareFactory` from Task 5, injected controllers from Tasks 6-7.
- Produces: nothing. This is the regression test proving the simulator is
  good enough to develop autofocus and tilt calibration against.

- [ ] **Step 1: Write the test**

```python
# tests/test_controllers/test_simulated_focus.py
"""End-to-end checks that the simulator reproduces focus behaviour."""

import pytest

from kalib.algorithms.sharpness import gradient_sharpness
from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _sim_rig(tilt_a=0.0, tilt_b=0.0, tilt_c=5.0):
    """Build connected controllers over a shared simulated world.

    Args:
        tilt_a: Focal plane gradient along X
        tilt_b: Focal plane gradient along Y
        tilt_c: Focal plane height at the origin

    Returns:
        Tuple of (camera controller, stage controller, world)
    """
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    world = factory.world
    world.tilt_a, world.tilt_b, world.tilt_c = tilt_a, tilt_b, tilt_c
    world.width, world.height = 128, 128

    camera = CameraController(device=factory.create_camera())
    stage = StageController(xy_device=factory.create_stage_xy(),
                            z_device=factory.create_stage_z())
    camera.connect_camera()
    stage.connect_xy_stage()
    stage.connect_z_stage()
    camera.start_acquisition()
    return camera, stage, world


def test_sharpness_peaks_at_the_focal_plane():
    """Sweeping z through focus produces a peak at the plane."""
    camera, stage, world = _sim_rig(tilt_c=5.0)

    heights = [3.0, 4.0, 5.0, 6.0, 7.0]
    scores = []
    for z in heights:
        stage.move_absolute(z=z)
        scores.append(gradient_sharpness(camera.capture_image()))

    assert heights[scores.index(max(scores))] == pytest.approx(5.0)


def test_focal_height_shifts_with_xy_when_the_sample_is_tilted():
    """A tilted sample focuses at different z depending on position.

    This is the behaviour tilt calibration exists to measure.
    """
    camera, stage, world = _sim_rig(tilt_a=0.01, tilt_c=5.0)

    stage.move_absolute(x=0.0, y=0.0)
    focus_at_origin = world.focus_z()

    stage.move_absolute(x=100.0, y=0.0)
    focus_at_far_x = world.focus_z()

    assert focus_at_far_x - focus_at_origin == pytest.approx(1.0)
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -m pytest tests/test_controllers/test_simulated_focus.py -v`
Expected: PASS, 2 tests.

If the first test fails because the sharpness peak lands off 5.0, the blur
model in `SimCamera.BLUR_PER_MM` is too weak to separate 1 mm steps. Raise
it until a 1 mm defocus is clearly distinguishable, and note the value in
the docstring.

- [ ] **Step 3: Commit**

```bash
git add tests/test_controllers/test_simulated_focus.py
git commit -m "test: verify simulated focus behaviour end to end"
```

---

### Task 10: Document the simulated backend

**Files:**
- Modify: `README.md` (Development section)
- Modify: `CLAUDE.md` (Development Commands)

- [ ] **Step 1: Verify the documented commands actually work**

Run: `.venv/bin/python -m kalib.main --help`
Expected: exits without error and lists `--simulate`.

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all tests pass.

- [ ] **Step 2: Add to README.md, in the Development section**

````markdown
### Running Without Hardware

The application can run against simulated devices, so development and
testing need no instrument attached:

```bash
python -m kalib.main --simulate
```

The simulator models a sample on a tilted focal plane. Moving the
simulated stage changes what the simulated camera sees, and frames blur in
proportion to defocus, so autofocus and tilt calibration behave as they do
on the instrument. Set `hardware.backend` to `sim` in configuration to make
this the default.
````

- [ ] **Step 3: Add to CLAUDE.md, under Development Commands**

```markdown
# Simulated hardware:  python -m kalib.main --simulate
```

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document the simulated hardware backend"
```

---

## Definition of Done

- [ ] `.venv/bin/python -m pytest tests/ -q` passes, including the previously empty `tests/test_controllers/`
- [ ] `python -m kalib.main --simulate` starts with no instrument attached
- [ ] No simulator imports `ids_peak`, `pipython`, or `serial`
- [ ] Real-hardware construction is unchanged when no device is injected
- [ ] `config/config.yaml` untouched

## Follow-on work

Plan 2 covers the command server, the CLI over SSH, and record/replay, all
of which depend on the seam this plan introduces.
