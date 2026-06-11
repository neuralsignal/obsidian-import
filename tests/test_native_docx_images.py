"""Tests for DOCX embedded-image extraction and ZIP decompression limits.

Text/structure extraction tests live in test_native_docx.py.
"""

import io
import logging
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import make_test_media_config
from PIL import Image

from obsidian_import.backends.native_docx import extract
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError

_TEST_MEDIA_CONFIG = make_test_media_config()

_SIMPLE_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello World</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""


def _drawing_doc(embed_id: str, text: str) -> str:
    """document.xml with one paragraph holding optional text and a drawing for embed_id."""
    text_run = f"<w:r><w:t>{text}</w:t></w:r>" if text else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      {text_run}
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="{embed_id}"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""


def _rels_xml(target: str) -> str:
    """document.xml.rels with a single image relationship rId1 -> target."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="{target}"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""


def _png_bytes(color: str) -> bytes:
    img = Image.new("RGB", (10, 10), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_docx(tmp_path: Path, name: str, entries: dict[str, str | bytes]) -> Path:
    docx_path = tmp_path / name
    with zipfile.ZipFile(str(docx_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, data in entries.items():
            zf.writestr(arcname, data)
    return docx_path


def _extract(docx_path: Path, media_config: MediaConfig, max_file_size_mb: int):
    return extract(
        docx_path,
        timeout_seconds=30,
        isolation="thread",
        media_config=media_config,
        max_file_size_mb=max_file_size_mb,
    )


class TestNativeDocxImages:
    def test_extracts_embedded_images(self, tmp_path):
        """DOCX with an embedded image extracts it and adds per-document wikilink."""
        docx_path = _make_docx(
            tmp_path,
            "withimage.docx",
            {
                "word/document.xml": _drawing_doc("rId1", "Before image"),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
                "word/media/image1.png": _png_bytes("red"),
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert len(result.media_files) == 1
        assert "![[withimage/" in result.markdown
        assert "![[media/" not in result.markdown
        assert result.media_files[0].media_type == "image"

    def test_image_only_paragraph(self, tmp_path):
        """Paragraph with image but no text runs produces wikilink."""
        docx_path = _make_docx(
            tmp_path,
            "imageonly.docx",
            {
                "word/document.xml": _drawing_doc("rId1", ""),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
                "word/media/image1.png": _png_bytes("blue"),
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert len(result.media_files) == 1
        assert "![[imageonly/" in result.markdown

    def test_path_traversal_in_relationship_target_skipped(self, tmp_path):
        """DOCX with path traversal in relationship target skips the image."""
        docx_path = _make_docx(
            tmp_path,
            "traversal.docx",
            {
                "word/document.xml": _drawing_doc("rId1", "Text"),
                "word/_rels/document.xml.rels": _rels_xml("../docProps/core.xml"),
                "docProps/core.xml": b"<secret>data</secret>",
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert result.media_files == ()

    def test_non_media_relationship_target_skipped(self, tmp_path):
        """DOCX with relationship target outside word/media/ is skipped."""
        docx_path = _make_docx(
            tmp_path,
            "nonmedia.docx",
            {
                "word/document.xml": _drawing_doc("rId1", "Text"),
                "word/_rels/document.xml.rels": _rels_xml("embeddings/oleObject1.bin"),
                "word/embeddings/oleObject1.bin": b"binary data",
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert result.media_files == ()

    def test_no_images_when_disabled(self, tmp_path):
        """When extract_images=False, no images should be extracted."""
        docx_path = _make_docx(tmp_path, "simple.docx", {"word/document.xml": _SIMPLE_DOC})
        config = MediaConfig(
            extract_images=False,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = _extract(docx_path, config, max_file_size_mb=50)
        assert result.media_files == ()

    def test_image_extraction_error_logs_warning(self, tmp_path, caplog):
        """When save_media_to_temp raises ExtractionError, warning is logged and extraction continues."""
        docx_path = _make_docx(
            tmp_path,
            "broken_img.docx",
            {
                "word/document.xml": _drawing_doc("rId1", "Text with broken image"),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
                "word/media/image1.png": b"not valid image bytes",
            },
        )

        with (
            patch(
                "obsidian_import.media.save_media_to_temp",
                side_effect=ExtractionError("PIL failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)

        assert result.media_files == ()
        assert "Text with broken image" in result.markdown
        assert "Failed to extract image" in caplog.text

    def test_embed_id_not_in_rel_map_is_skipped(self, tmp_path):
        """DOCX with a blip referencing an embed ID absent from rel_map skips silently."""
        docx_path = _make_docx(
            tmp_path,
            "dangling.docx",
            {
                "word/document.xml": _drawing_doc("rId99", "Text with dangling embed"),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert result.media_files == ()
        assert "Text with dangling embed" in result.markdown

    def test_media_path_missing_from_zip_is_skipped(self, tmp_path):
        """DOCX with rel_map resolving to a path not present in the zip skips silently."""
        docx_path = _make_docx(
            tmp_path,
            "missing_media.docx",
            {
                "word/document.xml": _drawing_doc("rId1", "Text with truncated archive"),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
            },
        )

        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert result.media_files == ()
        assert "Text with truncated archive" in result.markdown


class TestDecompressionBombGuard:
    """Verify that oversized ZIP entries are rejected before decompression."""

    def test_oversized_document_xml_raises(self, tmp_path):
        """document.xml with uncompressed size exceeding limit raises ExtractionError."""
        large_xml = (
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            + ("A" * 2_000_000)
            + "</w:t></w:r></w:p></w:body></w:document>"
        )
        docx_path = _make_docx(tmp_path, "bomb.docx", {"word/document.xml": large_xml})

        with pytest.raises(ExtractionError, match="uncompressed size"):
            _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=1)

    def test_oversized_rels_xml_raises(self, tmp_path):
        """document.xml.rels with uncompressed size exceeding limit raises ExtractionError."""
        large_rels = (
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ("<!-- " + "X" * 1000 + " -->\n") * 2000
            + "</Relationships>"
        )
        docx_path = _make_docx(
            tmp_path,
            "bomb_rels.docx",
            {"word/document.xml": _SIMPLE_DOC, "word/_rels/document.xml.rels": large_rels},
        )

        with pytest.raises(ExtractionError, match="uncompressed size"):
            _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=1)

    def test_oversized_media_entry_raises(self, tmp_path):
        """Media file with uncompressed size exceeding limit raises ExtractionError."""
        docx_path = _make_docx(
            tmp_path,
            "bomb_media.docx",
            {
                "word/document.xml": _drawing_doc("rId1", ""),
                "word/_rels/document.xml.rels": _rels_xml("media/image1.png"),
                "word/media/image1.png": b"\x00" * 2_000_000,
            },
        )

        with pytest.raises(ExtractionError, match="uncompressed size"):
            _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=1)

    def test_within_limit_succeeds(self, tmp_path):
        """DOCX within the size limit extracts successfully."""
        docx_path = _make_docx(tmp_path, "ok.docx", {"word/document.xml": _SIMPLE_DOC})
        result = _extract(docx_path, _TEST_MEDIA_CONFIG, max_file_size_mb=50)
        assert "Hello World" in result.markdown
