"""Tests for _dispatch_worker_result — the pure status/payload dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.exceptions import ExtractionError
from obsidian_import.timeout import _dispatch_worker_result

_LABEL = "test"
_PATH = Path("/tmp/f.txt")


class TestDispatchWorkerResult:
    def test_ok_status_returns_payload(self) -> None:
        assert _dispatch_worker_result("ok", "hello", _LABEL, _PATH) == "hello"

    def test_err_status_raises_extraction_error(self) -> None:
        with pytest.raises(ExtractionError, match="extraction failed for"):
            _dispatch_worker_result("err", "ValueError: boom", _LABEL, _PATH)

    def test_err_message_includes_payload(self) -> None:
        with pytest.raises(ExtractionError, match="RuntimeError: oops"):
            _dispatch_worker_result("err", "RuntimeError: oops", _LABEL, _PATH)

    def test_none_payload_raises_extraction_error(self) -> None:
        with pytest.raises(ExtractionError, match="returned no result"):
            _dispatch_worker_result("ok", None, _LABEL, _PATH)

    def test_none_payload_message_includes_label_and_path(self) -> None:
        label, path = "PDF", Path("/data/doc.pdf")
        with pytest.raises(ExtractionError, match="PDF") as exc_info:
            _dispatch_worker_result("ok", None, label, path)
        assert "/data/doc.pdf" in str(exc_info.value)

    @given(payload=st.text(min_size=1))
    def test_ok_with_nonempty_string_returns_payload(self, payload: str) -> None:
        assert _dispatch_worker_result("ok", payload, _LABEL, _PATH) == payload

    @given(payload=st.text())
    def test_err_always_raises(self, payload: str) -> None:
        with pytest.raises(ExtractionError, match="extraction failed for"):
            _dispatch_worker_result("err", payload, _LABEL, _PATH)
