"""Tests for docling backend extraction and converter building."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from conftest import make_pil_image

from obsidian_import.backends.docling import (
    _build_converter,
    extract,
)
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import BackendNotAvailableError
from obsidian_import.extraction_result import ExtractionResult

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)

_NO_IMAGES_CONFIG = MediaConfig(
    extract_images=False,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


def _mock_docling_document(text: str, pictures: list[MagicMock] | None) -> MagicMock:
    """Create a mock docling Document with text and optional pictures."""
    doc = MagicMock()
    doc.export_to_markdown.return_value = text
    if pictures is not None:
        doc.pictures = pictures
    else:
        doc.pictures = []
    return doc


def _mock_converter_result(doc: MagicMock) -> MagicMock:
    """Wrap a mock document in a mock converter result."""
    result = MagicMock()
    result.document = doc
    return result


class TestDoclingExtract:
    def test_extracts_basic_text(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        doc = _mock_docling_document("# Report\n\nSome content here.", pictures=[])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Report" in result.markdown
        assert "Some content here." in result.markdown
        assert isinstance(result, ExtractionResult)

    def test_empty_text_returns_fallback_message(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        doc = _mock_docling_document("", pictures=[])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "No text content extracted" in result.markdown
        assert "empty.pdf" in result.markdown

    def test_whitespace_only_text_returns_fallback(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "blank.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        doc = _mock_docling_document("   \n\n  ", pictures=[])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "No text content extracted" in result.markdown

    def test_no_images_when_disabled(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        doc = _mock_docling_document("Some text", pictures=[])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_NO_IMAGES_CONFIG)

        assert result.media_files == ()

    def test_extracts_images_with_wikilinks(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "withimg.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        pil_img = make_pil_image(10, 10, "blue")

        mock_picture = MagicMock()
        mock_picture.get_image.return_value = pil_img

        markdown_text = "# Title\n\n![Figure 1](image_ref_1.png)\n\nSome text."
        doc = _mock_docling_document(markdown_text, pictures=[mock_picture])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 1
        assert result.media_files[0].media_type == "image"
        assert "![[withimg/" in result.markdown
        assert "![[media/" not in result.markdown
        assert "Some text." in result.markdown

    def test_multiple_images_extracted(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        pictures = []
        for color in ("red", "green", "blue"):
            pic = MagicMock()
            pic.get_image.return_value = make_pil_image(10, 10, color)
            pictures.append(pic)

        markdown_text = "![img1](a.png)\n\n![img2](b.png)\n\n![img3](c.png)"
        doc = _mock_docling_document(markdown_text, pictures=pictures)
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 3
        assert result.markdown.count("![[multi/") == 3

    def test_image_extraction_failure_skipped(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "badfig.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        good_pic = MagicMock()
        good_pic.get_image.return_value = make_pil_image(10, 10, "red")

        bad_pic = MagicMock()
        bad_pic.get_image.side_effect = AttributeError("no image data")

        markdown_text = "![fig1](a.png)\n![fig2](b.png)"
        doc = _mock_docling_document(markdown_text, pictures=[bad_pic, good_pic])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 1

    def test_picture_returns_none_skipped(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "noneimg.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        pic = MagicMock()
        pic.get_image.return_value = None

        doc = _mock_docling_document("![fig](a.png)", pictures=[pic])
        conv_result = _mock_converter_result(doc)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 0

    def test_docling_not_installed_raises(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        with (
            patch("importlib.util.find_spec", return_value=None),
            pytest.raises(BackendNotAvailableError, match="docling is not installed"),
        ):
            extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

    def test_no_pictures_attribute_returns_empty(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "nopic.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        doc = MagicMock()
        doc.export_to_markdown.return_value = "Some text"
        doc.pictures = None

        conv_result = _mock_converter_result(doc)
        mock_converter = MagicMock()
        mock_converter.convert.return_value = conv_result

        with patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()


class TestBuildConverter:
    def test_without_images_returns_basic_converter(self) -> None:
        mock_dc = MagicMock()
        with patch("docling.document_converter.DocumentConverter", mock_dc) as patched:
            _build_converter(_NO_IMAGES_CONFIG)
            patched.assert_called_once_with()

    def test_with_images_builds_pipeline_options(self) -> None:
        mock_dc = MagicMock()
        mock_pipeline = MagicMock()
        mock_format_option = MagicMock()
        mock_input_format = MagicMock()
        mock_input_format.PDF = "pdf"

        with (
            patch("docling.document_converter.DocumentConverter", mock_dc),
            patch(
                "docling.datamodel.pipeline_options.PdfPipelineOptions",
                return_value=mock_pipeline,
            ),
            patch(
                "docling.document_converter.PdfFormatOption",
                return_value=mock_format_option,
            ),
            patch("docling.datamodel.base_models.InputFormat", mock_input_format),
        ):
            _build_converter(_TEST_MEDIA_CONFIG)
            mock_dc.assert_called_once()

    def test_import_error_falls_back_to_default(self) -> None:
        mock_dc = MagicMock()
        with (
            patch("docling.document_converter.DocumentConverter", mock_dc),
            patch.dict("sys.modules", {"docling.datamodel.pipeline_options": None}),
        ):
            _build_converter(_TEST_MEDIA_CONFIG)
            mock_dc.assert_called()
