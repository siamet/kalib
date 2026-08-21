# Kalib - Microscopy Control System

**Version 2.0.0** | **Status: Production Ready** ✅

Kalib is a comprehensive microscopy control system built with clean MVC architecture using PySide6 (Qt6). It provides advanced control for IDS cameras and PI motion stages with features including XY/Z-stack scanning, autofocus, and tilt calibration.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![Qt](https://img.shields.io/badge/Qt-6-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-production-brightgreen.svg)

---

## ✨ Features

### Hardware Support
- **IDS uEye Cameras** - Full control via IDS peak SDK
- **PI E-725 XY Stage** - High-precision XY motion control
- **PI E-816.DB Z Stage** - Focus control with piezo actuator
- **Illumination** - currently manual; not yet controllable from software.
  A serial LED controller is being sourced, and `led_driver.py` targets it.

### Core Capabilities
- **XY Scanning** - Automated grid scanning with position tracking
- **Z-Stack Scanning** - Multiple focus planes for 3D reconstruction
- **Tilt Calibration** - 4 or 9-point calibration with automatic Z correction
- **Autofocus** - Multiple sharpness metrics (Gradient, Sobel, Laplacian, Variance)
- **Live View** - Real-time camera feed with adjustable exposure/gain
- **Remote Operation** - drive the instrument over SSH; see [REMOTE_OPERATION.md](docs/REMOTE_OPERATION.md)
- **Simulated Hardware** - run the whole application with no instrument attached (`--simulate`)

### Modern Architecture
- **MVC Pattern** - Clean separation of Models, Views, Controllers
- **Qt6/PySide6** - Modern GUI with dark/light themes
- **YAML Configuration** - No hardcoded values, user-customizable settings
- **Structured Logging** - Multi-level logs with daily rotation
- **Error Handling** - Comprehensive exception hierarchy
- **Background Threading** - Responsive UI during long operations

---

## 📋 Quick Start

### Prerequisites
- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Rust-based Python package manager
- IDS peak SDK, extended version (install manually from IDS website)
  - **Must be >= 2.9** for Python 3.12 support
- PI motion controllers connected via USB

### Installation

#### Linux / macOS
```bash
# Clone repository
cd /path/to/kalib

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Create virtual environment and install dependencies
uv venv --python 3.12
source .venv/bin/activate
uv pip sync requirements.lock          # exact tested versions

# Install IDS peak SDK (manual step - see https://www.ids-imaging.com/)

# Verify installation
python -m pytest tests/ -v

# Launch application
python -m kalib.main
```

#### Windows
```bash
# IMPORTANT: Install Visual C++ Redistributables FIRST
# Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

# Clone repository
cd C:\path\to\kalib

# Install uv (if not installed - PowerShell as Administrator)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Create virtual environment and install dependencies
uv venv --python 3.12
.venv\Scripts\activate
uv pip sync requirements.lock          # exact tested versions

# Install IDS peak SDK (manual step - see https://www.ids-imaging.com/)

# Verify installation
python -m pytest tests/ -v

# Launch application
python -m kalib.main
```

**Windows DLL Errors?** See [WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) for comprehensive troubleshooting.

### First Launch

1. **Configure Hardware**:
   - Go to **Settings → Preferences**
   - Update camera and stage device IDs
   - Set data and log directories
   - Click **OK** to save

2. **Connect Hardware**:
   - Use **Tools → Connect All**
   - Or connect individually from Camera/Stage tabs
   - Verify green status indicators

3. **Test Scan**:
   - Navigate to **Scan** tab
   - Select "XY Scan"
   - Configure small test area (1mm × 1mm)
   - Click **Start Scan**

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[USER_GUIDE.md](docs/USER_GUIDE.md)** | Complete user manual with tutorials |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Technical architecture and design patterns |
| **[ENGINEERING-STANDARDS.md](docs/ENGINEERING-STANDARDS.md)** | Coding standards, workflow, and quality checklist |

### Quick Links
- [Installation Guide](docs/USER_GUIDE.md#installation)
- [Camera Control](docs/USER_GUIDE.md#camera-control)
- [Scanning Operations](docs/USER_GUIDE.md#scanning-operations)
- [Calibration](docs/USER_GUIDE.md#calibration)
- [Troubleshooting](docs/USER_GUIDE.md#troubleshooting)
- [Architecture Overview](docs/ARCHITECTURE.md#overview)
- [Testing Strategy](docs/ARCHITECTURE.md#testing-strategy)

---

## 🏗️ Architecture Overview

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

### Directory Structure

```
kalib/
├── config/                     # Configuration Management
│   ├── settings.py             # YAML config loader
│   └── default_config.yaml     # Default settings
│
├── kalib/
│   ├── main.py                 # Application entry point
│   ├── models/                 # Data & Business Logic
│   ├── controllers/            # Workflow Coordination
│   ├── views/                  # User Interface
│   ├── hardware/               # Device Drivers
│   ├── algorithms/             # Scientific Algorithms
│   └── utils/                  # Utilities
│
└── tests/                      # Test Suite
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed component descriptions.

---

## 🚀 Usage Examples

### Programmatic Camera Control

```python
from kalib.hardware import IDSCamera
from kalib.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Connect camera
camera = IDSCamera(device_idx=0)
camera.connect()

# Configure
camera.set_exposure_time(15000)  # 15ms
camera.set_gain(1.0)

# Capture
camera.start_acquisition()
image = camera.capture(timeout_ms=1000)

# Cleanup
camera.stop_acquisition()
camera.disconnect()
```

### XY Scanning Workflow

```python
from kalib.controllers import ScanController, CameraController, StageController
from kalib.models import XYScanParameters

# Initialize controllers
camera_ctrl = CameraController(device_idx=0)
stage_ctrl = StageController(xy_device_id="113068710", z_device_id="112064239")
scan_ctrl = ScanController(camera_ctrl, stage_ctrl)

# Configure scan
params = XYScanParameters(
    start_x=0.0, start_y=0.0,
    end_x=10.0, end_y=10.0,
    step_size=0.1
)
scan_ctrl.configure_xy_scan(params)

# Start scan
scan_ctrl.start_scan(save_path="./data/scan_001")

# Monitor progress via signals
scan_ctrl.progress_updated.connect(lambda cur, tot: print(f"{cur}/{tot}"))
scan_ctrl.scan_completed.connect(lambda: print("Scan complete!"))
```

### Command-Line Options

```bash
# Standard launch
python -m kalib.main

# Custom config
python -m kalib.main --config /path/to/config.yaml

# Debug mode
python -m kalib.main --log-level DEBUG

# Custom log directory
python -m kalib.main --log-dir /path/to/logs
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_models/test_camera_model.py -v

# With coverage
python -m pytest tests/ --cov=kalib --cov-report=html
```

### Test Coverage

| Component | Coverage | Status |
|-----------|----------|--------|
| Server / CLI | 93-100% | ✅ Good |
| Models | 60-91% | ⚠️ scan_model is the weak point |
| Controllers | 47-84% | ⚠️ scan_controller is the weak point |
| Algorithms | 63-71% | ⚠️ Partial |
| Views | 7-15% | ❌ Barely tested |

Overall **47%** (`pytest --cov=kalib`, measured 2026-08-21). The GUI layer is
essentially untested; everything reachable without a Qt widget is covered well.

---

## ⚙️ Configuration

### YAML Configuration

Settings are managed via YAML files with dot-notation access:

```yaml
# config/user_config.yaml
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

paths:
  data_dir: "./data"
  logs_dir: "./logs"

ui:
  theme: "dark"  # or "light"
```

### Accessing Configuration

```python
from config.settings import load_config

settings = load_config('config/user_config.yaml')

# Dot-notation access
exposure = settings.get('camera.default_exposure', 15000)
xy_device = settings.get('stages.xy.device_id')

# Update and save
settings.set('camera.default_exposure', 20000)
settings.save()
```

---

## 📊 Project Statistics

Run `find kalib -name '*.py' | wc -l` and `pytest --cov=kalib` for current
figures — hardcoding them here has meant they were wrong more often than right.

As of 2026-08-21: 48 modules, ~10,900 lines, 184 tests, 47% coverage.

---

## 🛠️ Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/siamet/kalib.git
cd kalib

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies (very fast!)
uv pip sync requirements.lock          # exact tested versions

# Run tests
python -m pytest tests/ -v
```

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

### Code Style

- **Python**: PEP 8 compliant
- **Type Hints**: Comprehensive type annotations
- **Docstrings**: Google-style docstrings
- **Line Length**: Max 100-120 characters
- **File Size**: Target < 500 lines per file

### Adding New Features

1. **Create Models**: Define data structures in `kalib/models/`
2. **Implement Controllers**: Add business logic in `kalib/controllers/`
3. **Create Views**: Build UI in `kalib/views/`
4. **Write Tests**: Add tests in `tests/`
5. **Update Documentation**: Update relevant docs

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed guidelines.

---

## 🔧 Troubleshooting

### Common Issues

**Windows: DLL load failed error** ⚠️
```
ImportError: DLL load failed while importing QtWidgets
```
**Solution**: Install Visual C++ Redistributables
```bash
# Download and install:
https://aka.ms/vs/17/release/vc_redist.x64.exe

# Or see comprehensive guide:
See WINDOWS_SETUP.md for 7 different solutions
```

**Camera not connecting**:
```bash
# Verify IDS peak SDK
python -c "import ids_peak"

# Check USB connection (USB 3.0 required)
# Try different USB port
```

**Stage not responding**:
```bash
# Verify device ID in settings
# Check USB connection
# Use PI software to verify device serial number
```

**Application won't start**:
```bash
# Verify environment is active
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Check Python version
python --version  # Should be 3.12+

# Check logs
cat logs/kalib_error.log
```

See [USER_GUIDE.md#troubleshooting](docs/USER_GUIDE.md#troubleshooting) for comprehensive troubleshooting.

---

## 📝 Changelog

### Version 2.0.0 (2026-02-03)

**Major Refactoring**:
- ✅ Complete rewrite with MVC architecture
- ✅ Upgrade from PyQt5 to PySide6 (Qt6)
- ✅ YAML-based configuration system
- ✅ Structured logging with rotation
- ✅ Comprehensive error handling
- ✅ Unit test suite (47% overall; server and CLI 93-100%, GUI largely untested)
- ✅ Modern themed UI (dark/light)

**Features**:
- ✅ All v1.x features preserved
- ✅ Background threading with QThread
- ✅ Real-time status indicators
- ✅ Progress bars and cancellation support
- ✅ Keyboard shortcuts
- ✅ Command-line arguments

**Breaking Changes**:
- Configuration moved to YAML files
- Requires Python 3.12+ (was 3.7+)
- Calibration format changed to JSON

### Version 1.x

- Original monolithic implementation
- Basic XY/Z scanning
- Tilt calibration
- IDS camera support
- PI stage support

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new features
4. Ensure tests pass (`pytest tests/`)
5. Follow code style guidelines
6. Update documentation
7. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

### Technologies
- **PySide6 (Qt6)** - Modern GUI framework
- **ids-peak** - IDS camera SDK
- **pipython** - PI motion controller library
- **NumPy** - Numerical computing
- **OpenCV** - Image processing

### Inspiration
This project follows industry best practices for scientific instrument control software, including MVC architecture, SOLID principles, and comprehensive error handling.

---

## 📞 Support

- **Documentation**: [USER_GUIDE.md](docs/USER_GUIDE.md)
- **Architecture**: [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Issues**: Report bugs via GitHub Issues (if repository hosted)

---

## 🗺️ Roadmap

### Planned Features

**v2.1** (Near-term):
- [ ] Integration tests for controllers
- [ ] UI tests with pytest-qt
- [ ] Depth profiling implementation
- [ ] Continuous Integration (CI/CD)

**v2.2** (Medium-term):
- [ ] REST API for remote control
- [ ] Plugin system for custom algorithms
- [ ] Live data visualization
- [ ] Multi-camera support

**v3.0** (Long-term):
- [ ] GPU-accelerated image processing
- [ ] Cloud data sync
- [ ] Advanced calibration methods
- [ ] Internationalization (i18n)

---

## 📈 Status

**Current Version**: 2.0.0
**Status**: ✅ Production Ready
**Last Updated**: 2026-02-03

All 7 implementation phases complete. Ready for deployment.

---

**Made with ❤️ using Python and Qt**
