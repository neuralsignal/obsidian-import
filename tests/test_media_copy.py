"""Tests for media file copying, result objects, and config."""

from pathlib import Path

import pytest
from conftest import make_png_bytes, make_test_media_config

from obsidian_import.extraction_result import ExtractionResult, MediaFile
from obsidian_import.media import _cleanup_temp_source, copy_media_files, save_media_to_temp


class TestCopyMediaFiles:
    def test_copies_to_per_document_dir(self, tmp_path):
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)

        media_dir = tmp_path / "report"
        destinations = copy_media_files((mf,), media_dir)
        assert len(destinations) == 1
        assert destinations[0].exists()
        assert destinations[0].parent.name == "report"

    def test_creates_media_dir(self, tmp_path):
        img_bytes = make_png_bytes(10, 10, "RGB")
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
        img_bytes = make_png_bytes(10, 10, "RGB")
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
            img_bytes = make_png_bytes(10, 10, "RGB")
            mf = save_media_to_temp(img_bytes, f"page{i}_img1.png", config)
            files.append(mf)

        media_dir = tmp_path / "multi_doc"
        destinations = copy_media_files(tuple(files), media_dir)
        assert len(destinations) == 3
        assert all(d.exists() for d in destinations)


class TestTempCleanup:
    def test_temp_dir_removed_after_copy(self, tmp_path):
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)
        temp_dir = mf.source_path.parent
        assert temp_dir.exists()

        copy_media_files((mf,), tmp_path / "report")
        assert not mf.source_path.exists()
        assert not temp_dir.exists()

    def test_temp_dir_removed_even_when_dest_exists(self, tmp_path):
        img_bytes = make_png_bytes(10, 10, "RGB")
        config = make_test_media_config()
        mf = save_media_to_temp(img_bytes, "test.png", config)
        temp_dir = mf.source_path.parent

        media_dir = tmp_path / "report"
        media_dir.mkdir()
        (media_dir / "test.png").write_bytes(b"existing")

        copy_media_files((mf,), media_dir)
        assert not temp_dir.exists()

    def test_non_temp_source_not_deleted(self, tmp_path):
        src_dir = tmp_path / "regular_dir"
        src_dir.mkdir()
        src_file = src_dir / "img.png"
        src_file.write_bytes(make_png_bytes(10, 10, "RGB"))

        mf = MediaFile(source_path=src_file, filename="img.png", media_type="image")
        copy_media_files((mf,), tmp_path / "report")
        assert src_file.exists()
        assert src_dir.exists()


class TestCleanupTempSource:
    def test_removes_temp_file_and_dir(self, tmp_path):
        temp_dir = tmp_path / "obsidian_media_abc123"
        temp_dir.mkdir()
        temp_file = temp_dir / "img.png"
        temp_file.write_bytes(b"data")

        _cleanup_temp_source(temp_file)
        assert not temp_file.exists()
        assert not temp_dir.exists()

    def test_skips_non_temp_dir(self, tmp_path):
        regular_dir = tmp_path / "my_images"
        regular_dir.mkdir()
        regular_file = regular_dir / "img.png"
        regular_file.write_bytes(b"data")

        _cleanup_temp_source(regular_file)
        assert regular_file.exists()
        assert regular_dir.exists()

    def test_handles_already_deleted_file(self, tmp_path):
        temp_dir = tmp_path / "obsidian_media_xyz"
        temp_dir.mkdir()
        temp_file = temp_dir / "img.png"

        _cleanup_temp_source(temp_file)
        assert not temp_dir.exists()

    def test_dir_not_removed_if_other_files_remain(self, tmp_path):
        temp_dir = tmp_path / "obsidian_media_multi"
        temp_dir.mkdir()
        target = temp_dir / "img1.png"
        target.write_bytes(b"data1")
        (temp_dir / "img2.png").write_bytes(b"data2")

        _cleanup_temp_source(target)
        assert not target.exists()
        assert temp_dir.exists()


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
