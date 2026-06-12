"""Fallback extractor using markitdown for unrecognized formats.

Requires the [markitdown] extra: pip install obsidian-import[markitdown]
"""

from __future__ import annotations

from pathlib import Path

from obsidian_import.exceptions import BackendNotAvailableError
from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int, isolation: str) -> str:
    """Extract text using markitdown as a fallback converter."""
    try:
        import markitdown  # noqa: F401
    except ImportError as exc:
        raise BackendNotAvailableError(
            "markitdown is not installed. Install with: pip install obsidian-import[markitdown]"
        ) from exc

    return run_with_timeout(_extract_markitdown, (path,), timeout_seconds, "markitdown", path, isolation)


def _extract_markitdown(path: Path) -> str:
    """Internal markitdown extraction logic (module-level for process isolation)."""
    from markitdown import MarkItDown

    converter = MarkItDown()
    converted = converter.convert(str(path))
    text = converted.text_content
    if not text or not text.strip():
        return f"*No text content extracted from `{path.name}`.*"
    return text
