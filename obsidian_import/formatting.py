"""Shared markdown formatting utilities.

Provides reusable functions for rendering markdown constructs
(tables, etc.) used across multiple extraction backends.
"""

from __future__ import annotations


def make_media_wikilink(doc_stem: str, filename: str) -> str:
    """Build an Obsidian wikilink embed for a media file."""
    return f"![[{doc_stem}/{filename}]]"


def _escape_cell(value: str) -> str:
    """Escape pipe characters and newlines in a table cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown_table(rows: list[list[str]]) -> str:
    """Render a list of rows as a GitHub-Flavored Markdown table.

    The first row is treated as the header row. All cells are escaped
    for pipe characters and newlines. Rows shorter than the longest
    row are padded with empty cells.

    Args:
        rows: Non-empty list of rows, each a list of cell strings.
              The first row is the header.

    Returns:
        A GFM markdown table string.
    """
    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    if max_cols == 0:
        return ""

    padded = [row + [""] * (max_cols - len(row)) for row in rows]

    headers = padded[0]
    md = ["| " + " | ".join(_escape_cell(h) for h in headers) + " |"]
    md.append("| " + " | ".join(["---"] * max_cols) + " |")
    for row in padded[1:]:
        md.append("| " + " | ".join(_escape_cell(c) for c in row) + " |")

    return "\n".join(md)
