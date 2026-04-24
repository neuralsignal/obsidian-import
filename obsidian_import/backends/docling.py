"""High-quality document extraction using docling.

Requires the [docling] extra: pip install obsidian-import[docling]
Supports image extraction via PdfPipelineOptions when available.
"""

from __future__ import annotations

import importlib.util
import io
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from obsidian_import.config import MediaConfig

if TYPE_CHECKING:
    from docling.datamodel.document import DoclingDocument
    from docling.document_converter import DocumentConverter

from obsidian_import.exceptions import BackendNotAvailableError, ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.formatting import make_media_wikilink
from obsidian_import.media import attempt_save_image, generate_media_filename
from obsidian_import.timeout import run_with_timeout

log = logging.getLogger(__name__)


def extract(path: Path, timeout_seconds: int, media_config: MediaConfig) -> ExtractionResult:
    """Extract text and images using docling for high-quality document conversion."""
    if importlib.util.find_spec("docling") is None:
        raise BackendNotAvailableError("docling is not installed. Install with: pip install obsidian-import[docling]")

    def _do_extract() -> ExtractionResult:
        converter = _build_converter(media_config)
        doc_result = converter.convert(str(path))
        doc = doc_result.document

        media_files: list[MediaFile] = []
        if media_config.extract_images:
            media_files = _extract_docling_images(doc, path, media_config)

        text = doc.export_to_markdown()
        if not text or not text.strip():
            text = f"*No text content extracted from `{path.name}`.*"

        result_media = tuple(media_files)
        if media_files:
            text = _replace_image_refs_with_wikilinks(text, media_files, path.stem)

        return ExtractionResult(markdown=text, media_files=result_media)

    return run_with_timeout(_do_extract, timeout_seconds, "docling", path)


def _build_converter(media_config: MediaConfig) -> DocumentConverter:
    """Build a DocumentConverter with optional image pipeline options."""
    from docling.document_converter import DocumentConverter

    if not media_config.extract_images:
        return DocumentConverter()

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions(generate_picture_images=True)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
    except (ImportError, AttributeError):
        log.warning("Docling image pipeline options not available; using defaults")
        return DocumentConverter()


def _extract_docling_images(doc: DoclingDocument, path: Path, media_config: MediaConfig) -> list[MediaFile]:
    """Extract images from a docling Document object."""
    media_files: list[MediaFile] = []

    pictures = getattr(doc, "pictures", None)
    if not pictures:
        return media_files

    for i, picture in enumerate(pictures, 1):
        filename = generate_media_filename("fig", i, ".png")
        mf = attempt_save_image(
            _make_docling_picture_reader(picture, doc, i),
            filename,
            media_config,
            f"picture {i} from {path} via docling",
        )
        if mf is not None:
            media_files.append(mf)

    return media_files


def _make_docling_picture_reader(picture: object, doc: DoclingDocument, index: int) -> Callable[[], bytes | None]:
    """Return a callable that extracts image bytes from a docling picture."""

    def _read() -> bytes | None:
        try:
            pil_image = picture.get_image(doc=doc)  # type: ignore[union-attr]
        except (AttributeError, ValueError) as exc:
            raise ExtractionError(f"docling image {index} unavailable: {exc}") from exc
        if pil_image is None:
            return None
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return buf.getvalue()

    return _read


def _replace_image_refs_with_wikilinks(markdown: str, media_files: list[MediaFile], doc_stem: str) -> str:
    """Replace standard markdown image references with Obsidian wikilinks."""
    media_iter = iter(media_files)

    def _match_image_ref(match: re.Match[str]) -> str:
        mf = next(media_iter, None)
        if mf is not None:
            return make_media_wikilink(doc_stem, mf.filename)
        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\([^)]+\)", _match_image_ref, markdown)
