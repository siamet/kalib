"""Main application window.

Provides the main UI window with tabbed interface for different
functions and status indicators.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu,
    QLabel, QToolBar, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon

from kalib.controllers import (
    CameraController,
    StageController,
    ScanController,
    CalibrationController
)
from kalib.utils.logger import get_logger
from config import Settings


class StatusIndicator(QLabel):
    """Status indicator widget with color."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.set_status(False)

    def set_status(self, connected: bool) -> None:
        """Set connection status.

        Args:
            connected: True if connected
        """
        color = "green" if connected else "red"
        text = "●" if connected else "○"
        self.setText(f"{text} {self.label_text}")
        self.setStyleSheet(f"color: {color}; font-weight: bold;")


class MainWindow(QMainWindow):
    """Main application window.

    Provides tabbed interface for camera, stage, scanning, and
    calibration operations with status indicators.
    """

    def __init__(self,
                 camera_controller: CameraController,
                 stage_controller: StageController,
                 scan_controller: ScanController,
                 calibration_controller: CalibrationController,
                 settings: Settings):
        """Initialize main window.

        Args:
            camera_controller: Camera controller
            stage_controller: Stage controller
            scan_controller: Scan controller
            calibration_controller: Calibration controller
            settings: Application settings
        """
        super().__init__()

        self._logger = get_logger(__name__)
        self.settings = settings

        # Controllers
        self.camera = camera_controller
        self.stage = stage_controller
        self.scan = scan_controller
        self.calibration = calibration_controller

        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._setup_status_timer()

        self._logger.info("Main window initialized")

    def _setup_ui(self) -> None:
        """Setup user interface."""
        # Window properties
        self.setWindowTitle("Kalib - Microscopy Control System")
        geometry = self.settings.get('ui.window_geometry', [1554, 866])
        self.resize(geometry[0], geometry[1])

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Create menu bar
        self._create_menu_bar()

        # Create toolbar
        self._create_toolbar()

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Import and add tab widgets
        from kalib.views.camera_widget import CameraWidget
        from kalib.views.stage_widget import StageWidget
        from kalib.views.scan_widget import ScanWidget
        from kalib.views.calibration_widget import CalibrationWidget

        # Create tabs
        self.camera_widget = CameraWidget(self.camera, self.settings)
        self.stage_widget = StageWidget(self.stage, self.settings)
        self.scan_widget = ScanWidget(self.scan, self.camera, self.stage, self.settings)
        self.calibration_widget = CalibrationWidget(
            self.calibration, self.camera, self.stage, self.settings
        )

        # Add tabs
        self.tabs.addTab(self.camera_widget, "Camera")
        self.tabs.addTab(self.stage_widget, "Stage")
        self.tabs.addTab(self.scan_widget, "Scan")
        self.tabs.addTab(self.calibration_widget, "Calibration")

        # Create status bar
        self._create_status_bar()

        # Apply theme
        self._apply_theme()

    def _create_menu_bar(self) -> None:
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        save_action = QAction("&Save Configuration", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_configuration)
        file_menu.addAction(save_action)

        load_action = QAction("&Load Configuration", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._load_configuration)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        connect_all_action = QAction("Connect &All Devices", self)
        connect_all_action.triggered.connect(self._connect_all_devices)
        tools_menu.addAction(connect_all_action)

        disconnect_all_action = QAction("&Disconnect All Devices", self)
        disconnect_all_action.triggered.connect(self._disconnect_all_devices)
        tools_menu.addAction(disconnect_all_action)

        tools_menu.addSeparator()

        export_cal_action = QAction("&Export Calibration", self)
        export_cal_action.triggered.connect(self._export_calibration)
        tools_menu.addAction(export_cal_action)

        import_cal_action = QAction("&Import Calibration", self)
        import_cal_action.triggered.connect(self._import_calibration)
        tools_menu.addAction(import_cal_action)

        # Settings menu
        settings_menu = menubar.addMenu("&Settings")

        preferences_action = QAction("&Preferences", self)
        preferences_action.triggered.connect(self._show_preferences)
        settings_menu.addAction(preferences_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        """Create toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Connect all button
        connect_btn = QPushButton("Connect All")
        connect_btn.clicked.connect(self._connect_all_devices)
        toolbar.addWidget(connect_btn)

        # Disconnect all button
        disconnect_btn = QPushButton("Disconnect All")
        disconnect_btn.clicked.connect(self._disconnect_all_devices)
        toolbar.addWidget(disconnect_btn)

        toolbar.addSeparator()

        # Emergency stop button
        stop_btn = QPushButton("Emergency Stop")
        stop_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        stop_btn.clicked.connect(self._emergency_stop)
        toolbar.addWidget(stop_btn)

    def _create_status_bar(self) -> None:
        """Create status bar with indicators."""
        statusbar = QStatusBar()
        self.setStatusBar(statusbar)

        # Status indicators
        self.camera_indicator = StatusIndicator("Camera")
        self.xy_stage_indicator = StatusIndicator("XY Stage")
        self.z_stage_indicator = StatusIndicator("Z Stage")

        statusbar.addPermanentWidget(self.camera_indicator)
        statusbar.addPermanentWidget(self.xy_stage_indicator)
        statusbar.addPermanentWidget(self.z_stage_indicator)

        # Position display
        self.position_label = QLabel("Position: X=0.000 Y=0.000 Z=0.000")
        statusbar.addPermanentWidget(self.position_label)

        # FPS display
        self.fps_label = QLabel("FPS: 0.0")
        statusbar.addPermanentWidget(self.fps_label)

    def _apply_theme(self) -> None:
        """Apply UI theme."""
        theme = self.settings.get('ui.theme', 'dark')

        if theme == 'dark':
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #3d3d3d;
                    background-color: #2b2b2b;
                }
                QTabBar::tab {
                    background-color: #3d3d3d;
                    color: #ffffff;
                    padding: 8px 16px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: #4a4a4a;
                }
                QPushButton {
                    background-color: #3d3d3d;
                    color: #ffffff;
                    border: 1px solid #5d5d5d;
                    padding: 5px 15px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #5d5d5d;
                }
                QLabel {
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: #3d3d3d;
                    color: #ffffff;
                    border: 1px solid #5d5d5d;
                    padding: 3px;
                }
                QGroupBox {
                    border: 1px solid #5d5d5d;
                    margin-top: 10px;
                    color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        # Camera signals
        self.camera.connected.connect(lambda: self.camera_indicator.set_status(True))
        self.camera.disconnected.connect(lambda: self.camera_indicator.set_status(False))

        # Stage signals
        self.stage.xy_connected.connect(lambda: self.xy_stage_indicator.set_status(True))
        self.stage.xy_disconnected.connect(lambda: self.xy_stage_indicator.set_status(False))
        self.stage.z_connected.connect(lambda: self.z_stage_indicator.set_status(True))
        self.stage.z_disconnected.connect(lambda: self.z_stage_indicator.set_status(False))

        self.stage.position_changed.connect(self._update_position_display)

    def _setup_status_timer(self) -> None:
        """Setup timer for status updates."""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(100)  # Update every 100ms

    def _update_status(self) -> None:
        """Update status displays."""
        # Update FPS if camera acquiring
        if self.camera.is_acquiring:
            fps = self.camera.model.settings.fps
            self.fps_label.setText(f"FPS: {fps:.1f}")

    def _update_position_display(self, x: float, y: float, z: float) -> None:
        """Update position display.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.position_label.setText(
            f"Position: X={x:.3f} Y={y:.3f} Z={z:.3f}"
        )

    def _connect_all_devices(self) -> None:
        """Connect all devices."""
        self._logger.info("Connecting all devices...")

        # Connect camera
        if not self.camera.is_connected:
            self.camera.connect_camera()

        # Connect stages
        xy_id = self.settings.get('stages.xy.device_id')
        z_id = self.settings.get('stages.z.device_id')

        if not self.stage.is_xy_connected and xy_id:
            self.stage.connect_xy_stage(xy_id)

        if not self.stage.is_z_connected and z_id:
            self.stage.connect_z_stage(z_id)

        self.statusBar().showMessage("Connecting devices...", 2000)

    def _disconnect_all_devices(self) -> None:
        """Disconnect all devices."""
        self._logger.info("Disconnecting all devices...")

        # Stop any running scans
        if self.scan.is_scanning:
            self.scan.cancel_scan()

        # Stop camera acquisition
        if self.camera.is_acquiring:
            self.camera.stop_acquisition()

        # Disconnect devices
        self.camera.disconnect_camera()
        self.stage.disconnect_xy_stage()
        self.stage.disconnect_z_stage()

        self.statusBar().showMessage("Devices disconnected", 2000)

    def _emergency_stop(self) -> None:
        """Emergency stop all operations."""
        self._logger.warning("Emergency stop triggered")

        # Cancel scans
        if self.scan.is_scanning:
            self.scan.cancel_scan()

        # Stop stage movement
        self.stage.stop_movement()

        # Stop camera acquisition
        if self.camera.is_acquiring:
            self.camera.stop_acquisition()

        QMessageBox.warning(
            self,
            "Emergency Stop",
            "All operations stopped."
        )

    def _save_configuration(self) -> None:
        """Save configuration."""
        # TODO: Implement configuration save dialog
        self.statusBar().showMessage("Configuration saved", 2000)

    def _load_configuration(self) -> None:
        """Load configuration."""
        # TODO: Implement configuration load dialog
        self.statusBar().showMessage("Configuration loaded", 2000)

    def _export_calibration(self) -> None:
        """Export calibration data."""
        from PySide6.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Calibration",
            "",
            "JSON Files (*.json)"
        )

        if filepath:
            self.calibration.export_calibration(filepath)
            self.statusBar().showMessage(f"Calibration exported to {filepath}", 2000)

    def _import_calibration(self) -> None:
        """Import calibration data."""
        from PySide6.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Calibration",
            "",
            "JSON Files (*.json)"
        )

        if filepath:
            self.calibration.import_calibration(filepath)
            self.statusBar().showMessage(f"Calibration imported from {filepath}", 2000)

    def _show_preferences(self) -> None:
        """Show preferences dialog."""
        from kalib.views.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self._apply_theme()
            self.statusBar().showMessage("Settings updated", 2000)

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Kalib",
            "Kalib - Microscopy Control System\n\n"
            "Version 2.0.0\n\n"
            "A comprehensive system for controlling IDS cameras and PI motion stages "
            "for microscopy applications.\n\n"
            "Built with PySide6 and modern software architecture."
        )

    def closeEvent(self, event) -> None:
        """Handle window close event.

        Args:
            event: Close event
        """
        # Confirm exit if devices connected
        if self.camera.is_connected or self.stage.is_connected:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Devices are still connected. Disconnect and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._disconnect_all_devices()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
