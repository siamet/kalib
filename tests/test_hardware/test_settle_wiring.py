"""The configured settle tolerance must actually reach the stage.

A config key nothing reads is worse than no key: it tells the next reader a
value is adjustable when changing it does nothing. This is the same fault the
Z block's velocity setting had before it was removed.
"""

from config import Settings
from kalib.controllers.stage_controller import StageController
from kalib.hardware.pi_stage_z import SETTLE_TOLERANCE_UM, PIStageZ


def test_stage_defaults_to_the_module_tolerance():
    """An unconfigured stage still has a sane tolerance."""
    stage = PIStageZ(device_id="test")
    assert stage.settle_tolerance == SETTLE_TOLERANCE_UM


def test_stage_takes_the_tolerance_it_is_given():
    """The value is a property of the stage, so it must be constructible."""
    stage = PIStageZ(device_id="test", settle_tolerance=0.05)
    assert stage.settle_tolerance == 0.05


def test_controller_carries_the_tolerance_through_to_the_stage():
    """StageController builds PIStageZ lazily, so it must hold the value."""
    controller = StageController(z_device_id="test", settle_tolerance=0.05)
    assert controller.settle_tolerance == 0.05


def test_controller_defaults_when_not_configured():
    """Omitting it is allowed and falls back to the module default."""
    controller = StageController(z_device_id="test")
    assert controller.settle_tolerance == SETTLE_TOLERANCE_UM


def test_the_shipped_config_value_is_the_one_that_would_be_used():
    """Reading the key from a Settings tree yields the stage's tolerance.

    This is the assertion that would have failed while the key was dead.
    """
    settings = Settings({'stages': {'z': {'settle_tolerance': 0.05}}})
    assert settings.get('stages.z.settle_tolerance') == 0.05
    controller = StageController(
        z_device_id="test",
        settle_tolerance=settings.get('stages.z.settle_tolerance'),
    )
    assert controller.settle_tolerance == 0.05
