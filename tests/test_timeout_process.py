"""Tests for the process isolation mode of run_with_timeout.

The worker functions are module-level so the spawn context can pickle them.
"""

from __future__ import annotations

import multiprocessing
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from obsidian_import.exceptions import ExtractionError, ExtractionTimeoutError
from obsidian_import.extraction_result import ExtractionResult
from obsidian_import.timeout import _recv_result, run_with_timeout


def _echo(value: str) -> str:
    return value


def _sleep_forever() -> str:
    time.sleep(120)
    return "never"


def _raise_value_error() -> str:
    raise ValueError("bad input from child")


def _return_extraction_result(markdown: str) -> ExtractionResult:
    return ExtractionResult(markdown=markdown, media_files=())


def _return_with_lingering_thread() -> str:
    """Returns immediately, but a non-daemon thread keeps the child alive."""
    threading.Thread(target=time.sleep, args=(60,), daemon=False).start()
    return "done"


class TwoArgError(Exception):
    """Pickles fine but fails to UNpickle: __init__ needs two args, pickle replays one."""

    def __init__(self, code: int, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _raise_two_arg_error() -> str:
    raise TwoArgError(42, "boom")


class UnpicklableError(Exception):
    """Fails to pickle at all: holds a thread lock."""

    def __init__(self) -> None:
        super().__init__("cannot pickle me")
        self.lock = threading.Lock()


def _raise_unpicklable_error() -> str:
    raise UnpicklableError()


def _noop_grandchild() -> None:
    pass


def _spawn_grandchild() -> str:
    """Backends like docling may spawn their own worker processes."""
    ctx = multiprocessing.get_context("spawn")
    grandchild = ctx.Process(target=_noop_grandchild)
    grandchild.start()
    grandchild.join()
    return "grandchild-ok"


def _return_none() -> None:
    return None


def _exit_without_sending() -> str:
    os._exit(0)


def _boom_on_load() -> None:
    raise TypeError("unpickle boom")


class _EvilPayload:
    """Pickles fine; raises TypeError when unpickled on the receiving side."""

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        return (_boom_on_load, ())


def _child_pids() -> set[int]:
    """PIDs of direct children of this process, via os-level ps (psutil is not a dep).

    Excludes the ps invocation itself, which is briefly a child of this
    process and lists itself in its own output.
    """
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True, check=True).stdout
    me = os.getpid()
    pids: set[int] = set()
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[1].isdigit() and int(parts[1]) == me and not parts[2].endswith("ps"):
            pids.add(int(parts[0]))
    return pids


