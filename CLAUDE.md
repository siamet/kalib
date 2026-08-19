# CLAUDE.md - AI Development Context

This file provides project-specific guidance to Claude Code when working with this
repository: the technology stack, architecture, hardware configuration, and the
patterns particular to Kalib.

**Engineering standards live in [docs/ENGINEERING-STANDARDS.md](docs/ENGINEERING-STANDARDS.md)** -
development philosophy, code structure limits, style and naming conventions, testing
strategy, error handling, git workflow, and the quality checklist. Read both.

---

## 🎯 Quick Session Start

- Use `/status` to check current progress and priorities

---

## 🛠️ Technology Stack & Environment

### Primary Technologies
- **Language**: Python 3.12+
- **Framework**: PySide6 (Qt6) - Modern GUI framework
- **Hardware SDKs**:
  - IDS peak SDK (camera control)
  - pipython (PI motion controllers)
  - pyserial (LED driver communication)
- **Scientific Computing**: NumPy, SciPy, scikit-image, OpenCV
- **Testing**: pytest, pytest-qt, pytest-cov, pytest-mock
- **Configuration**: PyYAML

### Development Environment
**Environment Management**: uv
**Package Manager**: uv pip (Rust-based, extremely fast)
**Python Version**: 3.12
**Virtual Environment**: .venv

### Essential Commands
```bash
# Environment setup (first time)
uv venv --python 3.12                        # Create virtual environment
source .venv/bin/activate                    # Activate (macOS/Linux)
uv pip install -r requirements.txt           # Install dependencies

# Daily use
source .venv/bin/activate                    # Activate environment
./run_kalib.sh                               # Or use launcher script

# Development/Launch
python -m kalib.main                         # Standard launch
python -m kalib.main --log-level DEBUG       # Debug mode
python -m kalib.main --config /path/to/config.yaml  # Custom config

# Testing
python -m pytest tests/ -v                   # All tests
python -m pytest tests/test_models/ -v       # Specific module
python -m pytest tests/ --cov=kalib --cov-report=html  # With coverage

# Code Quality
pylint kalib/                                # Lint code
black kalib/ tests/                          # Format code
mypy kalib/                                  # Type checking
```

---

## 🔧 Project-Specific Context

### Current Architecture
**Kalib** is a production-ready microscopy control system built with clean MVC architecture:

```
View Layer (PySide6 Widgets)
    ↓ Qt Signals/Slots
Controller Layer (Business Logic)
    ↓ Commands/Updates
Model Layer (State) + Hardware Layer (Device Abstraction)
```

**Project Type**: Desktop Scientific Instrument Control Application
**Status**: Version 2.0.0 - Production Ready ✅
**Lines of Code**: ~8,509 lines across 40+ Python modules

### Key Files and Directories

**Configuration**:
- `config/default_config.yaml` - Default system settings (122 lines)
- `config/settings.py` - YAML config loader with dot-notation access
- `requirements.txt` - Python dependencies (installed with uv)
- `.python-version` - Python version pin for uv (3.12)

**Application Entry**:
- `kalib/main.py` - Application entry point, dependency injection

**Models** (Data & State):
- `kalib/models/camera_model.py` - Camera state and settings
- `kalib/models/stage_model.py` - Stage position and limits
- `kalib/models/scan_model.py` - Scan parameters and progress
- `kalib/models/calibration_model.py` - Calibration data

**Controllers** (Business Logic):
- `kalib/controllers/camera_controller.py` - Camera lifecycle and capture
- `kalib/controllers/stage_controller.py` - Motion control coordination
- `kalib/controllers/scan_controller.py` - Scanning workflow with QThread
- `kalib/controllers/calibration_controller.py` - Tilt calibration and autofocus

**Views** (User Interface):
- `kalib/views/main_window.py` - Main tabbed interface
- `kalib/views/camera_widget.py` - Camera control UI
- `kalib/views/stage_widget.py` - Stage control UI
- `kalib/views/scan_widget.py` - Scanning interface
- `kalib/views/calibration_widget.py` - Calibration UI
- `kalib/views/settings_dialog.py` - Configuration dialog

**Hardware Drivers**:
- `kalib/hardware/base.py` - Abstract base class with connection lifecycle
- `kalib/hardware/ids_camera.py` - IDS uEye camera driver (585 lines)
- `kalib/hardware/pi_stage_xy.py` - PI E-725 XY stage
- `kalib/hardware/pi_stage_z.py` - PI E-816.DB Z stage
- `kalib/hardware/led_driver.py` - Serial LED controller

**Algorithms**:
- `kalib/algorithms/sharpness.py` - Focus quality metrics (gradient, Sobel, Laplacian, variance)
- `kalib/algorithms/tilt_calibration.py` - Tilt plane fitting

**Utilities**:
- `kalib/utils/logger.py` - Structured logging with daily rotation
- `kalib/utils/image_utils.py` - Image processing utilities

**Tests**:
- `tests/test_models/` - Model unit tests (>80% coverage)
- `tests/test_algorithms/` - Algorithm tests
- `tests/test_hardware/` - Hardware abstraction tests
- `tests/conftest.py` - Shared pytest fixtures

**Documentation**:
- `README.md` - Project overview, quick start, examples (503 lines)
- `ARCHITECTURE.md` - Technical architecture documentation (468 lines)
- `USER_GUIDE.md` - Complete user manual with tutorials (800+ lines)
- `CLAUDE.md` - AI development context (this file)

