"""PDF text extraction using pdfplumber + pypdf.

Extracts text with layout preservation, tables as markdown, and form field metadata.
"""

from __future__ import annotations

from pathlib import Path

from obsidian_import.timeout import run_with_timeout


def extract(path: Path, timeout_seconds: int) -> str:
    """Extract text and tables from a PDF file, returning markdown."""
    return run_with_timeout(lambda: _extract_pdf(path), timeout_seconds, "PDF", path)


def _extract_pdf(path: Path) -> str:
    """Internal PDF extraction logic."""
    import pdfplumber
    from pypdf import PdfReader

    sections: list[str] = []

    reader = PdfReader(str(path))
    meta = reader.metadata
    if meta:
        title = meta.title or path.stem
        if meta.author:
            sections.append(f"**Author:** {meta.author}")
        if meta.creation_date:
            sections.append(f"**Created:** {meta.creation_date}")
    else:
        title = path.stem

    sections.insert(0, f"# {title}")

    fields = reader.get_fields()
    if fields:
        field_lines = ["", "## Form Fields", ""]
        for name, field in fields.items():
            field_type = field.get("/FT", "unknown")
            value = field.get("/V", "")
            field_lines.append(f"- **{name}** ({field_type}): {value}")
        sections.append("\n".join(field_lines))

    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            page_sections: list[str] = [f"\n## Page {i}\n"]

            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if not table or not table[0]:
                        continue
                    headers = [str(cell or "").strip() for cell in table[0]]
                    md_table = ["| " + " | ".join(headers) + " |"]
                    md_table.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in table[1:]:
                        cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
                        while len(cells) < len(headers):
                            cells.append("")
                        cells = cells[: len(headers)]
                        md_table.append("| " + " | ".join(cells) + " |")
                    page_sections.append("\n".join(md_table))

            text = page.extract_text()
            if text:
                page_sections.append(text.strip())

            if len(page_sections) > 1:
                sections.append("\n".join(page_sections))

    return "\n\n".join(sections)
