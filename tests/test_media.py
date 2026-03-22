"""Tests for media utilities module."""

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import copy_media_files, generate_media_filename, save_media_to_temp


def _make_png_bytes(width: int, height: int, mode: str = "RGB") -> bytes:
    """Create minimal PNG image bytes."""
    color: str | tuple[int, ...] = (255, 0, 0, 128) if mode == "RGBA" else (128,) if mode == "L" else "red"
    img = Image.new(mode, (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _test_media_config() -> MediaConfig:
    return MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)


class TestGenerateMediaFilename:
    def test_basic_filename(self):
        result = generate_media_filename("page1", 1, ".png")
        assert result == "page1_img1.png"

    def test_different_contexts(self):
        assert "doc" in generate_media_filename("doc", 1, ".png")
        assert "slide5" in generate_media_filename("slide5", 1, ".png")
        assert "fig" in generate_media_filename("fig", 1, ".png")

    def test_context_and_index_in_result(self):
        result = generate_media_filename("page3", 7, ".jpeg")
        assert result == "page3_img7.jpeg"


class TestGenerateMediaFilenameProperties:
    @given(
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg", ".gif", ".bmp"]),
    )
    @settings(max_examples=100)
    def test_always_ends_with_extension(self, context: str, index: int, ext: str) -> None:
        result = generate_media_filename(context, index, ext)
        assert result.endswith(ext)

    @given(
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg"]),
    )
    @settings(max_examples=100)
    def test_contains_img_prefix_with_index(self, context: str, index: int, ext: str) -> None:
        result = generate_media_filename(context, index, ext)
        assert f"_img{index}" in result

    @given(
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg"]),
    )
    @settings(max_examples=100)
    def test_starts_with_context(self, context: str, index: int, ext: str) -> None:
        result = generate_media_filename(context, index, ext)
        assert result.startswith(context)

    @given(
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg", ".gif"]),
    )
    @settings(max_examples=50)
    def test_deterministic(self, context: str, index: int, ext: str) -> None:
        a = generate_media_filename(context, index, ext)
        b = generate_media_filename(context, index, ext)
        assert a == b


class TestSaveMediaToTemp:
    def test_saves_png(self):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)
        assert mf.source_path.exists()
        assert mf.filename == "test.png"
        assert mf.media_type == "image"

    def test_converts_format_to_png(self):
        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)
        mf = save_media_to_temp(jpeg_bytes, "test.jpeg", config)
        assert mf.filename.endswith(".png")

    def test_respects_max_dimension(self):
        img_bytes = _make_png_bytes(200, 200)
        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=50)
        mf = save_media_to_temp(img_bytes, "big.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.width <= 50
        assert saved_img.height <= 50


class TestPilImportError:
    def test_raises_extraction_error_when_pillow_missing(self) -> None:
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "PIL" or name.startswith("PIL."):
                raise ImportError("No module named 'PIL'")
            return original_import(name, *args, **kwargs)

        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()

        import obsidian_import.media as media_mod

        with (
            patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}),
            patch("builtins.__import__", side_effect=_mock_import),
            pytest.raises(ExtractionError, match="Pillow is required"),
        ):
            media_mod._process_image_bytes(img_bytes, config)


