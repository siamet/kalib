"""Tests for the command line client."""

import pytest

from kalib.cli.client import CommandFailed, build_parser, cli_to_wire


def test_parser_accepts_a_command_and_arguments():
    """The parser takes a command name and key/value arguments."""
    args = build_parser().parse_args(["move-xy", "--x", "1.5", "--y", "2.5"])
    assert args.command == "move-xy"
    assert args.x == 1.5
    assert args.y == 2.5


def test_parser_has_a_port_option():
    """The port is overridable for non-default deployments."""
    args = build_parser().parse_args(["status", "--port", "9100"])
    assert args.port == 9100


def test_cli_names_map_to_wire_names():
    """Hyphenated CLI names become underscored wire names."""
    assert cli_to_wire("move-xy") == "move_xy"
    assert cli_to_wire("job-status") == "job_status"
    assert cli_to_wire("status") == "status"


def test_command_failed_is_a_runtime_error():
    """Callers can catch failures without importing a bespoke base."""
    assert issubclass(CommandFailed, RuntimeError)
