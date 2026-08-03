"""JSON wire codec for the parent/child extraction IPC.

The child process sends ``[status, payload]`` as JSON bytes rather than a
pickle, so a compromised or buggy child cannot achieve code execution in the
parent through a crafted payload. Only the two result shapes extraction
backends actually return travel the wire: ``str`` and ``ExtractionResult``.
"""

from __future__ import annotations

import json
from multiprocessing.connection import Connection

from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult

WIRE_TYPE_STR = "str"
WIRE_TYPE_EXTRACTION_RESULT = "ExtractionResult"

_ENVELOPE_LENGTH = 2


def serialize_payload(result: object) -> list[object]:
    """Convert an extraction result to a JSON-safe [type_tag, value] pair."""
    if isinstance(result, str):
        return [WIRE_TYPE_STR, result]
    if isinstance(result, ExtractionResult):
        return [WIRE_TYPE_EXTRACTION_RESULT, result.to_dict()]
    raise ExtractionError(
        f"Process IPC cannot serialize {type(result).__name__}; only str and ExtractionResult are supported"
    )


def deserialize_payload(data: object) -> object:
    """Reconstruct an extraction result from its JSON wire [type_tag, value] pair."""
    if not is_envelope(data):
        raise ExtractionError(f"Malformed IPC payload: expected [type, value], got {type(data).__name__}")
    wire_type, value = data
    if wire_type == WIRE_TYPE_STR:
        if not isinstance(value, str):
            raise ExtractionError(f"IPC type tag 'str' but value is {type(value).__name__}")
        return value
    if wire_type == WIRE_TYPE_EXTRACTION_RESULT:
        if not isinstance(value, dict):
            raise ExtractionError(f"IPC type tag 'ExtractionResult' but value is {type(value).__name__}")
        return ExtractionResult.from_dict(value)
    raise ExtractionError(f"Unknown IPC type tag: {wire_type!r}")


def send_message(conn: Connection, status: str, payload: object) -> None:
    """Send a [status, payload] message as JSON bytes over the connection."""
    wire_payload = serialize_payload(payload) if status == "ok" else str(payload)
    conn.send_bytes(json.dumps([status, wire_payload]).encode("utf-8"))


def is_envelope(data: object) -> bool:
    """True if a decoded message has the [status, payload] shape."""
    return isinstance(data, list) and len(data) == _ENVELOPE_LENGTH
