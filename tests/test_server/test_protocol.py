"""Tests for the command wire protocol."""

import json
import pytest

from kalib.hardware.base import CommandError, ConnectionError
from kalib.server.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_message,
    encode_error,
    encode_ok,
    encode_request,
)


def test_request_round_trips():
    """A request encodes to one JSON line and decodes back."""
    raw = encode_request("move_xy", {"x": 1.0, "y": 2.0}, "abc")
    assert raw.endswith(b"\n")
    msg = decode_message(raw)
    assert msg == {"v": PROTOCOL_VERSION, "id": "abc", "cmd": "move_xy",
                   "args": {"x": 1.0, "y": 2.0}}


def test_ok_response_carries_result():
    """A success response reports ok and the result payload."""
    msg = decode_message(encode_ok("abc", {"x": 1.0}))
    assert msg["ok"] is True
    assert msg["result"] == {"x": 1.0}
    assert msg["id"] == "abc"


def test_error_response_uses_the_exception_class_name():
    """Error type reuses the project's exception taxonomy."""
    msg = decode_message(encode_error("abc", CommandError("nope")))
    assert msg["ok"] is False
    assert msg["error"]["type"] == "CommandError"
    assert msg["error"]["message"] == "nope"


def test_error_distinguishes_exception_types():
    """A different exception class produces a different type field."""
    msg = decode_message(encode_error("abc", ConnectionError("down")))
    assert msg["error"]["type"] == "ConnectionError"


def test_encoded_message_is_a_single_line():
    """Multi-line content must not break the newline framing."""
    raw = encode_error("abc", CommandError("line one\nline two"))
    assert raw.count(b"\n") == 1


def test_decode_rejects_malformed_json():
    """Garbage on the wire raises ProtocolError, not a bare JSONDecodeError."""
    with pytest.raises(ProtocolError):
        decode_message(b"{not json\n")


def test_decode_rejects_wrong_version():
    """A mismatched protocol version fails loudly rather than strangely."""
    bad = json.dumps({"v": 99, "id": "a", "cmd": "status", "args": {}}).encode()
    with pytest.raises(ProtocolError):
        decode_message(bad + b"\n")
