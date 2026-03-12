"""Data model for extraction results with media file support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaFile:
    """An image or media file extracted from a document."""

    source_path: Path
    filename: str
    media_type: str


@dataclass(frozen=True)
class ExtractionResult:
    """Raw result from a backend extraction."""

    markdown: str
    media_files: tuple[MediaFile, ...]
