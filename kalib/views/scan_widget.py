"""Scan control widget.

Provides UI for configuring and running XY and Z-stack scans.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox,
    QProgressBar, QComboBox, QLineEdit, QFileDialog,
    QCheckBox
)

from kalib.controllers import ScanController, CameraController, StageController
from kalib.models import XYScanParameters, ZStackParameters
from config import Settings
from kalib.utils.logger import get_logger


class ScanWidget(QWidget):
    """Scan control widget."""

    def __init__(self, scan_controller: ScanController,
                 camera_controller: CameraController,
                 stage_controller: StageController,
                 settings: Settings):
        """Initialize scan widget."""
        super().__init__()

        self._logger = get_logger(__name__)
        self.scan = scan_controller
        self.camera = camera_controller
        self.stage = stage_controller
        self.settings = settings

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup user interface."""
        layout = QVBoxLayout(self)

        # Scan type selection
        type_group = QGroupBox("Scan Type")
        type_layout = QHBoxLayout(type_group)

        type_layout.addWidget(QLabel("Scan Type:"))
        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(["XY Scan", "Z-Stack"])
        self.scan_type_combo.currentTextChanged.connect(self._on_scan_type_changed)
        type_layout.addWidget(self.scan_type_combo)

        type_layout.addStretch()

        layout.addWidget(type_group)

        # XY Scan parameters
        self.xy_group = QGroupBox("XY Scan Parameters")
        xy_layout = QVBoxLayout(self.xy_group)

        # Start position
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start X:"))
        self.start_x_spin = QDoubleSpinBox()
        self.start_x_spin.setDecimals(3)
        self.start_x_spin.setRange(0, 100)
        start_layout.addWidget(self.start_x_spin)

        start_layout.addWidget(QLabel("Y:"))
        self.start_y_spin = QDoubleSpinBox()
        self.start_y_spin.setDecimals(3)
        self.start_y_spin.setRange(0, 100)
        start_layout.addWidget(self.start_y_spin)

        self.set_current_start_btn = QPushButton("Use Current")
        self.set_current_start_btn.clicked.connect(self._set_current_as_start)
        start_layout.addWidget(self.set_current_start_btn)

        start_layout.addStretch()
        xy_layout.addLayout(start_layout)

        # End position
        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End X:"))
        self.end_x_spin = QDoubleSpinBox()
        self.end_x_spin.setDecimals(3)
        self.end_x_spin.setRange(0, 100)
        self.end_x_spin.setValue(10)
        end_layout.addWidget(self.end_x_spin)

        end_layout.addWidget(QLabel("Y:"))
        self.end_y_spin = QDoubleSpinBox()
        self.end_y_spin.setDecimals(3)
        self.end_y_spin.setRange(0, 100)
        self.end_y_spin.setValue(10)
        end_layout.addWidget(self.end_y_spin)

        self.set_current_end_btn = QPushButton("Use Current")
        self.set_current_end_btn.clicked.connect(self._set_current_as_end)
        end_layout.addWidget(self.set_current_end_btn)

        end_layout.addStretch()
        xy_layout.addLayout(end_layout)

        # Step size
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step X:"))
        self.step_x_spin = QDoubleSpinBox()
        self.step_x_spin.setDecimals(3)
        self.step_x_spin.setRange(0.001, 10)
        self.step_x_spin.setValue(1.0)
        step_layout.addWidget(self.step_x_spin)

        step_layout.addWidget(QLabel("Y:"))
        self.step_y_spin = QDoubleSpinBox()
        self.step_y_spin.setDecimals(3)
        self.step_y_spin.setRange(0.001, 10)
        self.step_y_spin.setValue(1.0)
        step_layout.addWidget(self.step_y_spin)

        step_layout.addStretch()
        xy_layout.addLayout(step_layout)

        layout.addWidget(self.xy_group)

        # Z-Stack parameters
        self.z_group = QGroupBox("Z-Stack Parameters")
        z_layout = QVBoxLayout(self.z_group)

        z_start_layout = QHBoxLayout()
        z_start_layout.addWidget(QLabel("Start Z:"))
        self.start_z_spin = QDoubleSpinBox()
        self.start_z_spin.setDecimals(3)
        self.start_z_spin.setRange(0, 10)
        z_start_layout.addWidget(self.start_z_spin)

        self.set_current_z_start_btn = QPushButton("Use Current")
        self.set_current_z_start_btn.clicked.connect(self._set_current_z_as_start)
        z_start_layout.addWidget(self.set_current_z_start_btn)

        z_start_layout.addStretch()
        z_layout.addLayout(z_start_layout)

        z_end_layout = QHBoxLayout()
        z_end_layout.addWidget(QLabel("End Z:"))
        self.end_z_spin = QDoubleSpinBox()
        self.end_z_spin.setDecimals(3)
        self.end_z_spin.setRange(0, 10)
        self.end_z_spin.setValue(1.0)
        z_end_layout.addWidget(self.end_z_spin)

        self.set_current_z_end_btn = QPushButton("Use Current")
        self.set_current_z_end_btn.clicked.connect(self._set_current_z_as_end)
        z_end_layout.addWidget(self.set_current_z_end_btn)

        z_end_layout.addStretch()
        z_layout.addLayout(z_end_layout)

        z_step_layout = QHBoxLayout()
        z_step_layout.addWidget(QLabel("Step Z:"))
        self.step_z_spin = QDoubleSpinBox()
        self.step_z_spin.setDecimals(3)
        self.step_z_spin.setRange(0.001, 1.0)
        self.step_z_spin.setValue(0.1)
        z_step_layout.addWidget(self.step_z_spin)

        z_step_layout.addStretch()
        z_layout.addLayout(z_step_layout)

        self.z_group.setVisible(False)
        layout.addWidget(self.z_group)

        # Save options
        save_group = QGroupBox("Save Options")
        save_layout = QVBoxLayout(save_group)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save Path:"))
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setText("./data/scan")
        path_layout.addWidget(self.save_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(browse_btn)

        save_layout.addLayout(path_layout)

        self.save_frames_check = QCheckBox("Save Individual Frames")
        self.save_frames_check.setChecked(True)
        save_layout.addWidget(self.save_frames_check)

        layout.addWidget(save_group)

        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        progress_info_layout = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        progress_info_layout.addWidget(self.progress_label)

        self.time_label = QLabel("Time: 0s")
        progress_info_layout.addWidget(self.time_label)

        progress_info_layout.addStretch()
        progress_layout.addLayout(progress_info_layout)

        layout.addWidget(progress_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Scan")
        self.start_btn.clicked.connect(self._start_scan)
        control_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._pause_scan)
        self.pause_btn.setEnabled(False)
        control_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_scan)
        self.cancel_btn.setEnabled(False)
        control_layout.addWidget(self.cancel_btn)

        control_layout.addStretch()

        layout.addLayout(control_layout)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        self.scan.scan_started.connect(self._on_scan_started)
        self.scan.scan_completed.connect(self._on_scan_completed)
        self.scan.scan_cancelled.connect(self._on_scan_cancelled)
        self.scan.progress_updated.connect(self._on_progress_updated)

    def _on_scan_type_changed(self, scan_type: str) -> None:
        """Handle scan type change."""
        if scan_type == "XY Scan":
            self.xy_group.setVisible(True)
            self.z_group.setVisible(False)
        else:  # Z-Stack
            self.xy_group.setVisible(False)
            self.z_group.setVisible(True)

    def _set_current_as_start(self) -> None:
        """Set current position as scan start."""
        x, y, z = self.stage.get_position()
        self.start_x_spin.setValue(x)
        self.start_y_spin.setValue(y)

    def _set_current_as_end(self) -> None:
        """Set current position as scan end."""
        x, y, z = self.stage.get_position()
        self.end_x_spin.setValue(x)
        self.end_y_spin.setValue(y)

    def _set_current_z_as_start(self) -> None:
        """Set current Z as start."""
        x, y, z = self.stage.get_position()
        self.start_z_spin.setValue(z)

    def _set_current_z_as_end(self) -> None:
        """Set current Z as end."""
        x, y, z = self.stage.get_position()
        self.end_z_spin.setValue(z)

    def _browse_save_path(self) -> None:
        """Browse for save directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if path:
            self.save_path_edit.setText(path)

    def _start_scan(self) -> None:
        """Start configured scan."""
        scan_type = self.scan_type_combo.currentText()

        if scan_type == "XY Scan":
            params = XYScanParameters(
                start_x=self.start_x_spin.value(),
                start_y=self.start_y_spin.value(),
                end_x=self.end_x_spin.value(),
                end_y=self.end_y_spin.value(),
                step_x=self.step_x_spin.value(),
                step_y=self.step_y_spin.value()
            )
            self.scan.configure_xy_scan(params)
        else:
            params = ZStackParameters(
                start_z=self.start_z_spin.value(),
                end_z=self.end_z_spin.value(),
                step_z=self.step_z_spin.value()
            )
            self.scan.configure_z_stack(params)

        # Set save options
        self.scan.model.save_individual_frames = self.save_frames_check.isChecked()
        save_path = self.save_path_edit.text() if self.save_frames_check.isChecked() else None

        self.scan.start_scan(save_path=save_path)

    def _pause_scan(self) -> None:
        """Pause/resume scan."""
        if self.scan.model.state.value == "running":
            self.scan.pause_scan()
            self.pause_btn.setText("Resume")
        else:
            self.scan.resume_scan()
            self.pause_btn.setText("Pause")

    def _cancel_scan(self) -> None:
        """Cancel scan."""
        self.scan.cancel_scan()

    def _on_scan_started(self, scan_type: str) -> None:
        """Handle scan start."""
        self.progress_label.setText(f"Running {scan_type}...")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self._logger.info(f"Scan started: {scan_type}")

    def _on_scan_completed(self) -> None:
        """Handle scan completion."""
        self.progress_label.setText("Scan completed")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self._logger.info("Scan completed")

    def _on_scan_cancelled(self) -> None:
        """Handle scan cancellation."""
        self.progress_label.setText("Scan cancelled")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self._logger.info("Scan cancelled")

    def _on_progress_updated(self, current: int, total: int) -> None:
        """Handle progress update."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        percent = (current / total * 100) if total > 0 else 0
        self.progress_label.setText(f"Progress: {current}/{total} ({percent:.1f}%)")
