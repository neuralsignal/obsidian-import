"""Obsidian markdown formatter: frontmatter + metadata + headings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import metadata
from pathlib import Path

from obsidian_import.config import OutputConfig
from obsidian_import.extraction_result import MediaFile

_PACKAGE_NAME: str = metadata("obsidian-import")["Name"]


@dataclass(frozen=True)
class ExtractedDocument:
    """Result of a file extraction."""

    source_path: Path
    markdown: str
    title: str
    file_type: str
    page_count: int | None
    associated_files: tuple[Path, ...]
    media_files: tuple[MediaFile, ...]


def format_output(doc: ExtractedDocument, config: OutputConfig) -> str:
    """Format an extracted document as Obsidian-flavored markdown.

    Adds YAML frontmatter if configured, wraps with consistent structure.
    """
    parts: list[str] = []

    if config.frontmatter:
        frontmatter = _build_frontmatter(doc, config)
        parts.append(frontmatter)

    parts.append(doc.markdown)

    return "\n\n".join(parts)


def _build_frontmatter(doc: ExtractedDocument, config: OutputConfig) -> str:
    """Build YAML frontmatter block from document metadata."""
    fields: dict[str, str] = {}

    field_builders: dict[str, Callable[[], str | None]] = {
        "title": lambda: doc.title,
        "source": lambda: _PACKAGE_NAME,
        "original_path": lambda: str(doc.source_path),
        "file_type": lambda: doc.file_type,
        "extracted_at": lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "page_count": lambda: str(doc.page_count) if doc.page_count is not None else None,
    }

    for field_name in config.metadata_fields:
        builder = field_builders.get(field_name)
        if builder is not None:
            value = builder()
            if value is not None:
                fields[field_name] = value

    lines = ["---"]
    for key, value in fields.items():
        if "\n" in value or ":" in value or '"' in value:
            escaped = value.replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")

    return "\n".join(lines)


def output_path_for(source_path: Path, output_directory: str) -> Path:
    """Compute the output path for a source file."""
    out_dir = Path(output_directory)
    return out_dir / f"{source_path.stem}.md"
