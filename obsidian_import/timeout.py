"""Shared timeout wrapper for extraction backends.

Supports two isolation modes (config: extraction.isolation):

- "thread": run the extraction in a daemon thread. Lower latency, but a
  timed-out extraction keeps running in the background until it finishes
  or the interpreter exits.
- "process": run the extraction in a separate spawned process. On timeout
  the process is terminated (killed if necessary) and reaped — true
  cancellation and memory isolation, at the cost of spawn latency. The
  callable and its args must be picklable (top-level functions only), and
  script-based callers must invoke extraction under an
  ``if __name__ == "__main__":`` guard, because spawn re-imports the
  calling module in the child. Each call pays child bootstrap and backend
  imports against timeout_seconds — heavy backends (docling/torch) import
  far slower here than in thread mode, where imports amortize.
"""

from __future__ import annotations

import multiprocessing
import pickle
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path

from obsidian_import.exceptions import ConfigError, ExtractionError, ExtractionTimeoutError

VALID_ISOLATION_MODES: tuple[str, ...] = ("thread", "process")


@dataclass(frozen=True)
class TimeoutContext:
    """Groups the parameters that describe how and where a timeout-guarded extraction runs."""

    timeout_seconds: int
    label: str
    path: Path
    isolation: str


# Grace given to a worker process between SIGTERM and SIGKILL, and to a
# finished worker to exit on its own before being terminated. Deliberately a
# module constant, not a config key: it is an internal cleanup escalation, not
# a behavior knob — the extraction deadline itself always comes from
# extraction.timeout_seconds (YAGNI: no concrete use case for tuning this).
_TERMINATE_GRACE_SECONDS = 5


def validated_isolation(value: object) -> str:
    """Validate an isolation mode against the modes run_with_timeout supports.

    Single source of truth for both the config boundary and the runtime
    dispatch. Raises ConfigError for unsupported modes.
    """
    isolation = str(value)
    if isolation not in VALID_ISOLATION_MODES:
        allowed = " or ".join(f"'{mode}'" for mode in VALID_ISOLATION_MODES)
        raise ConfigError(f"extraction.isolation must be {allowed}, got '{isolation}'")
    return isolation


def run_with_timeout[T](
    fn: Callable[..., T],
    args: tuple[object, ...],
    context: TimeoutContext,
) -> T:
    """Run an extraction function with a timeout.

    Args:
        fn: Top-level callable executing the extraction. Must be picklable
            (no closures/lambdas) when isolation is "process".
        args: Positional arguments for fn. Must be picklable in process mode.
        context: TimeoutContext grouping timeout_seconds, label, path, and
            isolation mode.

    Returns:
        The result from fn(*args).

    Raises:
        ExtractionTimeoutError: If fn does not complete within the timeout.
        ExtractionError: If fn raises or returns no result.
        ConfigError: If isolation is not a supported mode.
    """
    mode = validated_isolation(context.isolation)
    if mode == "thread":
        return _run_in_thread(fn, args, context.timeout_seconds, context.label, context.path)
    return _run_in_process(fn, args, context.timeout_seconds, context.label, context.path)


def _timeout_error(timeout_seconds: int, label: str, path: Path) -> ExtractionTimeoutError:
    return ExtractionTimeoutError(
        f"{label} extraction timed out after {timeout_seconds}s: {path} ({_format_file_size(path)})"
    )


def _format_file_size(path: Path) -> str:
    """File size for timeout telemetry; substitutes an explicit marker if unstatable."""
    try:
        size_bytes = path.stat().st_size
    except OSError:
        # Telemetry only: the file may have vanished mid-extraction. Reporting
        # "size unknown" here must not mask the timeout error being raised.
        return "size unknown"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _run_in_thread[T](
    fn: Callable[..., T], args: tuple[object, ...], timeout_seconds: int, label: str, path: Path
) -> T:
    result: list[T | None] = [None]
    error: list[BaseException | None] = [None]

    def _worker() -> None:
        try:
            result[0] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 — thread boundary: re-raised below
            error[0] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise _timeout_error(timeout_seconds, label, path)
    if error[0] is not None:
        raise ExtractionError(f"{label} extraction failed for {path}: {error[0]}") from error[0]
    if result[0] is None:
        raise ExtractionError(f"{label} extraction returned no result for {path}")

    return result[0]


