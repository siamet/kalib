"""A localhost command server embedded in the Kalib Qt application.

QTcpServer delivers its signals on the Qt event loop, so command handlers run
on the main thread alongside the controllers and need no cross-thread
marshalling. The server binds loopback only: SSH provides the network hop and
authentication, so the server implements none of its own.
"""

from typing import Optional

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
        self._logger = get_logger(__name__)
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
        """Begin listening on loopback.

        Returns:
            The bound port

        Raises:
            RuntimeError: If the port cannot be bound
        """
        if not self._server.listen(QHostAddress(
                QHostAddress.SpecialAddress.LocalHost), self._requested_port):
            raise RuntimeError(
                f"Could not bind 127.0.0.1:{self._requested_port}: "
                f"{self._server.errorString()}"
            )
        self._logger.info(f"Command server listening on 127.0.0.1:{self.port}")
        return self.port

    def stop(self) -> None:
        """Stop listening and drop any open connections."""
        for sock in list(self._buffers):
            sock.disconnectFromHost()
        self._buffers.clear()
        if self._server.isListening():
            self._server.close()
            self._logger.info("Command server stopped")

    def _on_new_connection(self) -> None:
        """Accept a pending connection and wire its signals."""
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_disconnected(s))
            self._logger.debug("Client connected")

    def _on_disconnected(self, sock: QTcpSocket) -> None:
        """Forget a client that has gone away."""
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock: QTcpSocket) -> None:
        """Consume whole lines from a client and answer each one."""
        self._buffers[sock] = self._buffers.get(sock, b"") + bytes(sock.readAll())
        while b"\n" in self._buffers[sock]:
            line, _, rest = self._buffers[sock].partition(b"\n")
            self._buffers[sock] = rest
            sock.write(self._handle_line(line + b"\n"))
            sock.flush()

    def _handle_line(self, line: bytes) -> bytes:
        """Decode, dispatch and encode one request.

        Args:
            line: One newline-terminated request

        Returns:
            The encoded response
        """
        request_id = "?"
        try:
            msg = decode_message(line)
            request_id = str(msg.get("id", "?"))
            cmd = msg.get("cmd")
            if not isinstance(cmd, str):
                raise ProtocolError(
                    "Request must carry a 'cmd' field of type string"
                )
            result = self._registry.dispatch(cmd, msg.get("args") or {})
            self.command_served.emit(cmd, True)
            return encode_ok(request_id, result)
        except ProtocolError as exc:
            self._logger.warning(f"Protocol error: {exc}")
            return encode_error(request_id, exc)
        except Exception as exc:
            self._logger.error(f"Command failed: {exc}", exc_info=True)
            self.command_served.emit(locals().get("cmd", "") or "", False)
            return encode_error(request_id, exc)
