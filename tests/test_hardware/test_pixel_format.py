"""Tests for pixel format parsing."""

import pytest

from kalib.hardware.base import ConfigurationError
from kalib.hardware.ids_camera import parse_pixel_format


def test_auto_defers_to_the_camera():
    """'auto' yields no colorness, so the driver uses the sensor's own mode."""
    assert parse_pixel_format("auto") == (8, None)


def test_native_is_accepted_as_a_synonym_for_auto():
    """'native' reads more naturally in some configs and means the same."""
    assert parse_pixel_format("native") == (8, None)


def test_empty_configuration_falls_back_to_auto():
    """A missing or blank value must not crash the camera at connect time."""
    assert parse_pixel_format("") == (8, None)
    assert parse_pixel_format(None) == (8, None)


def test_explicit_mono_and_rgb_are_parsed():
    """Explicit names override the sensor's native mode."""
    assert parse_pixel_format("Mono8") == (8, "Mono")
    assert parse_pixel_format("RGB8") == (8, "RGB")
    assert parse_pixel_format("Mono12") == (12, "Mono")


def test_parsing_is_case_insensitive():
    """Configuration files should not be case-sensitive here."""
    assert parse_pixel_format("mono8") == (8, "Mono")
    assert parse_pixel_format("rgb8") == (8, "RGB")


def test_unsupported_bit_rate_is_rejected():
    """Only 8, 10 and 12 bit are supported by the driver."""
    with pytest.raises(ConfigurationError):
        parse_pixel_format("Mono16")


def test_unrecognised_name_is_rejected():
    """A typo fails loudly at parse time rather than deep in the SDK."""
    with pytest.raises(ConfigurationError):
        parse_pixel_format("BayerRG8")
