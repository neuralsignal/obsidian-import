"""Tests for image bytes validation in media processing."""

import io

import pytest
from conftest import make_png_bytes
from PIL import Image

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.media import _process_image_bytes


def _make_config(
    image_max_bytes: int,
    image_allowed_formats: frozenset[str],
) -> MediaConfig:
    return MediaConfig(
        extract_images=True,
        image_format="png",
        image_max_dimension=0,
        image_max_bytes=image_max_bytes,
        image_allowed_formats=image_allowed_formats,
    )


class TestImageByteSizeValidation:
    def test_rejects_oversized_image_bytes(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=10,
            image_allowed_formats=frozenset({"PNG"}),
        )
        with pytest.raises(ExtractionError, match="exceed configured maximum"):
            _process_image_bytes(img_bytes, config)

    def test_accepts_image_bytes_within_limit(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=len(img_bytes) + 1000,
            image_allowed_formats=frozenset({"PNG"}),
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_zero_max_bytes_disables_size_check(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=0,
            image_allowed_formats=frozenset({"PNG"}),
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_exact_limit_is_accepted(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=len(img_bytes),
            image_allowed_formats=frozenset({"PNG"}),
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0


class TestImageFormatValidation:
    def test_rejects_disallowed_format(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"JPEG"}),
        )
        with pytest.raises(ExtractionError, match="not in the allowed formats"):
            _process_image_bytes(img_bytes, config)

    def test_accepts_allowed_format(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG"}),
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_rejects_with_empty_allowlist(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset(),
        )
        with pytest.raises(ExtractionError, match="not in the allowed formats"):
            _process_image_bytes(img_bytes, config)

    def test_jpeg_format_allowed(self) -> None:
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"JPEG"}),
        )
        result = _process_image_bytes(jpeg_bytes, config)
        assert len(result) > 0

    def test_error_message_includes_format_and_allowlist(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"JPEG", "GIF"}),
        )
        with pytest.raises(ExtractionError, match="PNG") as exc_info:
            _process_image_bytes(img_bytes, config)
        assert "GIF" in str(exc_info.value)
        assert "JPEG" in str(exc_info.value)
