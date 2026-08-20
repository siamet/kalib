"""Tests for the --serve flag and daemon wiring."""

from kalib.controllers.camera_controller import CameraController
from kalib.controllers.stage_controller import StageController
from kalib.hardware.factory import HardwareFactory
from kalib.main import KalibApplication, parse_arguments
from kalib.utils.logger import get_logger


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


class FakeSettings:
    """Minimal stand-in for Settings, supporting dot-notation get."""

    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def _bare_app_with_controllers() -> KalibApplication:
    """Build a KalibApplication with sim controllers, skipping __init__.

    __init__ loads config files and sets up logging, neither of which
    _start_command_server or cleanup need. The controllers are QObject-based
    and construct fine without a QApplication, mirroring the pattern in
    tests/test_controllers/test_main_hardware_wiring.py and the `daemon`
    fixture in tests/test_server/test_daemon.py.

    Returns:
        A KalibApplication with camera/stage controllers, no scan or
        calibration controller, _serve_port set to 0 (OS picks a free
        port), and daemon set to None.
    """
    factory = HardwareFactory(FakeSettings({'hardware.backend': 'sim'}))
    app = object.__new__(KalibApplication)
    app.camera = CameraController(device=factory.create_camera())
    app.stage = StageController(xy_device=factory.create_stage_xy(),
                                 z_device=factory.create_stage_z())
    app.scan = None
    app.calibration = None
    app.daemon = None
    app._serve_port = 0
    app._logger = get_logger(__name__)
    return app


def test_start_command_server_binds_a_listening_daemon(qapp):
    """_start_command_server sets self.daemon to a listening daemon."""
    app = _bare_app_with_controllers()
    try:
        app._start_command_server()

        assert app.daemon is not None
        assert app.daemon.is_listening()
        assert app.daemon.port > 0
    finally:
        if app.daemon is not None:
            app.daemon.stop()


def test_start_command_server_wires_the_real_controllers(qapp):
    """The registry the daemon dispatches into holds this app's controllers."""
    app = _bare_app_with_controllers()
    try:
        app._start_command_server()

        registry = app.daemon._registry
        assert registry.camera is app.camera
        assert registry.stage is app.stage
    finally:
        if app.daemon is not None:
            app.daemon.stop()


def test_cleanup_stops_the_daemon(qapp):
    """cleanup() stops the command server started by _start_command_server."""
    app = _bare_app_with_controllers()
    app._start_command_server()
    assert app.daemon.is_listening()

    try:
        app.cleanup()

        assert app.daemon.is_listening() is False
    finally:
        if app.daemon is not None:
            app.daemon.stop()
