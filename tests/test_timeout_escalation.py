"""Tests for SIGKILL escalation and watchdog-race edge cases in timeout.py.

Covers lines 178-179, 212-213, and 229.
"""

from __future__ import annotations

import multiprocessing.process
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsidian_import.exceptions import ExtractionTimeoutError
from obsidian_import.timeout import (
    _TERMINATE_GRACE_SECONDS,
    TimeoutContext,
    _kill_process,
    _reap_process,
    run_with_timeout,
)


def _echo(value: str) -> str:
    return value


class TestKillProcessSigkillEscalation:
    """_kill_process must escalate to SIGKILL when the child ignores SIGTERM."""

    def test_escalates_when_process_survives_terminate(self) -> None:
        process = MagicMock(spec=multiprocessing.process.BaseProcess)
        process.is_alive.return_value = True

        _kill_process(process)

        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        assert process.join.call_count == 2
        process.join.assert_any_call(timeout=_TERMINATE_GRACE_SECONDS)

    def test_no_sigkill_when_terminate_succeeds(self) -> None:
        process = MagicMock(spec=multiprocessing.process.BaseProcess)
        process.is_alive.return_value = False

        _kill_process(process)

        process.terminate.assert_called_once()
        process.kill.assert_not_called()
        process.join.assert_called_once_with(timeout=_TERMINATE_GRACE_SECONDS)


class TestReapProcessEscalation:
    """_reap_process must kill a worker that lingers past the grace period."""

    def test_kills_lingering_process(self) -> None:
        process = MagicMock(spec=multiprocessing.process.BaseProcess)
        process.is_alive.return_value = True

        _reap_process(process)

        process.terminate.assert_called_once()
        process.kill.assert_called_once()


class _SynchronousTimer:
    """Timer replacement that fires its callback synchronously in start()."""

    def __init__(
        self,
        interval: float,
        function: Callable[..., object],
        args: tuple[object, ...] | None = None,
        kwargs: dict[str, object] | None = None,
    ) -> None:
        self._function = function
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._function(*self._args, **self._kwargs)

    def cancel(self) -> None:
        pass


class TestWatchdogRaceDuringRecv:
    """EOFError during recv when the watchdog has already fired must surface
    as ExtractionTimeoutError, not ExtractionError."""

    def test_eof_with_timed_out_raises_timeout_error(self, tmp_path: Path) -> None:
        path = tmp_path / "f.txt"
        path.write_text("x")

        mock_process = MagicMock()
        mock_parent = MagicMock()
        mock_child = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.Pipe.return_value = (mock_parent, mock_child)
        mock_ctx.Process.return_value = mock_process
        mock_parent.poll.return_value = True
        mock_parent.recv.side_effect = EOFError("pipe closed")

        with (
            patch("obsidian_import.timeout.multiprocessing.get_context", return_value=mock_ctx),
            patch("obsidian_import.timeout.threading.Timer", _SynchronousTimer),
        ):
            with pytest.raises(ExtractionTimeoutError, match="timed out") as exc_info:
                run_with_timeout(
                    _echo,
                    ("hello",),
                    TimeoutContext(timeout_seconds=5, label="test", path=path, isolation="process"),
                )
            assert isinstance(exc_info.value.__cause__, EOFError)
