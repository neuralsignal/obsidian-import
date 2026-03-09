"""Glob-based file discovery across configured directories."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from obsidian_import.config import ImportConfig


@dataclass(frozen=True)
class DiscoveredFile:
    """A file discovered for extraction."""

    path: Path
    extension: str
    size_bytes: int
    source_directory: str


def discover_files(config: ImportConfig) -> Iterator[DiscoveredFile]:
    """Walk configured input directories and yield files matching extension filters.

    Respects exclude patterns and max_file_size_mb limit.
    """
    max_size = config.extraction.max_file_size_mb * 1024 * 1024

    for dir_config in config.input.directories:
        directory = Path(dir_config.path)
        if not directory.is_dir():
            continue

        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            extension = file_path.suffix.lower()
            if extension not in dir_config.extensions:
                continue

            if _is_excluded(file_path, directory, dir_config.exclude):
                continue

            size = file_path.stat().st_size
            if size > max_size:
                continue

            yield DiscoveredFile(
                path=file_path,
                extension=extension,
                size_bytes=size,
                source_directory=str(dir_config.path),
            )


def _is_excluded(path: Path, base_dir: Path, exclude_patterns: tuple[str, ...]) -> bool:
    """Check if a path matches any exclude pattern."""
    relative = str(path.relative_to(base_dir))
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        if fnmatch.fnmatch(path.name, pattern):
            return True
    return False
