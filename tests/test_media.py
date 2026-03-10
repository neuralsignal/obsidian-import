"""Tests for media utilities module."""

import io
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from obsidian_import.config import MediaConfig
from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import copy_media_files, generate_media_filename, save_media_to_temp


def _make_png_bytes(width: int, height: int) -> bytes:
    """Create minimal PNG image bytes."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _test_media_config() -> MediaConfig:
    return MediaConfig(extract_images=True, image_format="png", image_max_dimension=0, media_subfolder="media")


class TestGenerateMediaFilename:
    def test_basic_filename(self):
        result = generate_media_filename("report", "page1", 1, ".png")
        assert result == "report_page1_img1.png"

    def test_spaces_replaced(self):
        result = generate_media_filename("my report", "slide2", 3, ".jpeg")
        assert result == "my_report_slide2_img3.jpeg"

    def test_different_contexts(self):
        assert "doc" in generate_media_filename("file", "doc", 1, ".png")
        assert "slide5" in generate_media_filename("file", "slide5", 1, ".png")
        assert "fig" in generate_media_filename("file", "fig", 1, ".png")


class TestGenerateMediaFilenameProperties:
    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg", ".gif", ".bmp"]),
    )
    @settings(max_examples=100)
    def test_always_ends_with_extension(self, stem: str, context: str, index: int, ext: str) -> None:
        result = generate_media_filename(stem, context, index, ext)
        assert result.endswith(ext)

    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        context=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        index=st.integers(min_value=1, max_value=1000),
        ext=st.sampled_from([".png", ".jpeg"]),
    )
    @settings(max_examples=100)
    def test_no_spaces_in_result(self, stem: str, context: str, index: int, ext: str) -> None:
        result = generate_media_filename(stem, context, index, ext)
        assert " " not in result


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

        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0, media_subfolder="media")
        mf = save_media_to_temp(jpeg_bytes, "test.jpeg", config)
        assert mf.filename.endswith(".png")

    def test_respects_max_dimension(self):
        img_bytes = _make_png_bytes(200, 200)
        config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=50, media_subfolder="media")
        mf = save_media_to_temp(img_bytes, "big.png", config)
        saved_img = Image.open(mf.source_path)
        assert saved_img.width <= 50
        assert saved_img.height <= 50


class TestCopyMediaFiles:
    def test_copies_to_subfolder(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        destinations = copy_media_files((mf,), tmp_path, "media")
        assert len(destinations) == 1
        assert destinations[0].exists()
        assert destinations[0].parent.name == "media"

    def test_creates_media_subfolder(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "media"
        assert not media_dir.exists()

        copy_media_files((mf,), tmp_path, "media")
        assert media_dir.exists()

    def test_empty_list_returns_empty(self, tmp_path):
        result = copy_media_files((), tmp_path, "media")
        assert result == []

    def test_skip_existing_file(self, tmp_path):
        img_bytes = _make_png_bytes(10, 10)
        config = _test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "media"
        media_dir.mkdir()
        (media_dir / "test.png").write_bytes(b"existing")

        destinations = copy_media_files((mf,), tmp_path, "media")
        assert len(destinations) == 1
        assert (media_dir / "test.png").read_bytes() == b"existing"


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
        assert config.media.media_subfolder == "media"

    def test_media_config_from_file(self, tmp_path):
        from obsidian_import.config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
media:
  extract_images: false
  image_format: jpeg
  image_max_dimension: 800
  media_subfolder: images
""")
        config = load_config(config_file)
        assert config.media.extract_images is False
        assert config.media.image_format == "jpeg"
        assert config.media.image_max_dimension == 800
        assert config.media.media_subfolder == "images"
