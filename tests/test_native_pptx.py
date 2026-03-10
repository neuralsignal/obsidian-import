"""Tests for PPTX extraction (mock python-pptx)."""

from unittest.mock import MagicMock, patch

from obsidian_import.backends.native_pptx import extract
from obsidian_import.config import MediaConfig

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True, image_format="png", image_max_dimension=0, media_subfolder="media"
)


def _mock_presentation(slides_data: list[dict]) -> MagicMock:
    """Build a mock Presentation with the given slide data."""
    prs = MagicMock()
    prs.slide_width = 9144000  # 10 inches in EMU
    prs.slide_height = 6858000  # 7.5 inches in EMU

    mock_slides = []
    for data in slides_data:
        slide = MagicMock()
        title_shape = MagicMock()
        title_shape.text = data.get("title", "")

        if data.get("title"):
            slide.shapes.title = title_shape
        else:
            slide.shapes.title = None

        shapes = []
        for text in data.get("body_texts", []):
            shape = MagicMock()
            shape.has_text_frame = True
            shape.has_table = False
            shape.shape_type = 1  # not a picture
            para = MagicMock()
            para.text = text
            para.level = 0
            shape.text_frame.paragraphs = [para]
            shapes.append(shape)

        if data.get("title"):
            shapes.insert(0, title_shape)
            title_shape.has_text_frame = True
            title_shape.has_table = False
            title_shape.shape_type = 1

        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))
        slide.shapes.__len__ = MagicMock(return_value=len(shapes))
        slide.has_notes_slide = False
        mock_slides.append(slide)

    prs.slides = mock_slides
    return prs


class TestNativePptxExtract:
    def test_extracts_slide_text(self, tmp_path):
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation(
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

        mock_prs = _mock_presentation(
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

        mock_prs = _mock_presentation(
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
        """When extract_images=False, no images extracted."""
        pptx_path = tmp_path / "test.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Test"}])

        config = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0, media_subfolder="media")

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=config)

        assert result.media_files == ()
