"""Models module - Data structures and business logic."""

from kalib.models.camera_model import CameraModel, CameraSettings, CameraState
from kalib.models.stage_model import StageModel, Position3D, StageLimits
from kalib.models.scan_model import (
    ScanModel,
    ScanType,
    ScanState,
    XYScanParameters,
    ZStackParameters,
    SFFScanParameters,
    ScanProgress
)
from kalib.models.calibration_model import (
    CalibrationModel,
    TiltCalibration,
    MagneticCalibration,
    AutofocusData
)

__all__ = [
    # Camera
    'CameraModel',
    'CameraSettings',
    'CameraState',

    # Stage
    'StageModel',
    'Position3D',
    'StageLimits',

    # Scan
    'ScanModel',
    'ScanType',
    'ScanState',
    'XYScanParameters',
    'ZStackParameters',
    'SFFScanParameters',
    'ScanProgress',

    # Calibration
    'CalibrationModel',
    'TiltCalibration',
    'MagneticCalibration',
    'AutofocusData',
]
