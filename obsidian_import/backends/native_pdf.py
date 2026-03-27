"""PDF text extraction using pdfplumber + pypdf.

Extracts text with layout preservation, tables as markdown, form field metadata,
and embedded images via pypdf XObject extraction.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from obsidian_import.config import MediaConfig

if TYPE_CHECKING:
    from pypdf import PdfReader
    from pypdf.generic import EncodedStreamObject

from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.formatting import render_markdown_table
from obsidian_import.media import generate_media_filename, save_media_to_temp
from obsidian_import.timeout import run_with_timeout

log = logging.getLogger(__name__)


def extract(path: Path, timeout_seconds: int, media_config: MediaConfig) -> ExtractionResult:
    """Extract text, tables, and images from a PDF file, returning ExtractionResult."""
    return run_with_timeout(lambda: _extract_pdf(path, media_config), timeout_seconds, "PDF", path)


def _extract_pdf(path: Path, media_config: MediaConfig) -> ExtractionResult:
    """Internal PDF extraction logic."""
    import pdfplumber
    from pypdf import PdfReader

    sections: list[str] = []
    media_files: list[MediaFile] = []

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
                    cleaned = [[str(cell or "").strip() for cell in row] for row in table]
                    page_sections.append(render_markdown_table(cleaned))

            text = page.extract_text()
            if text:
                page_sections.append(text.strip())

            if media_config.extract_images:
                page_images = _extract_page_images(reader, i - 1, path, media_config)
                for mf in page_images:
                    media_files.append(mf)
                    page_sections.append(f"![[{path.stem}/{mf.filename}]]")

            if len(page_sections) > 1:
                sections.append("\n".join(page_sections))

    return ExtractionResult(
        markdown="\n\n".join(sections),
        media_files=tuple(media_files),
    )


def _extract_page_images(
    reader: PdfReader,
    page_index: int,
    path: Path,
    media_config: MediaConfig,
) -> list[MediaFile]:
    """Extract images from a single PDF page via pypdf XObject resources."""
    media_files: list[MediaFile] = []
    try:
        page = reader.pages[page_index]
        resources = page.get("/Resources")
        if resources is None:
            return []

        xobjects = resources.get("/XObject")
        if xobjects is None:
            return []

        xobject_dict = xobjects.get_object()
        image_index = 0
        for obj_name in xobject_dict:
            xobj = xobject_dict[obj_name].get_object()
            subtype = xobj.get("/Subtype")
            if subtype != "/Image":
                continue

            image_index += 1
            try:
                img_bytes = xobj.get_data()
                ext = _pdf_image_extension(xobj)
                filename = generate_media_filename(f"page{page_index + 1}", image_index, ext)
                mf = save_media_to_temp(img_bytes, filename, media_config)
                media_files.append(mf)
            except (ExtractionError, ValueError, KeyError):
                log.warning(
                    "Failed to extract image %s from page %d of %s",
                    obj_name,
                    page_index + 1,
                    path,
                )
    except (KeyError, AttributeError):
        log.warning("Failed to access XObjects on page %d of %s", page_index + 1, path)

    return media_files


def _pdf_image_extension(xobj: EncodedStreamObject) -> str:
    """Determine file extension from PDF image XObject filter."""
    filter_val = getattr(xobj, "get", lambda k: None)("/Filter")
    if filter_val is None:
        return ".png"
    filter_str = str(filter_val)
    if "DCTDecode" in filter_str:
        return ".jpeg"
    if "JPXDecode" in filter_str:
        return ".jp2"
    if "CCITTFaxDecode" in filter_str:
        return ".tiff"
    return ".png"
