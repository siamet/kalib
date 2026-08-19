# CLAUDE.md - AI Development Context

This file provides comprehensive guidance to Claude Code when working with this repository. It defines coding standards, development practices, and project-specific context that should persist across all sessions.

## 🎯 Quick Session Start
- Use `/status` to check current progress and priorities

---

## 🧱 Core Development Philosophy

### KISS (Keep It Simple, Stupid)
Simplicity should be a key goal in design. Choose straightforward solutions over complex ones whenever possible. Simple solutions are easier to understand, maintain, and debug.

### YAGNI (You Aren't Gonna Need It)
Avoid building functionality on speculation. Implement features only when they are needed, not when you anticipate they might be useful in the future.

### Design Principles
- **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Open/Closed Principle**: Software entities should be open for extension but closed for modification.
- **Single Responsibility**: Each function, class, and module should have one clear purpose.
- **Fail Fast**: Check for potential errors early and raise exceptions immediately when issues occur.

---

## 🏗️ Code Structure & Standards

### File and Function Limits
- **Files should be under 500 lines**. If approaching this limit, refactor by splitting into modules/components
- **Functions should be under 50 lines** with a single, clear responsibility
- **Classes/Components should be under 100 lines** and represent a single concept or entity
- **Line length should be max 100-120 characters** (following project linting rules)
- **Use project-specific environment** (virtual env, node_modules, etc.) for all commands

### Code Organization
- **Organize code into clearly separated modules/components**, grouped by feature or responsibility
- **Follow consistent directory structure** as defined in project architecture
- **Maintain clear separation of concerns** between layers (UI, business logic, data)

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

## 📋 Style & Conventions

### Code Style
- **Follow language-specific best practices** (PEP 8 for Python, ESLint for JS/TS, etc.)
- **Use type annotations** where supported (TypeScript, Python type hints, etc.)
- **Prefer explicit over implicit** - make intentions clear in any language
- **Use descriptive names** that explain purpose and context

### Naming Conventions
**[Adapt based on language/framework conventions]**
- **Variables/Functions**: [e.g., camelCase (JS/TS), snake_case (Python), PascalCase (C#)]
- **Classes/Components**: [e.g., PascalCase (most languages), kebab-case (Vue components)]
- **Constants**: [e.g., UPPER_SNAKE_CASE, ALL_CAPS]
- **Files**: [e.g., kebab-case.js, snake_case.py, PascalCase.cs]
- **Directories**: [e.g., kebab-case, snake_case, consistent with project]

### Documentation Standards
**[Language-specific documentation format]**
```
// JavaScript/TypeScript JSDoc
/**
 * Brief description of function purpose
 * @param {string} param1 - Description of parameter
 * @param {number} param2 - Description of parameter  
 * @returns {boolean} Description of return value
 * @throws {Error} When validation fails
 */

# Python docstrings
"""Brief description of function purpose.

Args:
    param1: Description of parameter
    param2: Description of parameter
    
Returns:
    Description of return value
    
Raises:
    ValueError: When validation fails
"""
```

---

## 🧪 Testing Strategy

### Test-Driven Development (TDD)
1. **Write tests first** - Define expected behavior before implementation
2. **Run tests and confirm they fail** - Ensure tests are actually testing something
3. **Write minimal code** to make tests pass
4. **Refactor** while keeping tests green

### Test Organization
- **Unit tests**: Test individual functions and classes in isolation
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete user workflows
- **Test file naming**: `test_[module_name].py`

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
- `environment.yml` - Conda environment specification

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

## 🚨 Error Handling & Logging

### Exception Best Practices
- **Use language-specific exception types** rather than generic errors
- **Provide meaningful error messages** that help with debugging
- **Log errors with context** including relevant data for diagnosis
- **Fail fast** - validate inputs early and handle errors gracefully

### Logging Strategy
**[Adapt to language/framework logging system]**
```
// JavaScript/Node.js
console.debug('Detailed information for diagnosis');
console.info('General information about execution');
console.warn('Something unexpected happened');
console.error('A serious problem occurred');

// Python
import logging
logger = logging.getLogger(__name__)
logger.debug("Detailed information")
logger.info("General information")
logger.warning("Something unexpected")
logger.error("Serious problem")

// Java
logger.debug("Detailed information");
logger.info("General information");  
logger.warn("Something unexpected");
logger.error("Serious problem");
```

---

## 🔄 Development Workflow

### Git Workflow
- **Feature branches** for all new development
- **Descriptive commit messages** following conventional format
- **Small, focused commits** that represent single logical changes
- **Pull request reviews** before merging to main

### Branch Strategy
```bash
main              # Production-ready code
develop           # Integration branch for features
feature/[name]    # Individual feature development
hotfix/[name]     # Critical production fixes
```

### Commit Message Format
```
type(scope): brief description

Detailed explanation if needed

- List any breaking changes
- Reference related issues (#123)

Types: feat, fix, docs, style, refactor, test, chore
```

---

## 🛡️ Security & Performance

### Security Guidelines
- **Never commit secrets** - use environment variables or secure vaults
- **Validate all inputs** - sanitize and validate user data appropriately
- **Use parameterized queries** - prevent injection attacks
- **Implement proper authentication** and authorization patterns
- **Follow OWASP guidelines** for web applications
- **Keep dependencies updated** - regularly update packages/libraries

### Performance Considerations
- **Database optimization**: Use indexes, avoid N+1 queries, optimize query patterns
- **Caching strategies**: Implement appropriate caching at multiple levels
- **Resource management**: Properly close connections, manage memory usage
- **Profiling**: Measure performance before optimizing - don't guess
- **Bundle/Build optimization**: Minimize bundle size, optimize assets

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

## ⚠️ Important Development Notes

### Critical Guidelines
- **NEVER ASSUME OR GUESS** - When in doubt, ask for clarification
- **Always verify file paths and imports** before use
- **Use project environment** (venv, node_modules, etc.) for all commands
- **Test your code** - No feature is complete without tests
- **Update documentation** when making architectural changes
- **Follow the planning workflow** - use `/plan-feature` before coding

### Session Management
- **Use `/clear`** when switching to completely different features
- **Use `/update-planning`** to save progress and decisions
- **Keep CLAUDE.md current** - update when patterns or practices change

### Quality Checklist
Before completing any feature:
- [ ] Code follows style guidelines
- [ ] Tests are written and passing
- [ ] Documentation is updated
- [ ] Error handling is implemented
- [ ] Performance impact is considered
- [ ] Security implications are reviewed

---

## 🔍 Search & Discovery Commands

When analyzing code or debugging:
1. **Use `tree` command** to understand project structure
2. **Search for patterns** using `grep` or `rg` (ripgrep)
3. **Check git history** for context on changes
4. **Review test files** to understand expected behavior
5. **Examine config files** for environment setup

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