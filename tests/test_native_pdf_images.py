"""Tests for PDF image extraction and extension mapping."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.backends.native_pdf import (
    _extract_page_images,
    _pdf_image_extension,
)
from obsidian_import.config import MediaConfig


class TestExtractPageImages:
    def test_no_xobjects_returns_empty(self):
        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: None if k == "/XObject" else None

        mock_page = MagicMock()
        mock_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_non_image_xobject_skipped(self):
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

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_image_extraction_failure_logs_warning(self):
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

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        mock_log.warning.assert_called_once()

    def test_malformed_page_xobjects_logs_warning(self):
        """KeyError/AttributeError accessing XObjects logs warning (lines 134-135)."""
        mock_page = MagicMock()
        mock_page.get.side_effect = AttributeError("no resources")

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        mock_log.warning.assert_called_once()
        assert "page resources" in mock_log.warning.call_args[0][0]

    def test_no_resources_returns_empty(self):
        mock_page = MagicMock()
        mock_page.get.return_value = None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_xobject_key_error_logs_warning(self):
        """KeyError raised while accessing XObject entries logs warning (line 166)."""
        mock_xobject_dict = MagicMock()
        mock_xobject_dict.__iter__.return_value = iter(["img0"])
        mock_xobject_dict.__getitem__.side_effect = KeyError("missing xobject entry")

        mock_xobjects = MagicMock()
        mock_xobjects.get_object.return_value = mock_xobject_dict

        mock_resources = MagicMock()
        mock_resources.get.side_effect = lambda k: mock_xobjects if k == "/XObject" else None

        mock_page = MagicMock()
        mock_page.get.side_effect = lambda k: mock_resources if k == "/Resources" else None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        media_config = MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        mock_log.warning.assert_called_once()
        assert "XObjects" in mock_log.warning.call_args[0][0]


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
        xobj = MagicMock()
        xobj.get.return_value = filter_val
        ext = _pdf_image_extension(xobj)
        assert ext.startswith(".")

    @given(st.sampled_from(["/DCTDecode", "/JPXDecode", "/CCITTFaxDecode", "/FlateDecode", None]))
    def test_extension_is_known_format(self, filter_val):
        xobj = MagicMock()
        xobj.get.return_value = filter_val
        ext = _pdf_image_extension(xobj)
        assert ext in {".png", ".jpeg", ".jp2", ".tiff"}