class TestRunWithTimeoutProcess:
    def test_returns_result_on_success(self, tmp_path: Path) -> None:
        path = tmp_path / "f.csv"
        path.write_text("x")
        result = run_with_timeout(_echo, ("hello",), timeout_seconds=30, label="test", path=path, isolation="process")
        assert result == "hello"

    def test_extraction_result_survives_pickling(self, tmp_path: Path) -> None:
        path = tmp_path / "f.pdf"
        path.write_text("x")
        result = run_with_timeout(
            _return_extraction_result, ("# doc",), timeout_seconds=30, label="test", path=path, isolation="process"
        )
        assert result == ExtractionResult(markdown="# doc", media_files=())

    def test_raises_extraction_error_on_child_exception(self, tmp_path: Path) -> None:
        path = tmp_path / "f.csv"
        path.write_text("x")
        with pytest.raises(ExtractionError, match="failed for") as exc_info:
            run_with_timeout(_raise_value_error, (), timeout_seconds=30, label="test", path=path, isolation="process")
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_timeout_raises_and_kills_child_process(self, tmp_path: Path) -> None:
        """A timed-out extraction process must be killed — no zombie, no survivor."""
        path = tmp_path / "slow.pdf"
        path.write_bytes(b"\0" * (2 * 1024 * 1024))

        # Warm-up call so multiprocessing helper processes (if any) are
        # excluded from the before/after child-PID comparison.
        run_with_timeout(_echo, ("warm",), timeout_seconds=30, label="test", path=path, isolation="process")
        before = _child_pids()

        start = time.monotonic()
        with pytest.raises(ExtractionTimeoutError) as exc_info:
            run_with_timeout(_sleep_forever, (), timeout_seconds=2, label="PDF", path=path, isolation="process")
        elapsed = time.monotonic() - start

        message = str(exc_info.value)
        assert "timed out after 2s" in message
        assert "2.0 MB" in message
        assert str(path) in message
        assert elapsed < 30, f"timeout handling took {elapsed:.1f}s — the child was not killed promptly"

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            leftover = _child_pids() - before
            if not leftover and not multiprocessing.active_children():
                break
            time.sleep(0.1)

        assert _child_pids() - before == set(), "child extraction process survived the timeout"
        assert multiprocessing.active_children() == [], "multiprocessing still tracks a live child"

    def test_result_returns_promptly_despite_lingering_child_thread(self, tmp_path: Path) -> None:
        """A child that delivers its result but cannot exit must not block the caller.

        Regression: process.join() after recv() had no timeout, so a worker
        that started a non-daemon thread made run_with_timeout hang until
        that thread finished (or forever).
        """
        path = tmp_path / "f.csv"
        path.write_text("x")

        start = time.monotonic()
        result = run_with_timeout(
            _return_with_lingering_thread, (), timeout_seconds=30, label="test", path=path, isolation="process"
        )
        elapsed = time.monotonic() - start

        assert result == "done"
        assert elapsed < 20, f"caller blocked {elapsed:.1f}s on a child that already delivered its result"

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and multiprocessing.active_children():
            time.sleep(0.1)
        assert multiprocessing.active_children() == [], "lingering child process was not reaped"

    def test_unpicklable_child_exception_preserves_message(self, tmp_path: Path) -> None:
        """An exception that cannot survive the pickle round-trip must surface as
        ExtractionError with the original message — not a raw TypeError that
        aborts the CLI batch loop."""
        path = tmp_path / "f.csv"
        path.write_text("x")
        with pytest.raises(ExtractionError, match="42: boom"):
            run_with_timeout(_raise_two_arg_error, (), timeout_seconds=30, label="test", path=path, isolation="process")

    def test_undumpable_child_exception_preserves_message(self, tmp_path: Path) -> None:
        path = tmp_path / "f.csv"
        path.write_text("x")
        with pytest.raises(ExtractionError, match="cannot pickle me") as exc_info:
            run_with_timeout(
                _raise_unpicklable_error, (), timeout_seconds=30, label="test", path=path, isolation="process"
            )
        assert "UnpicklableError" in str(exc_info.value)

    def test_recv_unpickle_failure_wrapped_as_extraction_error(self) -> None:
        """Parent-side defense: a payload that fails to unpickle out of the pipe
        is wrapped in ExtractionError instead of escaping as TypeError."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        child_conn.send(("err", _EvilPayload()))
        child_conn.close()
        with pytest.raises(ExtractionError, match="unpickle"):
            _recv_result(parent_conn, "test", Path("/tmp/f.txt"))
        parent_conn.close()

    def test_worker_may_spawn_its_own_processes(self, tmp_path: Path) -> None:
        """The worker must not be daemonic: backends (e.g. docling) can spawn
        their own worker processes."""
        path = tmp_path / "f.pdf"
        path.write_text("x")
        result = run_with_timeout(
            _spawn_grandchild, (), timeout_seconds=60, label="test", path=path, isolation="process"
        )
        assert result == "grandchild-ok"

    def test_none_result_raises_extraction_error(self, tmp_path: Path) -> None:
        path = tmp_path / "f.csv"
        path.write_text("x")
        with pytest.raises(ExtractionError, match="returned no result"):
            run_with_timeout(_return_none, (), timeout_seconds=30, label="test", path=path, isolation="process")

    def test_child_death_without_result_mentions_main_guard(self, tmp_path: Path) -> None:
        """The 'died without a result' error must hint at the spawn __main__-guard
        requirement — the most common cause for script consumers."""
        path = tmp_path / "f.csv"
        path.write_text("x")
        with pytest.raises(ExtractionError, match="__main__") as exc_info:
            run_with_timeout(
                _exit_without_sending, (), timeout_seconds=30, label="test", path=path, isolation="process"
            )
        assert "died without a result" in str(exc_info.value)
