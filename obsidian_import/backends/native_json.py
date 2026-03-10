"""JSON extraction: render JSON files as fenced code blocks in markdown.

Uses Python stdlib json module. No external dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int, **kwargs: object) -> str:
    """Extract a JSON file as a fenced code block in markdown."""
    return run_with_timeout(lambda: _extract_json(path), timeout_seconds, "JSON", path)


def _extract_json(path: Path) -> str:
    """Internal JSON extraction logic."""
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    formatted = json.dumps(parsed, indent=2, ensure_ascii=False)

    return f"# {path.stem}\n\n```json\n{formatted}\n```"
