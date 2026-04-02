"""Tests for PPTX slide extraction."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import mock_pptx_presentation

from obsidian_import.backends.native_pptx import extract
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import MediaFile

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


class TestNativePptxExtract:
    def test_extracts_slide_text(self, tmp_path):
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation(
            [
                {"title": "Intro", "body_texts": ["Welcome to the presentation"]},
            ]
        )

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "# test" in result.markdown
        assert "Slide 1: Intro" in result.markdown

    def test_extracts_multiple_slides(self, tmp_path):
        pptx_path = tmp_path / "multi.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation(
            [
                {"title": "Slide One"},
                {"title": "Slide Two"},
            ]
        )

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Slide 1: Slide One" in result.markdown
        assert "Slide 2: Slide Two" in result.markdown

    def test_slide_without_title(self, tmp_path):
        pptx_path = tmp_path / "notitle.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation(
            [
                {"body_texts": ["Some content"]},
            ]
        )

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "## Slide 1" in result.markdown

    def test_no_images_when_disabled(self, tmp_path):
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Test"}])

        config = MediaConfig(
            extract_images=False,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=config)

        assert result.media_files == ()

    def test_wikilinks_use_document_stem_prefix(self, tmp_path):
        pptx_path = tmp_path / "slides.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Title"}])
        slide = mock_prs.slides[0]

        pic_shape = MagicMock()
        pic_shape.has_text_frame = False
        pic_shape.has_table = False
        pic_shape.shape_type = 13
        pic_shape.image.blob = b"\x89PNG" + b"\x00" * 100
        pic_shape.image.content_type = "image/png"

        shapes = list(slide.shapes.__iter__()) + [pic_shape]
        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch("obsidian_import.backends.native_pptx.save_media_to_temp") as mock_save,
        ):
            mock_save.return_value = MediaFile(
                source_path=Path("/tmp/img.png"), filename="slide1_img1.png", media_type="image"
            )
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "![[slides/slide1_img1.png]]" in result.markdown
        assert "![[media/" not in result.markdown

    def test_indented_bullet_paragraphs(self, tmp_path):
        pptx_path = tmp_path / "indent.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Bullets"}])
        slide = mock_prs.slides[0]

        shape = MagicMock()
        shape.has_text_frame = True
        shape.has_table = False
        shape.shape_type = 1

        para_level1 = MagicMock()
        para_level1.text = "Level one"
        para_level1.level = 1

        para_level2 = MagicMock()
        para_level2.text = "Level two"
        para_level2.level = 2

        shape.text_frame.paragraphs = [para_level1, para_level2]

        shapes = list(slide.shapes.__iter__()) + [shape]
        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "  - Level one" in result.markdown
        assert "    - Level two" in result.markdown

    def test_shape_with_table(self, tmp_path):
        pptx_path = tmp_path / "table.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Data"}])
        slide = mock_prs.slides[0]

        table_shape = MagicMock()
        table_shape.has_text_frame = False
        table_shape.has_table = True
        table_shape.shape_type = 1

        row1 = MagicMock()
        cell1a, cell1b = MagicMock(), MagicMock()
        cell1a.text = "Header A"
        cell1b.text = "Header B"
        row1.cells = [cell1a, cell1b]

        row2 = MagicMock()
        cell2a, cell2b = MagicMock(), MagicMock()
        cell2a.text = "Val 1"
        cell2b.text = "Val 2"
        row2.cells = [cell2a, cell2b]

        table_shape.table.rows = [row1, row2]

        shapes = list(slide.shapes.__iter__()) + [table_shape]
        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Header A" in result.markdown
        assert "Header B" in result.markdown
        assert "Val 1" in result.markdown
        assert "---" in result.markdown

    def test_image_extraction_failure_logs_warning(self, tmp_path, caplog):
        pptx_path = tmp_path / "broken_img.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Pics", "body_texts": ["Some text"]}])
        slide = mock_prs.slides[0]

        pic_shape = MagicMock()
        pic_shape.has_text_frame = False
        pic_shape.has_table = False
        pic_shape.shape_type = 13
        pic_shape.image.blob = b"\x89PNG"
        pic_shape.image.content_type = "image/png"

        shapes = list(slide.shapes.__iter__()) + [pic_shape]
        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch(
                "obsidian_import.backends.native_pptx.save_media_to_temp",
                side_effect=AttributeError("no image data"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Failed to extract image" in caplog.text
        assert "Some text" in result.markdown

    def test_image_extraction_error_logs_warning(self, tmp_path, caplog):
        pptx_path = tmp_path / "err_img.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Pics"}])
        slide = mock_prs.slides[0]

        pic_shape = MagicMock()
        pic_shape.has_text_frame = False
        pic_shape.has_table = False
        pic_shape.shape_type = 13
        pic_shape.image.blob = b"\x89PNG"
        pic_shape.image.content_type = "image/png"

        shapes = list(slide.shapes.__iter__()) + [pic_shape]
        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch(
                "obsidian_import.backends.native_pptx.save_media_to_temp",
                side_effect=ExtractionError("corrupt image"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Failed to extract image" in caplog.text

    def test_speaker_notes_extracted(self, tmp_path):
        pptx_path = tmp_path / "notes.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Talk", "body_texts": ["Content"]}])
        slide = mock_prs.slides[0]
        slide.has_notes_slide = True
        slide.notes_slide.notes_text_frame.text = "Remember to pause here"

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "> **Speaker Notes:** Remember to pause here" in result.markdown

    def test_empty_speaker_notes_not_emitted(self, tmp_path):
        pptx_path = tmp_path / "empty_notes.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Talk"}])
        slide = mock_prs.slides[0]
        slide.has_notes_slide = True
        slide.notes_slide.notes_text_frame.text = "   "

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Speaker Notes" not in result.markdown
