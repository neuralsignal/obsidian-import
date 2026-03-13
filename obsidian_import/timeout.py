"""Shared threading-based timeout wrapper for extraction backends."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from obsidian_import.exceptions import ExtractionError, ExtractionTimeoutError


def run_with_timeout[T](fn: Callable[[], T], timeout_seconds: int, label: str, path: Path) -> T:
    """Run an extraction function in a thread with a timeout.

    Args:
        fn: Zero-argument callable that returns a result.
        timeout_seconds: Maximum seconds to wait before raising timeout.
        label: Human-readable backend name for error messages (e.g. "PDF", "DOCX").
        path: Source file path for error messages.

    Returns:
        The result from fn.

    Raises:
        ExtractionTimeoutError: If the function does not complete within timeout.
        ExtractionError: If the function raises or returns no result.
    """
    result: list[T | None] = [None]
    error: list[BaseException | None] = [None]

    def _worker() -> None:
        try:
            result[0] = fn()
        except BaseException as exc:  # noqa: BLE001 — thread boundary: re-raised below
            error[0] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise ExtractionTimeoutError(f"{label} extraction timed out after {timeout_seconds}s: {path}")
    if error[0] is not None:
        raise ExtractionError(f"{label} extraction failed for {path}: {error[0]}") from error[0]
    if result[0] is None:
        raise ExtractionError(f"{label} extraction returned no result for {path}")

    return result[0]
