"""Tests for docling backend extraction."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from obsidian_import.backends.docling import (
    _build_converter,
    _extract_docling_images,
    _replace_image_refs_with_wikilinks,
    extract,
)
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import BackendNotAvailableError
from obsidian_import.extraction_result import ExtractionResult, MediaFile

_TEST_MEDIA_CONFIG = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)

_NO_IMAGES_CONFIG = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0)


def _make_pil_image(width: int, height: int, color: str) -> Image.Image:
    """Create a PIL image for testing."""
    return Image.new("RGB", (width, height), color=color)


def _pil_to_bytes(img: Image.Image) -> bytes:
    """Convert PIL image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
        """Docling returns markdown text from a document."""
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
        """When docling returns empty text, a fallback message is produced."""
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
        """Whitespace-only text is treated as empty."""
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
        """When extract_images=False, no image extraction is attempted."""
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
        """When pictures are present, wikilinks use per-document folder."""
        pdf_path = tmp_path / "withimg.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        pil_img = _make_pil_image(10, 10, "blue")

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
        """Multiple pictures are extracted and mapped to wikilinks."""
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        pictures = []
        for color in ("red", "green", "blue"):
            pic = MagicMock()
            pic.get_image.return_value = _make_pil_image(10, 10, color)
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
        """If a picture fails to extract, it is skipped without raising."""
        pdf_path = tmp_path / "badfig.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        good_pic = MagicMock()
        good_pic.get_image.return_value = _make_pil_image(10, 10, "red")

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
        """If get_image returns None, that picture is skipped."""
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
        """When docling is not installed, BackendNotAvailableError is raised."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        with (
            patch("importlib.util.find_spec", return_value=None),
            pytest.raises(BackendNotAvailableError, match="docling is not installed"),
        ):
            extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

    def test_no_pictures_attribute_returns_empty(self, tmp_path: Path) -> None:
        """If the document has no pictures attribute, no media files are returned."""
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
        """When extract_images is False, a basic DocumentConverter is returned."""
        mock_dc = MagicMock()
        with patch("docling.document_converter.DocumentConverter", mock_dc) as patched:
            _build_converter(_NO_IMAGES_CONFIG)
            patched.assert_called_once_with()

    def test_with_images_builds_pipeline_options(self) -> None:
        """When extract_images is True, pipeline options with generate_picture_images are used."""
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
        """If pipeline options import fails, fallback to basic converter."""
        mock_dc = MagicMock()
        with (
            patch("docling.document_converter.DocumentConverter", mock_dc),
            patch.dict("sys.modules", {"docling.datamodel.pipeline_options": None}),
        ):
            _build_converter(_TEST_MEDIA_CONFIG)
            mock_dc.assert_called()


class TestExtractDoclingImages:
    def test_empty_pictures_list(self) -> None:
        """Empty pictures list returns empty media list."""
        doc = MagicMock()
        doc.pictures = []
        result = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert result == []

    def test_no_pictures_attribute(self) -> None:
        """No pictures attribute returns empty media list."""
        doc = MagicMock()
        doc.pictures = None
        result = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert result == []

    def test_successful_extraction(self) -> None:
        """Successful image extraction returns MediaFile objects."""
        pil_img = _make_pil_image(20, 20, "green")
        pic = MagicMock()
        pic.get_image.return_value = pil_img

        doc = MagicMock()
        doc.pictures = [pic]

        result = _extract_docling_images(doc, Path("report.pdf"), _TEST_MEDIA_CONFIG)
        assert len(result) == 1
        assert result[0].media_type == "image"
        assert "fig" in result[0].filename
        assert result[0].source_path.exists()


class TestReplaceImageRefsWithWikilinks:
    def test_replaces_single_image_ref(self) -> None:
        """A single markdown image ref is replaced with a per-doc wikilink."""
        media_files = [MediaFile(source_path=Path("/tmp/img.png"), filename="fig_img1.png", media_type="image")]
        text = "Before ![alt](path/to/img.png) after"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "report")
        assert "![[report/fig_img1.png]]" in result
        assert "Before" in result
        assert "after" in result

    def test_replaces_multiple_image_refs(self) -> None:
        """Multiple image refs are replaced in order."""
        media_files = [
            MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image"),
            MediaFile(source_path=Path("/tmp/b.png"), filename="b.png", media_type="image"),
        ]
        text = "![first](x.png) text ![second](y.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "doc")
        assert "![[doc/a.png]]" in result
        assert "![[doc/b.png]]" in result

    def test_no_media_files_preserves_original(self) -> None:
        """When no media files, original image refs are preserved."""
        text = "![alt](path.png)"
        result = _replace_image_refs_with_wikilinks(text, [], "doc")
        assert result == text

    def test_more_refs_than_files(self) -> None:
        """If more image refs than media files, extra refs are preserved."""
        media_files = [
            MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image"),
        ]
        text = "![img1](x.png) ![img2](y.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "doc")
        assert "![[doc/a.png]]" in result
        assert "![img2](y.png)" in result


class TestReplaceImageRefsProperties:
    @given(
        doc_stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
            lambda s: s + ".png"
        ),
    )
    @settings(max_examples=50)
    def test_replacement_contains_doc_stem(self, doc_stem: str, filename: str) -> None:
        media_files = [MediaFile(source_path=Path("/tmp/x.png"), filename=filename, media_type="image")]
        text = "![alt](ref.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), doc_stem)
        assert f"![[{doc_stem}/{filename}]]" in result

    @given(
        n_files=st.integers(min_value=0, max_value=5),
        n_refs=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_replacement_count_matches_min_of_files_and_refs(self, n_files: int, n_refs: int) -> None:
        media_files = [
            MediaFile(source_path=Path(f"/tmp/{i}.png"), filename=f"img{i}.png", media_type="image")
            for i in range(n_files)
        ]
        refs = " ".join(f"![alt{i}](ref{i}.png)" for i in range(n_refs))
        result = _replace_image_refs_with_wikilinks(refs, list(media_files), "doc")
        expected_replacements = min(n_files, n_refs)
        assert result.count("![[doc/") == expected_replacements
