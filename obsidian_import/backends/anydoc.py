"""Document extraction using anydoc.

Requires the firecrawl-anydoc package (core dependency).
anydoc is a fast Rust-based document-to-Markdown converter by Firecrawl.
"""

from __future__ import annotations

from pathlib import Path

from obsidian_import.exceptions import BackendNotAvailableError
from obsidian_import.timeout import TimeoutContext, run_with_timeout


def extract(path: Path, timeout_seconds: int, isolation: str) -> str:
    """Extract text using anydoc for high-quality document conversion."""
    try:
        import anydoc  # noqa: F401
    except ImportError as exc:
        raise BackendNotAvailableError("anydoc is not installed. Install with: pip install firecrawl-anydoc") from exc

    ctx = TimeoutContext(timeout_seconds=timeout_seconds, label="anydoc", path=path, isolation=isolation)
    return run_with_timeout(_extract_anydoc, (path,), ctx)


def _extract_anydoc(path: Path) -> str:
    """Internal anydoc extraction logic (module-level for process isolation)."""
    import anydoc

    text = anydoc.to_markdown(str(path))
    if not text or not text.strip():
        return f"*No text content extracted from `{path.name}`.*"
    return text
