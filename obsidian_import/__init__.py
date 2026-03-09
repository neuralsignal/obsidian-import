"""obsidian-import: Extract files into Obsidian-flavored Markdown.

Public API:
    extract_file(path, config) -> ExtractedDocument
    extract_text(path, config) -> str
    discover_files(config) -> Iterator[DiscoveredFile]
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from obsidian_import.config import ImportConfig
from obsidian_import.discovery import DiscoveredFile
from obsidian_import.discovery import discover_files as _discover_files
from obsidian_import.output import ExtractedDocument
from obsidian_import.registry import extract_with_backend


def extract_file(path: Path, config: ImportConfig) -> ExtractedDocument:
    """Extract a single file to Obsidian-flavored markdown.

    Uses the configured backend for the file's extension.
    Returns an ExtractedDocument with the extracted markdown and metadata.
    """
    extension = path.suffix.lower()
    extra_kwargs: dict[str, object] = {}

    if extension == ".xlsx":
        extra_kwargs["max_rows_per_sheet"] = config.extraction.xlsx_max_rows_per_sheet

    markdown = extract_with_backend(
        path,
        backends=config.backends,
        timeout_seconds=config.extraction.timeout_seconds,
        **extra_kwargs,
    )

    page_count = _estimate_page_count(markdown, extension)

    return ExtractedDocument(
        source_path=path,
        markdown=markdown,
        title=path.stem,
        file_type=extension.lstrip("."),
        page_count=page_count,
    )


def discover_files(config: ImportConfig) -> Iterator[DiscoveredFile]:
    """Discover files matching the configured input directories and extensions."""
    return _discover_files(config)


def extract_text(path: Path, config: ImportConfig) -> str:
    """Extract raw markdown text from a file. No frontmatter, no metadata wrapping."""
    extension = path.suffix.lower()
    extra_kwargs: dict[str, object] = {}
    if extension == ".xlsx":
        extra_kwargs["max_rows_per_sheet"] = config.extraction.xlsx_max_rows_per_sheet
    return extract_with_backend(
        path,
        backends=config.backends,
        timeout_seconds=config.extraction.timeout_seconds,
        **extra_kwargs,
    )


def _estimate_page_count(markdown: str, extension: str) -> int | None:
    """Estimate page count from extracted markdown.

    For PDFs, count '## Page N' headings. For other formats, return None.
    """
    if extension == ".pdf":
        count = 0
        for line in markdown.splitlines():
            if line.startswith("## Page "):
                count += 1
        return count if count > 0 else None
    return None