### Hardware Configuration
**No Database** - This is a real-time control application, not a data-driven app

**Supported Hardware**:
- **Camera**: IDS uEye cameras (via IDS peak SDK)
- **XY Stage**: PI E-725 controller (device ID: "113068710")
- **Z Stage**: PI E-816.DB controller (device ID: "112064239")
- **LED**: Serial-controlled illumination

**Configuration System**:
All hardware settings stored in YAML with dot-notation access:
```python
settings.get('stages.xy.device_id')  # "113068710"
settings.get('camera.default_exposure', 15000)  # 15000µs fallback
```

### Key Workflows

**XY Scanning**: Automated grid scanning with position tracking
**Z-Stack Scanning**: Multiple focus planes for 3D reconstruction
**Tilt Calibration**: 4 or 9-point calibration with automatic Z correction
**Autofocus**: Multiple sharpness metrics (Gradient, Sobel, Laplacian, Variance)
**Shape from Focus (SFF)**: Advanced depth profiling

### External Dependencies

**GUI Framework**: PySide6 (Qt6) - Modern cross-platform GUI
**Hardware SDKs**:
- `ids-peak` - IDS camera SDK (requires manual installation)
- `pipython>=2.9.0` - PI motion controller library
- `pyserial>=3.5` - Serial communication for LED

**Scientific Stack**:
- `numpy>=1.24.0` - Array operations
- `scipy>=1.10.0` - Scientific computing
- `opencv-python>=4.7.0` - Image processing
- `scikit-image>=0.20.0` - Advanced image algorithms
- `matplotlib>=3.7.0` - Visualization

**Configuration & Testing**:
- `PyYAML>=6.0` - Configuration management
- `pytest>=7.3.0` + plugins - Testing framework

---

## 📚 Development Commands & Tools

### Essential Development Commands
```bash
# Environment setup: uv venv --python 3.12 && uv pip install -r requirements.txt
# Run application:   python -m kalib.main
# Testing:           python -m pytest tests/ -v
# Linting:           pylint kalib/
# Formatting:        black kalib/ tests/
# Type checking:     mypy kalib/
```

### Debugging Tools
- **Language debugger**: [e.g., Node.js inspector, pdb/ipdb, gdb, IDE debuggers]
- **Logging**: Use structured logging appropriate for the stack
- **Testing**: Verbose test output for debugging test failures  
- **Profiling**: [e.g., Chrome DevTools, cProfile, pprof, perf]
- **Network debugging**: [e.g., browser DevTools, curl, Postman, wire protocol tools]

---

## 🔄 Session Management

- **Use `/clear`** when switching to completely different features
- **Use `/update-planning`** to save progress and decisions
- **Keep CLAUDE.md current** - update when patterns or practices change

---

## 🎓 Learning Context for New Sessions

### Quick Session Start Checklist
When starting a new session with this project:

1. ✅ **Project Type**: Desktop scientific instrument control application
2. ✅ **Language**: Python 3.12+ with type hints
3. ✅ **Architecture**: MVC pattern with Qt6/PySide6
4. ✅ **Status**: Production-ready v2.0.0
5. ✅ **Environment**: uv virtual environment (activate with `source .venv/bin/activate`)
6. ✅ **Entry Point**: `python -m kalib.main`
7. ✅ **Testing**: `python -m pytest tests/ -v`

### Code Patterns to Follow

**Hardware Interaction**:
```python
# Always use controllers, never call hardware directly from views
camera_controller.capture_image()  # ✅ Good
camera_hardware.capture()  # ❌ Bad - bypasses controller layer
```

**Configuration Access**:
```python
# Use dot-notation for nested config
exposure = settings.get('camera.default_exposure', 15000)  # ✅ Good
exposure = settings['camera']['default_exposure']  # ❌ Bad - no default
```

**Error Handling**:
```python
# Use custom exceptions, log and re-raise
try:
    hardware.connect()
except HardwareError as e:
    logger.error(f"Connection failed: {e}")
    raise  # Let controller handle it
```

**Threading**:
```python
# Use QThread for long operations, emit signals for progress
class ScanWorker(QObject):
    progress_updated = Signal(int, int)

    def run_scan(self):
        for i, pos in enumerate(positions):
            # Do work
            self.progress_updated.emit(i, len(positions))
```

### Common Tasks Reference

**Adding a New Hardware Device**:
1. Create driver in `kalib/hardware/` inheriting from `HardwareDevice`
2. Implement abstract methods: `_do_connect()`, `_do_disconnect()`, `_do_initialize()`
3. Add to `hardware/__init__.py` exports
4. Create controller in `kalib/controllers/`
5. Create model in `kalib/models/` (if needed)
6. Create view widget in `kalib/views/`
7. Add configuration to `config/default_config.yaml`
8. Write tests in `tests/test_hardware/`

**Adding a New Algorithm**:
1. Create module in `kalib/algorithms/`
2. Implement pure functions (no hardware dependencies)
3. Add comprehensive docstrings with math notation if needed
4. Write unit tests in `tests/test_algorithms/`
5. Export from `algorithms/__init__.py`
6. Integrate into appropriate controller

**Adding a New UI Feature**:
1. Add model properties in relevant model class
2. Add controller methods with Qt signals
3. Create/update widget in `kalib/views/`
4. Connect signals/slots
5. Update main window if needed
6. Test with pytest-qt

---

**Project Version**: 2.0.0 (Production Ready)
**Python Version**: 3.12
**Environment**: .venv (uv)
