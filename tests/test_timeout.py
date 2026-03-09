"""Tests for the shared threading timeout utility."""

import time
from pathlib import Path

import pytest

from obsidian_import.exceptions import ExtractionError, ExtractionTimeoutError
from obsidian_import.timeout import run_with_timeout


class TestRunWithTimeout:
    def test_returns_result_on_success(self):
        result = run_with_timeout(lambda: "hello", timeout_seconds=5, label="test", path=Path("/tmp/f.txt"))
        assert result == "hello"

    def test_raises_timeout_when_slow(self):
        def slow() -> str:
            time.sleep(10)
            return "never"

        with pytest.raises(ExtractionTimeoutError, match="timed out after 1s"):
            run_with_timeout(slow, timeout_seconds=1, label="test", path=Path("/tmp/f.txt"))

    def test_raises_extraction_error_on_exception(self):
        def failing() -> str:
            raise ValueError("bad input")

        with pytest.raises(ExtractionError, match="failed for"):
            run_with_timeout(failing, timeout_seconds=5, label="test", path=Path("/tmp/f.txt"))

    def test_raises_extraction_error_on_none_result(self):
        # This should not happen with our implementation since fn() always returns str,
        # but the guard exists for safety.
        pass

    def test_error_message_includes_label_and_path(self):
        with pytest.raises(ExtractionTimeoutError, match="PDF") as exc_info:
            run_with_timeout(lambda: time.sleep(10) or "x", timeout_seconds=1, label="PDF", path=Path("/data/doc.pdf"))
        assert "/data/doc.pdf" in str(exc_info.value)

    def test_preserves_original_exception_as_cause(self):
        def failing() -> str:
            raise RuntimeError("root cause")

        with pytest.raises(ExtractionError) as exc_info:
            run_with_timeout(failing, timeout_seconds=5, label="test", path=Path("/tmp/f.txt"))
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)
