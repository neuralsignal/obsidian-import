"""DOCX text extraction using defusedxml + zipfile.

Opens the DOCX as a ZIP archive, parses word/document.xml to extract
text with structure preservation (headings, paragraphs, tables).
Extracts embedded images from word/media/ when media extraction is enabled.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _DocxZipContext:
    """Groups zipfile-related context for DOCX image extraction."""

    zf: zipfile.ZipFile
    rel_map: dict[str, str]
    path: Path


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

        rel_map = _build_rel_map(zf, fromstring)
        zip_ctx = _DocxZipContext(zf=zf, rel_map=rel_map, path=path)

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
                    extracted, image_index = _extract_docx_images(
                        element,
                        zip_ctx,
                        media_config,
                        image_index,
                    )
                    media_files.extend(extracted)
                    for mf in extracted:
                        embed = f"![[{path.stem}/{mf.filename}]]"
                        text = f"{text}\n\n{embed}" if text else embed

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


def _build_rel_map(zf: zipfile.ZipFile, fromstring: object) -> dict[str, str]:
    """Build relationship ID to target path map from document.xml.rels."""
    rel_map: dict[str, str] = {}
    if "word/_rels/document.xml.rels" not in zf.namelist():
        return rel_map

    rels_xml = zf.read("word/_rels/document.xml.rels")
    rels_root = fromstring(rels_xml)  # type: ignore[operator]
    for rel in rels_root:
        rid = rel.get("Id", "")
        target = rel.get("Target", "")
        if rid and target:
            rel_map[rid] = target
    return rel_map


def _extract_docx_images(
    element: Element,
    zip_ctx: _DocxZipContext,
    media_config: MediaConfig,
    image_index: int,
) -> tuple[list[MediaFile], int]:
    """Extract images from drawing elements in a paragraph.

    Returns the list of extracted MediaFiles and the updated image_index.
    """
    media_files: list[MediaFile] = []
    drawings = element.findall(f".//{{{_NS['w']}}}drawing")
    for drawing in drawings:
        blips = drawing.findall(f".//{{{_NS['a']}}}blip")
        for blip in blips:
            embed_id = blip.get(f"{{{_NS['r']}}}embed", "")
            if not embed_id or embed_id not in zip_ctx.rel_map:
                continue
            target = zip_ctx.rel_map[embed_id]
            media_path = f"word/{target}" if not target.startswith("word/") else target
            if ".." in Path(media_path).parts:
                continue
            if not media_path.startswith("word/media/"):
                continue
            if media_path not in zip_ctx.zf.namelist():
                continue
            image_index += 1
            img_bytes = zip_ctx.zf.read(media_path)
            orig_ext = Path(media_path).suffix
            filename = generate_media_filename("doc", image_index, orig_ext)
            try:
                mf = save_media_to_temp(img_bytes, filename, media_config)
                media_files.append(mf)
            except ExtractionError:
                log.warning(
                    "Failed to extract image %s from %s",
                    media_path,
                    zip_ctx.path,
                )
    return media_files, image_index


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
