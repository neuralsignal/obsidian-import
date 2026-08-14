"""Markdown block-span extraction for anydoc placement.

Splits markdown into blank-line-separated blocks, keeping fenced code blocks
whole and merging indented continuations onto the preceding block.
"""

from __future__ import annotations

_FENCE = "```"


def block_spans(markdown: str) -> list[tuple[int, int]]:
    """Return (start, end) character spans of the blank-line separated markdown blocks.

    Fenced code blocks are kept whole: the blank lines inside them do not
    separate blocks.
    """
    spans: list[tuple[int, int]] = []
    offset = 0
    start: int | None = None
    end = 0
    in_fence = False

    for line in markdown.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(_FENCE):
            in_fence = not in_fence
        if not stripped and not in_fence:
            if start is not None:
                spans.append((start, end))
                start = None
        else:
            if start is None:
                start = offset
            end = offset + len(line.rstrip("\n"))
        offset += len(line)

    if start is not None:
        spans.append((start, end))
    return _merge_continuations(spans, markdown)


def _merge_continuations(spans: list[tuple[int, int]], markdown: str) -> list[tuple[int, int]]:
    """Join a span onto the previous one when it is an indented continuation of it.

    A nested list is one block of the document model but anydoc renders it with
    a blank line before the nested items (`1. Outer\\n\\n   1. Inner`), which
    would otherwise split one block across two spans.
    """
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and markdown[start] in " \t":
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged
