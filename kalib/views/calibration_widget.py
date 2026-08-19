"""Calibration control widget.

Provides UI for tilt calibration, autofocus, and magnetic calibration.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
    QCheckBox, QProgressBar
)

from kalib.controllers import CalibrationController, CameraController, StageController
from config import Settings
from kalib.utils.logger import get_logger


class CalibrationWidget(QWidget):
    """Calibration control widget."""

    def __init__(self, calibration_controller: CalibrationController,
                 camera_controller: CameraController,
                 stage_controller: StageController,
                 settings: Settings):
        """Initialize calibration widget."""
        super().__init__()

        self._logger = get_logger(__name__)
        self.calibration = calibration_controller
        self.camera = camera_controller
        self.stage = stage_controller
        self.settings = settings

        self._current_corner = 0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup user interface."""
        layout = QVBoxLayout(self)

        # Tilt calibration
        tilt_group = QGroupBox("Tilt Calibration")
        tilt_layout = QVBoxLayout(tilt_group)

        # Number of corners
        corners_layout = QHBoxLayout()
        corners_layout.addWidget(QLabel("Corners:"))
        self.num_corners_spin = QSpinBox()
        self.num_corners_spin.setMinimum(4)
        self.num_corners_spin.setMaximum(9)
        self.num_corners_spin.setValue(4)
        corners_layout.addWidget(self.num_corners_spin)

        self.start_tilt_btn = QPushButton("Start Tilt Calibration")
        self.start_tilt_btn.clicked.connect(self._start_tilt_calibration)
        corners_layout.addWidget(self.start_tilt_btn)

        corners_layout.addStretch()
        tilt_layout.addLayout(corners_layout)

        # Corner measurement
        corner_layout = QHBoxLayout()
        self.corner_label = QLabel("Corner: 0/4")
        corner_layout.addWidget(self.corner_label)

        self.measure_corner_btn = QPushButton("Measure Corner (with Autofocus)")
        self.measure_corner_btn.clicked.connect(lambda: self._measure_corner(True))
        self.measure_corner_btn.setEnabled(False)
        corner_layout.addWidget(self.measure_corner_btn)

        corner_layout.addStretch()
        tilt_layout.addLayout(corner_layout)

        # Complete calibration
        complete_layout = QHBoxLayout()

        self.complete_tilt_btn = QPushButton("Complete Tilt Calibration")
        self.complete_tilt_btn.clicked.connect(self._complete_tilt_calibration)
        self.complete_tilt_btn.setEnabled(False)
        complete_layout.addWidget(self.complete_tilt_btn)

        self.tilt_enable_check = QCheckBox("Enable Tilt Correction")
        self.tilt_enable_check.toggled.connect(self._toggle_tilt_correction)
        complete_layout.addWidget(self.tilt_enable_check)

        complete_layout.addStretch()
        tilt_layout.addLayout(complete_layout)

        # Tilt status
        self.tilt_status_label = QLabel("Status: Not calibrated")
        tilt_layout.addWidget(self.tilt_status_label)

        layout.addWidget(tilt_group)

        # Autofocus
        autofocus_group = QGroupBox("Autofocus")
        autofocus_layout = QVBoxLayout(autofocus_group)

        af_params_layout = QHBoxLayout()
        af_params_layout.addWidget(QLabel("Search Range (mm):"))
        self.af_range_spin = QDoubleSpinBox()
        self.af_range_spin.setDecimals(3)
        self.af_range_spin.setRange(0.1, 5.0)
        self.af_range_spin.setValue(1.0)
        af_params_layout.addWidget(self.af_range_spin)

        af_params_layout.addWidget(QLabel("Steps:"))
        self.af_steps_spin = QSpinBox()
        self.af_steps_spin.setRange(5, 50)
        self.af_steps_spin.setValue(20)
        af_params_layout.addWidget(self.af_steps_spin)

        af_params_layout.addStretch()
        autofocus_layout.addLayout(af_params_layout)

        af_buttons_layout = QHBoxLayout()

        self.quick_af_btn = QPushButton("Quick Autofocus")
        self.quick_af_btn.clicked.connect(self._quick_autofocus)
        af_buttons_layout.addWidget(self.quick_af_btn)

        self.iterative_af_btn = QPushButton("Iterative Autofocus")
        self.iterative_af_btn.clicked.connect(self._iterative_autofocus)
        af_buttons_layout.addWidget(self.iterative_af_btn)

        af_buttons_layout.addStretch()
        autofocus_layout.addLayout(af_buttons_layout)

        # Autofocus progress
        self.af_progress = QProgressBar()
        autofocus_layout.addWidget(self.af_progress)

        # Autofocus result
        self.af_result_label = QLabel("Best Focus: N/A")
        autofocus_layout.addWidget(self.af_result_label)

        layout.addWidget(autofocus_group)

        # Calibration data
        data_group = QGroupBox("Calibration Data")
        data_layout = QVBoxLayout(data_group)

        io_layout = QHBoxLayout()

        self.export_btn = QPushButton("Export Calibration")
        self.export_btn.clicked.connect(self._export_calibration)
        io_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import Calibration")
        self.import_btn.clicked.connect(self._import_calibration)
        io_layout.addWidget(self.import_btn)

        io_layout.addStretch()
        data_layout.addLayout(io_layout)

        layout.addWidget(data_group)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        self.calibration.calibration_started.connect(self._on_calibration_started)
        self.calibration.calibration_completed.connect(self._on_calibration_completed)
        self.calibration.corner_measured.connect(self._on_corner_measured)
        self.calibration.focus_found.connect(self._on_focus_found)
        self.calibration.progress_updated.connect(self._on_progress_updated)

    def _start_tilt_calibration(self) -> None:
        """Start tilt calibration."""
        num_corners = self.num_corners_spin.value()
        self.calibration.start_tilt_calibration(num_corners)

    def _measure_corner(self, autofocus: bool) -> None:
        """Measure current corner."""
        success = self.calibration.measure_tilt_corner(self._current_corner, autofocus)
        if success:
            self._current_corner += 1

    def _complete_tilt_calibration(self) -> None:
        """Complete tilt calibration."""
        self.calibration.complete_tilt_calibration()

    def _toggle_tilt_correction(self, enabled: bool) -> None:
        """Toggle tilt correction."""
        self.calibration.enable_tilt_correction(enabled)

    def _quick_autofocus(self) -> None:
        """Perform quick autofocus."""
        num_steps = self.af_steps_spin.value()
        search_range = self.af_range_spin.value()
        self.calibration.quick_autofocus(num_steps, search_range)

    def _iterative_autofocus(self) -> None:
        """Perform iterative autofocus."""
        search_range = self.af_range_spin.value()
        self.calibration.autofocus_at_position(search_range=search_range)

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

    def _on_calibration_started(self, cal_type: str) -> None:
        """Handle calibration start."""
        if cal_type == "tilt":
            self._current_corner = 0
            num_corners = self.num_corners_spin.value()
            self.corner_label.setText(f"Corner: 0/{num_corners}")
            self.measure_corner_btn.setEnabled(True)
            self.start_tilt_btn.setEnabled(False)
            self.tilt_status_label.setText("Status: Measuring corners...")

    def _on_calibration_completed(self, cal_type: str) -> None:
        """Handle calibration completion."""
        if cal_type == "tilt":
            self.measure_corner_btn.setEnabled(False)
            self.complete_tilt_btn.setEnabled(False)
            self.start_tilt_btn.setEnabled(True)

            # Get tilt angles
            if self.calibration.is_tilt_calibrated:
                tilt_x, tilt_y = self.calibration.model.tilt_calibration.tilt_angles
                self.tilt_status_label.setText(
                    f"Status: Calibrated (Tilt X: {tilt_x:.3f}°, Y: {tilt_y:.3f}°)"
                )
                self.tilt_enable_check.setEnabled(True)

    def _on_corner_measured(self, current: int, total: int) -> None:
        """Handle corner measurement."""
        self.corner_label.setText(f"Corner: {current}/{total}")

        if current >= total:
            self.measure_corner_btn.setEnabled(False)
            self.complete_tilt_btn.setEnabled(True)

    def _on_focus_found(self, z_position: float) -> None:
        """Handle focus found."""
        self.af_result_label.setText(f"Best Focus: Z={z_position:.3f} mm")

    def _on_progress_updated(self, current: int, total: int) -> None:
        """Handle progress update."""
        self.af_progress.setMaximum(total)
        self.af_progress.setValue(current)
