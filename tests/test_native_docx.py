"""Tests for DOCX extraction (mock defusedxml)."""

import io
import logging
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement

import pytest
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from obsidian_import.backends.native_docx import (
    _extract_paragraph,
    _extract_table,
    _local_name,
    extract,
)
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_max_pixels=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


def _make_docx(tmp_path: Path, name: str, xml_content: str) -> Path:
    """Create a minimal DOCX file (ZIP with word/document.xml)."""
    docx_path = tmp_path / name
    with zipfile.ZipFile(str(docx_path), "w") as zf:
        zf.writestr("word/document.xml", xml_content)
    return docx_path


_SIMPLE_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello World</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

_HEADING_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>Title</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>Body text</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

_TABLE_DOC = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Col1</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Col2</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""


class TestNativeDocxExtract:
    def test_extracts_simple_text(self, tmp_path):
        docx = _make_docx(tmp_path, "simple.docx", _SIMPLE_DOC)
        result = extract(docx, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert "# simple" in result.markdown
        assert "Hello World" in result.markdown

    def test_extracts_headings(self, tmp_path):
        docx = _make_docx(tmp_path, "heading.docx", _HEADING_DOC)
        result = extract(docx, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert "## Title" in result.markdown
        assert "Body text" in result.markdown

    def test_extracts_tables(self, tmp_path):
        docx = _make_docx(tmp_path, "table.docx", _TABLE_DOC)
        result = extract(docx, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert "Col1" in result.markdown
        assert "Col2" in result.markdown
        assert "|" in result.markdown

    def test_invalid_zip_raises(self, tmp_path):
        bad_file = tmp_path / "bad.docx"
        bad_file.write_bytes(b"not a zip")
        with pytest.raises(ExtractionError, match="Not a valid DOCX"):
            extract(bad_file, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

    def test_missing_document_xml_raises(self, tmp_path):
        docx_path = tmp_path / "empty.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("content.xml", "<root/>")
        with pytest.raises(ExtractionError, match="No word/document.xml"):
            extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

    def test_no_body_returns_message(self, tmp_path):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:document>"""
        docx = _make_docx(tmp_path, "nobody.docx", xml)
        result = extract(docx, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert "No body content" in result.markdown

    def test_extracts_embedded_images(self, tmp_path):
        """DOCX with an embedded image extracts it and adds per-document wikilink."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Before image</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="media/image1.png"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        docx_path = tmp_path / "withimage.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/media/image1.png", img_bytes)

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert len(result.media_files) == 1
        assert "![[withimage/" in result.markdown
        assert "![[media/" not in result.markdown
        assert result.media_files[0].media_type == "image"

    def test_image_only_paragraph(self, tmp_path):
        """Paragraph with image but no text runs produces wikilink (line 106)."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="media/image1.png"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        docx_path = tmp_path / "imageonly.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/media/image1.png", img_bytes)

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert len(result.media_files) == 1
        assert "![[imageonly/" in result.markdown

    def test_path_traversal_in_relationship_target_skipped(self, tmp_path):
        """DOCX with path traversal in relationship target skips the image."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Text</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="../docProps/core.xml"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        docx_path = tmp_path / "traversal.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("docProps/core.xml", b"<secret>data</secret>")

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert result.media_files == ()

    def test_non_media_relationship_target_skipped(self, tmp_path):
        """DOCX with relationship target outside word/media/ is skipped."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Text</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="embeddings/oleObject1.bin"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        docx_path = tmp_path / "nonmedia.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/embeddings/oleObject1.bin", b"binary data")

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert result.media_files == ()

    def test_no_images_when_disabled(self, tmp_path):
        """When extract_images=False, no images should be extracted."""
        docx = _make_docx(tmp_path, "simple.docx", _SIMPLE_DOC)
        config = MediaConfig(
            extract_images=False,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        )
        result = extract(docx, timeout_seconds=30, media_config=config)
        assert result.media_files == ()

    def test_image_extraction_error_logs_warning(self, tmp_path, caplog):
        """When save_media_to_temp raises ExtractionError, warning is logged and extraction continues."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Text with broken image</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="media/image1.png"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        docx_path = tmp_path / "broken_img.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/media/image1.png", b"not valid image bytes")

        with (
            patch(
                "obsidian_import.media.save_media_to_temp",
                side_effect=ExtractionError("PIL failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Text with broken image" in result.markdown
        assert "Failed to extract image" in caplog.text

    def test_embed_id_not_in_rel_map_is_skipped(self, tmp_path):
        """DOCX with a blip referencing an embed ID absent from rel_map skips silently."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Text with dangling embed</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId99"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="media/image1.png"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        docx_path = tmp_path / "dangling.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert result.media_files == ()
        assert "Text with dangling embed" in result.markdown

    def test_media_path_missing_from_zip_is_skipped(self, tmp_path):
        """DOCX with rel_map resolving to a path not present in the zip skips silently."""
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Text with truncated archive</w:t></w:r>
      <w:r>
        <w:drawing>
          <wp:inline>
            <a:graphic>
              <a:graphicData>
                <a:blip r:embed="rId1"/>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

        rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="media/image1.png"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"/>
</Relationships>"""

        docx_path = tmp_path / "missing_media.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)

        result = extract(docx_path, timeout_seconds=30, media_config=_TEST_MEDIA_CONFIG)
        assert result.media_files == ()
        assert "Text with truncated archive" in result.markdown

    def test_extract_table_empty_rows(self):
        """A w:tbl with no w:tr children returns empty string."""
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        tbl = Element(f"{{{ns}}}tbl")
        assert _extract_table(tbl) == ""

    def test_extract_paragraph_non_numeric_heading(self):
        """HeadingCustom style falls back to plain text (no # prefix)."""
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        para = Element(f"{{{ns}}}p")
        ppr = SubElement(para, f"{{{ns}}}pPr")
        pstyle = SubElement(ppr, f"{{{ns}}}pStyle")
        pstyle.set(f"{{{ns}}}val", "HeadingCustom")
        run = SubElement(para, f"{{{ns}}}r")
        t = SubElement(run, f"{{{ns}}}t")
        t.text = "Custom heading text"

        result = _extract_paragraph(para)
        assert result == "Custom heading text"
        assert not result.startswith("#")


class TestLocalName:
    def test_with_namespace(self):
        elem = Element("{http://example.com}body")
        assert _local_name(elem) == "body"

    def test_without_namespace(self):
        elem = Element("plainTag")
        assert _local_name(elem) == "plainTag"

    @given(tag=st.text(min_size=1).filter(lambda s: "}" not in s))
    def test_no_namespace_returns_tag_unchanged(self, tag):
        elem = Element(tag)
        assert _local_name(elem) == tag

    @given(
        ns=st.text(min_size=1).filter(lambda s: "}" not in s),
        local=st.text(min_size=1).filter(lambda s: "}" not in s),
    )
    def test_namespace_stripped(self, ns, local):
        elem = Element(f"{{{ns}}}{local}")
        assert _local_name(elem) == local


class TestExtractParagraphEdgeCases:
    def test_runs_with_whitespace_only_text(self):
        """Paragraph with runs containing only whitespace returns empty string."""
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        para = Element(f"{{{ns}}}p")
        run = SubElement(para, f"{{{ns}}}r")
        t = SubElement(run, f"{{{ns}}}t")
        t.text = "   "

        assert _extract_paragraph(para) == ""

    @given(level=st.integers(min_value=1, max_value=6))
    def test_heading_levels(self, level):
        """Valid heading levels produce correct markdown prefix."""
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        para = Element(f"{{{ns}}}p")
        ppr = SubElement(para, f"{{{ns}}}pPr")
        pstyle = SubElement(ppr, f"{{{ns}}}pStyle")
        pstyle.set(f"{{{ns}}}val", f"Heading{level}")
        run = SubElement(para, f"{{{ns}}}r")
        t = SubElement(run, f"{{{ns}}}t")
        t.text = "Text"

        result = _extract_paragraph(para)
        assert result == f"{'#' * (level + 1)} Text"
