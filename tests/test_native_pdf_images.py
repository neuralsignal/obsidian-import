"""Tests for PDF image extraction and extension mapping."""

import io
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.backends.native_pdf import (
    _extract_page_images,
    _pdf_image_extension,
)
from obsidian_import.config import MediaConfig


def _minimal_png_bytes() -> bytes:
    """Create a minimal valid PNG image in memory."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buf, format="PNG")
    return buf.getvalue()


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
            image_max_pixels=50_000_000,
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
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_image_extraction_failure_logs_warning(self, caplog):
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
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with caplog.at_level(logging.WARNING):
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        assert "Failed to extract image" in caplog.text

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
            image_max_pixels=50_000_000,
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
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)
        assert result == []

    def test_xobject_key_error_logs_warning(self):
        """KeyError raised while accessing XObject entries logs warning per object."""
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
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert result == []
        mock_log.warning.assert_called_once()
        assert "XObject" in mock_log.warning.call_args[0][0]
        assert "img0" in mock_log.warning.call_args[0][1]

    def test_bad_xobject_does_not_abort_remaining_images(self):
        """A KeyError on one XObject must not prevent extraction of subsequent ones."""
        good_xobj = MagicMock()
        good_xobj.get.side_effect = lambda k: "/Image" if k == "/Subtype" else None
        good_xobj.get_data.return_value = _minimal_png_bytes()

        bad_ref = MagicMock()
        bad_ref.get_object.side_effect = KeyError("corrupt indirect ref")

        good_ref = MagicMock()
        good_ref.get_object.return_value = good_xobj

        mock_xobject_dict = {"bad_img": bad_ref, "good_img": good_ref}

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
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )

        with patch("obsidian_import.backends.native_pdf.log") as mock_log:
            result = _extract_page_images(mock_reader, 0, Path("/fake.pdf"), media_config)

        assert len(result) == 1
        mock_log.warning.assert_called_once()
        assert "bad_img" in mock_log.warning.call_args[0][1]


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
