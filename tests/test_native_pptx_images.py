"""Tests for PPTX image extraction and error handling."""

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
    image_max_pixels=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


class TestNativePptxImages:
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
        slide.shapes.__iter__ = MagicMock(side_effect=lambda s=shapes: iter(s))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch("obsidian_import.media.save_media_to_temp") as mock_save,
        ):
            mock_save.return_value = MediaFile(
                source_path=Path("/tmp/img.png"), filename="slide1_img1.png", media_type="image"
            )
            result = extract(pptx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "![[slides/slide1_img1.png]]" in result.markdown
        assert "![[media/" not in result.markdown

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
        slide.shapes.__iter__ = MagicMock(side_effect=lambda s=shapes: iter(s))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch(
                "obsidian_import.media.save_media_to_temp",
                side_effect=ExtractionError("image save failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = extract(pptx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

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
        slide.shapes.__iter__ = MagicMock(side_effect=lambda s=shapes: iter(s))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch(
                "obsidian_import.media.save_media_to_temp",
                side_effect=ExtractionError("corrupt image"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            extract(pptx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "Failed to extract image" in caplog.text

    def test_shape_image_attribute_error_converted_to_extraction_error(self, tmp_path, caplog):
        """AttributeError from shape.image is converted to ExtractionError and logged."""
        pptx_path = tmp_path / "bad_shape.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = mock_pptx_presentation([{"title": "Pics", "body_texts": ["Some text"]}])
        slide = mock_prs.slides[0]

        class BrokenImageShape:
            has_text_frame = False
            has_table = False
            shape_type = 13

            @property
            def image(self):
                raise AttributeError("no image data")

        pic_shape = BrokenImageShape()

        shapes = list(slide.shapes.__iter__()) + [pic_shape]
        slide.shapes.__iter__ = MagicMock(side_effect=lambda s=shapes: iter(s))

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
            patch("obsidian_import.media.save_media_to_temp"),
            caplog.at_level(logging.WARNING),
        ):
            result = extract(pptx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "Failed to extract image" in caplog.text
        assert "Some text" in result.markdown
