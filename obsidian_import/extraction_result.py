"""Data model for extraction results with media file support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MediaFile:
    """An image or media file extracted from a document."""

    source_path: Path
    filename: str
    media_type: str

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-safe dict for IPC."""
        return {
            "source_path": str(self.source_path),
            "filename": self.filename,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaFile:
        """Reconstruct from a dict produced by to_dict."""
        return cls(
            source_path=Path(data["source_path"]),
            filename=data["filename"],
            media_type=data["media_type"],
        )


@dataclass(frozen=True)
class ExtractionResult:
    """Raw result from a backend extraction."""

    markdown: str
    media_files: tuple[MediaFile, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict for IPC."""
        return {
            "markdown": self.markdown,
            "media_files": [m.to_dict() for m in self.media_files],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionResult:
        """Reconstruct from a dict produced by to_dict."""
        return cls(
            markdown=data["markdown"],
            media_files=tuple(MediaFile.from_dict(m) for m in data["media_files"]),
        )
