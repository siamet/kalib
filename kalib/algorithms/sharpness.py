"""Sharpness and focus quality metrics for autofocus.

Implements various sharpness calculation methods including gradient-based,
Sobel-based, Laplacian, and variance metrics.
"""

from typing import Optional, Tuple, List
import numpy as np
import cv2


def gradient_sharpness(image: np.ndarray,
                      roi: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Calculate sharpness using gradient magnitude.

    This is the method from main.py cal_sharp().

    Args:
        image: Input image (grayscale or color)
        roi: Optional region of interest (x, y, width, height)

    Returns:
        Sharpness value (higher = sharper)
    """
    # Extract ROI if specified
    if roi is not None:
        x, y, w, h = roi
        image = image[y:y+h, x:x+w]

    # Convert to float
    if image.dtype != np.float64:
        img = image.astype(np.float64)
    else:
        img = image

    # Calculate gradients
    gx = np.gradient(img, axis=0)
    gy = np.gradient(img, axis=1)

    # Gradient magnitude
    gnorm = np.sqrt(gx**2 + gy**2)

    # Average gradient magnitude as sharpness
    sharpness = np.average(gnorm)

    return float(sharpness)


def sobel_sharpness(image: np.ndarray,
                   ksize: int = 5,
                   roi: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Calculate sharpness using Sobel operator.

    This is the method from Ui.py getSharp() and getSharp2().

    Args:
        image: Input image (grayscale or color)
        ksize: Sobel kernel size (default: 5)
        roi: Optional region of interest (x, y, width, height)

    Returns:
        Sharpness value (higher = sharper)
    """
    # Extract ROI if specified
    if roi is not None:
        x, y, w, h = roi
        image = image[y:y+h, x:x+w]

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Apply Sobel operators
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)

    # Combined gradient
    sobel_combined = sobelx + sobely

    # Mean of standard deviation as sharpness metric
    _, std_dev = cv2.meanStdDev(sobel_combined)
    sharpness = float(std_dev[0, 0])

    return sharpness


def laplacian_sharpness(image: np.ndarray,
                       roi: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Calculate sharpness using Laplacian variance.

    Args:
        image: Input image (grayscale or color)
        roi: Optional region of interest (x, y, width, height)

    Returns:
        Sharpness value (higher = sharper)
    """
    # Extract ROI if specified
    if roi is not None:
        x, y, w, h = roi
        image = image[y:y+h, x:x+w]

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Calculate Laplacian
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)

    # Variance of Laplacian as sharpness
    _, std_dev = cv2.meanStdDev(laplacian)
    sharpness = float(std_dev[0, 0])

    return sharpness


def variance_sharpness(image: np.ndarray,
                      roi: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Calculate sharpness using image variance.

    Simple and fast metric based on pixel intensity variance.

    Args:
        image: Input image (grayscale or color)
        roi: Optional region of interest (x, y, width, height)

    Returns:
        Sharpness value (higher = sharper)
    """
    # Extract ROI if specified
    if roi is not None:
        x, y, w, h = roi
        image = image[y:y+h, x:x+w]

    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Calculate variance
    sharpness = float(np.var(gray))

    return sharpness


def contrast_metric(image: np.ndarray,
                   roi: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Calculate image contrast.

    From main.py cal_sharp() method.

    Args:
        image: Input image (grayscale or color)
        roi: Optional region of interest (x, y, width, height)

    Returns:
        Contrast value (0-1, higher = more contrast)
    """
    # Extract ROI if specified
    if roi is not None:
        x, y, w, h = roi
        image = image[y:y+h, x:x+w]

    # Calculate contrast
    img_max = float(image.max())
    img_min = float(image.min())

    if img_max + img_min == 0:
        return 0.0

    contrast = (img_max - img_min) / (img_max + img_min)

    return float(contrast)


def calculate_sharpness(image: np.ndarray,
                       method: str = "gradient",
                       roi: Optional[Tuple[int, int, int, int]] = None,
                       **kwargs) -> float:
    """Calculate sharpness using specified method.

    Args:
        image: Input image (grayscale or color)
        method: Sharpness method ("gradient", "sobel", "laplacian", "variance")
        roi: Optional region of interest (x, y, width, height)
        **kwargs: Additional arguments for specific methods

    Returns:
        Sharpness value

    Raises:
        ValueError: If unknown method specified
    """
    method = method.lower()

    if method == "gradient":
        return gradient_sharpness(image, roi)
    elif method == "sobel":
        ksize = kwargs.get('ksize', 5)
        return sobel_sharpness(image, ksize, roi)
    elif method == "laplacian":
        return laplacian_sharpness(image, roi)
    elif method == "variance":
        return variance_sharpness(image, roi)
    else:
        raise ValueError(
            f"Unknown sharpness method: {method}. "
            f"Valid: gradient, sobel, laplacian, variance"
        )


def autofocus_search(z_positions: List[float],
                    images: List[np.ndarray],
                    method: str = "sobel",
                    roi: Optional[Tuple[int, int, int, int]] = None
                    ) -> Tuple[float, List[float]]:
    """Perform autofocus search across Z positions.

    Args:
        z_positions: List of Z positions
        images: List of images at each Z position
        method: Sharpness calculation method
        roi: Optional region of interest

    Returns:
        Tuple of (best_focus_z, sharpness_values)
    """
    if len(z_positions) != len(images):
        raise ValueError("Number of positions must match number of images")

    if len(z_positions) == 0:
        raise ValueError("No positions provided")

    # Calculate sharpness for each image
    sharpness_values = []
    for image in images:
        sharpness = calculate_sharpness(image, method=method, roi=roi)
        sharpness_values.append(sharpness)

    # Find peak sharpness
    peak_idx = np.argmax(sharpness_values)
    best_focus_z = z_positions[peak_idx]

    return best_focus_z, sharpness_values


def autofocus_iterative(current_z: float,
                       capture_func,
                       step_size: float = 0.5,
                       max_iterations: int = 10,
                       tolerance: float = 0.1,
                       method: str = "sobel"
                       ) -> Tuple[float, float]:
    """Perform iterative autofocus search.

    This implements the getSharp2() algorithm from Ui.py with
    adaptive step size.

    Args:
        current_z: Current Z position
        capture_func: Function to capture image at given Z: capture_func(z) -> image
        step_size: Initial step size for search
        max_iterations: Maximum search iterations
        tolerance: Stop when step size < tolerance
        method: Sharpness calculation method

    Returns:
        Tuple of (best_focus_z, peak_sharpness)
    """
    best_z = current_z
    step = step_size

    while step > tolerance and max_iterations > 0:
        # Capture at three positions: current - step, current, current + step
        positions = [best_z - step, best_z, best_z + step]
        sharpness_values = []

        for z_pos in positions:
            image = capture_func(z_pos)
            sharpness = calculate_sharpness(image, method=method)
            sharpness_values.append(sharpness)

        # Find best position
        best_idx = np.argmax(sharpness_values)
        best_z = positions[best_idx]

        # If best is in the middle, reduce step size
        if best_idx == 1:
            step *= 0.5

        max_iterations -= 1

    # Get final sharpness at best position
    final_image = capture_func(best_z)
    peak_sharpness = calculate_sharpness(final_image, method=method)

    return best_z, peak_sharpness


def auto_exposure(image: np.ndarray,
                 target_brightness: float = 150.0,
                 tolerance: float = 10.0,
                 current_exposure: float = 15000.0,
                 gain_factor: float = 20.0
                 ) -> float:
    """Calculate optimal exposure time for target brightness.

    This implements the auto-exposure algorithm from Ui.py getSharp2().

    Args:
        image: Current image
        target_brightness: Target mean brightness (0-255)
        tolerance: Acceptable deviation from target
        current_exposure: Current exposure time in microseconds
        gain_factor: Adjustment gain factor

    Returns:
        Recommended exposure time in microseconds
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Calculate current brightness
    current_brightness = float(np.mean(gray))

    # Calculate error
    error = target_brightness - current_brightness

    # If within tolerance, no change needed
    if abs(error) <= tolerance:
        return current_exposure

    # Calculate new exposure
    new_exposure = current_exposure + gain_factor * error

    # Clamp to reasonable range
    new_exposure = max(100, min(100000, new_exposure))

    return new_exposure


def calculate_focus_quality_metrics(image: np.ndarray,
                                    roi: Optional[Tuple[int, int, int, int]] = None
                                    ) -> dict:
    """Calculate multiple focus quality metrics.

    Args:
        image: Input image
        roi: Optional region of interest

    Returns:
        Dictionary of metrics
    """
    metrics = {
        'gradient': gradient_sharpness(image, roi),
        'sobel': sobel_sharpness(image, roi=roi),
        'laplacian': laplacian_sharpness(image, roi),
        'variance': variance_sharpness(image, roi),
        'contrast': contrast_metric(image, roi),
    }

    return metrics
