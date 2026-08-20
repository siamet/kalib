"""Newline-delimited JSON wire protocol for the command server.

Every message is one JSON object on one line. Requests carry a command name
and arguments; responses carry either a result or an error whose type is the
name of the exception class that produced it, so the existing exception
taxonomy in kalib.hardware.base doubles as the wire taxonomy.
"""

import json
from typing import Any, Dict

PROTOCOL_VERSION = 1


class ProtocolError(Exception):
    """Raised when a message cannot be parsed or has the wrong version."""


def encode_request(cmd: str, args: Dict[str, Any], request_id: str) -> bytes:
    """Encode a command request.

    Args:
        cmd: Command name
        args: Command arguments
        request_id: Caller-chosen identifier echoed in the response

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "cmd": cmd,
                  "args": args})


def encode_ok(request_id: str, result: Any) -> bytes:
    """Encode a success response.

    Args:
        request_id: Identifier from the request being answered
        result: JSON-serialisable payload

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "ok": True,
                  "result": result})


def encode_error(request_id: str, exc: Exception) -> bytes:
    """Encode a failure response.

    Args:
        request_id: Identifier from the request being answered
        exc: The exception that caused the failure

    Returns:
        One newline-terminated JSON line
    """
    return _line({"v": PROTOCOL_VERSION, "id": request_id, "ok": False,
                  "error": {"type": type(exc).__name__, "message": str(exc)}})


def decode_message(line: bytes) -> Dict[str, Any]:
    """Decode one wire message.

    Args:
        line: A single newline-terminated JSON line

    Returns:
        The decoded message

    Raises:
        ProtocolError: If the line is not valid JSON or carries an
            unsupported protocol version
    """
    try:
        msg = json.loads(line.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError(f"Malformed message: {exc}") from exc

    if not isinstance(msg, dict):
        raise ProtocolError("Message must be a JSON object")

    version = msg.get("v")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
            f"Unsupported protocol version {version}; "
            f"this server speaks {PROTOCOL_VERSION}"
        )
    return msg


def _line(payload: Dict[str, Any]) -> bytes:
    """Serialise a payload to one newline-terminated JSON line."""
    return (json.dumps(payload) + "\n").encode("utf-8")
