"""PDF text extraction using pdfplumber + pypdf.

Extracts text with layout preservation, tables as markdown, form field metadata,
and embedded images via pypdf XObject extraction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from obsidian_import.config import MediaConfig

if TYPE_CHECKING:
    from pypdf import PdfReader
    from pypdf.generic import EncodedStreamObject

from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.formatting import render_markdown_table
from obsidian_import.media import attempt_save_image, generate_media_filename
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
            page_content, page_media = _extract_page_content(
                page,
                reader,
                i,
                path,
                media_config,
            )
            media_files.extend(page_media)
            if page_content:
                sections.append(page_content)

    return ExtractionResult(
        markdown="\n\n".join(sections),
        media_files=tuple(media_files),
    )


def _extract_page_content(
    page: object,
    reader: PdfReader,
    page_number: int,
    path: Path,
    media_config: MediaConfig,
) -> tuple[str, list[MediaFile]]:
    """Extract tables, text, and images from a single PDF page.

    Returns the assembled page markdown and a list of extracted media files.
    """
    page_sections: list[str] = [f"\n## Page {page_number}\n"]
    media_files: list[MediaFile] = []

    tables = page.extract_tables()  # type: ignore[attr-defined]
    if tables:
        for table in tables:
            if not table or not table[0]:
                continue
            cleaned = [[str(cell or "").strip() for cell in row] for row in table]
            page_sections.append(render_markdown_table(cleaned))

    text = page.extract_text()  # type: ignore[attr-defined]
    if text:
        page_sections.append(text.strip())

    if media_config.extract_images:
        page_images = _extract_page_images(reader, page_number - 1, path, media_config)
        for mf in page_images:
            media_files.append(mf)
            page_sections.append(f"![[{path.stem}/{mf.filename}]]")

    if len(page_sections) > 1:
        return "\n".join(page_sections), media_files
    return "", media_files


def _get_page_xobjects(reader: PdfReader, page_index: int) -> dict | None:
    """Access the XObject dictionary for a PDF page.

    Returns the XObject dict, or None if no XObjects exist.
    Raises ExtractionError if the page is inaccessible or malformed.
    """
    try:
        page = reader.pages[page_index]
    except (IndexError, KeyError) as exc:
        raise ExtractionError(f"page {page_index} not accessible: {exc}") from exc

    try:
        resources = page.get("/Resources")
    except AttributeError as exc:
        raise ExtractionError(f"malformed page resources: {exc}") from exc

    if resources is None:
        return None

    xobjects = resources.get("/XObject")
    if xobjects is None:
        return None

    return xobjects.get_object()


def _extract_page_images(
    reader: PdfReader,
    page_index: int,
    path: Path,
    media_config: MediaConfig,
) -> list[MediaFile]:
    """Extract images from a single PDF page via pypdf XObject resources."""
    try:
        xobject_dict = _get_page_xobjects(reader, page_index)
    except ExtractionError:
        log.warning("Failed to read page resources on page %d of %s", page_index + 1, path)
        return []

    if xobject_dict is None:
        return []

    media_files: list[MediaFile] = []
    image_index = 0
    for obj_name in xobject_dict:
        try:
            xobj = xobject_dict[obj_name].get_object()
            subtype = xobj.get("/Subtype")
            if subtype != "/Image":
                continue

            image_index += 1
            ext = _pdf_image_extension(xobj)
            filename = generate_media_filename(f"page{page_index + 1}", image_index, ext)
            mf = attempt_save_image(
                _make_pdf_xobj_reader(xobj, obj_name),
                filename,
                media_config,
                f"{obj_name} from page {page_index + 1} of {path}",
            )
            if mf is not None:
                media_files.append(mf)
        except KeyError:
            log.warning("Failed to access XObject %s on page %d of %s", obj_name, page_index + 1, path)

    return media_files


def _make_pdf_xobj_reader(xobj: EncodedStreamObject, obj_name: str) -> Callable[[], bytes]:
    """Return a callable that decodes image bytes from a PDF XObject."""

    def _read() -> bytes:
        try:
            return xobj.get_data()
        except (ValueError, KeyError) as exc:
            raise ExtractionError(f"PDF image {obj_name} decode failed: {exc}") from exc

    return _read


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
