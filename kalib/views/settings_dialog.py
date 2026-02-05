"""Settings dialog for application preferences."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QTabWidget, QWidget, QSpinBox
)

from config import Settings


class SettingsDialog(QDialog):
    """Settings dialog for configuring application preferences."""

    def __init__(self, settings: Settings, parent=None):
        """Initialize settings dialog.

        Args:
            settings: Application settings
            parent: Parent widget
        """
        super().__init__(parent)

        self.settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Setup user interface."""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)

        # Tabs
        tabs = QTabWidget()

        # General tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        # Theme
        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout(theme_group)

        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        theme_layout.addWidget(self.theme_combo)

        theme_layout.addStretch()
        general_layout.addWidget(theme_group)

        general_layout.addStretch()
        tabs.addTab(general_tab, "General")

        # Camera tab
        camera_tab = QWidget()
        camera_layout = QVBoxLayout(camera_tab)

        cam_group = QGroupBox("Camera Settings")
        cam_form_layout = QVBoxLayout(cam_group)

        # Default exposure
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Default Exposure (µs):"))
        self.default_exposure = QSpinBox()
        self.default_exposure.setRange(100, 100000)
        exp_layout.addWidget(self.default_exposure)
        exp_layout.addStretch()
        cam_form_layout.addLayout(exp_layout)

        # FPS limit
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS Limit:"))
        self.fps_limit = QSpinBox()
        self.fps_limit.setRange(1, 120)
        fps_layout.addWidget(self.fps_limit)
        fps_layout.addStretch()
        cam_form_layout.addLayout(fps_layout)

        camera_layout.addWidget(cam_group)
        camera_layout.addStretch()
        tabs.addTab(camera_tab, "Camera")

        # Stage tab
        stage_tab = QWidget()
        stage_layout = QVBoxLayout(stage_tab)

        # XY Stage
        xy_group = QGroupBox("XY Stage")
        xy_layout = QVBoxLayout(xy_group)

        xy_id_layout = QHBoxLayout()
        xy_id_layout.addWidget(QLabel("Device ID:"))
        self.xy_device_id = QLineEdit()
        xy_id_layout.addWidget(self.xy_device_id)
        xy_layout.addLayout(xy_id_layout)

        stage_layout.addWidget(xy_group)

        # Z Stage
        z_group = QGroupBox("Z Stage")
        z_layout = QVBoxLayout(z_group)

        z_id_layout = QHBoxLayout()
        z_id_layout.addWidget(QLabel("Device ID:"))
        self.z_device_id = QLineEdit()
        z_id_layout.addWidget(self.z_device_id)
        z_layout.addLayout(z_id_layout)

        stage_layout.addWidget(z_group)

        stage_layout.addStretch()
        tabs.addTab(stage_tab, "Stages")

        # Paths tab
        paths_tab = QWidget()
        paths_layout = QVBoxLayout(paths_tab)

        paths_group = QGroupBox("File Paths")
        paths_form_layout = QVBoxLayout(paths_group)

        # Data directory
        data_layout = QHBoxLayout()
        data_layout.addWidget(QLabel("Data Directory:"))
        self.data_dir = QLineEdit()
        data_layout.addWidget(self.data_dir)
        paths_form_layout.addLayout(data_layout)

        # Logs directory
        logs_layout = QHBoxLayout()
        logs_layout.addWidget(QLabel("Logs Directory:"))
        self.logs_dir = QLineEdit()
        logs_layout.addWidget(self.logs_dir)
        paths_form_layout.addLayout(logs_layout)

        paths_layout.addWidget(paths_group)
        paths_layout.addStretch()
        tabs.addTab(paths_tab, "Paths")

        layout.addWidget(tabs)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        """Load settings into widgets."""
        # General
        self.theme_combo.setCurrentText(self.settings.get('ui.theme', 'dark'))

        # Camera
        self.default_exposure.setValue(
            self.settings.get('camera.default_exposure', 15000)
        )
        self.fps_limit.setValue(
            self.settings.get('camera.fps_limit', 30)
        )

        # Stages
        self.xy_device_id.setText(
            self.settings.get('stages.xy.device_id', '')
        )
        self.z_device_id.setText(
            self.settings.get('stages.z.device_id', '')
        )

        # Paths
        self.data_dir.setText(
            self.settings.get('paths.data_dir', './data')
        )
        self.logs_dir.setText(
            self.settings.get('paths.logs_dir', './logs')
        )

    def _save_and_accept(self) -> None:
        """Save settings and accept dialog."""
        # General
        self.settings.set('ui.theme', self.theme_combo.currentText())

        # Camera
        self.settings.set('camera.default_exposure', self.default_exposure.value())
        self.settings.set('camera.fps_limit', self.fps_limit.value())

        # Stages
        self.settings.set('stages.xy.device_id', self.xy_device_id.text())
        self.settings.set('stages.z.device_id', self.z_device_id.text())

        # Paths
        self.settings.set('paths.data_dir', self.data_dir.text())
        self.settings.set('paths.logs_dir', self.logs_dir.text())

        # Save to file (if needed)
        # from config import save_config
        # save_config(self.settings, 'config/config.yaml')

        self.accept()
