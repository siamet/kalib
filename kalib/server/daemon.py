"""A localhost command server embedded in the Kalib Qt application.

QTcpServer delivers its signals on the Qt event loop, so command handlers run
on the main thread alongside the controllers and need no cross-thread
marshalling. The server binds loopback only and implements no authentication
of its own: any local process or local user session on the instrument can
connect to this port and drive the hardware. SSH is what makes the server
reachable from a *different* machine, and only that -- it authenticates the
network hop, not connections made from the instrument itself. See
docs/REMOTE_OPERATION.md for the full threat model.
"""

from typing import Optional, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from kalib.server.commands import CommandRegistry
from kalib.server.protocol import (
    ProtocolError,
    decode_message,
    encode_error,
    encode_ok,
)
from kalib.utils.logger import get_logger

DEFAULT_PORT = 8765

# A client that never sends a newline would otherwise grow its per-socket
# buffer without limit; close the connection once an unterminated line
# passes this size instead.
MAX_BUFFER_BYTES = 1_000_000

_logger = get_logger(__name__)


def _handle_line(registry: CommandRegistry,
                  line: bytes) -> Tuple[bytes, Optional[str], bool]:
    """Decode, dispatch and encode one request.

    Module-level and pure request-in/response-out, like the handlers in
    kalib.server.handlers: it needs no daemon state, only the registry to
    dispatch into, so it does not belong on CommandDaemon itself.

    Args:
        registry: Command registry to dispatch into
        line: One newline-terminated request

    Returns:
        A tuple of (encoded response, command name or None, whether the
        command succeeded). The command name is None when the request never
        named a valid command, so callers know not to report one served.
    """
    request_id = "?"
    cmd: Optional[str] = None
    try:
        msg = decode_message(line)
        request_id = str(msg.get("id", "?"))
        cmd = msg.get("cmd")
        if not isinstance(cmd, str):
            raise ProtocolError(
                "Request must carry a 'cmd' field of type string"
            )
        result = registry.dispatch(cmd, msg.get("args") or {})
        return encode_ok(request_id, result), cmd, True
    except ProtocolError as exc:
        _logger.warning(f"Protocol error: {exc}")
        return encode_error(request_id, exc), None, False
    except Exception as exc:
        _logger.error(f"Command failed: {exc}", exc_info=True)
        return encode_error(request_id, exc), cmd, False


def _shutdown_safe_state(registry: CommandRegistry) -> dict:
    """Put the instrument into a safe state.

    Stops acquisition and cancels any running scan. The stages are
    deliberately left exactly where they are and are never homed: homing a
    microscopy stage unattended risks driving the objective into the
    sample, so parking is the safe failure mode and recovery is a human
    decision.

    Module-level, like _handle_line: it needs no daemon state, only the
    registry to act on, so it does not belong on CommandDaemon itself and
    keeps the class under the line-count cap. Each cleanup step is wrapped
    separately so a failure in one does not prevent the other from running.

    Args:
        registry: Command registry whose camera and scan controllers are
            put into a safe state

    Returns:
        What was actually stopped: {"acquisition_stopped": bool,
        "scan_cancelled": bool}
    """
    acquisition_stopped = False
    scan_cancelled = False

    try:
        if registry.camera.is_acquiring:
            acquisition_stopped = bool(registry.camera.stop_acquisition())
    except Exception as exc:
        _logger.error(f"Could not stop acquisition: {exc}")

    try:
        if registry.scan is not None and registry.scan.is_scanning:
            scan_cancelled = bool(registry.scan.cancel_scan())
    except Exception as exc:
        _logger.error(f"Could not cancel scan: {exc}")

    _logger.info(
        f"Safe state: acquisition_stopped={acquisition_stopped}, "
        f"scan_cancelled={scan_cancelled}; stages left in place"
    )
    return {"acquisition_stopped": acquisition_stopped,
            "scan_cancelled": scan_cancelled}


def _over_cap(buf: bytes) -> bool:
    """Whether an unterminated line has grown past MAX_BUFFER_BYTES.

    Module-level, like _handle_line and _shutdown_safe_state: a client
    that never sends a newline would otherwise grow its per-socket buffer
    without limit, and this check needs no daemon state to make -- it
    also keeps CommandDaemon itself under the line-count cap.
    """
    return b"\n" not in buf and len(buf) > MAX_BUFFER_BYTES


def _close_oversized_client(sock: QTcpSocket, size: int) -> None:
    """Log and close a connection whose unterminated line exceeded the cap."""
    _logger.warning(
        f"Client sent {size} bytes with no newline terminator "
        f"(cap is {MAX_BUFFER_BYTES}); closing connection"
    )
    sock.abort()
    sock.deleteLater()


class CommandDaemon(QObject):
    """Serve commands over a loopback TCP socket.

    Example:
        daemon = CommandDaemon(registry)
        daemon.start()
    """

    command_served = Signal(str, bool)  # command name, ok

    def __init__(self, registry: CommandRegistry, port: int = DEFAULT_PORT,
                 parent: Optional[QObject] = None):
        """Initialize the daemon.

        Args:
            registry: Command registry to dispatch into
            port: TCP port to bind; 0 asks the OS for a free one
            parent: Optional Qt parent
        """
        super().__init__(parent)
        self._registry = registry
        self._requested_port = port
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._buffers = {}

    @property
    def port(self) -> int:
        """The bound port, or 0 when not listening."""
        return int(self._server.serverPort())

    def host_address(self) -> str:
        """The bound address as a string."""
        return self._server.serverAddress().toString()

    def is_listening(self) -> bool:
        """Whether the server is accepting connections."""
        return bool(self._server.isListening())

    def start(self) -> int:
        """Begin listening on loopback; returns the bound port.

        Raises:
            RuntimeError: If the port cannot be bound
        """
        if not self._server.listen(QHostAddress(
                QHostAddress.SpecialAddress.LocalHost), self._requested_port):
            raise RuntimeError(
                f"Could not bind 127.0.0.1:{self._requested_port}: "
                f"{self._server.errorString()}"
            )
        _logger.info(f"Command server listening on 127.0.0.1:{self.port}")
        return self.port

    def shutdown_safe_state(self) -> dict:
        """Put the instrument in a safe state; see _shutdown_safe_state."""
        return _shutdown_safe_state(self._registry)

    def stop(self) -> None:
        """Stop listening, put the instrument in a safe state, drop clients."""
        self.shutdown_safe_state()
        for sock in list(self._buffers):
            sock.disconnectFromHost()
        self._buffers.clear()
        if self._server.isListening():
            self._server.close()
            _logger.info("Command server stopped")

    def _on_new_connection(self) -> None:
        """Accept a pending connection and wire its signals."""
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_disconnected(s))
            _logger.debug("Client connected")

    def _on_disconnected(self, sock: QTcpSocket) -> None:
        """Forget a client that has gone away."""
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock: QTcpSocket) -> None:
        """Consume whole lines from a client and answer each one."""
        buf = self._buffers.get(sock, b"") + bytes(sock.readAll())
        if _over_cap(buf):
            self._buffers.pop(sock, None)
            _close_oversized_client(sock, len(buf))
            return

        self._buffers[sock] = buf
        while b"\n" in self._buffers[sock]:
            line, _, rest = self._buffers[sock].partition(b"\n")
            self._buffers[sock] = rest
            response, cmd, ok = _handle_line(self._registry, line + b"\n")
            if cmd is not None:
                self.command_served.emit(cmd, ok)
            sock.write(response)
            sock.flush()
