"""Tests for PDF extraction (mock pdfplumber)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.backends.native_pdf import (
    _extract_page_images,
    _pdf_image_extension,
    extract,
)
from obsidian_import.config import MediaConfig
from obsidian_import.extraction_result import MediaFile

_TEST_MEDIA_CONFIG = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)


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

        config = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0)

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
        ):
            result = extract(pdf_path, timeout_seconds=30, media_config=config)

        assert result.media_files == ()

    def test_wikilinks_use_document_stem_prefix(self, tmp_path):
        """Wikilinks reference <stem>/<filename>, not media/<filename>."""
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_page.extract_text.return_value = "text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        mock_xobj = MagicMock()
        mock_xobj.get.return_value = "/Image"
        mock_xobj.get_data.return_value = b"\x89PNG" + b"\x00" * 100

        mock_xobj_dict = {"img0": MagicMock()}
        mock_xobj_dict["img0"].get_object.return_value = mock_xobj

        mock_xobjects = MagicMock()
        mock_xobjects.get_object.return_value = mock_xobj_dict

        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: mock_xobjects if k == "/XObject" else None

        mock_reader_page = MagicMock()
        mock_reader_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.metadata = None
        mock_reader.get_fields.return_value = None
        mock_reader.pages = [mock_reader_page]

        with (
            patch("pdfplumber.open", return_value=mock_pdf),
            patch("pypdf.PdfReader", return_value=mock_reader),
            patch("obsidian_import.backends.native_pdf.save_media_to_temp") as mock_save,
        ):
            mock_save.return_value = MediaFile(
                source_path=Path("/tmp/img.png"), filename="page1_img1.png", media_type="image"
            )
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "![[report/page1_img1.png]]" in result.markdown
        assert "![[media/" not in result.markdown

    def test_extracts_form_fields(self, tmp_path):
        """PDF with form fields emits ## Form Fields section."""
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
            result = extract(pdf_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert "## Form Fields" in result.markdown
        assert "**FullName** (/Tx): Alice" in result.markdown
        assert "**Checkbox1** (/Btn): /Yes" in result.markdown

    def test_empty_table_guard(self, tmp_path):
        """Tables that are empty or have empty first row are skipped."""
        pdf_path = tmp_path / "empty_table.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [[], [None], [["Header"], ["val"]]]
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

        assert "Header" in result.markdown
        assert "val" in result.markdown


class TestExtractPageImages:
    def test_no_xobjects_returns_empty(self):
        """Page with resources but no /XObject returns empty list."""
        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: None if k == "/XObject" else None

        mock_page = MagicMock()
        mock_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_non_image_xobject_skipped(self):
        """XObjects with subtype != /Image are skipped."""
        mock_xobj = MagicMock()
        mock_xobj.get.return_value = "/Form"

        mock_xobj_dict = {"form0": MagicMock()}
        mock_xobj_dict["form0"].get_object.return_value = mock_xobj

        mock_xobjects = MagicMock()
        mock_xobjects.get_object.return_value = mock_xobj_dict

        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: mock_xobjects if k == "/XObject" else None

        mock_page = MagicMock()
        mock_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_image_extraction_failure_logs_warning(self):
        """When get_data() raises, a warning is logged and processing continues."""
        mock_xobj = MagicMock()
        mock_xobj.get.return_value = "/Image"
        mock_xobj.get_data.side_effect = ValueError("corrupt image")

        mock_xobj_dict = {"img0": MagicMock()}
        mock_xobj_dict["img0"].get_object.return_value = mock_xobj

        mock_xobjects = MagicMock()
        mock_xobjects.get_object.return_value = mock_xobj_dict

        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: mock_xobjects if k == "/XObject" else None

        mock_page = MagicMock()
        mock_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        mock_log.warning.assert_called_once()

    def test_no_resources_returns_empty(self):
        """Page with no /Resources returns empty list."""
        mock_page = MagicMock()
        mock_page.get.return_value = None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []


class TestPdfImageExtension:
    def test_none_filter_returns_png(self):
        xobj = MagicMock()
        xobj.get.return_value = None
        assert _pdf_image_extension(xobj) == ".png"

    def test_dctdecode_returns_jpeg(self):
        xobj = MagicMock()
        xobj.get.return_value = "/DCTDecode"
        assert _pdf_image_extension(xobj) == ".jpeg"

    def test_jpxdecode_returns_jp2(self):
        xobj = MagicMock()
        xobj.get.return_value = "/JPXDecode"
        assert _pdf_image_extension(xobj) == ".jp2"

    def test_ccittfaxdecode_returns_tiff(self):
        xobj = MagicMock()
        xobj.get.return_value = "/CCITTFaxDecode"
        assert _pdf_image_extension(xobj) == ".tiff"

    def test_unknown_filter_returns_png(self):
        xobj = MagicMock()
        xobj.get.return_value = "/FlateDecode"
        assert _pdf_image_extension(xobj) == ".png"

    @given(st.sampled_from(["/DCTDecode", "/JPXDecode", "/CCITTFaxDecode", "/FlateDecode", None]))
    def test_extension_always_starts_with_dot(self, filter_val):
        """Property: returned extension always starts with a dot."""
        xobj = MagicMock()
        xobj.get.return_value = filter_val
        ext = _pdf_image_extension(xobj)
        assert ext.startswith(".")

    @given(st.sampled_from(["/DCTDecode", "/JPXDecode", "/CCITTFaxDecode", "/FlateDecode", None]))
    def test_extension_is_known_format(self, filter_val):
        """Property: returned extension is one of the known formats."""
        xobj = MagicMock()
        xobj.get.return_value = filter_val
        ext = _pdf_image_extension(xobj)
        assert ext in {".png", ".jpeg", ".jp2", ".tiff"}
