"""Glob-based file discovery across configured directories."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from obsidian_import.config import DirectoryConfig, ExtractionConfig, ImportConfig


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
    for dir_config in config.input.directories:
        directory = Path(dir_config.path)
        if not directory.is_dir():
            continue

        base_resolved = directory.resolve()

        for file_path in directory.rglob("*"):
            if not _should_yield(file_path, base_resolved, dir_config, config.extraction):
                continue

            extension = file_path.suffix.lower()
            size = file_path.stat().st_size
            yield DiscoveredFile(
                path=file_path,
                extension=extension,
                size_bytes=size,
                source_directory=str(dir_config.path),
            )


def _should_yield(
    file_path: Path,
    base_resolved: Path,
    dir_config: DirectoryConfig,
    extraction_config: ExtractionConfig,
) -> bool:
    """Per-file acceptance predicate for discover_files."""
    if file_path.is_symlink():
        return False
    if not file_path.is_file():
        return False
    if not file_path.resolve().is_relative_to(base_resolved):
        return False
    if file_path.suffix.lower() not in dir_config.extensions:
        return False
    if _is_excluded(file_path, Path(dir_config.path), dir_config.exclude):
        return False
    return not extraction_config.exceeds_max_file_size(file_path.stat().st_size)


def _is_excluded(path: Path, base_dir: Path, exclude_patterns: tuple[str, ...]) -> bool:
    """Check if a path matches any exclude pattern."""
    relative = str(path.relative_to(base_dir))
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        if fnmatch.fnmatch(path.name, pattern):
            return True
    return False
