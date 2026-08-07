"""Document extraction using anydoc, the default backend for document formats.

anydoc (https://github.com/firecrawl/anydoc) is a Rust converter that turns
PDF, Word, PowerPoint, Excel, OpenDocument, RTF, EPUB, and CSV inputs into
GitHub-Flavored Markdown. It ships as a compiled wheel with no model
downloads, so it is a required dependency rather than an extra.

Two behaviors of the upstream library shape this backend:

- Embedded images are absent from anydoc's Markdown: an embedded image renders
  as its alt text, or as nothing when it has none. The images live on the
  document model instead, which this backend reads to recover them, and
  ``anydoc_placement`` splices their wikilinks back in at the position they
  occupied in the source document.
- PDF has no document-model form upstream (it converts straight to Markdown),
  so PDF extraction through this backend is text only. The bundled default
  keeps ``backends.pdf: native`` for that reason.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anydoc import Asset, Document

from obsidian_import.anydoc_placement import place_media_embeds
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import BackendNotAvailableError, ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import attempt_save_image, generate_media_filename
from obsidian_import.timeout import TimeoutContext, run_with_timeout

log = logging.getLogger(__name__)

_ASSET_FILENAME_CONTEXT = "asset"
_IMAGE_MEDIA_TYPE_PREFIX = "image/"
_FORMATS_WITHOUT_DOCUMENT_MODEL = frozenset({"pdf"})


def extract(path: Path, timeout_seconds: int, isolation: str, media_config: MediaConfig) -> ExtractionResult:
    """Extract text and embedded images from a document using anydoc."""
    if importlib.util.find_spec("anydoc") is None:
        raise BackendNotAvailableError(
            "anydoc is not installed. Install with: pip install firecrawl-anydoc "
            "(it ships as a required dependency of obsidian-import)"
        )

    ctx = TimeoutContext(timeout_seconds=timeout_seconds, label="anydoc", path=path, isolation=isolation)
    return run_with_timeout(_extract_anydoc, (path, media_config), ctx)


def _extract_anydoc(path: Path, media_config: MediaConfig) -> ExtractionResult:
    """Internal anydoc extraction logic (module-level for process isolation)."""
    import anydoc

    data = path.read_bytes()
    doc_format = anydoc.format_from_bytes(data) or anydoc.format_from_extension(path.suffix)

    text = _convert_to_markdown(data, doc_format, path)

    media_by_asset_id: dict[int, MediaFile] = {}
    if media_config.extract_images:
        document = _read_document_model(data, doc_format, path)
        if document is not None:
            media_by_asset_id = _extract_assets(document, path, media_config)
            if media_by_asset_id:
                text = place_media_embeds(text, document, media_by_asset_id, path.stem)

    if not text.strip():
        text = f"*No text content extracted from `{path.name}`.*"

    return ExtractionResult(markdown=text, media_files=tuple(media_by_asset_id.values()))


def _convert_to_markdown(data: bytes, doc_format: str | None, path: Path) -> str:
    """Convert document bytes to markdown, translating anydoc failures."""
    import anydoc

    try:
        return anydoc.to_markdown_bytes(data, doc_format)
    except anydoc.ConvertError as exc:
        raise ExtractionError(
            f"anydoc could not convert {path} (detected format: {doc_format or 'unrecognized'}): {exc}. "
            "Set a different backend for this extension under the `backends` config section, "
            "or convert the file to a supported format first."
        ) from exc


def _read_document_model(data: bytes, doc_format: str | None, path: Path) -> Document | None:
    """Parse the document model that carries the embedded images, or None if unavailable."""
    import anydoc

    if doc_format in _FORMATS_WITHOUT_DOCUMENT_MODEL:
        log.info("anydoc exposes no document model for %s; extracting text only from %s", doc_format, path)
        return None

    try:
        return anydoc.to_document(data, doc_format)
    except anydoc.ConvertError as exc:
        log.warning(
            "anydoc could not read the document model of %s (%s); text was extracted without images. "
            "Set backends for this extension to a native backend to recover images.",
            path,
            exc,
        )
        return None


def _extract_assets(document: Document, path: Path, media_config: MediaConfig) -> dict[int, MediaFile]:
    """Save the document's embedded images, keyed by the asset id that references them."""
    media_by_asset_id: dict[int, MediaFile] = {}
    image_assets = [a for a in document.assets if a.media_type.startswith(_IMAGE_MEDIA_TYPE_PREFIX)]
    for index, asset in enumerate(image_assets, 1):
        filename = generate_media_filename(_ASSET_FILENAME_CONTEXT, index, f".{media_config.image_format}")
        media_file = attempt_save_image(
            _make_asset_reader(asset),
            filename,
            media_config,
            f"asset {asset.id} ({asset.media_type}) from {path} via anydoc",
        )
        if media_file is not None:
            media_by_asset_id[asset.id] = media_file

    return media_by_asset_id


def _make_asset_reader(asset: Asset) -> Callable[[], bytes | None]:
    """Return a callable yielding the raw bytes of an anydoc asset."""

    def _read() -> bytes | None:
        return asset.data

    return _read
