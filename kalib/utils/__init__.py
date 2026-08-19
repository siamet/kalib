"""Utilities module - Helper functions and common utilities."""

from kalib.utils.logger import (
    setup_logging,
    get_logger,
    set_console_level,
    set_file_level
)

from kalib.utils.image_utils import (
    save_image,
    load_image,
    resize_image,
    crop_roi,
    convert_to_grayscale,
    normalize_image,
    enhance_contrast,
    create_thumbnail,
    stack_images_grid,
    calculate_histogram,
    apply_gaussian_blur,
    merge_images_alpha_blend,
    get_image_stats
)

__all__ = [
    # Logger
    'setup_logging',
    'get_logger',
    'set_console_level',
    'set_file_level',

    # Image utilities
    'save_image',
    'load_image',
    'resize_image',
    'crop_roi',
    'convert_to_grayscale',
    'normalize_image',
    'enhance_contrast',
    'create_thumbnail',
    'stack_images_grid',
    'calculate_histogram',
    'apply_gaussian_blur',
    'merge_images_alpha_blend',
    'get_image_stats',
]
