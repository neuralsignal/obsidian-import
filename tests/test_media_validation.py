"""Tests for image bytes validation in media processing."""

import io

import pytest
from conftest import make_png_bytes
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.media import (
    _encode_image,
    _open_image_safely,
    _process_image_bytes,
    _resize_if_needed,
    _validate_byte_size,
    _validate_image_format,
)


def _make_config(
    image_max_bytes: int,
    image_allowed_formats: frozenset[str],
    image_max_pixels: int = 50_000_000,
) -> MediaConfig:
    return MediaConfig(
        extract_images=True,
        image_format="png",
        image_max_dimension=0,
        image_max_bytes=image_max_bytes,
        image_max_pixels=image_max_pixels,
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


class TestMaxImagePixelsRestored:
    """Verify that _process_image_bytes does not leak global PIL state."""

    def test_restores_max_pixels_after_successful_call(self) -> None:
        from PIL import Image as _Image

        sentinel = _Image.MAX_IMAGE_PIXELS
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=1_000,
        )
        _process_image_bytes(img_bytes, config)
        assert sentinel == _Image.MAX_IMAGE_PIXELS

    def test_restores_max_pixels_after_error(self) -> None:
        from PIL import Image as _Image

        sentinel = _Image.MAX_IMAGE_PIXELS
        img_bytes = make_png_bytes(200, 200, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=100,
        )
        with pytest.raises(ExtractionError):
            _process_image_bytes(img_bytes, config)
        assert sentinel == _Image.MAX_IMAGE_PIXELS


class TestImagePixelCountValidation:
    def test_pillow_decompression_bomb_guard_rejects_large_image(self) -> None:
        img_bytes = make_png_bytes(200, 200, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=100,
        )
        with pytest.raises(ExtractionError, match="pixel limit"):
            _process_image_bytes(img_bytes, config)

    def test_explicit_check_rejects_image_between_limit_and_double(self) -> None:
        img_bytes = make_png_bytes(13, 13, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=100,
        )
        with pytest.raises(ExtractionError, match="pixel count"):
            _process_image_bytes(img_bytes, config)

    def test_accepts_image_within_pixel_limit(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=1_000,
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_exact_pixel_limit_is_accepted(self) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=100,
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_zero_max_pixels_disables_pixel_check(self) -> None:
        img_bytes = make_png_bytes(100, 100, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=0,
        )
        result = _process_image_bytes(img_bytes, config)
        assert len(result) > 0

    def test_error_message_includes_pixel_count_and_limit(self) -> None:
        img_bytes = make_png_bytes(13, 13, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
            image_max_pixels=100,
        )
        with pytest.raises(ExtractionError, match="169") as exc_info:
            _process_image_bytes(img_bytes, config)
        assert "100" in str(exc_info.value)


class TestValidateByteSizeProperties:
    @given(
        width=st.integers(min_value=1, max_value=20),
        height=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_zero_limit_never_raises(self, width: int, height: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGB")
        _validate_byte_size(img_bytes, _make_config(image_max_bytes=0, image_allowed_formats=frozenset({"PNG"})))

    @given(extra=st.integers(min_value=1, max_value=1000))
    @settings(max_examples=30)
    def test_always_raises_when_over_limit(self, extra: int) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        limit = len(img_bytes) - extra
        if limit < 1:
            return
        with pytest.raises(ExtractionError, match="exceed configured maximum"):
            _validate_byte_size(
                img_bytes,
                _make_config(image_max_bytes=limit, image_allowed_formats=frozenset({"PNG"})),
            )

    @given(extra=st.integers(min_value=0, max_value=1000))
    @settings(max_examples=30)
    def test_never_raises_when_within_limit(self, extra: int) -> None:
        img_bytes = make_png_bytes(10, 10, "RGB")
        _validate_byte_size(
            img_bytes,
            _make_config(image_max_bytes=len(img_bytes) + extra, image_allowed_formats=frozenset({"PNG"})),
        )


class TestValidateImageFormatProperties:
    @given(
        width=st.integers(min_value=1, max_value=20),
        height=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_png_accepted_when_in_allowlist(self, width: int, height: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGB")
        config = _make_config(image_max_bytes=50_000_000, image_allowed_formats=frozenset({"PNG"}))
        img = _open_image_safely(img_bytes, config)
        _validate_image_format(img, config)

    @given(
        width=st.integers(min_value=1, max_value=20),
        height=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_png_rejected_when_not_in_allowlist(self, width: int, height: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGB")
        config = _make_config(image_max_bytes=50_000_000, image_allowed_formats=frozenset({"JPEG"}))
        img = _open_image_safely(img_bytes, config)
        with pytest.raises(ExtractionError, match="not in the allowed formats"):
            _validate_image_format(img, config)


class TestResizeIfNeededProperties:
    @given(
        width=st.integers(min_value=1, max_value=200),
        height=st.integers(min_value=1, max_value=200),
        max_dim=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=50)
    def test_output_within_bounds(self, width: int, height: int, max_dim: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGB")
        config = _make_config(
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
        )
        config_with_dim = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=max_dim,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
        )
        img = _open_image_safely(img_bytes, config)
        result = _resize_if_needed(img, config_with_dim)
        assert result.width <= max(max_dim, width)
        assert result.height <= max(max_dim, height)

    @given(
        width=st.integers(min_value=1, max_value=50),
        height=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=30)
    def test_zero_dimension_preserves_size(self, width: int, height: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGB")
        config = _make_config(image_max_bytes=50_000_000, image_allowed_formats=frozenset({"PNG"}))
        img = _open_image_safely(img_bytes, config)
        result = _resize_if_needed(img, config)
        assert result.width == width
        assert result.height == height


class TestEncodeImageProperties:
    @given(
        width=st.integers(min_value=1, max_value=30),
        height=st.integers(min_value=1, max_value=30),
        mode=st.sampled_from(["RGB", "RGBA", "L"]),
        fmt=st.sampled_from(["png", "jpeg", "jpg"]),
    )
    @settings(max_examples=50)
    def test_produces_valid_image_bytes(self, width: int, height: int, mode: str, fmt: str) -> None:
        img_bytes = make_png_bytes(width, height, mode)
        config = MediaConfig(
            extract_images=True,
            image_format=fmt,
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG"}),
        )
        img = _open_image_safely(img_bytes, config)
        result = _encode_image(img, config)
        decoded = Image.open(io.BytesIO(result))
        expected_format = "JPEG" if fmt.upper() in ("JPG", "JPEG") else fmt.upper()
        assert decoded.format == expected_format

    @given(
        width=st.integers(min_value=1, max_value=20),
        height=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20)
    def test_rgba_converted_to_rgb_for_jpeg(self, width: int, height: int) -> None:
        img_bytes = make_png_bytes(width, height, "RGBA")
        config = MediaConfig(
            extract_images=True,
            image_format="jpeg",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG"}),
        )
        img = _open_image_safely(img_bytes, config)
        result = _encode_image(img, config)
        decoded = Image.open(io.BytesIO(result))
        assert decoded.mode == "RGB"
