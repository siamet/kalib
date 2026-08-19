"""Camera control widget.

Provides UI for camera connection, settings, and live view.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QSlider, QLineEdit,
    QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap

from kalib.controllers import CameraController
from config import Settings
from kalib.utils.logger import get_logger


class CameraWidget(QWidget):
    """Camera control widget.

    Provides controls for camera connection, exposure, gain, FPS,
    and live camera feed display.
    """

    def __init__(self, camera_controller: CameraController, settings: Settings):
        """Initialize camera widget.

        Args:
            camera_controller: Camera controller
            settings: Application settings
        """
        super().__init__()

        self._logger = get_logger(__name__)
        self.camera = camera_controller
        self.settings = settings

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Setup user interface."""
        layout = QVBoxLayout(self)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self.connect_btn = QPushButton("Connect Camera")
        self.connect_btn.clicked.connect(self._toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        self.acquisition_btn = QPushButton("Start Acquisition")
        self.acquisition_btn.clicked.connect(self._toggle_acquisition)
        self.acquisition_btn.setEnabled(False)
        conn_layout.addWidget(self.acquisition_btn)

        self.capture_btn = QPushButton("Capture Image")
        self.capture_btn.clicked.connect(self._capture_image)
        self.capture_btn.setEnabled(False)
        conn_layout.addWidget(self.capture_btn)

        conn_layout.addStretch()

        layout.addWidget(conn_group)

        # Camera settings group
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Exposure
        exp_layout = QHBoxLayout()
        exp_layout.addWidget(QLabel("Exposure (µs):"))
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setMinimum(
            self.settings.get('camera.exposure_time_min', 100)
        )
        self.exposure_slider.setMaximum(
            self.settings.get('camera.exposure_time_max', 100000)
        )
        self.exposure_slider.setValue(
            self.settings.get('camera.default_exposure', 15000)
        )
        self.exposure_slider.valueChanged.connect(self._on_exposure_changed)
        exp_layout.addWidget(self.exposure_slider)

        self.exposure_value = QLineEdit(str(self.exposure_slider.value()))
        self.exposure_value.setMaximumWidth(80)
        self.exposure_value.returnPressed.connect(self._on_exposure_entered)
        exp_layout.addWidget(self.exposure_value)

        settings_layout.addLayout(exp_layout)

        # Gain
        gain_layout = QHBoxLayout()
        gain_layout.addWidget(QLabel("Gain:"))
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setMinimum(10)  # 1.0 * 10
        self.gain_slider.setMaximum(100)  # 10.0 * 10
        self.gain_slider.setValue(10)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        gain_layout.addWidget(self.gain_slider)

        self.gain_value = QLineEdit("1.0")
        self.gain_value.setMaximumWidth(60)
        self.gain_value.returnPressed.connect(self._on_gain_entered)
        gain_layout.addWidget(self.gain_value)

        settings_layout.addLayout(gain_layout)

        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setMinimum(1)
        self.fps_slider.setMaximum(self.settings.get('camera.fps_limit', 30))
        self.fps_slider.setValue(30)
        self.fps_slider.valueChanged.connect(self._on_fps_changed)
        fps_layout.addWidget(self.fps_slider)

        self.fps_value = QLineEdit("30")
        self.fps_value.setMaximumWidth(60)
        self.fps_value.returnPressed.connect(self._on_fps_entered)
        fps_layout.addWidget(self.fps_value)

        settings_layout.addLayout(fps_layout)

        layout.addWidget(settings_group)

        # Display options group
        display_group = QGroupBox("Display Options")
        display_layout = QHBoxLayout(display_group)

        self.live_view_check = QCheckBox("Live View")
        self.live_view_check.setChecked(True)
        display_layout.addWidget(self.live_view_check)

        display_layout.addWidget(QLabel("Refresh Rate (ms):"))
        self.refresh_spin = QSpinBox()
        self.refresh_spin.setMinimum(10)
        self.refresh_spin.setMaximum(1000)
        self.refresh_spin.setValue(33)  # ~30fps
        display_layout.addWidget(self.refresh_spin)

        display_layout.addStretch()

        layout.addWidget(display_group)

        # Live view display
        view_group = QGroupBox("Live View")
        view_layout = QVBoxLayout(view_group)

        self.image_label = QLabel("No image")
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #5d5d5d; background-color: #1a1a1a;")
        view_layout.addWidget(self.image_label)

        # Image stats
        stats_layout = QHBoxLayout()
        self.frame_count_label = QLabel("Frames: 0")
        stats_layout.addWidget(self.frame_count_label)

        self.error_count_label = QLabel("Errors: 0")
        stats_layout.addWidget(self.error_count_label)

        self.current_exposure_label = QLabel("Current Exposure: 0 µs")
        stats_layout.addWidget(self.current_exposure_label)

        stats_layout.addStretch()

        view_layout.addLayout(stats_layout)

        layout.addWidget(view_group)

        # Live view timer
        self.live_view_timer = QTimer()
        self.live_view_timer.timeout.connect(self._update_live_view)

    def _connect_signals(self) -> None:
        """Connect controller signals."""
        self.camera.connected.connect(self._on_camera_connected)
        self.camera.disconnected.connect(self._on_camera_disconnected)
        self.camera.acquisition_started.connect(self._on_acquisition_started)
        self.camera.acquisition_stopped.connect(self._on_acquisition_stopped)
        self.camera.image_captured.connect(self._on_image_captured)
        self.camera.error_occurred.connect(self._on_error)

    def _toggle_connection(self) -> None:
        """Toggle camera connection."""
        if self.camera.is_connected:
            self.camera.disconnect_camera()
        else:
            self.camera.connect_camera()

    def _toggle_acquisition(self) -> None:
        """Toggle image acquisition."""
        if self.camera.is_acquiring:
            self.camera.stop_acquisition()
            self.live_view_timer.stop()
        else:
            if self.camera.start_acquisition():
                interval = self.refresh_spin.value()
                self.live_view_timer.start(interval)

    def _capture_image(self) -> None:
        """Capture single image."""
        self.camera.capture_image()

    def _on_exposure_changed(self, value: int) -> None:
        """Handle exposure slider change.

        Args:
            value: Exposure value in microseconds
        """
        self.exposure_value.setText(str(value))
        if self.camera.is_connected:
            self.camera.set_exposure_time(float(value))

    def _on_exposure_entered(self) -> None:
        """Handle exposure text entry."""
        try:
            value = int(self.exposure_value.text())
            self.exposure_slider.setValue(value)
        except ValueError:
            pass

    def _on_gain_changed(self, value: int) -> None:
        """Handle gain slider change.

        Args:
            value: Gain value * 10
        """
        gain = value / 10.0
        self.gain_value.setText(f"{gain:.1f}")
        if self.camera.is_connected:
            self.camera.set_gain(gain)

    def _on_gain_entered(self) -> None:
        """Handle gain text entry."""
        try:
            gain = float(self.gain_value.text())
            self.gain_slider.setValue(int(gain * 10))
        except ValueError:
            pass

    def _on_fps_changed(self, value: int) -> None:
        """Handle FPS slider change.

        Args:
            value: FPS value
        """
        self.fps_value.setText(str(value))
        if self.camera.is_connected:
            self.camera.set_fps(float(value))

    def _on_fps_entered(self) -> None:
        """Handle FPS text entry."""
        try:
            fps = int(self.fps_value.text())
            self.fps_slider.setValue(fps)
        except ValueError:
            pass

    def _on_camera_connected(self) -> None:
        """Handle camera connection."""
        self.connect_btn.setText("Disconnect Camera")
        self.acquisition_btn.setEnabled(True)
        self._logger.info("Camera connected")

    def _on_camera_disconnected(self) -> None:
        """Handle camera disconnection."""
        self.connect_btn.setText("Connect Camera")
        self.acquisition_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.live_view_timer.stop()
        self._logger.info("Camera disconnected")

    def _on_acquisition_started(self) -> None:
        """Handle acquisition start."""
        self.acquisition_btn.setText("Stop Acquisition")
        self.capture_btn.setEnabled(True)
        self._logger.info("Acquisition started")

    def _on_acquisition_stopped(self) -> None:
        """Handle acquisition stop."""
        self.acquisition_btn.setText("Start Acquisition")
        self.capture_btn.setEnabled(False)
        self._logger.info("Acquisition stopped")

    def _on_image_captured(self, image) -> None:
        """Handle image capture.

        Args:
            image: Captured image
        """
        # Update stats
        self.frame_count_label.setText(f"Frames: {self.camera.model.state.frame_count}")
        self.error_count_label.setText(f"Errors: {self.camera.model.state.error_count}")

        # Get current settings
        settings = self.camera.get_current_settings()
        if 'exposure_time' in settings:
            self.current_exposure_label.setText(
                f"Current Exposure: {settings['exposure_time']:.0f} µs"
            )

    def _update_live_view(self) -> None:
        """Update live view display."""
        if not self.live_view_check.isChecked():
            return

        image = self.camera.model.get_current_image()
        if image is None:
            # Capture new image
            image = self.camera.capture_image()

        if image is not None:
            self._display_image(image)

    def _display_image(self, image) -> None:
        """Display image in label.

        Args:
            image: Image to display (numpy array)
        """
        import numpy as np
        import cv2

        # Convert to 8-bit if needed
        if image.dtype != np.uint8:
            image = (image / image.max() * 255).astype(np.uint8)

        # Convert to RGB if grayscale
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Create QImage
        height, width, channels = image.shape
        bytes_per_line = channels * width
        q_image = QImage(
            image.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )

        # Scale to fit label
        pixmap = QPixmap.fromImage(q_image)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)

    def _on_error(self, error_msg: str) -> None:
        """Handle error message.

        Args:
            error_msg: Error message
        """
        self._logger.error(f"Camera error: {error_msg}")
        # Error is also displayed in main window status bar
