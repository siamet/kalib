

# Kalib Architecture Documentation

## Overview

Kalib is a comprehensive microscopy control system built with clean MVC (Model-View-Controller) architecture using PySide6 (Qt6). The system provides control for IDS cameras and PI motion stages with advanced features including XY/Z-stack scanning, autofocus, and tilt calibration.

## Architecture Pattern: MVC

```
┌─────────────────────────────────────────────────────────────┐
│                         View Layer                          │
│  (PySide6 Widgets - User Interface)                         │
│  - MainWindow, CameraWidget, StageWidget, etc.              │
└────────────────┬────────────────────────────────────────────┘
                 │ Qt Signals/Slots
                 ↓
┌─────────────────────────────────────────────────────────────┐
│                     Controller Layer                        │
│  (Business Logic & Workflow Coordination)                   │
│  - CameraController, StageController, ScanController        │
└────────────────┬──────────┬─────────────────────────────────┘
                 │          │
        Updates  │          │ Commands
                 ↓          ↓
┌──────────────────┐  ┌────────────────────────────────────┐
│   Model Layer    │  │      Hardware Layer                │
│  (Data & State)  │  │  (Device Abstraction)              │
│  - CameraModel   │  │  - IDSCamera, PIStageXY/Z          │
│  - StageModel    │  │  - LEDDriver                       │
│  - ScanModel     │  │                                    │
└──────────────────┘  └────────────────────────────────────┘
```

## Directory Structure

```
kalib/
├── config/                     # Configuration Management
│   ├── __init__.py
│   ├── settings.py             # YAML config loader
│   └── default_config.yaml     # Default settings
│
├── kalib/                      # Main Application Package
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   │
│   ├── models/                 # MODEL Layer
│   │   ├── camera_model.py     # Camera state & settings
│   │   ├── stage_model.py      # Stage position & limits
│   │   ├── scan_model.py       # Scan parameters & progress
│   │   └── calibration_model.py # Calibration data
│   │
│   ├── controllers/            # CONTROLLER Layer
│   │   ├── camera_controller.py
│   │   ├── stage_controller.py
│   │   ├── scan_controller.py
│   │   └── calibration_controller.py
│   │
│   ├── views/                  # VIEW Layer
│   │   ├── main_window.py      # Main application window
│   │   ├── camera_widget.py
│   │   ├── stage_widget.py
│   │   ├── scan_widget.py
│   │   ├── calibration_widget.py
│   │   └── settings_dialog.py
│   │
│   ├── server/                 # REMOTE OPERATION
│   │   ├── protocol.py         # Newline-delimited JSON, version 1
│   │   ├── commands.py         # CommandRegistry + dispatch table
│   │   ├── handlers.py         # Device, capture and focus handlers
│   │   ├── handlers_scan.py    # Scan job handlers
│   │   └── daemon.py           # QTcpServer bound to 127.0.0.1
│   │
│   ├── cli/                    # Thin client, invoked over SSH
│   │   └── client.py
│   │
│   ├── hardware/               # Hardware Abstraction Layer
│   │   ├── base.py             # Abstract base class
│   │   ├── ids_camera.py       # IDS camera driver
│   │   ├── pi_stage_xy.py      # PI XY stage
│   │   ├── pi_stage_z.py       # PI Z stage
│   │   ├── led_driver.py       # LED driver (no controller drives it yet)
│   │   ├── factory.py          # Builds real or simulated devices
│   │   └── sim/                # Simulated devices sharing one SimWorld
│   │
│   ├── algorithms/             # Scientific Algorithms
│   │   ├── sharpness.py        # Focus quality metrics
│   │   └── tilt_calibration.py # Tilt plane fitting
│   │
│   └── utils/                  # Utilities
│       ├── logger.py           # Logging system
│       └── image_utils.py      # Image processing
│
└── tests/                      # Test Suite
    ├── test_models/
    ├── test_controllers/
    ├── test_hardware/
    └── test_algorithms/
```

## Component Details

### 1. Hardware Layer

**Purpose**: Provide unified interface to hardware devices with proper error handling.

**Base Class Pattern**:
```python
class HardwareDevice(ABC):
    - Connection lifecycle (connect, disconnect, cleanup)
    - Error handling with custom exceptions
    - State management (DISCONNECTED, CONNECTING, CONNECTED, ERROR)
    - Context manager support
```

