"""Talk to a running Kalib command server over a loopback socket.

Intended to be invoked over SSH from the development machine:

    ssh winbox python -m kalib.cli move-xy --x 10 --y 20

SSH carries the network hop and the authentication; this client only ever
connects to localhost on the machine it runs on.
"""

import argparse
import json
import socket
import sys
import uuid
from typing import Any, Dict, List, Optional

from kalib.server.protocol import decode_message, encode_request

DEFAULT_PORT = 8765


class CommandFailed(RuntimeError):
    """Raised when the server answers with an error response."""


def cli_to_wire(name: str) -> str:
    """Convert a hyphenated CLI command name to its wire form.

    Args:
        name: CLI command name, e.g. "move-xy"

    Returns:
        The wire command name, e.g. "move_xy"
    """
    return name.replace("-", "_")


def send_command(cmd: str, args: Dict[str, Any], host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT, timeout: float = 30.0) -> Any:
    """Send one command and return its result.

    Args:
        cmd: Wire command name
        args: Command arguments
        host: Server host; always loopback in normal use
        port: Server port
        timeout: Socket timeout in seconds

    Returns:
        The command's result payload

    Raises:
        CommandFailed: If the server answers with an error
    """
    request_id = uuid.uuid4().hex[:8]
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(encode_request(cmd, args, request_id))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                raise CommandFailed("Server closed the connection")
            buf += chunk

    msg = decode_message(buf)
    if not msg.get("ok"):
        error = msg.get("error", {})
        raise CommandFailed(f"{error.get('type', 'Error')}: "
                            f"{error.get('message', 'unknown')}")
    return msg.get("result")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        The configured parser
    """
    parser = argparse.ArgumentParser(
        prog="kalib.cli",
        description="Drive a running Kalib command server."
    )
    parser.add_argument("command", help="Command name, e.g. move-xy, snap, status")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Server port (default: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Socket timeout in seconds (default: 30)")
    for name in ("x", "y", "z", "dx", "dy", "dz", "start_x", "start_y",
                 "end_x", "end_y", "step_x", "step_y", "start_z", "end_z",
                 "step_z", "search_range"):
        parser.add_argument(f"--{name}", type=float, default=None)
    for name in ("num_steps", "num_corners", "corner_idx", "max_px"):
        parser.add_argument(f"--{name}", type=int, default=None)
    for name in ("path", "save_path"):
        parser.add_argument(f"--{name}", type=str, default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Run one command and print its result as JSON.

    Args:
        argv: Argument list; reads sys.argv when None

    Returns:
        Process exit code: 0 on success, 1 on a command error
    """
    args = build_parser().parse_args(argv)
    reserved = {"command", "port", "timeout"}
    payload = {k: v for k, v in vars(args).items()
               if k not in reserved and v is not None}
    try:
        result = send_command(cli_to_wire(args.command), payload,
                              port=args.port, timeout=args.timeout)
    except (CommandFailed, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
