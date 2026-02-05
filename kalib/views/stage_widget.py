"""Stage control widget.

Provides UI for XY and Z stage control and positioning.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QGridLayout
)
from PySide6.QtCore import Qt

from kalib.controllers import StageController
from config import Settings
from kalib.utils.logger import get_logger


class StageWidget(QWidget):
    """Stage control widget.

    Provides controls for XY and Z stage connection and positioning.
    """

    def __init__(self, stage_controller: StageController, settings: Settings):
        """Initialize stage widget.

        Args:
            stage_controller: Stage controller
            settings: Application settings
        """
        super().__init__()

        self._logger = get_logger(__name__)
        self.stage = stage_controller
        self.settings = settings

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup user interface."""
        layout = QVBoxLayout(self)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self.connect_xy_btn = QPushButton("Connect XY Stage")
        self.connect_xy_btn.clicked.connect(self._toggle_xy_connection)
        conn_layout.addWidget(self.connect_xy_btn)

        self.connect_z_btn = QPushButton("Connect Z Stage")
        self.connect_z_btn.clicked.connect(self._toggle_z_connection)
        conn_layout.addWidget(self.connect_z_btn)

        conn_layout.addStretch()

        layout.addWidget(conn_group)

        # XY Stage control
        xy_group = QGroupBox("XY Stage Control")
        xy_layout = QVBoxLayout(xy_group)

        # Current position display
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("Current Position:"))
        self.xy_position_label = QLabel("X: 0.000 mm, Y: 0.000 mm")
        self.xy_position_label.setStyleSheet("font-weight: bold;")
        pos_layout.addWidget(self.xy_position_label)
        pos_layout.addStretch()
        xy_layout.addLayout(pos_layout)

        # Step size
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step Size (mm):"))
        self.step_size_spin = QDoubleSpinBox()
        self.step_size_spin.setDecimals(3)
        self.step_size_spin.setMinimum(0.001)
        self.step_size_spin.setMaximum(10.0)
        self.step_size_spin.setValue(0.1)
        self.step_size_spin.setSingleStep(0.01)
        step_layout.addWidget(self.step_size_spin)
        step_layout.addStretch()
        xy_layout.addLayout(step_layout)

        # Movement buttons
        move_grid = QGridLayout()

        # Y+
        self.y_up_btn = QPushButton("Y+")
        self.y_up_btn.clicked.connect(lambda: self._move_relative(dy=self.step_size_spin.value()))
        move_grid.addWidget(self.y_up_btn, 0, 1)

        # X-, X+, Y-
        self.x_down_btn = QPushButton("X-")
        self.x_down_btn.clicked.connect(lambda: self._move_relative(dx=-self.step_size_spin.value()))
        move_grid.addWidget(self.x_down_btn, 1, 0)

        self.home_btn = QPushButton("Stop")
        self.home_btn.clicked.connect(self._stop_movement)
        move_grid.addWidget(self.home_btn, 1, 1)

        self.x_up_btn = QPushButton("X+")
        self.x_up_btn.clicked.connect(lambda: self._move_relative(dx=self.step_size_spin.value()))
        move_grid.addWidget(self.x_up_btn, 1, 2)

        self.y_down_btn = QPushButton("Y-")
        self.y_down_btn.clicked.connect(lambda: self._move_relative(dy=-self.step_size_spin.value()))
        move_grid.addWidget(self.y_down_btn, 2, 1)

        xy_layout.addLayout(move_grid)

        # Absolute positioning
        abs_layout = QHBoxLayout()
        abs_layout.addWidget(QLabel("Go to X:"))
        self.target_x_spin = QDoubleSpinBox()
        self.target_x_spin.setDecimals(3)
        self.target_x_spin.setMinimum(self.settings.get('stages.xy.x_range[0]', 0))
        self.target_x_spin.setMaximum(self.settings.get('stages.xy.x_range[1]', 100))
        abs_layout.addWidget(self.target_x_spin)

        abs_layout.addWidget(QLabel("Y:"))
        self.target_y_spin = QDoubleSpinBox()
        self.target_y_spin.setDecimals(3)
        self.target_y_spin.setMinimum(self.settings.get('stages.xy.y_range[0]', 0))
        self.target_y_spin.setMaximum(self.settings.get('stages.xy.y_range[1]', 100))
        abs_layout.addWidget(self.target_y_spin)

        self.go_xy_btn = QPushButton("Go")
        self.go_xy_btn.clicked.connect(self._move_absolute_xy)
        abs_layout.addWidget(self.go_xy_btn)

        abs_layout.addStretch()
        xy_layout.addLayout(abs_layout)

        layout.addWidget(xy_group)

        # Z Stage control
        z_group = QGroupBox("Z Stage Control")
        z_layout = QVBoxLayout(z_group)

        # Current Z position
        z_pos_layout = QHBoxLayout()
        z_pos_layout.addWidget(QLabel("Current Z Position:"))
        self.z_position_label = QLabel("0.000 mm")
        self.z_position_label.setStyleSheet("font-weight: bold;")
        z_pos_layout.addWidget(self.z_position_label)
        z_pos_layout.addStretch()
        z_layout.addLayout(z_pos_layout)

        # Z step size
        z_step_layout = QHBoxLayout()
        z_step_layout.addWidget(QLabel("Z Step Size (mm):"))
        self.z_step_size_spin = QDoubleSpinBox()
        self.z_step_size_spin.setDecimals(3)
        self.z_step_size_spin.setMinimum(0.001)
        self.z_step_size_spin.setMaximum(1.0)
        self.z_step_size_spin.setValue(0.01)
        self.z_step_size_spin.setSingleStep(0.001)
        z_step_layout.addWidget(self.z_step_size_spin)
        z_step_layout.addStretch()
        z_layout.addLayout(z_step_layout)

        # Z movement buttons
        z_move_layout = QHBoxLayout()

        self.z_up_btn = QPushButton("Z+ (Up)")
        self.z_up_btn.clicked.connect(lambda: self._move_relative(dz=self.z_step_size_spin.value()))
        z_move_layout.addWidget(self.z_up_btn)

        self.z_down_btn = QPushButton("Z- (Down)")
        self.z_down_btn.clicked.connect(lambda: self._move_relative(dz=-self.z_step_size_spin.value()))
        z_move_layout.addWidget(self.z_down_btn)

        z_move_layout.addStretch()
        z_layout.addLayout(z_move_layout)

        # Z absolute positioning
        z_abs_layout = QHBoxLayout()
        z_abs_layout.addWidget(QLabel("Go to Z:"))
        self.target_z_spin = QDoubleSpinBox()
        self.target_z_spin.setDecimals(3)
        self.target_z_spin.setMinimum(self.settings.get('stages.z.z_range[0]', 0))
        self.target_z_spin.setMaximum(self.settings.get('stages.z.z_range[1]', 10))
        z_abs_layout.addWidget(self.target_z_spin)

        self.go_z_btn = QPushButton("Go")
        self.go_z_btn.clicked.connect(self._move_absolute_z)
        z_abs_layout.addWidget(self.go_z_btn)

        z_abs_layout.addStretch()
        z_layout.addLayout(z_abs_layout)

        layout.addWidget(z_group)

        layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        self.stage.xy_connected.connect(self._on_xy_connected)
        self.stage.xy_disconnected.connect(self._on_xy_disconnected)
        self.stage.z_connected.connect(self._on_z_connected)
        self.stage.z_disconnected.connect(self._on_z_disconnected)
        self.stage.position_changed.connect(self._on_position_changed)

    def _toggle_xy_connection(self) -> None:
        """Toggle XY stage connection."""
        if self.stage.is_xy_connected:
            self.stage.disconnect_xy_stage()
        else:
            device_id = self.settings.get('stages.xy.device_id')
            self.stage.connect_xy_stage(device_id)

    def _toggle_z_connection(self) -> None:
        """Toggle Z stage connection."""
        if self.stage.is_z_connected:
            self.stage.disconnect_z_stage()
        else:
            device_id = self.settings.get('stages.z.device_id')
            self.stage.connect_z_stage(device_id)

    def _move_relative(self, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> None:
        """Move relative to current position.

        Args:
            dx: Relative X movement
            dy: Relative Y movement
            dz: Relative Z movement
        """
        self.stage.move_relative(dx=dx, dy=dy, dz=dz, wait=False)

    def _move_absolute_xy(self) -> None:
        """Move to absolute XY position."""
        x = self.target_x_spin.value()
        y = self.target_y_spin.value()
        self.stage.move_absolute(x=x, y=y, wait=False)

    def _move_absolute_z(self) -> None:
        """Move to absolute Z position."""
        z = self.target_z_spin.value()
        self.stage.move_absolute(z=z, wait=False)

    def _stop_movement(self) -> None:
        """Stop stage movement."""
        self.stage.stop_movement()

    def _on_xy_connected(self) -> None:
        """Handle XY stage connection."""
        self.connect_xy_btn.setText("Disconnect XY Stage")
        self._logger.info("XY stage connected")

    def _on_xy_disconnected(self) -> None:
        """Handle XY stage disconnection."""
        self.connect_xy_btn.setText("Connect XY Stage")
        self._logger.info("XY stage disconnected")

    def _on_z_connected(self) -> None:
        """Handle Z stage connection."""
        self.connect_z_btn.setText("Disconnect Z Stage")
        self._logger.info("Z stage connected")

    def _on_z_disconnected(self) -> None:
        """Handle Z stage disconnection."""
        self.connect_z_btn.setText("Connect Z Stage")
        self._logger.info("Z stage disconnected")

    def _on_position_changed(self, x: float, y: float, z: float) -> None:
        """Handle position change.

        Args:
            x: X position
            y: Y position
            z: Z position
        """
        self.xy_position_label.setText(f"X: {x:.3f} mm, Y: {y:.3f} mm")
        self.z_position_label.setText(f"{z:.3f} mm")

        # Update spin boxes
        self.target_x_spin.setValue(x)
        self.target_y_spin.setValue(y)
        self.target_z_spin.setValue(z)
