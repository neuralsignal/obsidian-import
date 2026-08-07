"""Inline placement of media embeds inside anydoc's markdown output.

anydoc renders an embedded image as its alt text, or as nothing when it has
none, and offers no option to emit an image reference. The rendered markdown
therefore contains no anchor to rewrite into an Obsidian wikilink, and the
document model that does carry the images records no character position for
them. What both sides do share is block order: anydoc's markdown is a sequence
of blank-line separated blocks in the same order as ``Document.blocks``.

Placement walks the two sequences in step. A block that renders to text
consumes the next markdown block and its images are embedded after it; a block
that renders to nothing (an image-only paragraph) consumes no markdown and its
images are embedded at that position. Each consumed pair is verified against
the block's own text, and placement stops at the first mismatch rather than
guessing — anything left unplaced is embedded at the end of the note by
``extract_file``.

Embeds are inserted at character offsets in the original markdown, so text
anydoc produced is never rewritten, only interleaved.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anydoc import Block, Document, Inline

from obsidian_import.extraction_result import MediaFile
from obsidian_import.formatting import make_media_wikilink

log = logging.getLogger(__name__)

_FENCE = "```"
_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")
# How much of a block's own text must prefix the markdown block it is matched
# against. Long enough that neighbouring blocks cannot be confused, short
# enough to survive the markdown syntax anydoc adds around the text.
_MATCH_PREFIX_CHARS = 12
# Block kinds that always produce markdown, whatever text they carry: a rule
# renders as `---` with no text of its own, and the container kinds always
# render their children.
_ALWAYS_RENDERED_KINDS = frozenset({"rule", "table", "list", "block_quote", "code_block"})


def place_media_embeds(
    markdown: str,
    document: Document,
    media_by_asset_id: dict[int, MediaFile],
    doc_stem: str,
) -> str:
    """Return the markdown with wikilink embeds inserted at their images' positions.

    Images whose position cannot be established are left out; the caller is
    responsible for surfacing them (``extract_file`` appends the leftovers).
    """
    spans = _block_spans(markdown)
    insertions = _plan_insertions(document, spans, markdown)

    additions: list[tuple[int, str]] = []
    for offset, at_block_start, asset_ids in insertions:
        embeds = [
            make_media_wikilink(doc_stem, media_by_asset_id[asset_id].filename)
            for asset_id in asset_ids
            if asset_id in media_by_asset_id
        ]
        if embeds:
            paragraph = "\n".join(embeds)
            additions.append((offset, f"{paragraph}\n\n" if at_block_start else f"\n\n{paragraph}"))

    return _apply_insertions(markdown, additions)


def _block_spans(markdown: str) -> list[tuple[int, int]]:
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
    return spans


def _plan_insertions(
    document: Document,
    spans: Sequence[tuple[int, int]],
    markdown: str,
) -> list[tuple[int, bool, list[int]]]:
    """Align document blocks with markdown blocks, planning where images belong.

    Returns (offset, at_block_start, asset_ids) entries. Alignment stops at the
    first block that does not match the markdown block it consumes.
    """
    insertions: list[tuple[int, bool, list[int]]] = []
    cursor = 0

    for block in document.blocks:
        asset_ids = list(_image_asset_ids(block))
        if not _expects_markdown(block):
            if asset_ids:
                insertions.append(_insertion_for_unrendered_block(cursor, spans, markdown, asset_ids))
            continue

        if cursor >= len(spans) or not _matches(block, markdown[spans[cursor][0] : spans[cursor][1]]):
            if _remaining_asset_ids(document.blocks, block):
                log.info(
                    "anydoc markdown no longer lines up with its document model at block %d; "
                    "the remaining images are embedded at the end of the note instead",
                    cursor,
                )
            break

        if asset_ids:
            insertions.append((spans[cursor][1], False, asset_ids))
        cursor += 1

    return insertions


def _insertion_for_unrendered_block(
    cursor: int,
    spans: Sequence[tuple[int, int]],
    markdown: str,
    asset_ids: list[int],
) -> tuple[int, bool, list[int]]:
    """Insertion for a block anydoc renders nothing for, so consumes no markdown.

    Its images belong before the markdown block that follows it, or after the
    last one when the block trails the document.
    """
    if cursor < len(spans):
        return (spans[cursor][0], True, asset_ids)
    if spans:
        return (spans[-1][1], False, asset_ids)
    return (len(markdown), False, asset_ids)


def _remaining_asset_ids(blocks: Sequence[Block], from_block: Block) -> list[int]:
    """Asset ids in from_block and every block after it, for reporting a stopped alignment."""
    reached = False
    remaining: list[int] = []
    for block in blocks:
        reached = reached or block is from_block
        if reached:
            remaining.extend(_image_asset_ids(block))
    return remaining


def _expects_markdown(block: Block) -> bool:
    """True when the block renders to a markdown block of its own."""
    if block.kind in _ALWAYS_RENDERED_KINDS:
        return True
    return bool(_block_text(block).strip())


def _matches(block: Block, rendered: str) -> bool:
    """True when the rendered markdown block is the rendering of this block.

    Compared on alphanumeric characters only: anydoc wraps and escapes the text
    it renders (`## `, `- `, `|`, backslashes), none of which survive the
    reduction, while the text itself does.
    """
    expected = _reduce(_block_text(block))
    if not expected:
        return True
    return _reduce(rendered).startswith(expected[:_MATCH_PREFIX_CHARS])


def _reduce(text: str) -> str:
    """Reduce text to its lowercase alphanumeric characters."""
    return _ALPHANUMERIC.sub("", text.casefold())


def _block_text(block: Block) -> str:
    """The plain text a block renders, including the text of nested blocks."""
    parts: list[str] = []
    if block.kind == "code_block":
        parts.append(f"{block.lang or ''} {block.text or ''}")
    if block.content is not None:
        parts.extend(_inline_text(inline) for inline in block.content)
    for nested in _nested_blocks(block):
        parts.append(_block_text(nested))
    return " ".join(part for part in parts if part)


def _inline_text(inline: Inline) -> str:
    """The plain text an inline renders (an image renders its alt text)."""
    if inline.kind == "image":
        return inline.alt or ""
    if inline.content is not None:
        return " ".join(_inline_text(child) for child in inline.content)
    return inline.text or ""


def _image_asset_ids(block: Block) -> Iterator[int]:
    """Asset ids of the embedded images in a block, in document order."""
    if block.content is not None:
        yield from _inline_asset_ids(block.content)
    for nested in _nested_blocks(block):
        yield from _image_asset_ids(nested)


def _inline_asset_ids(inlines: Sequence[Inline]) -> Iterator[int]:
    """Asset ids of the embedded images among inlines, in order."""
    for inline in inlines:
        if inline.kind == "image":
            source = inline.source
            if source is not None and source.kind == "asset" and source.asset_id is not None:
                yield source.asset_id
        elif inline.content is not None:
            yield from _inline_asset_ids(inline.content)


def _nested_blocks(block: Block) -> Iterator[Block]:
    """The blocks a container block holds: list items, table cells, quoted blocks."""
    if block.blocks is not None:
        yield from block.blocks
    if block.list is not None:
        for item in block.list.items:
            yield from item.blocks
    if block.table is not None:
        for row in block.table.grid:
            for slot in row:
                if slot.kind == "origin" and slot.cell is not None:
                    yield from slot.cell.blocks


def _apply_insertions(markdown: str, additions: Sequence[tuple[int, str]]) -> str:
    """Insert text at the given character offsets, leaving the rest untouched."""
    if not additions:
        return markdown

    pieces: list[str] = []
    previous = 0
    for offset, text in sorted(additions, key=lambda addition: addition[0]):
        pieces.append(markdown[previous:offset])
        pieces.append(text)
        previous = offset
    pieces.append(markdown[previous:])
    return "".join(pieces)
