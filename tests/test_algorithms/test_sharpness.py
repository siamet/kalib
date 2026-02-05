"""Tests for sharpness algorithms."""

import pytest
import numpy as np

from kalib.algorithms import (
    gradient_sharpness,
    sobel_sharpness,
    laplacian_sharpness,
    variance_sharpness,
    calculate_sharpness,
    autofocus_search
)


class TestSharpnessMetrics:
    """Test sharpness calculation methods."""

    def test_gradient_sharpness(self):
        """Test gradient-based sharpness."""
        # Sharp image (high gradient)
        sharp_image = np.array([
            [0, 255, 0],
            [255, 0, 255],
            [0, 255, 0]
        ], dtype=np.float64)

        # Blur image (low gradient)
        blur_image = np.ones((3, 3), dtype=np.float64) * 128

        sharp_value = gradient_sharpness(sharp_image)
        blur_value = gradient_sharpness(blur_image)

        assert sharp_value > blur_value

    def test_sobel_sharpness(self):
        """Test Sobel-based sharpness."""
        sharp_image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        blur_image = np.ones((100, 100), dtype=np.uint8) * 128

        sharp_value = sobel_sharpness(sharp_image)
        blur_value = sobel_sharpness(blur_image)

        assert sharp_value > blur_value

    def test_laplacian_sharpness(self):
        """Test Laplacian-based sharpness."""
        sharp_image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        blur_image = np.ones((100, 100), dtype=np.uint8) * 128

        sharp_value = laplacian_sharpness(sharp_image)
        blur_value = laplacian_sharpness(blur_image)

        assert sharp_value > blur_value

    def test_variance_sharpness(self):
        """Test variance-based sharpness."""
        sharp_image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        blur_image = np.ones((100, 100), dtype=np.uint8) * 128

        sharp_value = variance_sharpness(sharp_image)
        blur_value = variance_sharpness(blur_image)

        assert sharp_value > blur_value

    def test_calculate_sharpness(self):
        """Test unified sharpness calculation."""
        image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        # Test all methods
        gradient_val = calculate_sharpness(image, method="gradient")
        sobel_val = calculate_sharpness(image, method="sobel")
        laplacian_val = calculate_sharpness(image, method="laplacian")
        variance_val = calculate_sharpness(image, method="variance")

        assert gradient_val > 0
        assert sobel_val > 0
        assert laplacian_val > 0
        assert variance_val > 0

    def test_roi_sharpness(self):
        """Test sharpness with ROI."""
        image = np.ones((100, 100), dtype=np.uint8) * 128
        # Make center region sharper
        image[40:60, 40:60] = np.random.randint(0, 256, (20, 20))

        roi = (40, 40, 20, 20)  # x, y, w, h
        roi_sharpness = gradient_sharpness(image, roi=roi)
        full_sharpness = gradient_sharpness(image)

        assert roi_sharpness > full_sharpness

    def test_autofocus_search(self):
        """Test autofocus search."""
        # Generate images with varying sharpness
        z_positions = [0.0, 1.0, 2.0, 3.0, 4.0]
        images = []

        for i, z in enumerate(z_positions):
            # Make middle position sharpest
            if i == 2:
                img = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
            else:
                img = np.ones((50, 50), dtype=np.uint8) * 128

            images.append(img)

        best_z, sharpness_values = autofocus_search(z_positions, images)

        assert best_z == 2.0
        assert len(sharpness_values) == 5
        assert sharpness_values[2] == max(sharpness_values)
