"""Image processing utilities.

Common image processing functions for microscopy applications.
"""

from typing import Optional, Tuple
import numpy as np
import cv2
from pathlib import Path


def save_image(image: np.ndarray, filepath: str, format: str = 'tiff') -> None:
    """Save image to file.

    Args:
        image: Image array to save
        filepath: Output file path
        format: Image format ('tiff', 'png', 'jpg', 'bmp')

    Raises:
        ValueError: If unsupported format
        IOError: If save fails
    """
    # Ensure directory exists
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)

    # Add extension if not present
    if not filepath.endswith(f'.{format}'):
        filepath = f'{filepath}.{format}'

    # Save based on format
    try:
        if format.lower() in ['tif', 'tiff']:
            cv2.imwrite(filepath, image, [cv2.IMWRITE_TIFF_COMPRESSION, 1])
        elif format.lower() in ['png']:
            cv2.imwrite(filepath, image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        elif format.lower() in ['jpg', 'jpeg']:
            cv2.imwrite(filepath, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif format.lower() in ['bmp']:
            cv2.imwrite(filepath, image)
        else:
            raise ValueError(f"Unsupported image format: {format}")
    except Exception as e:
        raise IOError(f"Failed to save image: {e}") from e


def load_image(filepath: str, grayscale: bool = False) -> np.ndarray:
    """Load image from file.

    Args:
        filepath: Input file path
        grayscale: Load as grayscale

    Returns:
        Image array

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If load fails
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"Image file not found: {filepath}")

    try:
        if grayscale:
            image = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        else:
            image = cv2.imread(filepath, cv2.IMREAD_COLOR)

        if image is None:
            raise IOError(f"Failed to load image: {filepath}")

        return image
    except Exception as e:
        raise IOError(f"Failed to load image: {e}") from e


def resize_image(image: np.ndarray,
                width: Optional[int] = None,
                height: Optional[int] = None,
                scale: Optional[float] = None,
                keep_aspect: bool = True) -> np.ndarray:
    """Resize image.

    Args:
        image: Input image
        width: Target width (None to calculate from height/scale)
        height: Target height (None to calculate from width/scale)
        scale: Scale factor (overrides width/height if provided)
        keep_aspect: Keep aspect ratio

    Returns:
        Resized image

    Raises:
        ValueError: If invalid parameters
    """
    h, w = image.shape[:2]

    if scale is not None:
        # Scale by factor
        new_w = int(w * scale)
        new_h = int(h * scale)
    elif width is not None and height is not None:
        # Explicit dimensions
        new_w = width
        new_h = height
    elif width is not None:
        # Width specified, calculate height
        new_w = width
        new_h = int(h * (width / w)) if keep_aspect else h
    elif height is not None:
        # Height specified, calculate width
        new_h = height
        new_w = int(w * (height / h)) if keep_aspect else w
    else:
        raise ValueError("Must specify scale, width, or height")

    # Resize
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    return resized


def crop_roi(image: np.ndarray,
            x: int, y: int, width: int, height: int) -> np.ndarray:
    """Crop region of interest from image.

    Args:
        image: Input image
        x: Top-left X coordinate
        y: Top-left Y coordinate
        width: ROI width
        height: ROI height

    Returns:
        Cropped image
    """
    return image[y:y+height, x:x+width]


def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert image to grayscale.

    Args:
        image: Input image (RGB or BGR)

    Returns:
        Grayscale image
    """
    if len(image.shape) == 2:
        return image  # Already grayscale

    # Assume BGR (OpenCV default)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray


def normalize_image(image: np.ndarray,
                   min_val: float = 0.0,
                   max_val: float = 255.0) -> np.ndarray:
    """Normalize image to specified range.

    Args:
        image: Input image
        min_val: Minimum output value
        max_val: Maximum output value

    Returns:
        Normalized image
    """
    img_min = image.min()
    img_max = image.max()

    if img_max == img_min:
        return np.full_like(image, min_val, dtype=np.float32)

    # Normalize to [0, 1]
    normalized = (image.astype(np.float32) - img_min) / (img_max - img_min)

    # Scale to desired range
    scaled = normalized * (max_val - min_val) + min_val

    return scaled.astype(image.dtype)


def enhance_contrast(image: np.ndarray,
                    clip_limit: float = 2.0,
                    tile_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Enhance image contrast using CLAHE.

    Args:
        image: Input image
        clip_limit: Contrast clipping limit
        tile_size: Size of grid for histogram equalization

    Returns:
        Contrast-enhanced image
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = convert_to_grayscale(image)
    else:
        gray = image

    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
    enhanced = clahe.apply(gray)

    return enhanced


def create_thumbnail(image: np.ndarray,
                    max_size: int = 200) -> np.ndarray:
    """Create thumbnail of image.

    Args:
        image: Input image
        max_size: Maximum dimension (width or height)

    Returns:
        Thumbnail image
    """
    h, w = image.shape[:2]

    # Calculate scale to fit within max_size
    scale = min(max_size / w, max_size / h)

    if scale >= 1.0:
        return image  # Already small enough

    return resize_image(image, scale=scale)


def stack_images_grid(images: list,
                     grid_shape: Optional[Tuple[int, int]] = None,
                     padding: int = 2) -> np.ndarray:
    """Stack images in a grid layout.

    Args:
        images: List of images (all same size)
        grid_shape: (rows, cols) for grid (None to auto-calculate)
        padding: Padding between images

    Returns:
        Stacked grid image

    Raises:
        ValueError: If images have different sizes
    """
    if not images:
        raise ValueError("No images provided")

    # Check all images same size
    shape = images[0].shape
    if not all(img.shape == shape for img in images):
        raise ValueError("All images must have same dimensions")

    num_images = len(images)

    # Auto-calculate grid shape
    if grid_shape is None:
        cols = int(np.ceil(np.sqrt(num_images)))
        rows = int(np.ceil(num_images / cols))
        grid_shape = (rows, cols)

    rows, cols = grid_shape

    # Image dimensions
    if len(shape) == 3:
        h, w, channels = shape
    else:
        h, w = shape
        channels = 1

    # Create output image
    out_h = rows * h + (rows - 1) * padding
    out_w = cols * w + (cols - 1) * padding

    if channels == 1:
        output = np.zeros((out_h, out_w), dtype=images[0].dtype)
    else:
        output = np.zeros((out_h, out_w, channels), dtype=images[0].dtype)

    # Place images in grid
    idx = 0
    for row in range(rows):
        for col in range(cols):
            if idx >= num_images:
                break

            y = row * (h + padding)
            x = col * (w + padding)

            output[y:y+h, x:x+w] = images[idx]
            idx += 1

    return output


def calculate_histogram(image: np.ndarray,
                       bins: int = 256) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate image histogram.

    Args:
        image: Input image
        bins: Number of histogram bins

    Returns:
        Tuple of (histogram, bin_edges)
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = convert_to_grayscale(image)
    else:
        gray = image

    # Calculate histogram
    hist, bin_edges = np.histogram(gray.flatten(), bins=bins, range=(0, 256))

    return hist, bin_edges


def apply_gaussian_blur(image: np.ndarray,
                       kernel_size: int = 5,
                       sigma: float = 0) -> np.ndarray:
    """Apply Gaussian blur to image.

    Args:
        image: Input image
        kernel_size: Size of Gaussian kernel (must be odd)
        sigma: Gaussian kernel standard deviation (0 = auto)

    Returns:
        Blurred image
    """
    # Ensure kernel size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1

    blurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)

    return blurred


def merge_images_alpha_blend(image1: np.ndarray,
                             image2: np.ndarray,
                             alpha: float = 0.5) -> np.ndarray:
    """Alpha blend two images.

    Args:
        image1: First image
        image2: Second image
        alpha: Blend factor (0=image2 only, 1=image1 only)

    Returns:
        Blended image

    Raises:
        ValueError: If images have different shapes
    """
    if image1.shape != image2.shape:
        raise ValueError("Images must have same dimensions")

    blended = cv2.addWeighted(image1, alpha, image2, 1 - alpha, 0)

    return blended


def get_image_stats(image: np.ndarray) -> dict:
    """Get image statistics.

    Args:
        image: Input image

    Returns:
        Dictionary of statistics
    """
    stats = {
        'shape': image.shape,
        'dtype': str(image.dtype),
        'min': float(image.min()),
        'max': float(image.max()),
        'mean': float(image.mean()),
        'std': float(image.std()),
        'median': float(np.median(image)),
    }

    return stats
