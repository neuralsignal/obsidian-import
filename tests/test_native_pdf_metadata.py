"""Tests for PDF metadata and form field extraction."""

from unittest.mock import MagicMock, patch

from obsidian_import.backends.native_pdf import extract
from obsidian_import.config import MediaConfig

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_max_pixels=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


class TestNativePdfMetadata:
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
            result = extract(pdf_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "# My PDF" in result.markdown
        assert "Author Name" in result.markdown

    def test_extracts_form_fields(self, tmp_path):
        pdf_path = tmp_path / "form.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "content"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = {
            "FullName": {"/FT": "/Tx", "/V": "Alice"},
            "Checkbox1": {"/FT": "/Btn", "/V": "/Yes"},
        }
        mock_reader.pages = [MagicMock()]
        mock_reader.pages[0].get.return_value = None

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "## Form Fields" in result.markdown
        assert "**FullName** (/Tx): Alice" in result.markdown
        assert "**Checkbox1** (/Btn): /Yes" in result.markdown

    def test_form_fields_sanitized_against_markdown_injection(self, tmp_path):
        pdf_path = tmp_path / "malicious.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "content"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = {
            "x** (injected bold": {"/FT": "/Tx", "/V": "normal"},
            "safe": {"/FT": "/Tx", "/V": "\n\n## Injected Heading"},
            "breaks": {"/FT": "/Tx", "/V": "\n\n---"},
        }
        mock_reader.pages = [MagicMock()]
        mock_reader.pages[0].get.return_value = None

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "## Injected Heading" not in result.markdown
        assert "\n\n---" not in result.markdown
        assert "injected bold" in result.markdown
        assert r"\*\*" in result.markdown
