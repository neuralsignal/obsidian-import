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


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _picture_xml(image_number: int) -> str:
    return (
        f"<w:p><w:r><w:drawing><wp:inline>"
        f'<wp:docPr id="{image_number}" name="Picture {image_number}"/>'
        f'<a:graphic><a:graphicData><a:blip r:embed="rId{image_number}"/></a:graphicData></a:graphic>'
        f"</wp:inline></w:drawing></w:r></w:p>"
    )


def _document_xml(body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <w:body>{body}</w:body>
</w:document>"""


def _write_docx(path: Path, items: tuple[tuple[str, str], ...]) -> Path:
    """Write a valid OOXML package from ("text", value) and ("image", color) items, in order.

    Repeating a color reuses that image part, the way a document that embeds the
    same picture twice does.
    """
    body_parts: list[str] = []
    part_numbers: dict[str, int] = {}
    for kind, value in items:
        if kind == "text":
            body_parts.append(_paragraph_xml(value))
        else:
            part_numbers.setdefault(value, len(part_numbers) + 1)
            body_parts.append(_picture_xml(part_numbers[value]))

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/_rels/document.xml.rels", _doc_rels(len(part_numbers)))
        zf.writestr("word/document.xml", _document_xml("".join(body_parts)))
        for color, number in part_numbers.items():
            zf.writestr(f"word/media/image{number}.png", _png_bytes(color))
    return path


_FOOTNOTE_CONTENT_TYPES = _CONTENT_TYPES.replace(
    "</Types>",
    '  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.footnotes+xml"/>\n</Types>',
)

_FOOTNOTE_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId5" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" '
    'Target="footnotes.xml"/>' + _IMAGE_REL.format(index=1) + "</Relationships>"
)


def _write_docx_with_footnote_image(path: Path) -> Path:
    """Write a DOCX whose footnote body holds the only embedded image."""
    body = '<w:p><w:r><w:t>Body text here</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r></w:p>' + _paragraph_xml(
        "Tail paragraph"
    )
    footnotes = (
        _document_xml("")
        .replace("w:document", "w:footnotes")
        .replace(
            "<w:body></w:body>",
            f'<w:footnote w:id="2">{_paragraph_xml("Footnote body text")}{_picture_xml(1)}</w:footnote>',
        )
    )

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _FOOTNOTE_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("word/_rels/document.xml.rels", _FOOTNOTE_DOC_RELS)
        zf.writestr("word/document.xml", _document_xml(body))
        zf.writestr("word/footnotes.xml", footnotes)
        zf.writestr("word/media/image1.png", _png_bytes("red"))
    return path


_CONTAINER_XML = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

_PACKAGE_OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">test</dc:identifier><dc:title>Doc</dc:title><dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>
    <item id="img" href="figure.png" media-type="image/png"/>
  </manifest>
  <spine><itemref idref="c1"/></spine>
</package>"""


def _write_epub(path: Path, body: str) -> Path:
    """Write a minimal EPUB whose single chapter holds the given XHTML body."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("content.opf", _PACKAGE_OPF)
        zf.writestr("figure.png", _png_bytes("red"))
        zf.writestr(
            "c1.xhtml",
            '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" '
            f'xmlns:epub="http://www.idpf.org/2007/ops"><body>{body}</body></html>',
        )
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
        docx = _write_docx(tmp_path / "report.docx", (("text", "Quarterly summary"),))

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
        docx = _write_docx(tmp_path / "isolated.docx", (("text", "Runs in a child process"),))

        result = extract(docx, timeout_seconds=120, isolation="process", media_config=_TEST_MEDIA_CONFIG)

        assert "Runs in a child process" in result.markdown


class TestAnydocMedia:
    def test_embedded_images_become_media_files(self, tmp_path):
        docx = _write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red"), ("image", "blue")))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 2
        assert [mf.filename for mf in result.media_files] == ["asset_img1.png", "asset_img2.png"]
        for media_file in result.media_files:
            assert media_file.media_type == "image"
            assert media_file.source_path.read_bytes()

    def test_images_are_embedded_where_they_sit_in_the_document(self, tmp_path):
        docx = _write_docx(
            tmp_path / "deck.docx",
            (
                ("text", "Text before the figure."),
                ("image", "red"),
                ("text", "Text between the figures."),
                ("image", "blue"),
                ("text", "Text after the figures."),
            ),
        )

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.markdown == (
            "Text before the figure.\n\n"
            "![[deck/asset_img1.png]]\n\n"
            "Text between the figures.\n\n"
            "![[deck/asset_img2.png]]\n\n"
            "Text after the figures.\n"
        )

    def test_repeated_image_is_embedded_at_each_position(self, tmp_path):
        # anydoc deduplicates assets by content: one media file, two embeds.
        docx = _write_docx(
            tmp_path / "deck.docx",
            (("image", "red"), ("text", "Between the two copies."), ("image", "red")),
        )

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 1
        assert result.markdown == ("![[deck/asset_img1.png]]\n\nBetween the two copies.\n\n![[deck/asset_img1.png]]\n")

    def test_images_disabled_yields_text_only(self, tmp_path):
        docx = _write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red")))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_NO_IMAGE_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "![[" not in result.markdown

    def test_unreadable_document_model_keeps_text(self, tmp_path, caplog):
        import anydoc

        docx = _write_docx(tmp_path / "deck.docx", (("text", "Text survives"), ("image", "red")))

        with (
            patch("anydoc.to_document", side_effect=anydoc.MalformedError("unreadable part")),
            caplog.at_level(logging.WARNING, logger="obsidian_import.backends.anydoc"),
        ):
            result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Text survives" in result.markdown
        assert any("document model" in record.getMessage() for record in caplog.records)

    def test_footnote_image_is_not_surfaced_as_an_asset(self, tmp_path):
        # anydoc records footnote bodies on Document.notes, which placement does
        # not walk. That costs nothing today because anydoc drops images inside
        # a footnote part rather than exposing them as assets, so there is no
        # media file to position. If a future anydoc surfaces them, this fails
        # and placement needs to walk notes too.
        docx = _write_docx_with_footnote_image(tmp_path / "noted.docx")

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Body text here" in result.markdown
        assert "Footnote body text" in result.markdown

    def test_unreadable_image_is_skipped_with_text_kept(self, tmp_path):
        docx = _write_docx(tmp_path / "broken.docx", (("text", "Text survives"), ("image", "red")))
        tiny_pixel_config = dataclasses.replace(_TEST_MEDIA_CONFIG, image_max_pixels=1)

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=tiny_pixel_config)

        assert result.media_files == ()
        assert "Text survives" in result.markdown


class TestAnydocPlacementAgainstRealMarkdown:
    """Constructs anydoc renders with no document-model counterpart.

    Each of these once stopped block alignment, which left every image after it
    appended at the end of the note instead of embedded where it belonged.
    """

    def _embed_position(self, path: Path) -> tuple[str, int, int]:
        result = extract(path, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)
        markdown = result.markdown
        assert len(result.media_files) == 1
        return markdown, markdown.index("![["), markdown.index("Tail paragraph.")

    @pytest.mark.parametrize(
        ("label", "list_html"),
        [
            ("decimal", "<ol><li>First item text</li><li>Second item text</li></ol>"),
            ("lower_alpha", '<ol type="a"><li>Alpha item text</li><li>Beta item text</li></ol>'),
            ("lower_roman", '<ol type="i"><li>Roman item text</li><li>Other item text</li></ol>'),
            ("nested", "<ol><li>Outer one item<ol><li>Inner one item</li></ol></li></ol>"),
        ],
    )
    def test_image_after_an_ordered_list_stays_inline(self, tmp_path, label, list_html):
        # anydoc renders the list marker into the text (`1. `, `- c. `, `- iii. `),
        # and puts a blank line before nested items, neither of which the
        # document model's own text carries.
        epub = _write_epub(
            tmp_path / f"{label}.epub",
            f'<p>Intro paragraph.</p>{list_html}<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail for {label}: {markdown!r}"

    def test_image_after_a_referenced_link_target_stays_inline(self, tmp_path):
        # A referenced footnote target renders as an `<a id="..."></a>` block of
        # its own, which no document-model block accounts for.
        epub = _write_epub(
            tmp_path / "notes.epub",
            '<p>Text with a note<a epub:type="noteref" href="#fn1">1</a>.</p>'
            '<aside epub:type="footnote" id="fn1"><p>Note body</p></aside>'
            '<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail: {markdown!r}"

    def test_bullet_list_and_numeric_table_keep_placing(self, tmp_path):
        epub = _write_epub(
            tmp_path / "mixed.epub",
            "<p>Intro paragraph.</p><ul><li>First item text</li></ul>"
            "<table><tr><td>2024</td><td>3141</td></tr></table>"
            '<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail: {markdown!r}"


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
        docx = _write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red"), ("image", "blue")))

        document = extract_file(docx, default_config())

        assert "With figures" in document.markdown
        assert len(document.media_files) == 2
        for media_file in document.media_files:
            assert f"![[deck/{media_file.filename}]]" in document.markdown

    def test_xlsx_row_cap_is_reported_as_ignored(self, tmp_path, caplog):
        # The shipped default is `xlsx: anydoc`, which reads every row, so
        # extraction.xlsx_max_rows_per_sheet does not apply on the default path.
        # It stays configured for `xlsx: native`, and the gap is reported rather
        # than passing silently.
        sheet = tmp_path / "rows.xlsx"
        sheet.write_bytes(b"not a real workbook")

        with (
            caplog.at_level(logging.WARNING, logger="obsidian_import.registry"),
            pytest.raises(ExtractionError),
        ):
            extract_file(sheet, default_config())

        assert any("max_rows_per_sheet" in record.getMessage() for record in caplog.records)

    @pytest.mark.parametrize("stem", ["book.epub", "memo.rtf", "sheet.ods"])
    def test_formats_without_a_config_key_reach_anydoc(self, tmp_path, stem):
        # These extensions have no `backends` key, so `default: anydoc` is what
        # dispatches them; the placeholder content makes anydoc reject them,
        # which proves the file reached the anydoc backend.
        unreadable = tmp_path / stem
        unreadable.write_bytes(b"placeholder")

        with pytest.raises(ExtractionError, match="anydoc could not convert"):
            extract_file(unreadable, default_config())
