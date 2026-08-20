"""Tests for the --serve flag and daemon wiring."""

from kalib.main import parse_arguments


def test_serve_defaults_to_off():
    """Without the flag no command server runs."""
    assert parse_arguments([]).serve is False


def test_serve_flag_enables_the_server():
    """--serve turns the command server on."""
    assert parse_arguments(["--serve"]).serve is True


def test_serve_port_has_a_default():
    """A default port is supplied when none is given."""
    assert parse_arguments(["--serve"]).serve_port == 8765


def test_serve_port_can_be_overridden():
    """--serve-port sets the bound port."""
    assert parse_arguments(["--serve", "--serve-port", "9100"]).serve_port == 9100


def test_existing_flags_still_parse():
    """Adding the flags does not disturb the existing ones."""
    args = parse_arguments(["--simulate", "--log-level", "DEBUG"])
    assert args.simulate is True
    assert args.log_level == "DEBUG"
    assert args.serve is False
