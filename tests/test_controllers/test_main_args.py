"""Tests for command line argument handling."""

from kalib.main import parse_arguments


def test_simulate_defaults_to_false():
    """Without the flag the application targets real hardware."""
    args = parse_arguments([])
    assert args.simulate is False


def test_simulate_flag_sets_true():
    """The --simulate flag selects the simulated backend."""
    args = parse_arguments(['--simulate'])
    assert args.simulate is True


def test_existing_arguments_still_parse():
    """Adding the flag does not disturb the existing arguments."""
    args = parse_arguments(['--config', 'x.yaml', '--log-level', 'DEBUG'])
    assert args.config == 'x.yaml'
    assert args.log_level == 'DEBUG'
    assert args.simulate is False
