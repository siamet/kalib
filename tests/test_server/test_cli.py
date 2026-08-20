"""Tests for the command line client."""

import socket
import threading
import time

import pytest

from kalib.cli.client import CommandFailed, build_parser, cli_to_wire, main, send_command
from kalib.hardware.base import CommandError
from kalib.server.protocol import ProtocolError, decode_message, encode_error, encode_ok


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


class _FakeServer:
    """A one-shot TCP server for exercising send_command against real bytes.

    Listens on an OS-assigned loopback port, accepts a single connection,
    reads until a newline-terminated request line is seen (or the peer
    closes first), and hands the raw request bytes to a caller-supplied
    handler that writes back whatever response it likes, in as many
    `send`/`sendall` calls as it wants, before the connection is closed.
    """

    def __init__(self, handler):
        """Bind a listening socket and prepare (but do not start) the thread.

        Args:
            handler: Callable taking (connection, raw_request_bytes) that
                writes the response onto the connection.
        """
        self._handler = handler
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> "_FakeServer":
        """Start accepting the one connection this server will handle."""
        self._thread.start()
        return self

    def _serve(self) -> None:
        try:
            conn, _ = self._sock.accept()
        except OSError:
            return
        try:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            self._handler(conn, buf)
        finally:
            conn.close()

    def stop(self) -> None:
        """Close the listening socket and wait for the thread to exit."""
        self._sock.close()
        self._thread.join(timeout=5)


@pytest.fixture
def fake_server():
    """Yield a factory for one-shot fake servers, stopped after the test.

    Every server created through the factory is stopped in teardown even
    if the test raises, so no listening socket is ever left bound.
    """
    servers = []

    def _make(handler) -> _FakeServer:
        server = _FakeServer(handler).start()
        servers.append(server)
        return server

    yield _make
    for server in servers:
        server.stop()


def test_send_command_round_trip(fake_server):
    """A well-formed ok response is decoded and its result returned."""
    def handler(conn, request_bytes):
        request = decode_message(request_bytes)
        conn.sendall(encode_ok(request["id"], {"x": 1.0, "y": 2.0}))

    server = fake_server(handler)
    result = send_command("get_position", {}, port=server.port, timeout=5)
    assert result == {"x": 1.0, "y": 2.0}


def test_send_command_handles_multi_chunk_response(fake_server):
    """The accumulate-until-newline loop copes with a response split in two."""
    def handler(conn, request_bytes):
        request = decode_message(request_bytes)
        payload = encode_ok(request["id"], {"value": 42})
        split = len(payload) // 2
        conn.sendall(payload[:split])
        time.sleep(0.05)  # force two distinct TCP segments, not one
        conn.sendall(payload[split:])

    server = fake_server(handler)
    result = send_command("status", {}, port=server.port, timeout=5)
    assert result == {"value": 42}


def test_send_command_raises_on_closed_connection(fake_server):
    """A server that closes without sending a newline fails loudly."""
    def handler(conn, request_bytes):
        conn.sendall(b'{"v": 1, "id": "abc", "ok": true')  # no newline, then close

    server = fake_server(handler)
    with pytest.raises(CommandFailed, match="closed the connection"):
        send_command("status", {}, port=server.port, timeout=5)


def test_send_command_raises_command_failed_on_error_response(fake_server):
    """An error response is surfaced with both its type and its message."""
    def handler(conn, request_bytes):
        request = decode_message(request_bytes)
        conn.sendall(encode_error(request["id"], CommandError("nope")))

    server = fake_server(handler)
    with pytest.raises(CommandFailed) as excinfo:
        send_command("status", {}, port=server.port, timeout=5)
    assert "CommandError" in str(excinfo.value)
    assert "nope" in str(excinfo.value)


def test_main_forwards_supplied_arguments_only(monkeypatch):
    """`--x 0` reaches the wire; an unsupplied `--y` never does."""
    captured = {}

    def fake_send_command(cmd, args, host="127.0.0.1", port=8765, timeout=30.0):
        captured["cmd"] = cmd
        captured["args"] = args
        return {"ok": True}

    monkeypatch.setattr("kalib.cli.client.send_command", fake_send_command)
    exit_code = main(["move-xy", "--x", "0"])
    assert exit_code == 0
    assert captured["cmd"] == "move_xy"
    assert captured["args"] == {"x": 0.0}
    assert "y" not in captured["args"]


def test_main_returns_1_on_command_failure(monkeypatch, capsys):
    """A CommandFailed from the server prints an error line and exits 1."""
    def fake_send_command(cmd, args, host="127.0.0.1", port=8765, timeout=30.0):
        raise CommandFailed("boom")

    monkeypatch.setattr("kalib.cli.client.send_command", fake_send_command)
    exit_code = main(["status"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_handles_protocol_error(monkeypatch, capsys):
    """A stale/mismatched server raises ProtocolError, not a traceback."""
    def fake_send_command(cmd, args, host="127.0.0.1", port=8765, timeout=30.0):
        raise ProtocolError("Unsupported protocol version 2")

    monkeypatch.setattr("kalib.cli.client.send_command", fake_send_command)
    exit_code = main(["status"])
    assert exit_code == 1
    assert "Unsupported protocol version 2" in capsys.readouterr().err
