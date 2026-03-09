"""Tests for PDF extraction (mock pdfplumber)."""

from unittest.mock import MagicMock, patch

from obsidian_import.backends.native_pdf import extract


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

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30)

        assert "# test" in result
        assert "Hello world" in result

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

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30)

        assert "Header1" in result
        assert "val1" in result
        assert "|" in result

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

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30)

        assert "# My PDF" in result
        assert "Author Name" in result
