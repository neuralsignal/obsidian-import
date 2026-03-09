"""Tests for DOCX extraction (mock defusedxml)."""

import zipfile
from pathlib import Path

import pytest

from obsidian_import.backends.native_docx import extract
from obsidian_import.exceptions import ExtractionError


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
        result = extract(docx, timeout_seconds=30)
        assert "# simple" in result
        assert "Hello World" in result

    def test_extracts_headings(self, tmp_path):
        docx = _make_docx(tmp_path, "heading.docx", _HEADING_DOC)
        result = extract(docx, timeout_seconds=30)
        assert "## Title" in result
        assert "Body text" in result

    def test_extracts_tables(self, tmp_path):
        docx = _make_docx(tmp_path, "table.docx", _TABLE_DOC)
        result = extract(docx, timeout_seconds=30)
        assert "Col1" in result
        assert "Col2" in result
        assert "|" in result

    def test_invalid_zip_raises(self, tmp_path):
        bad_file = tmp_path / "bad.docx"
        bad_file.write_bytes(b"not a zip")
        with pytest.raises(ExtractionError, match="Not a valid DOCX"):
            extract(bad_file, timeout_seconds=30)

    def test_missing_document_xml_raises(self, tmp_path):
        docx_path = tmp_path / "empty.docx"
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("content.xml", "<root/>")
        with pytest.raises(ExtractionError, match="No word/document.xml"):
            extract(docx_path, timeout_seconds=30)

    def test_no_body_returns_message(self, tmp_path):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
</w:document>"""
        docx = _make_docx(tmp_path, "nobody.docx", xml)
        result = extract(docx, timeout_seconds=30)
        assert "No body content" in result
