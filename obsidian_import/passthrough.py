"""Pass-through file matching and copying for files that skip extraction."""

from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path

from obsidian_import.config import PassthroughConfig
from obsidian_import.exceptions import OutputConflictError


def matches_passthrough(path: Path, cfg: PassthroughConfig) -> bool:
    """Return True if the file should be copied as-is without extraction.

    Checks extension, path glob, and regex rules in order. First match wins (OR logic).

    Path globs use fnmatch semantics against the full path string. Unlike standard
    glob, '*' matches '/' so '**/' is not required for directory traversal. Patterns
    are not anchored to the path start — e.g. 'raw/**' matches only if 'raw/' appears
    at the start of the string representation.
    """
    extension = path.suffix.lower()
    if extension in cfg.extensions:
        return True

    path_str = str(path)
    for glob_pattern in cfg.paths:
        # fnmatch matches against the full path string; '*' matches '/',
        # so "**/*.md" works but patterns are not anchored to path start.
        if fnmatch.fnmatch(path_str, glob_pattern):
            return True

    return any(re.search(regex_pattern, path_str) for regex_pattern in cfg.patterns)


def copy_passthrough(src: Path, dest_dir: Path) -> Path:
    """Copy a file to the destination directory without modification.

    Raises OutputConflictError if the destination file already exists.
    Returns the destination path.
    """
    dest = dest_dir / src.name
    if dest.exists():
        raise OutputConflictError(f"Output file already exists: {dest.name}. Source: {src}, destination: {dest}")
    shutil.copy2(src, dest)
    return dest
