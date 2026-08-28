"""Tests for _recv_result IPC deserialization in process isolation mode."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from obsidian_import.exceptions import ExtractionError
from obsidian_import.timeout import _recv_result


class TestRecvResult:
    def test_invalid_json_wrapped_as_extraction_error(self) -> None:
        """Parent-side defense: non-JSON bytes are wrapped in ExtractionError."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(b"not valid json {{{")
        child_conn.close()
        with pytest.raises(ExtractionError, match="failed to decode"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_malformed_json_structure_raises_extraction_error(self) -> None:
        """A valid JSON value that is not [status, payload] is rejected."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(json.dumps({"unexpected": "object"}).encode("utf-8"))
        child_conn.close()
        with pytest.raises(ExtractionError, match="malformed"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_pickle_bytes_rejected(self) -> None:
        """Raw pickle bytes from a compromised child must not be deserialized."""
        import pickle

        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(pickle.dumps(("ok", "injected")))
        child_conn.close()
        with pytest.raises(ExtractionError, match="failed to decode"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_unknown_type_tag_raises_extraction_error(self) -> None:
        """A JSON payload with an unknown type tag is rejected."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(json.dumps(["ok", ["UnknownType", {}]]).encode("utf-8"))
        child_conn.close()
        with pytest.raises(ExtractionError, match="Unknown IPC type tag"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_str_type_with_non_string_value_raises(self) -> None:
        """A type tag of 'str' with a non-string value is rejected."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(json.dumps(["ok", ["str", 42]]).encode("utf-8"))
        child_conn.close()
        with pytest.raises(ExtractionError, match="type tag 'str' but value is"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_extraction_result_type_with_non_dict_raises(self) -> None:
        """A type tag of 'ExtractionResult' with a non-dict value is rejected."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(json.dumps(["ok", ["ExtractionResult", "not a dict"]]).encode("utf-8"))
        child_conn.close()
        with pytest.raises(ExtractionError, match="type tag 'ExtractionResult' but value is"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_malformed_payload_not_list_raises(self) -> None:
        """A JSON payload where the result is not a [type, value] list is rejected."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send_bytes(json.dumps(["ok", "bare_string"]).encode("utf-8"))
        child_conn.close()
        with pytest.raises(ExtractionError, match="Malformed IPC payload"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()
