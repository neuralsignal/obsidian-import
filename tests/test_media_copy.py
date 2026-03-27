"""Tests for media file copying, result objects, and config."""

from pathlib import Path

import pytest
from conftest import make_png_bytes, make_test_media_config

from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import copy_media_files, save_media_to_temp


class TestCopyMediaFiles:
    def test_copies_to_per_document_dir(self, tmp_path):
        img_bytes = make_png_bytes(10, 10)
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "report"
        destinations = copy_media_files((mf,), media_dir)
        assert len(destinations) == 1
        assert destinations[0].exists()
        assert destinations[0].parent.name == "report"

    def test_creates_media_dir(self, tmp_path):
        img_bytes = make_png_bytes(10, 10)
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "doc_name"
        assert not media_dir.exists()

        copy_media_files((mf,), media_dir)
        assert media_dir.exists()

    def test_empty_list_returns_empty(self, tmp_path):
        result = copy_media_files((), tmp_path / "report")
        assert result == []

    def test_skip_existing_file(self, tmp_path):
        img_bytes = make_png_bytes(10, 10)
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "report"
        media_dir.mkdir()
        (media_dir / "test.png").write_bytes(b"existing")

        destinations = copy_media_files((mf,), media_dir)
        assert len(destinations) == 1
        assert (media_dir / "test.png").read_bytes() == b"existing"

    def test_multiple_files_copied(self, tmp_path):
        config = make_test_media_config()
        files = []
        for i in range(3):
            img_bytes = make_png_bytes(10, 10)
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
