"""PPTX text extraction using python-pptx.

Extracts per-slide text, speaker notes, and tables.
"""

from __future__ import annotations

from pathlib import Path

from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int) -> str:
    """Extract text from a PPTX file, returning markdown."""
    return run_with_timeout(lambda: _extract_pptx(path), timeout_seconds, "PPTX", path)


def _extract_pptx(path: Path) -> str:
    """Internal PPTX extraction logic."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation(str(path))
    sections: list[str] = [f"# {path.stem}"]

    slide_width = prs.slide_width
    slide_height = prs.slide_height
    if slide_width and slide_height:
        w_in = slide_width / Inches(1)
        h_in = slide_height / Inches(1)
        sections.append(f'*Slide dimensions: {w_in:.1f}" x {h_in:.1f}"*')

    for i, slide in enumerate(prs.slides, 1):
        slide_sections: list[str] = []

        title = ""
        if slide.shapes.title:
            title = slide.shapes.title.text.strip()

        if title:
            slide_sections.append(f"## Slide {i}: {title}")
        else:
            slide_sections.append(f"## Slide {i}")

        body_texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                if shape == slide.shapes.title:
                    continue
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        level = para.level or 0
                        if level > 0:
                            body_texts.append(f"{'  ' * level}- {text}")
                        else:
                            body_texts.append(text)

            if shape.has_table:
                table_md = _extract_table(shape.table)
                if table_md:
                    body_texts.append(table_md)

        if body_texts:
            slide_sections.append("\n".join(body_texts))

        if slide.has_notes_slide:
            notes_frame = slide.notes_slide.notes_text_frame
            notes_text = notes_frame.text.strip() if notes_frame else ""
            if notes_text:
                slide_sections.append(f"\n> **Speaker Notes:** {notes_text}")

        if len(slide_sections) > 1:
            sections.append("\n\n".join(slide_sections))
        else:
            sections.append(slide_sections[0])

    return "\n\n".join(sections)


def _extract_table(table: object) -> str:
    """Extract a PPTX table as markdown."""
    rows: list[list[str]] = []
    for row in table.rows:  # type: ignore[attr-defined]
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append("")

    headers = rows[0]
    md = ["| " + " | ".join(headers) + " |"]
    md.append("| " + " | ".join(["---"] * max_cols) + " |")
    for row in rows[1:]:
        md.append("| " + " | ".join(row) + " |")

    return "\n".join(md)
