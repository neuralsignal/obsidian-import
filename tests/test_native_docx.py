"""Tests for DOCX text/structure extraction (mock defusedxml).

Embedded-image and decompression-limit tests live in test_native_docx_images.py.
"""

import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement

import pytest
from conftest import make_test_media_config
from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.backends.native_docx import (
    _extract_paragraph,
    _extract_table,
    _local_name,
    extract,
)
from obsidian_import.exceptions import ExtractionError

_TEST_MEDIA_CONFIG = make_test_media_config()


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
        result = extract(
            docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
        )
        assert "# simple" in result.markdown
        assert "Hello World" in result.markdown

    def test_extracts_headings(self, tmp_path):
        docx = _make_docx(tmp_path, "heading.docx", _HEADING_DOC)
        result = extract(
            docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
        )
        assert "## Title" in result.markdown
        assert "Body text" in result.markdown

    def test_extracts_tables(self, tmp_path):
        docx = _make_docx(tmp_path, "table.docx", _TABLE_DOC)
        result = extract(
            docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
        )
        assert "Col1" in result.markdown
        assert "Col2" in result.markdown
        assert "|" in result.markdown

    def test_invalid_zip_raises(self, tmp_path):
        bad_file = tmp_path / "bad.docx"
        bad_file.write_bytes(b"not a zip")
        with pytest.raises(ExtractionError, match="Not a valid DOCX"):
            extract(
                bad_file, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
            )

    def test_missing_document_xml_raises(self, tmp_path):
        docx_path = tmp_path / "empty.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("content.xml", "<root/>")
        with pytest.raises(ExtractionError, match="No word/document.xml"):
            extract(
                docx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
            )

    def test_no_body_returns_message(self, tmp_path):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:document>"""
        docx = _make_docx(tmp_path, "nobody.docx", xml)
        result = extract(
            docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
        )
        assert "No body content" in result.markdown

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

    @given(level=st.integers(min_value=7, max_value=999_999_999))
    def test_heading_level_capped_at_six(self, level):
        """Heading levels above 6 are clamped to 6 to prevent memory exhaustion."""
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        para = Element(f"{{{ns}}}p")
        ppr = SubElement(para, f"{{{ns}}}pPr")
        pstyle = SubElement(ppr, f"{{{ns}}}pStyle")
        pstyle.set(f"{{{ns}}}val", f"Heading{level}")
        run = SubElement(para, f"{{{ns}}}r")
        t = SubElement(run, f"{{{ns}}}t")
        t.text = "Text"

        result = _extract_paragraph(para)
        assert result == "####### Text"


class TestDecompressionBombGuard:
    """Verify that oversized ZIP entries are rejected before decompression."""

    def test_oversized_document_xml_raises(self, tmp_path):
        """document.xml with uncompressed size exceeding limit raises ExtractionError."""
        large_xml = (
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            + ("A" * 2_000_000)
            + "</w:t></w:r></w:p></w:body></w:document>"
        )
        docx_path = tmp_path / "bomb.docx"
        with zipfile.ZipFile(str(docx_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", large_xml)

        with pytest.raises(ExtractionError, match="uncompressed size"):
            extract(
                docx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=1
            )

    def test_oversized_rels_xml_raises(self, tmp_path):
        """document.xml.rels with uncompressed size exceeding limit raises ExtractionError."""
        small_doc = _SIMPLE_DOC
        large_rels = (
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ("<!-- " + "X" * 1000 + " -->\n") * 2000
            + "</Relationships>"
        )
        docx_path = tmp_path / "bomb_rels.docx"
        with zipfile.ZipFile(str(docx_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", small_doc)
            zf.writestr("word/_rels/document.xml.rels", large_rels)

        with pytest.raises(ExtractionError, match="uncompressed size"):
            extract(
                docx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=1
            )

    def test_oversized_media_entry_raises(self, tmp_path):
        """Media file with uncompressed size exceeding limit raises ExtractionError."""
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

        large_image = b"\x00" * 2_000_000

        docx_path = tmp_path / "bomb_media.docx"
        with zipfile.ZipFile(str(docx_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", xml)
            zf.writestr("word/_rels/document.xml.rels", rels_xml)
            zf.writestr("word/media/image1.png", large_image)

        with pytest.raises(ExtractionError, match="uncompressed size"):
            extract(
                docx_path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=1
            )

    def test_within_limit_succeeds(self, tmp_path):
        """DOCX within the size limit extracts successfully."""
        docx = _make_docx(tmp_path, "ok.docx", _SIMPLE_DOC)
        result = extract(
            docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG, max_file_size_mb=50
        )
        assert "Hello World" in result.markdown
