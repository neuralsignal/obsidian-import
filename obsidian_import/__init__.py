"""obsidian-import: Extract files into Obsidian-flavored Markdown.

Public API:
    extract_file(path, config) -> ExtractedDocument
    extract_text(path, config) -> str
    discover_files(config) -> Iterator[DiscoveredFile]
    config_from_overrides(overrides) -> ImportConfig
"""

from __future__ import annotations

from collections.abc import Iterator

from obsidian_import.config import ImportConfig
from obsidian_import.config import config_for_backend as config_for_backend
from obsidian_import.config import config_from_overrides as config_from_overrides
from obsidian_import.discovery import DiscoveredFile
from obsidian_import.discovery import discover_files as _discover_files
from obsidian_import.extraction import _estimate_page_count as _estimate_page_count
from obsidian_import.extraction import extract_file as extract_file
from obsidian_import.extraction import extract_text as extract_text


def discover_files(config: ImportConfig) -> Iterator[DiscoveredFile]:
    """Discover files matching the configured input directories and extensions."""
    return _discover_files(config)
