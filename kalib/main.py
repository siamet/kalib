"""Main application entry point.

Initializes the application, creates controllers, and launches the main window.
"""

import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config, Settings
from kalib.utils.logger import setup_logging, get_logger
from kalib.controllers import (
    CameraController,
    StageController,
    ScanController,
    CalibrationController
)
from kalib.views import MainWindow


class KalibApplication:
    """Main Kalib application.

    Manages application lifecycle, dependency injection, and cleanup.
    """

    def __init__(self, config_path: str = None, log_level: str = None):
        """Initialize application.

        Args:
            config_path: Path to configuration file
            log_level: Logging level override
        """
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
        self._logger.info("Kalib Microscopy Control System - Version 2026.02.01")
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

            self._logger.info("Application initialized successfully")
            return True

        except Exception as e:
            self._logger.error(f"Application initialization failed: {e}", exc_info=True)
            return False

    def _init_controllers(self) -> None:
        """Initialize controllers with dependency injection."""
        self._logger.info("Initializing controllers...")

        # Camera controller
        camera_settings = self.settings.get_section('camera')
        self.camera = CameraController(
            device_idx=0  # TODO: Get from config
        )

        # Stage controller
        xy_device_id = self.settings.get('stages.xy.device_id')
        z_device_id = self.settings.get('stages.z.device_id')

        from kalib.models import StageLimits
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
            limits=limits
        )

        # Scan controller
        self.scan = ScanController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )

        # Calibration controller
        self.calibration = CalibrationController(
            camera_controller=self.camera,
            stage_controller=self.stage
        )

        self._logger.info("Controllers initialized")

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


def parse_arguments():
    """Parse command line arguments.

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

    return parser.parse_args()


def main():
    """Main entry point."""
    # Parse arguments
    args = parse_arguments()

    # Create and run application
    app = KalibApplication(
        config_path=args.config,
        log_level=args.log_level
    )

    # Run application
    sys.exit(app.run())


if __name__ == '__main__':
    main()