def _process_worker(conn: Connection, fn: Callable[..., object], args: tuple[object, ...]) -> None:
    """Child-process entry point: run fn and send (status, payload) back."""
    try:
        conn.send(("ok", fn(*args)))
    except BaseException as exc:  # noqa: BLE001 — process boundary: re-raised in parent
        _send_error(conn, exc)
    finally:
        conn.close()


def _send_error(conn: Connection, exc: BaseException) -> None:
    """Send the worker's exception, degrading to its string form when needed.

    An exception that fails the pickle round-trip (unpicklable attributes, or
    an __init__ that pickle cannot replay on load) would either kill this
    child mid-send or raise out of the parent's recv() — losing the root
    cause. The round-trip check catches both directions here, where the
    original message is still available.
    """
    try:
        pickle.loads(pickle.dumps(exc))
    except Exception:  # noqa: BLE001 — corrective: fall back to string form
        conn.send(("err", f"{type(exc).__name__}: {exc}"))
        return
    conn.send(("err", exc))


def _recv_result(parent_conn: Connection, label: str, path: Path) -> tuple[str, object]:
    """Receive the worker's (status, payload) pair.

    EOFError (child died without sending) propagates to the caller, which
    distinguishes timeout kills from spontaneous child death. Any other
    failure is an unpicklable payload and is wrapped in ExtractionError so
    the CLI batch loop can contain it.
    """
    try:
        return parent_conn.recv()
    except EOFError:
        raise
    except Exception as exc:
        raise ExtractionError(f"{label} extraction result for {path} failed to unpickle: {exc!r}") from exc


def _kill_process(process: multiprocessing.process.BaseProcess) -> None:
    """Terminate a worker, escalating to SIGKILL, and reap it."""
    process.terminate()
    process.join(timeout=_TERMINATE_GRACE_SECONDS)
    if process.is_alive():
        process.kill()
        process.join()


def _reap_process(process: multiprocessing.process.BaseProcess) -> None:
    """Reap a worker that has delivered its payload.

    Normally the child exits within milliseconds; a child kept alive by a
    leftover non-daemon thread (e.g. started by a backend library) must not
    block the caller, so the wait is bounded and escalates to a kill.
    """
    process.join(timeout=_TERMINATE_GRACE_SECONDS)
    if process.is_alive():
        _kill_process(process)


def _run_in_process[T](
    fn: Callable[..., T], args: tuple[object, ...], timeout_seconds: int, label: str, path: Path
) -> T:
    # A fresh spawned process per call: nothing is reused after a kill, and
    # spawn avoids inheriting locks/state from the parent (fork is unsafe
    # with threads, e.g. the agent-scheduler daemon). The worker is not
    # daemonic so backends may spawn their own processes (e.g. docling's
    # torch DataLoader workers); every exit path below reaps it explicitly.
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_process_worker, args=(child_conn, fn, args), daemon=False)
    deadline = time.monotonic() + timeout_seconds
    process.start()
    child_conn.close()

    timed_out = threading.Event()

    def _enforce_deadline() -> None:
        timed_out.set()
        _kill_process(process)

    try:
        try:
            if not parent_conn.poll(timeout_seconds):
                raise _timeout_error(timeout_seconds, label, path)
            # poll() only guarantees the first bytes arrived; recv() blocks
            # until the full payload streams in. The watchdog kills the child
            # at the deadline so recv() unblocks with EOFError instead of
            # hanging on a stalled child.
            watchdog = threading.Timer(max(deadline - time.monotonic(), 0.0), _enforce_deadline)
            watchdog.start()
            try:
                status, payload = _recv_result(parent_conn, label, path)
            except EOFError as exc:
                if timed_out.is_set():
                    raise _timeout_error(timeout_seconds, label, path) from exc
                raise ExtractionError(
                    f"{label} extraction process died without a result for {path}. "
                    "If this was called from a script with isolation='process', the call "
                    'must run under an `if __name__ == "__main__":` guard — '
                    "multiprocessing spawn re-imports the calling module in the child."
                ) from exc
            finally:
                watchdog.cancel()
        except BaseException:
            # Timeout, child death, unpicklable payload, or caller interrupt:
            # never leave a worker behind.
            if process.is_alive():
                _kill_process(process)
            raise
    finally:
        parent_conn.close()

    _reap_process(process)

    if status == "err":
        if not isinstance(payload, BaseException):
            raise ExtractionError(f"{label} extraction failed for {path}: {payload!r}")
        raise ExtractionError(f"{label} extraction failed for {path}: {payload}") from payload
    if payload is None:
        raise ExtractionError(f"{label} extraction returned no result for {path}")
    return payload
