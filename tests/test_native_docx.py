"""Tests for DOCX extraction (mock defusedxml)."""

import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from obsidian_import.backends.native_docx import extract
from obsidian_import.config import MediaConfig
from obsidian_import.exceptions import ExtractionError

_TEST_MEDIA_CONFIG = MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)


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

    def test_no_images_when_disabled(self, tmp_path):
        """When extract_images=False, no images should be extracted."""
        docx = _make_docx(tmp_path, "simple.docx", _SIMPLE_DOC)
        config = MediaConfig(extract_images=False, image_format="png", image_max_dimension=0)
        result = extract(docx, timeout_seconds=30, media_config=config)
        assert result.media_files == ()
