"""Tests for the shared timeout utility (thread isolation mode)."""

import threading
import time
from pathlib import Path

import pytest

from obsidian_import.exceptions import ConfigError, ExtractionError, ExtractionTimeoutError
from obsidian_import.timeout import TimeoutContext, run_with_timeout


def _return_hello() -> str:
    return "hello"


def _sleep_then_return() -> str:
    time.sleep(10)
    return "never"


def _raise_value_error() -> str:
    raise ValueError("bad input")


def _return_none() -> str:
    return None  # type: ignore[return-value]


def _raise_runtime_error() -> str:
    raise RuntimeError("root cause")


class TestRunWithTimeoutThread:
    def test_returns_result_on_success(self):
        result = run_with_timeout(
            _return_hello,
            (),
            TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
        )
        assert result == "hello"

    def test_forwards_args(self):
        result = run_with_timeout(
            "{}-{}".format,
            ("a", "b"),
            TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
        )
        assert result == "a-b"

    def test_raises_timeout_when_slow(self):
        with pytest.raises(ExtractionTimeoutError, match="timed out after 1s"):
            run_with_timeout(
                _sleep_then_return,
                (),
                TimeoutContext(timeout_seconds=1, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
            )

    def test_raises_extraction_error_on_exception(self):
        with pytest.raises(ExtractionError, match="failed for"):
            run_with_timeout(
                _raise_value_error,
                (),
                TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
            )

    def test_raises_extraction_error_on_none_result(self):
        """Worker that returns None triggers the no-result guard."""
        with pytest.raises(ExtractionError, match="returned no result"):
            run_with_timeout(
                _return_none,
                (),
                TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
            )

    def test_error_message_includes_label_and_path(self):
        with pytest.raises(ExtractionTimeoutError, match="PDF") as exc_info:
            run_with_timeout(
                _sleep_then_return,
                (),
                TimeoutContext(timeout_seconds=1, label="PDF", path=Path("/data/doc.pdf"), isolation="thread"),
            )
        assert "/data/doc.pdf" in str(exc_info.value)

    def test_timeout_message_includes_file_size_mb(self, tmp_path: Path):
        big = tmp_path / "big.pdf"
        big.write_bytes(b"\0" * (3 * 1024 * 1024))

        with pytest.raises(ExtractionTimeoutError) as exc_info:
            run_with_timeout(
                _sleep_then_return,
                (),
                TimeoutContext(timeout_seconds=1, label="PDF", path=big, isolation="thread"),
            )
        assert "3.0 MB" in str(exc_info.value)

    def test_timeout_message_for_unstatable_path_reports_unknown_size(self):
        with pytest.raises(ExtractionTimeoutError) as exc_info:
            run_with_timeout(
                _sleep_then_return,
                (),
                TimeoutContext(
                    timeout_seconds=1,
                    label="PDF",
                    path=Path("/nonexistent/doc.pdf"),
                    isolation="thread",
                ),
            )
        assert "size unknown" in str(exc_info.value)

    def test_preserves_original_exception_as_cause(self):
        with pytest.raises(ExtractionError) as exc_info:
            run_with_timeout(
                _raise_runtime_error,
                (),
                TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="thread"),
            )
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_unknown_isolation_mode_raises_config_error(self):
        with pytest.raises(ConfigError, match="isolation"):
            run_with_timeout(
                _return_hello,
                (),
                TimeoutContext(timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="fiber"),
            )

    def test_thread_mode_leaks_worker_thread_after_timeout(self, tmp_path: Path):
        """KNOWN LIMITATION (pinned): thread isolation cannot cancel the worker.

        After a timeout, the daemon worker thread keeps running in the
        background and keeps holding its memory and file handles until the
        extraction finishes or the interpreter exits. This is why
        extraction.isolation: "process" is recommended for long-running
        daemons — only process mode actually kills the work on timeout.

        This test documents the leak by proving the worker is still alive
        after ExtractionTimeoutError was raised: releasing it afterwards
        lets it run to completion.
        """
        release = threading.Event()
        finished: list[bool] = []

        def _blocked() -> str:
            release.wait(timeout=30)
            finished.append(True)
            return "late"

        path = tmp_path / "f.txt"
        path.write_text("x")
        with pytest.raises(ExtractionTimeoutError):
            run_with_timeout(
                _blocked,
                (),
                TimeoutContext(timeout_seconds=1, label="test", path=path, isolation="thread"),
            )

        assert not finished, "worker should still be blocked when the timeout fires"

        release.set()
        deadline = time.monotonic() + 5
        while not finished and time.monotonic() < deadline:
            time.sleep(0.01)
        assert finished, "leaked worker thread was expected to still be alive and complete after release"
