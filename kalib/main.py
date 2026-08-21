"""Main application entry point.

Initializes the application, creates controllers, and launches the main window.
"""

import sys
import argparse
from pathlib import Path
from typing import Any, List, Optional, Tuple, TYPE_CHECKING
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config, Settings
from kalib.hardware.pi_stage_z import SETTLE_TOLERANCE_UM
from kalib.utils.logger import setup_logging, get_logger
from kalib.controllers import (
    CameraController,
    StageController,
    ScanController,
    CalibrationController
)
from kalib.views import MainWindow

if TYPE_CHECKING:
    from kalib.server.daemon import CommandDaemon


class KalibApplication:
    """Main Kalib application.

    Manages application lifecycle, dependency injection, and cleanup.
    """

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
        self.daemon: Optional["CommandDaemon"] = None
        self._logger = None
        self.settings: Settings = None
        self.app: QApplication = None
        self.main_window: MainWindow = None

        # Controllers
        self.camera: CameraController = None
        self.stage: StageController = None
        self.scan: ScanController = None
        self.calibration: CalibrationController = None

        # Load configuration
        try:
            self.settings = load_config(config_path=config_path)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            print("Using default configuration")
            from config import get_default_settings
            self.settings = get_default_settings()

        # Setup logging
        log_dir = self.settings.get('paths.logs_dir', './logs')
        console_level = log_level or self.settings.get('logging.console_level', 'INFO')
        file_level = self.settings.get('logging.file_level', 'DEBUG')

        setup_logging(
            log_dir=log_dir,
            console_level=getattr(__import__('logging'), console_level),
            file_level=getattr(__import__('logging'), file_level)
        )

        self._logger = get_logger(__name__)
        self._logger.info("=" * 60)
        self._logger.info("Kalib Microscopy Control System - Version 2.0.0")
        self._logger.info("=" * 60)

    def initialize(self) -> bool:
        """Initialize application components.

        Returns:
            True if initialization successful
        """
        try:
            self._logger.info("Initializing application...")

            # Create Qt application
            self.app = QApplication(sys.argv)
            self.app.setApplicationName("Kalib")
            self.app.setOrganizationName("Kalib Team")

            # High DPI support
            self.app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
            self.app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

            # Initialize controllers
            self._init_controllers()

            # Create main window
            self.main_window = MainWindow(
                camera_controller=self.camera,
                stage_controller=self.stage,
                scan_controller=self.scan,
                calibration_controller=self.calibration,
                settings=self.settings
            )

            if self._serve:
                self._start_command_server()

            self._logger.info("Application initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Application initialization failed: {e}", exc_info=True)
            return False

    def _init_controllers(self) -> None:
        """Initialize controllers with dependency injection."""
        self._logger.info("Initializing controllers...")

        from kalib.hardware import HardwareFactory

        if self._simulate:
            self.settings.set('hardware.backend', 'sim')

        factory = HardwareFactory(self.settings)
        self._logger.info(f"Hardware backend: {factory.backend}")

        xy_device_id = self.settings.get('stages.xy.device_id')
        z_device_id = self.settings.get('stages.z.device_id')
        limits = self._build_stage_limits()

        camera_device, xy_device, z_device = self._build_sim_devices(
            factory, xy_device_id, z_device_id, limits
        )

        self.camera = CameraController(
            device_idx=0,
            device=camera_device
        )

        self.stage = StageController(
            xy_device_id=xy_device_id,
            z_device_id=z_device_id,
            limits=limits,
            xy_device=xy_device,
            z_device=z_device,
            settle_tolerance=self.settings.get(
                'stages.z.settle_tolerance', SETTLE_TOLERANCE_UM),
        )

        self.scan = ScanController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )

        self.calibration = CalibrationController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )

        self._logger.info("Controllers initialized")

    def _build_stage_limits(self) -> Any:
        """Build stage movement limits from configuration.

        Returns:
            Configured StageLimits, defaulting to the standard XY/Z ranges
        """
        from kalib.models import StageLimits

        xy_x_range = self.settings.get('stages.xy.x_range', [0.0, 100.0])
        xy_y_range = self.settings.get('stages.xy.y_range', [0.0, 100.0])
        z_range = self.settings.get('stages.z.z_range', [0.0, 10.0])

        return StageLimits(
            x_min=xy_x_range[0],
            x_max=xy_x_range[1],
            y_min=xy_y_range[0],
            y_max=xy_y_range[1],
            z_min=z_range[0],
            z_max=z_range[1]
        )

    def _build_sim_devices(self, factory: Any, xy_device_id: Optional[str],
                            z_device_id: Optional[str], limits: Any
                            ) -> Tuple[Any, Any, Any]:
        """Build simulated devices for the sim backend.

        Real drivers stay lazy: the controllers construct them at connect
        time, as they always have. Constructing here would raise
        ImportError at startup on machines without the vendor SDKs, so
        this only builds devices when the sim backend is selected.

        Args:
            factory: Configured hardware factory
            xy_device_id: XY stage device ID from configuration
            z_device_id: Z stage device ID from configuration
            limits: Stage movement limits

        Returns:
            Tuple of (camera, xy stage, z stage) devices, all None unless
            the factory backend is 'sim'
        """
        if factory.backend != 'sim':
            return None, None, None

        camera_device = factory.create_camera(device_idx=0)
        xy_device = factory.create_stage_xy(
            device_id=xy_device_id,
            x_range=(limits.x_min, limits.x_max),
            y_range=(limits.y_min, limits.y_max)
        )
        z_device = factory.create_stage_z(
            device_id=z_device_id,
            z_range=(limits.z_min, limits.z_max)
        )
        return camera_device, xy_device, z_device

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

    def run(self) -> int:
        """Run application.

        Returns:
            Exit code
        """
        if not self.initialize():
            self._logger.error("Failed to initialize application")
            return 1

        try:
            # Show main window
            self.main_window.show()

            self._logger.info("Application started")

            # Run event loop
            return self.app.exec()

        except Exception as e:
            self._logger.error(f"Application error: {e}", exc_info=True)
            return 1

        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            self._logger.info("Cleaning up application...")

            if self.daemon is not None:
                self.daemon.stop()

            # Cleanup controllers
            if self.camera:
                self.camera.cleanup()

            if self.stage:
                self.stage.cleanup()

            if self.scan:
                self.scan.cleanup()

            if self.calibration:
                self.calibration.cleanup()

            self._logger.info("Application cleanup complete")

        except Exception as e:
            self._logger.error(f"Error during cleanup: {e}", exc_info=True)


def _add_serve_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the command-server arguments to a parser.

    Args:
        parser: Parser to extend
    """
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


def parse_arguments(argv: Optional[List[str]] = None):
    """Parse command line arguments.

    Args:
        argv: Argument list to parse; reads sys.argv when None

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Kalib - Microscopy Control System"
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help="Path to configuration file"
    )

    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=None,
        help="Logging level"
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default=None,
        help="Log directory path"
    )

    parser.add_argument(
        '--simulate',
        action='store_true',
        help="Run against simulated hardware instead of the instrument"
    )

    _add_serve_arguments(parser)

    return parser.parse_args(argv)


def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()

    # Create and run application
    app = KalibApplication(
        config_path=args.config,
        log_level=args.log_level,
        simulate=args.simulate,
        serve=args.serve,
        serve_port=args.serve_port
    )

    # Run application
    sys.exit(app.run())


if __name__ == '__main__':
    main()
