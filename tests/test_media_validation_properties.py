"""Property-based tests for image validation helper functions."""

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
