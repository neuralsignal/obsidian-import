"""CSV extraction: convert CSV files to GitHub-Flavored Markdown tables.

Uses Python stdlib csv module. No external dependencies.
"""

from __future__ import annotations

import csv
from pathlib import Path

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

    max_cols = max(len(row) for row in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    headers = rows[0]
    md_lines = [
        "| " + " | ".join(_escape_cell(h) for h in headers) + " |",
        "| " + " | ".join(["---"] * max_cols) + " |",
    ]
    for row in rows[1:]:
        md_lines.append("| " + " | ".join(_escape_cell(c) for c in row) + " |")

    sections.append("\n".join(md_lines))
    return "\n\n".join(sections)


def _escape_cell(value: str) -> str:
    """Escape pipe characters and newlines in table cells."""
    return value.replace("|", "\\|").replace("\n", " ")
