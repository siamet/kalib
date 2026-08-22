"""'auto' must mean the sensor's native mode, bit depth included.

It did not. `parse_pixel_format("auto")` returned a hardcoded 8, so a 12-bit
scientific camera came up in Mono8 and every frame railed at 255 instead of
4094. The colorness half was auto-detected and the depth half was not, which is
the harder kind of bug to see: the log line reads "Mono8 (internal) -> Mono8
(output)" and looks like a deliberate choice.
"""

import pytest

from kalib.hardware.base import ConfigurationError
from kalib.hardware.ids_camera import native_bit_depth

#: What a U3-3890CP actually offers, as get_available_pixel_formats returns it.
MONO_CAMERA = [
    "Mono8", "Mono10g40IDS", "Mono12g24IDS", "Mono12g40IDS", "Mono12",
]
COLOR_CAMERA = [
    "BayerRG8", "BayerRG10g40IDS", "BayerRG12g24IDS", "BayerRG12",
]


class TestNativeBitDepth:
    def test_it_picks_the_deepest_the_sensor_offers(self):
        assert native_bit_depth(MONO_CAMERA, "Mono") == 12

    def test_it_reads_the_ids_vendor_suffixes(self):
        """The deepest format on this camera is only offered as Mono12g40IDS."""
        assert native_bit_depth(["Mono8", "Mono12g40IDS"], "Mono") == 12

    def test_it_handles_a_bayer_camera(self):
        assert native_bit_depth(COLOR_CAMERA, "RGB", bayer_pattern="RG") == 12

    def test_it_ignores_depths_the_driver_cannot_convert(self):
        """16-bit is outside VALID_BIT_RATES, so it must not be selected."""
        assert native_bit_depth(["Mono8", "Mono16"], "Mono") == 8

    def test_it_ignores_the_other_colour_mode(self):
        """A mono request must not pick a depth only Bayer offers."""
        assert native_bit_depth(["Mono8", "BayerRG12"], "Mono") == 8

    def test_an_eight_bit_only_camera_gets_eight(self):
        assert native_bit_depth(["Mono8"], "Mono") == 8

    def test_nothing_usable_is_an_error_not_a_silent_default(self):
        with pytest.raises(ConfigurationError):
            native_bit_depth(["BayerRG8"], "Mono")

    def test_an_empty_list_is_an_error(self):
        with pytest.raises(ConfigurationError):
            native_bit_depth([], "Mono")
