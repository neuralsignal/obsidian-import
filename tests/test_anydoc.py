"""Tests for the anydoc backend, exercised against real anydoc conversions."""

import dataclasses
import io
import logging
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import make_test_media_config
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from obsidian_import import extract_file
from obsidian_import.backends.anydoc import extract
from obsidian_import.config import default_config
from obsidian_import.exceptions import BackendNotAvailableError, ExtractionError

_TEST_MEDIA_CONFIG = make_test_media_config()
_NO_IMAGE_MEDIA_CONFIG = dataclasses.replace(_TEST_MEDIA_CONFIG, extract_images=False)

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""

_IMAGE_REL = (
    '<Relationship Id="rId{index}" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
    'Target="media/image{index}.png"/>'
)


def _doc_rels(image_count: int) -> str:
    relationships = "".join(_IMAGE_REL.format(index=i) for i in range(1, image_count + 1))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )


def _png_bytes(color: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (12, 8), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _document_xml(text: str, image_count: int) -> str:
    pictures = "".join(
        f"""<w:p><w:r><w:drawing><wp:inline>
        <wp:docPr id="{i}" name="Picture {i}" descr="figure {i}"/>
        <a:graphic><a:graphicData><a:blip r:embed="rId{i}"/></a:graphicData></a:graphic>
        </wp:inline></w:drawing></w:r></w:p>"""
        for i in range(1, image_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
    {pictures}
  </w:body>
</w:document>"""


def _write_docx(path: Path, text: str, image_colors: tuple[str, ...]) -> Path:
    """Write a valid OOXML package with one paragraph and one image per color."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/_rels/document.xml.rels", _doc_rels(len(image_colors)))
        zf.writestr("word/document.xml", _document_xml(text, len(image_colors)))
        for i, color in enumerate(image_colors, 1):
            zf.writestr(f"word/media/image{i}.png", _png_bytes(color))
    return path


def _write_pdf(path: Path, text: str) -> Path:
    """Write a minimal single-page PDF holding one text run."""
    stream = f"BT /F1 24 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


class TestAnydocText:
    def test_extracts_docx_text(self, tmp_path):
        docx = _write_docx(tmp_path / "report.docx", "Quarterly summary", ())

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "Quarterly summary" in result.markdown
        assert result.media_files == ()

    def test_extracts_csv_as_markdown_table(self, tmp_path):
        csv = tmp_path / "rows.csv"
        csv.write_text("name,count\nwidget,3\n")

        result = extract(csv, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "| name | count |" in result.markdown
        assert "| widget | 3 |" in result.markdown

    @given(
        rows=st.lists(
            st.lists(
                st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=6),
                min_size=1,
                max_size=4,
            ),
            min_size=2,
            max_size=6,
        )
    )
    def test_csv_rows_survive_conversion(self, tmp_path_factory, rows):
        # Every CSV row reaches the markdown table as its own row, in order.
        # Which row becomes the header is anydoc's call, so the assertion is
        # on content preservation rather than on the header line.
        width = len(rows[0])
        square_rows = [row[:width] + ["x"] * (width - len(row)) for row in rows]
        csv = tmp_path_factory.mktemp("csv") / "rows.csv"
        csv.write_text("\n".join(",".join(row) for row in square_rows) + "\n")

        result = extract(csv, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        rendered = [line for line in result.markdown.splitlines() if line.startswith("|")]
        # Cells are lowercase letters only, so a dash marks the separator row.
        assert sum("---" in line for line in rendered) == 1
        data_lines = [line for line in rendered if "---" not in line]
        assert data_lines[-len(square_rows) :] == ["| " + " | ".join(row) + " |" for row in square_rows]

    def test_extracts_pdf_text_without_media(self, tmp_path):
        pdf = _write_pdf(tmp_path / "note.pdf", "Hello PDF")

        result = extract(pdf, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "Hello PDF" in result.markdown
        assert result.media_files == ()

    def test_empty_document_gets_placeholder(self, tmp_path):
        csv = tmp_path / "empty.csv"
        csv.write_text("")

        result = extract(csv, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert "No text content extracted" in result.markdown
        assert "empty.csv" in result.markdown

    def test_extracts_under_process_isolation(self, tmp_path):
        docx = _write_docx(tmp_path / "isolated.docx", "Runs in a child process", ())

        result = extract(docx, timeout_seconds=120, isolation="process", media_config=_TEST_MEDIA_CONFIG)

        assert "Runs in a child process" in result.markdown


class TestAnydocMedia:
    def test_embedded_images_become_media_files(self, tmp_path):
        docx = _write_docx(tmp_path / "deck.docx", "With figures", ("red", "blue"))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 2
        assert [mf.filename for mf in result.media_files] == ["asset_img1.png", "asset_img2.png"]
        for media_file in result.media_files:
            assert media_file.media_type == "image"
            assert media_file.source_path.read_bytes()

    def test_images_disabled_yields_text_only(self, tmp_path):
        docx = _write_docx(tmp_path / "deck.docx", "With figures", ("red",))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_NO_IMAGE_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "![[" not in result.markdown

    def test_unreadable_document_model_keeps_text(self, tmp_path, caplog):
        import anydoc

        docx = _write_docx(tmp_path / "deck.docx", "Text survives", ("red",))

        with (
            patch("anydoc.to_document", side_effect=anydoc.MalformedError("unreadable part")),
            caplog.at_level(logging.WARNING, logger="obsidian_import.backends.anydoc"),
        ):
            result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Text survives" in result.markdown
        assert any("document model" in record.getMessage() for record in caplog.records)

    def test_unreadable_image_is_skipped_with_text_kept(self, tmp_path):
        docx = _write_docx(tmp_path / "broken.docx", "Text survives", ("red",))
        tiny_pixel_config = dataclasses.replace(_TEST_MEDIA_CONFIG, image_max_pixels=1)

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=tiny_pixel_config)

        assert result.media_files == ()
        assert "Text survives" in result.markdown


class TestAnydocFailures:
    def test_unsupported_format_raises_extraction_error(self, tmp_path):
        unknown = tmp_path / "notes.txt"
        unknown.write_text("plain text has no anydoc parser")

        with pytest.raises(ExtractionError, match="anydoc could not convert"):
            extract(unknown, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

    def test_malformed_document_raises_extraction_error(self, tmp_path):
        broken = tmp_path / "corrupt.docx"
        broken.write_bytes(b"this is not a zip archive")

        with pytest.raises(ExtractionError, match="anydoc could not convert"):
            extract(broken, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

    def test_missing_file_propagates(self, tmp_path):
        with pytest.raises(ExtractionError, match="FileNotFoundError|No such file"):
            extract(tmp_path / "absent.docx", timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

    def test_missing_dependency_raises(self, tmp_path):
        with (
            patch("obsidian_import.backends.anydoc.importlib.util.find_spec", return_value=None),
            pytest.raises(BackendNotAvailableError, match="anydoc is not installed"),
        ):
            extract(tmp_path / "any.docx", timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)


class TestAnydocThroughDefaultConfig:
    """The shipped default config routes documents through anydoc."""

    def test_docx_extraction_embeds_images_in_the_note(self, tmp_path):
        docx = _write_docx(tmp_path / "deck.docx", "With figures", ("red", "blue"))

        document = extract_file(docx, default_config())

        assert "With figures" in document.markdown
        assert len(document.media_files) == 2
        for media_file in document.media_files:
            assert f"![[deck/{media_file.filename}]]" in document.markdown

    @pytest.mark.parametrize("stem", ["book.epub", "memo.rtf", "sheet.ods"])
    def test_formats_without_a_config_key_reach_anydoc(self, tmp_path, stem):
        # These extensions have no `backends` key, so `default: anydoc` is what
        # dispatches them; the placeholder content makes anydoc reject them,
        # which proves the file reached the anydoc backend.
        unreadable = tmp_path / stem
        unreadable.write_bytes(b"placeholder")

        with pytest.raises(ExtractionError, match="anydoc could not convert"):
            extract_file(unreadable, default_config())
