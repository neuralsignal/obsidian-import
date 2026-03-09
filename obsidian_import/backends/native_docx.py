"""DOCX text extraction using defusedxml + zipfile.

Opens the DOCX as a ZIP archive, parses word/document.xml to extract
text with structure preservation (headings, paragraphs, tables).
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element

from obsidian_import.exceptions import ExtractionError
from obsidian_import.timeout import run_with_timeout

_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def extract(path: Path, timeout_seconds: int) -> str:
    """Extract text from a DOCX file, returning markdown."""
    return run_with_timeout(lambda: _extract_docx(path), timeout_seconds, "DOCX", path)


def _extract_docx(path: Path) -> str:
    """Internal DOCX extraction logic."""
    from defusedxml.ElementTree import fromstring

    if not zipfile.is_zipfile(str(path)):
        raise ExtractionError(f"Not a valid DOCX (ZIP) file: {path}")

    with zipfile.ZipFile(str(path), "r") as zf:
        if "word/document.xml" not in zf.namelist():
            raise ExtractionError(f"No word/document.xml found in: {path}")

        doc_xml = zf.read("word/document.xml")
        root = fromstring(doc_xml)

    sections: list[str] = [f"# {path.stem}"]
    body = root.find(f"{{{_NS['w']}}}body")
    if body is None:
        return f"# {path.stem}\n\n*No body content found.*"

    for element in body:
        tag = _local_name(element)

        if tag == "p":
            text = _extract_paragraph(element)
            if text:
                sections.append(text)

        elif tag == "tbl":
            table_md = _extract_table(element)
            if table_md:
                sections.append(table_md)

    return "\n\n".join(sections)


def _local_name(element: Element) -> str:
    """Get the local name of an XML element (strip namespace)."""
    tag = element.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _extract_paragraph(para: Element) -> str:
    """Extract text from a w:p element, applying heading styles."""
    ppr = para.find(f"{{{_NS['w']}}}pPr")
    heading_level = 0
    if ppr is not None:
        pstyle = ppr.find(f"{{{_NS['w']}}}pStyle")
        if pstyle is not None:
            style_val = pstyle.get(f"{{{_NS['w']}}}val", "")
            if style_val.startswith("Heading"):
                try:
                    heading_level = int(style_val.replace("Heading", ""))
                except ValueError:
                    heading_level = 0

    texts: list[str] = []
    for run in para.iter(f"{{{_NS['w']}}}r"):
        for t in run.iter(f"{{{_NS['w']}}}t"):
            if t.text:
                texts.append(t.text)

    text = "".join(texts).strip()
    if not text:
        return ""

    if heading_level > 0:
        return f"{'#' * (heading_level + 1)} {text}"

    return text


def _extract_table(tbl: Element) -> str:
    """Extract a w:tbl element as a markdown table."""
    rows: list[list[str]] = []

    for tr in tbl.iter(f"{{{_NS['w']}}}tr"):
        cells: list[str] = []
        for tc in tr.iter(f"{{{_NS['w']}}}tc"):
            cell_texts: list[str] = []
            for p in tc.iter(f"{{{_NS['w']}}}p"):
                p_text = _extract_paragraph(p)
                if p_text:
                    cell_texts.append(p_text)
            cells.append(" ".join(cell_texts).replace("\n", " ").strip())
        if cells:
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
