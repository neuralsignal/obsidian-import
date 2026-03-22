"""Tests for PPTX extraction (mock python-pptx)."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.native_pptx import _extract_table, extract
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError
from obsidian_import.extraction_result import MediaFile

_TEST_MEDIA_CONFIG = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)


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

        config = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0)

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=config)

        assert result.media_files == ()

    def test_wikilinks_use_document_stem_prefix(self, tmp_path):
        """Image wikilinks reference <stem>/<filename>, not media/<filename>."""
        pptx_path = tmp_path / "slides.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Title"}])
        slide = mock_prs.slides[0]

        pic_shape = MagicMock()
        pic_shape.has_text_frame = False
        pic_shape.has_table = False
        pic_shape.shape_type = 13  # picture
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
        """Paragraphs with para.level > 0 produce indented bullets."""
        pptx_path = tmp_path / "indent.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Bullets"}])
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
        """Shapes with tables produce markdown table output."""
        pptx_path = tmp_path / "table.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Data"}])
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
        """When image extraction raises AttributeError, warning is logged."""
        pptx_path = tmp_path / "broken_img.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Pics", "body_texts": ["Some text"]}])
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
        """ExtractionError from image extraction is caught and logged."""
        pptx_path = tmp_path / "err_img.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Pics"}])
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
        """Slides with speaker notes produce a notes block."""
        pptx_path = tmp_path / "notes.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Talk", "body_texts": ["Content"]}])
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
        """Slides with empty notes text do not emit a notes block."""
        pptx_path = tmp_path / "empty_notes.pptx"
        pptx_path.write_bytes(b"fake pptx")

        mock_prs = _mock_presentation([{"title": "Talk"}])
        slide = mock_prs.slides[0]
        slide.has_notes_slide = True
        slide.notes_slide.notes_text_frame.text = "   "

        with (
            patch("pptx.Presentation", return_value=mock_prs),
            patch("pptx.util.Inches", return_value=914400),
        ):
            result = extract(pptx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Speaker Notes" not in result.markdown


class TestExtractTable:
    def test_empty_rows_returns_empty_string(self):
        """_extract_table with a table that has no rows returns empty string."""
        table = MagicMock()
        table.rows = []
        assert _extract_table(table) == ""

    def test_single_row_table(self):
        """A table with one row produces a header and separator."""
        table = MagicMock()
        row = MagicMock()
        cell_a, cell_b = MagicMock(), MagicMock()
        cell_a.text = "A"
        cell_b.text = "B"
        row.cells = [cell_a, cell_b]
        table.rows = [row]

        result = _extract_table(table)
        assert "| A | B |" in result
        assert "| --- | --- |" in result

    @given(
        data=st.lists(
            st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=50)
    def test_extract_table_property_row_count(self, data):
        """Output has header + separator + (n-1) data rows."""
        table = MagicMock()
        mock_rows = []
        for row_data in data:
            row = MagicMock()
            cells = []
            for text in row_data:
                cell = MagicMock()
                cell.text = text
                cells.append(cell)
            row.cells = cells
            mock_rows.append(row)
        table.rows = mock_rows

        result = _extract_table(table)
        lines = result.strip().split("\n")
        # header + separator + data rows
        assert len(lines) == 1 + 1 + max(0, len(data) - 1)

    @given(
        data=st.lists(
            st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=50)
    def test_extract_table_property_all_lines_are_pipe_delimited(self, data):
        """Every line starts and ends with a pipe."""
        table = MagicMock()
        mock_rows = []
        for row_data in data:
            row = MagicMock()
            cells = []
            for text in row_data:
                cell = MagicMock()
                cell.text = text
                cells.append(cell)
            row.cells = cells
            mock_rows.append(row)
        table.rows = mock_rows

        result = _extract_table(table)
        for line in result.strip().split("\n"):
            assert line.startswith("|")
            assert line.endswith("|")
