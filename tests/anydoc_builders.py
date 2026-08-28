"""Shared OOXML / EPUB / PDF builder helpers for anydoc tests."""

import io
import zipfile
from pathlib import Path

from PIL import Image

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


def write_docx(path: Path, items: tuple[tuple[str, str], ...]) -> Path:
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


def write_docx_with_footnote_image(path: Path) -> Path:
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


def write_epub(path: Path, body: str) -> Path:
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


def write_pdf(path: Path, text: str) -> Path:
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
    for i, body_bytes in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body_bytes + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
