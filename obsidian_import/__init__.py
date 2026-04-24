"""obsidian-import: Extract files into Obsidian-flavored Markdown.

Public API:
    extract_file(path, config) -> ExtractedDocument
    extract_text(path, config) -> str
    discover_files(config) -> Iterator[DiscoveredFile]
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from obsidian_import.backends.native_image import is_image_extension
from obsidian_import.config import ImportConfig
from obsidian_import.config import config_for_backend as config_for_backend
from obsidian_import.discovery import DiscoveredFile
from obsidian_import.discovery import discover_files as _discover_files
from obsidian_import.extraction_result import ExtractionResult
from obsidian_import.formatting import make_media_wikilink
from obsidian_import.output import ExtractedDocument
from obsidian_import.registry import extract_with_backend


def _build_extra_kwargs(extension: str, config: ImportConfig) -> dict[str, object]:
    """Build format-specific keyword arguments for backend extraction."""
    extra_kwargs: dict[str, object] = {}
    if extension == ".xlsx":
        extra_kwargs["max_rows_per_sheet"] = config.extraction.xlsx_max_rows_per_sheet
    return extra_kwargs


def _call_backend(path: Path, config: ImportConfig) -> ExtractionResult:
    """Run the configured backend on a file, including format-specific kwargs."""
    extension = path.suffix.lower()
    extra_kwargs = _build_extra_kwargs(extension, config)
    return extract_with_backend(
        path,
        backends=config.backends,
        timeout_seconds=config.extraction.timeout_seconds,
        media_config=config.media,
        **extra_kwargs,
    )


def extract_file(path: Path, config: ImportConfig) -> ExtractedDocument:
    """Extract a single file to Obsidian-flavored markdown.

    Uses the configured backend for the file's extension.
    Returns an ExtractedDocument with the extracted markdown and metadata.
    For image files, the source image is listed in associated_files for copying.
    """
    extension = path.suffix.lower()
    result = _call_backend(path, config)

    page_count = _estimate_page_count(result.markdown, extension)

    associated: tuple[Path, ...] = ()
    if is_image_extension(extension):
        associated = (path,)

    doc_stem = path.stem
    markdown = result.markdown
    if result.media_files:
        for mf in result.media_files:
            wikilink = make_media_wikilink(doc_stem, mf.filename)
            if wikilink not in markdown:
                markdown += f"\n\n{wikilink}"

    return ExtractedDocument(
        source_path=path,
        markdown=markdown,
        title=path.stem,
        file_type=extension.lstrip("."),
        page_count=page_count,
        associated_files=associated,
        media_files=result.media_files,
    )


def discover_files(config: ImportConfig) -> Iterator[DiscoveredFile]:
    """Discover files matching the configured input directories and extensions."""
    return _discover_files(config)


def extract_text(path: Path, config: ImportConfig) -> str:
    """Extract raw markdown text from a file. No frontmatter, no metadata wrapping."""
    result = _call_backend(path, config)
    return result.markdown


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
