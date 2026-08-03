"""Tests for the JSON wire codec used by the parent/child extraction IPC."""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.ipc_codec import (
    WIRE_TYPE_EXTRACTION_RESULT,
    WIRE_TYPE_STR,
    deserialize_payload,
    is_envelope,
    send_message,
    serialize_payload,
)


class TestIsEnvelope:
    def test_two_element_list_is_envelope(self) -> None:
        assert is_envelope(["ok", "payload"])

    @pytest.mark.parametrize("data", [None, "ok", 42, {"status": "ok"}, [], ["ok"], ["ok", 1, 2]])
    def test_other_shapes_are_not(self, data: object) -> None:
        assert not is_envelope(data)


class TestSerializePayload:
    def test_str_is_tagged(self) -> None:
        assert serialize_payload("hello") == [WIRE_TYPE_STR, "hello"]

    def test_extraction_result_is_tagged_as_dict(self) -> None:
        result = ExtractionResult(markdown="# Doc", media_files=())
        tag, value = serialize_payload(result)
        assert tag == WIRE_TYPE_EXTRACTION_RESULT
        assert value == result.to_dict()

    @pytest.mark.parametrize("unsupported", [None, 42, 1.5, b"bytes", ["a"], {"k": "v"}, Path("/tmp/f")])
    def test_unsupported_type_raises(self, unsupported: object) -> None:
        with pytest.raises(ExtractionError, match="cannot serialize"):
            serialize_payload(unsupported)

    def test_error_names_the_offending_type(self) -> None:
        with pytest.raises(ExtractionError, match="NoneType"):
            serialize_payload(None)


class TestDeserializePayload:
    def test_str_round_trip(self) -> None:
        assert deserialize_payload(serialize_payload("hello")) == "hello"

    def test_extraction_result_round_trip(self) -> None:
        media = MediaFile(source_path=Path("/tmp/i.png"), filename="i.png", media_type="image/png")
        result = ExtractionResult(markdown="# Doc\n\n![[i.png]]", media_files=(media,))
        assert deserialize_payload(serialize_payload(result)) == result

    @pytest.mark.parametrize("bad", ["bare", 42, None, {"type": "str"}, [], [WIRE_TYPE_STR]])
    def test_non_envelope_raises(self, bad: object) -> None:
        with pytest.raises(ExtractionError, match="Malformed IPC payload"):
            deserialize_payload(bad)

    def test_unknown_tag_raises(self) -> None:
        with pytest.raises(ExtractionError, match="Unknown IPC type tag"):
            deserialize_payload(["SomethingElse", {}])

    def test_str_tag_with_non_str_value_raises(self) -> None:
        with pytest.raises(ExtractionError, match="type tag 'str' but value is int"):
            deserialize_payload([WIRE_TYPE_STR, 42])

    def test_extraction_result_tag_with_non_dict_value_raises(self) -> None:
        with pytest.raises(ExtractionError, match="type tag 'ExtractionResult' but value is str"):
            deserialize_payload([WIRE_TYPE_EXTRACTION_RESULT, "not a dict"])


class TestPayloadRoundTripProperties:
    @given(value=st.text(max_size=200))
    def test_str_round_trips(self, value: str) -> None:
        assert deserialize_payload(serialize_payload(value)) == value

    @given(markdown=st.text(max_size=200), filenames=st.lists(st.text(min_size=1, max_size=30), max_size=5))
    def test_extraction_result_round_trips(self, markdown: str, filenames: list[str]) -> None:
        media = tuple(
            MediaFile(source_path=Path("/tmp") / name, filename=name, media_type="image/png") for name in filenames
        )
        result = ExtractionResult(markdown=markdown, media_files=media)
        assert deserialize_payload(serialize_payload(result)) == result

    @given(value=st.text(max_size=200))
    def test_wire_form_is_json_encodable(self, value: str) -> None:
        """The whole point of the codec: every payload survives a JSON round trip."""
        wire = serialize_payload(value)
        assert deserialize_payload(json.loads(json.dumps(wire))) == value


class TestSendMessage:
    def test_ok_message_carries_serialized_payload(self) -> None:
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        send_message(child_conn, "ok", "extracted")
        child_conn.close()
        status, wire_payload = json.loads(parent_conn.recv_bytes())
        parent_conn.close()
        assert status == "ok"
        assert deserialize_payload(wire_payload) == "extracted"

    def test_err_message_stringifies_payload(self) -> None:
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        send_message(child_conn, "err", "ValueError: bad input")
        child_conn.close()
        status, wire_payload = json.loads(parent_conn.recv_bytes())
        parent_conn.close()
        assert status == "err"
        assert wire_payload == "ValueError: bad input"

    def test_err_payload_needs_no_serializable_type(self) -> None:
        """An err payload bypasses serialize_payload, so any object is accepted."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        send_message(child_conn, "err", ValueError("boom"))
        child_conn.close()
        status, wire_payload = json.loads(parent_conn.recv_bytes())
        parent_conn.close()
        assert status == "err"
        assert wire_payload == "boom"

    def test_unserializable_ok_payload_raises(self) -> None:
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        with pytest.raises(ExtractionError, match="cannot serialize"):
            send_message(child_conn, "ok", object())
        child_conn.close()
        parent_conn.close()
