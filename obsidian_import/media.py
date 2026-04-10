"""Shared media utilities for image extraction and processing."""

from __future__ import annotations

import io
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import MediaFile

log = logging.getLogger(__name__)


def generate_media_filename(context: str, index: int, extension: str) -> str:
    """Generate a deterministic filename for an extracted media file.

    The filename does not include the document stem because media files
    live in a per-document folder that already provides the namespace.

    Args:
        context: Location context (e.g. "page3", "slide2").
        index: Image index within that context.
        extension: File extension including dot (e.g. ".png").
    """
    return f"{context}_img{index}{extension}"


def save_media_to_temp(
    image_bytes: bytes,
    filename: str,
    media_config: MediaConfig,
) -> MediaFile:
    """Save image bytes to a temp file, applying config-driven transformations.

    Returns a MediaFile pointing to the temp file.
    """
    processed = _process_image_bytes(image_bytes, media_config)
    target_ext = f".{media_config.image_format}"
    if not filename.endswith(target_ext):
        filename = Path(filename).stem + target_ext

    tmp_dir = Path(tempfile.mkdtemp(prefix="obsidian_media_"))
    dest = tmp_dir / filename
    dest.write_bytes(processed)

    return MediaFile(
        source_path=dest,
        filename=filename,
        media_type="image",
    )


def attempt_save_image(
    get_bytes: Callable[[], bytes | None],
    filename: str,
    media_config: MediaConfig,
    log_context: str,
) -> MediaFile | None:
    """Try to extract and save an image, returning None on failure.

    The get_bytes callable should raise ExtractionError for library-specific
    failures. Returns None if get_bytes returns None or any ExtractionError occurs.
    """
    try:
        img_bytes = get_bytes()
        if img_bytes is None:
            return None
        return save_media_to_temp(img_bytes, filename, media_config)
    except ExtractionError:
        log.warning("Failed to extract image: %s", log_context)
        return None


def _process_image_bytes(image_bytes: bytes, media_config: MediaConfig) -> bytes:
    """Apply format conversion and resizing to image bytes."""
    if media_config.image_max_bytes > 0 and len(image_bytes) > media_config.image_max_bytes:
        raise ExtractionError(
            f"Image bytes ({len(image_bytes)}) exceed configured maximum "
            f"({media_config.image_max_bytes}). Increase media.image_max_bytes to allow larger images."
        )

    try:
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError("Pillow is required for image extraction. Install with: pip install Pillow") from exc

    img = Image.open(io.BytesIO(image_bytes))

    if img.format not in media_config.image_allowed_formats:
        raise ExtractionError(
            f"Image format '{img.format}' is not in the allowed formats: "
            f"{sorted(media_config.image_allowed_formats)}. "
            "Update media.image_allowed_formats to allow this format."
        )

    if media_config.image_max_dimension > 0:
        max_dim = media_config.image_max_dimension
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    output = io.BytesIO()
    target_format = media_config.image_format.upper()
    if target_format == "JPG":
        target_format = "JPEG"

    if img.mode == "RGBA" and target_format == "JPEG":
        img = img.convert("RGB")

    img.save(output, format=target_format)
    return output.getvalue()


def copy_media_files(
    media_files: tuple[MediaFile, ...],
    media_dir: Path,
) -> list[Path]:
    """Copy extracted media files to a per-document media directory.

    Args:
        media_files: Tuple of MediaFile objects to copy.
        media_dir: Destination directory for media files.

    Returns the list of destination paths.
    """
    if not media_files:
        return []

    media_dir.mkdir(parents=True, exist_ok=True)

    destinations: list[Path] = []
    for mf in media_files:
        dest = media_dir / mf.filename
        if not dest.exists():
            shutil.copy2(mf.source_path, dest)
        destinations.append(dest)

    return destinations