**Implementations**:
- **IDSCamera**: IDS peak SDK camera interface
- **PIStageXY**: PI E-725 XY motion stage
- **PIStageZ**: PI E-816.DB Z motion stage
- **LEDDriver**: Serial-based LED control

**Error Handling**:
```python
try:
    camera.connect()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
```

### 2. Model Layer

**Purpose**: Manage data, state, and business logic without UI dependencies.

**Key Models**:

**CameraModel**:
- Camera settings (exposure, gain, FPS)
- Connection/acquisition state
- Image buffer management
- Frame counter and statistics

**StageModel**:
- Current 3D position (x, y, z)
- Movement limits and validation
- Position history tracking
- Target position for movements

**ScanModel**:
- Scan type (XY, Z-stack, SFF)
- Scan parameters and configuration
- Progress tracking
- Scan state machine (IDLE, RUNNING, PAUSED, COMPLETED)
- Position and image data storage

**CalibrationModel**:
- Tilt calibration data
- Magnetic calibration positions
- Autofocus results
- Import/export functionality

### 3. Controller Layer

**Purpose**: Coordinate hardware and models, implement workflows, emit Qt signals.

**Key Controllers**:

**CameraController**:
```python
# Qt Signals
connected, disconnected
acquisition_started, acquisition_stopped
image_captured(image)
error_occurred(str)

# Key Methods
connect_camera() -> bool
start_acquisition() -> bool
capture_image() -> np.ndarray
set_exposure_time(float)
```

**StageController**:
```python
# Qt Signals
xy_connected, z_connected
position_changed(x, y, z)
movement_completed
error_occurred(str)

# Key Methods
connect_xy_stage(device_id) -> bool
move_absolute(x, y, z, wait)
move_relative(dx, dy, dz, wait)
stop_movement()
```

**ScanController**:
```python
# Qt Signals
scan_started(type)
scan_completed, scan_cancelled
progress_updated(current, total)
position_reached(x, y, z)

# Key Methods
configure_xy_scan(XYScanParameters)
configure_z_stack(ZStackParameters)
start_scan(save_path) -> bool
cancel_scan()
```

**CalibrationController**:
```python
# Qt Signals
calibration_started, calibration_completed
corner_measured(current, total)
focus_found(z_position)

# Key Methods
start_tilt_calibration(num_corners)
measure_tilt_corner(corner_idx, autofocus)
autofocus_at_position(search_range)
export_calibration(filepath)
```

### 4. View Layer

**Purpose**: Provide user interface using PySide6 widgets with Qt signals/slots.

**Main Components**:

**MainWindow**:
- Tabbed interface
- Menu bar (File, Tools, Settings, Help)
- Toolbar (Connect All, Emergency Stop)
- Status bar with connection indicators
- Position and FPS display

**CameraWidget**:
- Connection controls
- Exposure/gain/FPS sliders
- Live view display
- Image statistics

**StageWidget**:
- XY/Z connection controls
- Directional movement buttons
- Absolute positioning inputs
- Position display

**ScanWidget**:
- Scan type selection
- Parameter configuration
- Progress bar and status
- Start/pause/cancel controls

**CalibrationWidget**:
- Tilt calibration workflow
- Autofocus controls
- Calibration import/export

### 5. Configuration System

**YAML-based configuration** with dot-notation access:

```yaml
camera:
  default_exposure: 15000
  fps_limit: 30

stages:
  xy:
    device_id: "113068710"
    x_range: [0, 100]
  z:
    device_id: "112064239"
    z_range: [0, 10]
```

**Usage**:
```python
settings = load_config('config/config.yaml')
exposure = settings.get('camera.default_exposure', 15000)
settings.set('camera.default_exposure', 20000)
```

### 6. Logging System

**Structured logging** with file rotation:

```python
from kalib.utils.logger import setup_logging, get_logger

setup_logging(log_dir='./logs', console_level='INFO')
logger = get_logger(__name__)

logger.info("Application started")
logger.error("Error occurred", exc_info=True)
```

**Log files**:
- `kalib_YYYYMMDD.log` - Daily rotating log
- `kalib_error.log` - Errors only

## Threading Model

**QThread for Background Operations**:

Scanning operations run in separate QThread to prevent UI blocking:

```python
class ScanWorker(QObject):
    def run_xy_scan(self):
        # Long-running scan operation
        for position in positions:
            # Move stage
            # Capture image
            # Emit progress signal
```

**Benefits**:
- Responsive UI during scans
- Proper signal/slot communication
- Clean cancellation support

