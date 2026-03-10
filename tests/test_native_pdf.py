"""Tests for PDF extraction (mock pdfplumber)."""

from unittest.mock import MagicMock, patch

from obsidian_import.backends.native_pdf import extract
from obsidian_import.config import MediaConfig

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True, image_format="png", image_max_dimension=0, media_subfolder="media"
)


class TestNativePdfExtract:
    def test_extracts_basic_pdf(self, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "Hello world"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = None
        mock_reader.pages = [MagicMock()]
        mock_reader.pages[0].get.return_value = None

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "# test" in result.markdown
        assert "Hello world" in result.markdown

    def test_extracts_tables(self, tmp_path):
        pdf_path = tmp_path / "table.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [[["Header1", "Header2"], ["val1", "val2"]]]
        mock_page.extract_text.return_value = ""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = None
        mock_reader.pages = [MagicMock()]
        mock_reader.pages[0].get.return_value = None

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "Header1" in result.markdown
        assert "val1" in result.markdown
        assert "|" in result.markdown

    def test_extracts_metadata(self, tmp_path):
        pdf_path = tmp_path / "meta.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "content"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_meta = MagicMock()
        mock_meta.title = "My PDF"
        mock_meta.author = "Author Name"
        mock_meta.creation_date = "2024-01-01"

        mock_reader = MagicMock()
        mock_reader.metadata = mock_meta
        mock_reader.get_fields.return_value = None
        mock_reader.pages = [MagicMock()]
        mock_reader.pages[0].get.return_value = None

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "# My PDF" in result.markdown
        assert "Author Name" in result.markdown

    def test_no_images_when_disabled(self, tmp_path):
        """When extract_images=False, no image extraction is attempted."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = None

        config = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0, media_subfolder="media")

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, media_config=config)

        assert result.media_files == ()
