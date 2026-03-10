"""YAML extraction: render YAML files as fenced code blocks in markdown.

Uses PyYAML (already a project dependency). Validates YAML on load
to fail fast on malformed input.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int, **kwargs: object) -> str:
    """Extract a YAML file as a fenced code block in markdown."""
    return run_with_timeout(lambda: _extract_yaml(path), timeout_seconds, "YAML", path)


def _extract_yaml(path: Path) -> str:
    """Internal YAML extraction logic."""
    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    formatted = yaml.dump(parsed, default_flow_style=False, allow_unicode=True)

    return f"# {path.stem}\n\n```yaml\n{formatted}```"
