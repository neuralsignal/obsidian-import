"""Shared media utilities for image extraction and processing."""

from __future__ import annotations

import io
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

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


def _validate_byte_size(image_bytes: bytes, media_config: MediaConfig) -> None:
    """Raise ExtractionError if image bytes exceed the configured maximum."""
    if media_config.image_max_bytes > 0 and len(image_bytes) > media_config.image_max_bytes:
        raise ExtractionError(
            f"Image bytes ({len(image_bytes)}) exceed configured maximum "
            f"({media_config.image_max_bytes}). Increase media.image_max_bytes to allow larger images."
        )


def _open_image_safely(image_bytes: bytes, media_config: MediaConfig) -> Image.Image:
    """Open image bytes with Pillow and validate pixel count.

    Caller must have configured Image.MAX_IMAGE_PIXELS before invocation.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError("Pillow is required for image extraction. Install with: pip install Pillow") from exc

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Image.DecompressionBombError as exc:
        raise ExtractionError(
            f"Image exceeds maximum pixel limit ({media_config.image_max_pixels} pixels). "
            "This may be a decompression bomb. Increase media.image_max_pixels to allow larger images."
        ) from exc

    if media_config.image_max_pixels > 0:
        pixel_count = img.width * img.height
        if pixel_count > media_config.image_max_pixels:
            raise ExtractionError(
                f"Image pixel count ({pixel_count}) exceeds maximum "
                f"({media_config.image_max_pixels}). "
                "Increase media.image_max_pixels to allow larger images."
            )

    return img


def _validate_image_format(img: Image.Image, media_config: MediaConfig) -> None:
    """Raise ExtractionError if the image format is not in the allow-list."""
    if img.format not in media_config.image_allowed_formats:
        raise ExtractionError(
            f"Image format '{img.format}' is not in the allowed formats: "
            f"{sorted(media_config.image_allowed_formats)}. "
            "Update media.image_allowed_formats to allow this format."
        )


def _resize_if_needed(img: Image.Image, media_config: MediaConfig) -> Image.Image:
    """Thumbnail-resize the image if it exceeds the max dimension."""
    if media_config.image_max_dimension > 0:
        max_dim = media_config.image_max_dimension
        if img.width > max_dim or img.height > max_dim:
            from PIL import Image

            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    return img


def _encode_image(img: Image.Image, media_config: MediaConfig) -> bytes:
    """Encode the image to the configured format, handling RGBA→RGB for JPEG."""
    target_format = media_config.image_format.upper()
    if target_format == "JPG":
        target_format = "JPEG"

    if img.mode == "RGBA" and target_format == "JPEG":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format=target_format)
    return output.getvalue()


def _process_image_bytes(image_bytes: bytes, media_config: MediaConfig) -> bytes:
    """Apply format conversion and resizing to image bytes.

    Scopes Image.MAX_IMAGE_PIXELS mutation to this function's lifetime so it
    cannot leak across threads or callers (see PR #163).
    """
    _validate_byte_size(image_bytes, media_config)

    try:
        from PIL import Image
    except ImportError as exc:
        raise ExtractionError("Pillow is required for image extraction. Install with: pip install Pillow") from exc

    old_limit = Image.MAX_IMAGE_PIXELS
    try:
        if media_config.image_max_pixels > 0:
            Image.MAX_IMAGE_PIXELS = media_config.image_max_pixels
        else:
            Image.MAX_IMAGE_PIXELS = None

        img = _open_image_safely(image_bytes, media_config)
        _validate_image_format(img, media_config)
        img = _resize_if_needed(img, media_config)
        return _encode_image(img, media_config)
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit


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
