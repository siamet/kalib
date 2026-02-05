"""Algorithms module - Scientific algorithms for image processing."""

from kalib.algorithms.sharpness import (
    gradient_sharpness,
    sobel_sharpness,
    laplacian_sharpness,
    variance_sharpness,
    contrast_metric,
    calculate_sharpness,
    autofocus_search,
    autofocus_iterative,
    auto_exposure,
    calculate_focus_quality_metrics
)

from kalib.algorithms.tilt_calibration import (
    fit_plane_lstsq,
    calculate_tilt_angles,
    get_z_correction,
    calibrate_tilt_from_corners,
    generate_corner_positions,
    apply_tilt_correction,
    validate_calibration,
    TiltCalibrator
)

__all__ = [
    # Sharpness
    'gradient_sharpness',
    'sobel_sharpness',
    'laplacian_sharpness',
    'variance_sharpness',
    'contrast_metric',
    'calculate_sharpness',
    'autofocus_search',
    'autofocus_iterative',
    'auto_exposure',
    'calculate_focus_quality_metrics',

    # Tilt Calibration
    'fit_plane_lstsq',
    'calculate_tilt_angles',
    'get_z_correction',
    'calibrate_tilt_from_corners',
    'generate_corner_positions',
    'apply_tilt_correction',
    'validate_calibration',
    'TiltCalibrator',
]