## Error Handling Strategy

**Layered error handling**:

1. **Hardware Layer**: Catch device exceptions, log, re-raise as custom exceptions
2. **Controller Layer**: Catch custom exceptions, emit error signals
3. **View Layer**: Display user-friendly dialogs
4. **Application Layer**: Last-resort exception handler

**Custom Exception Hierarchy**:
```
HardwareError
├── ConnectionError
├── CommandError
├── ConfigurationError
└── TimeoutError
```

## Remote Operation

The instrument runs on a separate machine. `--serve` starts a `QTcpServer`
inside the existing Qt event loop, bound to 127.0.0.1 only, so command
handlers call the controllers directly on the main thread with no
cross-thread marshalling. SSH provides the network hop and authentication;
the server implements none of its own.

Full-resolution frames never cross the command channel — `snap` writes to the
instrument's disk and returns a path, and `preview` is the only command
returning pixels, downscaled and size-capped. See
[REMOTE_OPERATION.md](REMOTE_OPERATION.md).

## Data Flow Examples

### Scanning Workflow

```
User clicks "Start Scan" in ScanWidget
        ↓
ScanWidget calls scan_controller.start_scan()
        ↓
ScanController creates ScanWorker and QThread
        ↓
ScanWorker loop:
  - stage_controller.move_absolute(x, y)
  - camera_controller.capture_image()
  - scan_model.add_scan_position(pos, image)
  - Emit progress_updated signal
        ↓
ScanWidget updates progress bar
        ↓
Worker emits scan_completed
        ↓
ScanWidget displays "Scan completed"
```

### Camera Capture Flow

```
User adjusts exposure slider in CameraWidget
        ↓
Slider valueChanged signal
        ↓
CameraWidget._on_exposure_changed()
        ↓
camera_controller.set_exposure_time(value)
        ↓
CameraController updates hardware
        ↓
camera_model.update_settings(exposure_time=value)
        ↓
CameraController emits settings_changed signal
```

## Testing Strategy

**Test Coverage**:

Measured 2026-08-21 with `pytest --cov=kalib`: **47% overall**. Server and CLI
sit at 93-100%; the Qt view layer is 7-15% and is effectively untested. Treat
any coverage figure written into a document as stale unless it names the date
it was measured.


- **Unit Tests**: Models, algorithms, utilities
- **Integration Tests**: Controllers with mocked hardware
- **Hardware Tests**: With mock devices
- **UI Tests**: pytest-qt for widget testing

**Example**:
```python
def test_camera_model_add_image():
    model = CameraModel()
    image = np.zeros((480, 640, 3))

    model.add_image(image)

    assert model.state.frame_count == 1
    assert model.get_current_image() is not None
```

## Performance Considerations

**Optimizations**:
- Image buffer size limit (default: 100 images)
- Configurable refresh rates
- Background threading for long operations
- Efficient numpy operations

**Bottlenecks**:
- Camera capture rate (hardware limited)
- Stage movement time (hardware limited)
- Image processing (GPU acceleration possible)

## Security Considerations

- No hardcoded credentials
- Environment-based configuration
- Input validation on all user inputs
- Safe file path handling
- Proper resource cleanup

## Extensibility

**Adding New Hardware**:

1. Create driver in `hardware/` inheriting from `HardwareDevice`
2. Implement `_do_connect()`, `_do_disconnect()`, `_do_initialize()`
3. Add device-specific methods
4. Export from `hardware/__init__.py`
5. Update configuration YAML

**Adding New Algorithms**:

1. Create module in `algorithms/`
2. Implement algorithm functions
3. Add unit tests
4. Export from `algorithms/__init__.py`
5. Integrate into controller

## Migration from Version 1.x

**Key Changes**:
- Monolithic → MVC architecture
- PyQt5 → PySide6 (Qt6)
- Hardcoded values → YAML configuration
- Print statements → Structured logging
- Daemon threads → QThread
- Minimal error handling → Comprehensive exceptions

**Migration Path**:
1. Export calibration data from v1.x
2. Update configuration to v2.0 format
3. Test hardware connections
4. Import calibration data
5. Verify scanning workflows

## Future Enhancements

**Potential Features**:
- REST API for remote control
- Real-time image processing pipeline
- GPU-accelerated algorithms
- Multi-camera support
- Advanced calibration methods
- Data visualization tools
- Plugin architecture

---

**Last Updated**: 2026-02-03
**Version**: 2.0.0
