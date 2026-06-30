"""YAML extraction: render YAML files as fenced code blocks in markdown.

Uses PyYAML (already a project dependency). Validates YAML on load
to fail fast on malformed input.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from obsidian_import.timeout import TimeoutContext, run_with_timeout


def extract(path: Path, timeout_seconds: int, isolation: str) -> str:
    """Extract a YAML file as a fenced code block in markdown."""
    ctx = TimeoutContext(timeout_seconds=timeout_seconds, label="YAML", path=path, isolation=isolation)
    return run_with_timeout(_extract_yaml, (path,), ctx)


def _extract_yaml(path: Path) -> str:
    """Internal YAML extraction logic."""
    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    formatted = yaml.dump(parsed, default_flow_style=False, allow_unicode=True).rstrip("\n")

    return f"# {path.stem}\n\n```yaml\n{formatted}\n```"
