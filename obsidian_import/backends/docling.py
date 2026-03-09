"""High-quality document extraction using docling.

Requires the [docling] extra: pip install obsidian-import[docling]
"""

from __future__ import annotations

from pathlib import Path

from obsidian_import.exceptions import BackendNotAvailableError
from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int) -> str:
    """Extract text using docling for high-quality document conversion."""
    try:
        from docling.document_converter import DocumentConverter  # noqa: F811
    except ImportError as exc:
        raise BackendNotAvailableError(
            "docling is not installed. Install with: pip install obsidian-import[docling]"
        ) from exc

    def _do_extract() -> str:
        converter = DocumentConverter()
        doc_result = converter.convert(str(path))
        text = doc_result.document.export_to_markdown()
        if not text or not text.strip():
            return f"*No text content extracted from `{path.name}`.*"
        return text

    return run_with_timeout(_do_extract, timeout_seconds, "docling", path)
