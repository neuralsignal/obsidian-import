"""High-quality document extraction using docling.

Requires the [docling] extra: pip install obsidian-import[docling]
Supports image extraction via PdfPipelineOptions when available.
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import BackendNotAvailableError, ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import generate_media_filename, save_media_to_temp
from obsidian_import.timeout import run_with_timeout

log = logging.getLogger(__name__)


def extract(path: Path, timeout_seconds: int, media_config: MediaConfig) -> ExtractionResult:
    """Extract text and images using docling for high-quality document conversion."""
    try:
        import importlib.util

        if importlib.util.find_spec("docling") is None:
            raise ImportError("docling not found")
    except ImportError as exc:
        raise BackendNotAvailableError(
            "docling is not installed. Install with: pip install obsidian-import[docling]"
        ) from exc

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

        if media_files:
            text = _replace_image_refs_with_wikilinks(text, media_files, media_config)

        return ExtractionResult(markdown=text, media_files=tuple(media_files))

    return run_with_timeout(_do_extract, timeout_seconds, "docling", path)


def _build_converter(media_config: MediaConfig) -> object:
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


def _extract_docling_images(doc: object, path: Path, media_config: MediaConfig) -> list[MediaFile]:
    """Extract images from a docling Document object."""
    media_files: list[MediaFile] = []

    pictures = getattr(doc, "pictures", None)
    if not pictures:
        return media_files

    for i, picture in enumerate(pictures, 1):
        try:
            pil_image = picture.get_image(doc=doc)
            if pil_image is None:
                continue

            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            img_bytes = buf.getvalue()

            filename = generate_media_filename(path.stem, "fig", i, ".png")
            mf = save_media_to_temp(img_bytes, filename, media_config)
            media_files.append(mf)
        except (ExtractionError, AttributeError, ValueError):
            log.warning("Failed to extract picture %d from %s via docling", i, path)

    return media_files


def _replace_image_refs_with_wikilinks(markdown: str, media_files: list[MediaFile], media_config: MediaConfig) -> str:
    """Replace standard markdown image references with Obsidian wikilinks."""
    result = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        lambda m: _match_image_ref(m, media_files, media_config),
        markdown,
    )
    return result


def _match_image_ref(
    match: re.Match[str],
    media_files: list[MediaFile],
    media_config: MediaConfig,
) -> str:
    """Replace a single markdown image ref with the corresponding wikilink."""
    if media_files:
        mf = media_files[0]
        media_files.pop(0)
        return f"![[{media_config.media_subfolder}/{mf.filename}]]"
    return match.group(0)
