"""CSV extraction: convert CSV files to GitHub-Flavored Markdown tables.

Uses Python stdlib csv module. No external dependencies.
"""

from __future__ import annotations

import csv
from pathlib import Path

from obsidian_import.formatting import render_markdown_table
from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int, **kwargs: object) -> str:
    """Extract a CSV file as a GFM markdown table."""
    return run_with_timeout(lambda: _extract_csv(path), timeout_seconds, "CSV", path)


def _extract_csv(path: Path) -> str:
    """Internal CSV extraction logic."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return f"# {path.stem}\n\n*Empty CSV file.*"

    sections: list[str] = [f"# {path.stem}"]

    sections.append(render_markdown_table(rows))
    return "\n\n".join(sections)
