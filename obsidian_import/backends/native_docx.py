"""DOCX text extraction using defusedxml + zipfile.

Opens the DOCX as a ZIP archive, parses word/document.xml to extract
text with structure preservation (headings, paragraphs, tables).
Extracts embedded images from word/media/ when media extraction is enabled.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.formatting import render_markdown_table
from obsidian_import.media import generate_media_filename, save_media_to_temp
from obsidian_import.timeout import run_with_timeout

log = logging.getLogger(__name__)

_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def extract(path: Path, timeout_seconds: int, media_config: MediaConfig) -> ExtractionResult:
    """Extract text and images from a DOCX file, returning ExtractionResult."""
    return run_with_timeout(lambda: _extract_docx(path, media_config), timeout_seconds, "DOCX", path)


def _extract_docx(path: Path, media_config: MediaConfig) -> ExtractionResult:
    """Internal DOCX extraction logic."""
    from defusedxml.ElementTree import fromstring

    if not zipfile.is_zipfile(str(path)):
        raise ExtractionError(f"Not a valid DOCX (ZIP) file: {path}")

    with zipfile.ZipFile(str(path), "r") as zf:
        if "word/document.xml" not in zf.namelist():
            raise ExtractionError(f"No word/document.xml found in: {path}")

        doc_xml = zf.read("word/document.xml")
        root = fromstring(doc_xml)

        rel_map: dict[str, str] = {}
        if "word/_rels/document.xml.rels" in zf.namelist():
            rels_xml = zf.read("word/_rels/document.xml.rels")
            rels_root = fromstring(rels_xml)
            for rel in rels_root:
                rid = rel.get("Id", "")
                target = rel.get("Target", "")
                if rid and target:
                    rel_map[rid] = target

        media_files: list[MediaFile] = []
        image_index = 0

        sections: list[str] = [f"# {path.stem}"]
        body = root.find(f"{{{_NS['w']}}}body")
        if body is None:
            return ExtractionResult(
                markdown=f"# {path.stem}\n\n*No body content found.*",
                media_files=(),
            )

        for element in body:
            tag = _local_name(element)

            if tag == "p":
                text = _extract_paragraph(element)

                if media_config.extract_images:
                    drawings = element.findall(f".//{{{_NS['w']}}}drawing")
                    for drawing in drawings:
                        blips = drawing.findall(f".//{{{_NS['a']}}}blip")
                        for blip in blips:
                            embed_id = blip.get(f"{{{_NS['r']}}}embed", "")
                            if embed_id and embed_id in rel_map:
                                target = rel_map[embed_id]
                                media_path = f"word/{target}" if not target.startswith("word/") else target
                                if media_path in zf.namelist():
                                    image_index += 1
                                    img_bytes = zf.read(media_path)
                                    orig_ext = Path(media_path).suffix
                                    filename = generate_media_filename("doc", image_index, orig_ext)
                                    try:
                                        mf = save_media_to_temp(img_bytes, filename, media_config)
                                        media_files.append(mf)
                                        if text:
                                            text += f"\n\n![[{path.stem}/{mf.filename}]]"
                                        else:
                                            text = f"![[{path.stem}/{mf.filename}]]"
                                    except ExtractionError:
                                        log.warning(
                                            "Failed to extract image %s from %s",
                                            media_path,
                                            path,
                                        )

                if text:
                    sections.append(text)

            elif tag == "tbl":
                table_md = _extract_table(element)
                if table_md:
                    sections.append(table_md)

    return ExtractionResult(
        markdown="\n\n".join(sections),
        media_files=tuple(media_files),
    )


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

    return render_markdown_table(rows)
