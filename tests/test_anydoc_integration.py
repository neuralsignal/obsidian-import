"""Integration tests for anydoc placement against real markdown and default config routing."""

import logging
from pathlib import Path

import pytest
from anydoc_builders import write_docx, write_epub
from conftest import make_test_media_config

from obsidian_import import extract_file
from obsidian_import.backends.anydoc import extract
from obsidian_import.config import default_config
from obsidian_import.exceptions import ExtractionError

_TEST_MEDIA_CONFIG = make_test_media_config()


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
        epub = write_epub(
            tmp_path / f"{label}.epub",
            f'<p>Intro paragraph.</p>{list_html}<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail for {label}: {markdown!r}"

    def test_image_after_a_referenced_link_target_stays_inline(self, tmp_path):
        epub = write_epub(
            tmp_path / "notes.epub",
            '<p>Text with a note<a epub:type="noteref" href="#fn1">1</a>.</p>'
            '<aside epub:type="footnote" id="fn1"><p>Note body</p></aside>'
            '<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail: {markdown!r}"

    def test_bullet_list_and_numeric_table_keep_placing(self, tmp_path):
        epub = write_epub(
            tmp_path / "mixed.epub",
            "<p>Intro paragraph.</p><ul><li>First item text</li></ul>"
            "<table><tr><td>2024</td><td>3141</td></tr></table>"
            '<p><img src="figure.png" alt=""/></p><p>Tail paragraph.</p>',
        )

        markdown, embed_at, tail_at = self._embed_position(epub)

        assert embed_at < tail_at, f"image was not embedded before the tail: {markdown!r}"


class TestAnydocThroughDefaultConfig:
    """The shipped default config routes documents through anydoc."""

    def test_docx_extraction_embeds_images_in_the_note(self, tmp_path):
        docx = write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red"), ("image", "blue")))

        document = extract_file(docx, default_config())

        assert "With figures" in document.markdown
        assert len(document.media_files) == 2
        for media_file in document.media_files:
            assert f"![[deck/{media_file.filename}]]" in document.markdown

    def test_xlsx_row_cap_is_reported_as_ignored(self, tmp_path, caplog):
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
        unreadable = tmp_path / stem
        unreadable.write_bytes(b"placeholder")

        with pytest.raises(ExtractionError, match="anydoc could not convert"):
            extract_file(unreadable, default_config())