class TestJpgNormalization:
    def test_jpg_format_produces_valid_jpeg(self) -> None:
        img_bytes = _make_png_bytes(10, 10)
        config = MediaConfig(extract_images=True, image_format="jpg", image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        assert mf.filename.endswith(".jpg")
        saved_img = Image.open(mf.source_path)
        assert saved_img.format == "JPEG"

    def test_uppercase_jpg_format(self) -> None:
        img_bytes = _make_png_bytes(10, 10)
        config = MediaConfig(extract_images=True, image_format="JPG", image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.format == "JPEG"


class TestRgbaToJpegConversion:
    def test_rgba_image_saved_as_jpeg(self) -> None:
        img_bytes = _make_png_bytes(10, 10, mode="RGBA")
        config = MediaConfig(extract_images=True, image_format="jpeg", image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        assert mf.filename.endswith(".jpeg")
        saved_img = Image.open(mf.source_path)
        assert saved_img.format == "JPEG"
        assert saved_img.mode == "RGB"

    def test_rgba_image_saved_as_jpg(self) -> None:
        img_bytes = _make_png_bytes(10, 10, mode="RGBA")
        config = MediaConfig(extract_images=True, image_format="jpg", image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.format == "JPEG"
        assert saved_img.mode == "RGB"


class TestJpegFormatProperties:
    @given(
        width=st.integers(min_value=1, max_value=50),
        height=st.integers(min_value=1, max_value=50),
        fmt=st.sampled_from(["jpg", "jpeg"]),
        mode=st.sampled_from(["RGB", "RGBA", "L"]),
    )
    @settings(max_examples=30)
    def test_any_mode_with_jpeg_format_produces_valid_jpeg(self, width: int, height: int, fmt: str, mode: str) -> None:
        img_bytes = _make_png_bytes(width, height, mode=mode)
        config = MediaConfig(extract_images=True, image_format=fmt, image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.format == "JPEG"


class TestSaveMediaToTempProperties:
    @given(
        width=st.integers(min_value=1, max_value=100),
        height=st.integers(min_value=1, max_value=100),
        max_dim=st.integers(min_value=10, max_value=50),
    )
    @settings(max_examples=30)
    def test_respects_max_dimension_property(self, width: int, height: int, max_dim: int) -> None:
        img_bytes = _make_png_bytes(width, height)
        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=max_dim)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.width <= max(max_dim, width)
        assert saved_img.height <= max(max_dim, height)

    @given(
        width=st.integers(min_value=1, max_value=50),
        height=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=20)
    def test_zero_max_dimension_preserves_size(self, width: int, height: int) -> None:
        img_bytes = _make_png_bytes(width, height)
        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)
        mf = save_media_to_temp(img_bytes, "test.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.width == width
        assert saved_img.height == height


class TestCopyMediaFiles:
    def test_copies_to_per_document_dir(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "report"
        destinations = copy_media_files((mf,), media_dir)
        assert len(destinations) == 1
        assert destinations[0].exists()
        assert destinations[0].parent.name == "report"

    def test_creates_media_dir(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "doc_name"
        assert not media_dir.exists()

        copy_media_files((mf,), media_dir)
        assert media_dir.exists()

    def test_empty_list_returns_empty(self, tmp_path):
        result = copy_media_files((), tmp_path / "report")
        assert result == []

    def test_skip_existing_file(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "report"
        media_dir.mkdir()
        (media_dir / "test.png").write_bytes(b"existing")

        destinations = copy_media_files((mf,), media_dir)
        assert len(destinations) == 1
        assert (media_dir / "test.png").read_bytes() == b"existing"

    def test_multiple_files_copied(self, tmp_path):
        config = _test_media_config()
        files = []
        for i in range(3):
            img_bytes = _make_png_bytes(10, 10)
            mf = save_media_to_temp(img_bytes, f"page{i}_img1.png", config)
            files.append(mf)

        media_dir = tmp_path / "multi_doc"
        destinations = copy_media_files(tuple(files), media_dir)
        assert len(destinations) == 3
        assert all(d.exists() for d in destinations)


class TestExtractionResult:
    def test_frozen(self):
        result = ExtractionResult(markdown="text", media_files=())
        with pytest.raises(AttributeError):
            result.markdown = "new"  # type: ignore[misc]

    def test_media_file_frozen(self):
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="img.png", media_type="image")
        with pytest.raises(AttributeError):
            mf.filename = "other.png"  # type: ignore[misc]


class TestMediaConfig:
    def test_default_media_config_from_yaml(self):
        from obsidian_import.config import default_config

        config = default_config()
        assert config.media.extract_images is True
        assert config.media.image_format == "png"
        assert config.media.image_max_dimension == 0

    def test_media_config_from_file(self, tmp_path):
        from obsidian_import.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
media:
  extract_images: false
  image_format: jpeg
  image_max_dimension: 800
""")
        config = load_config(config_file)
        assert config.media.extract_images is False
        assert config.media.image_format == "jpeg"
        assert config.media.image_max_dimension == 800
