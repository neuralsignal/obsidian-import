"""Tests for the anydoc backend, exercised against real anydoc conversions."""

import dataclasses
import logging
from unittest.mock import patch

import pytest
from anydoc_builders import write_docx, write_docx_with_footnote_image, write_pdf
from conftest import make_test_media_config
from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.backends.anydoc import extract
from obsidian_import.exceptions import BackendNotAvailableError, ExtractionError

_TEST_MEDIA_CONFIG = make_test_media_config()
_NO_IMAGE_MEDIA_CONFIG = dataclasses.replace(_TEST_MEDIA_CONFIG, extract_images=False)


class TestAnydocText:
    def test_extracts_docx_text(self, tmp_path):
        docx = write_docx(tmp_path / "report.docx", (("text", "Quarterly summary"),))

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
        width = len(rows[0])
        square_rows = [row[:width] + ["x"] * (width - len(row)) for row in rows]
        csv = tmp_path_factory.mktemp("csv") / "rows.csv"
        csv.write_text("\n".join(",".join(row) for row in square_rows) + "\n")

        result = extract(csv, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        rendered = [line for line in result.markdown.splitlines() if line.startswith("|")]
        assert sum("---" in line for line in rendered) == 1
        data_lines = [line for line in rendered if "---" not in line]
        assert data_lines[-len(square_rows) :] == ["| " + " | ".join(row) + " |" for row in square_rows]

    def test_extracts_pdf_text_without_media(self, tmp_path):
        pdf = write_pdf(tmp_path / "note.pdf", "Hello PDF")

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
        docx = write_docx(tmp_path / "isolated.docx", (("text", "Runs in a child process"),))

        result = extract(docx, timeout_seconds=120, isolation="process", media_config=_TEST_MEDIA_CONFIG)

        assert "Runs in a child process" in result.markdown


class TestAnydocMedia:
    def test_embedded_images_become_media_files(self, tmp_path):
        docx = write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red"), ("image", "blue")))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 2
        assert [mf.filename for mf in result.media_files] == ["asset_img1.png", "asset_img2.png"]
        for media_file in result.media_files:
            assert media_file.media_type == "image"
            assert media_file.source_path.read_bytes()

    def test_images_are_embedded_where_they_sit_in_the_document(self, tmp_path):
        docx = write_docx(
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
        docx = write_docx(
            tmp_path / "deck.docx",
            (("image", "red"), ("text", "Between the two copies."), ("image", "red")),
        )

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert len(result.media_files) == 1
        assert result.markdown == ("![[deck/asset_img1.png]]\n\nBetween the two copies.\n\n![[deck/asset_img1.png]]\n")

    def test_images_disabled_yields_text_only(self, tmp_path):
        docx = write_docx(tmp_path / "deck.docx", (("text", "With figures"), ("image", "red")))

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_NO_IMAGE_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "![[" not in result.markdown

    def test_unreadable_document_model_keeps_text(self, tmp_path, caplog):
        import anydoc

        docx = write_docx(tmp_path / "deck.docx", (("text", "Text survives"), ("image", "red")))

        with (
            patch("anydoc.to_document", side_effect=anydoc.MalformedError("unreadable part")),
            caplog.at_level(logging.WARNING, logger="obsidian_import.backends.anydoc"),
        ):
            result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Text survives" in result.markdown
        assert any("document model" in record.getMessage() for record in caplog.records)

    def test_footnote_image_is_not_surfaced_as_an_asset(self, tmp_path):
        docx = write_docx_with_footnote_image(tmp_path / "noted.docx")

        result = extract(docx, timeout_seconds=30, isolation="thread", media_config=_TEST_MEDIA_CONFIG)

        assert result.media_files == ()
        assert "Body text here" in result.markdown
        assert "Footnote body text" in result.markdown

    def test_unreadable_image_is_skipped_with_text_kept(self, tmp_path):
        docx = write_docx(tmp_path / "broken.docx", (("text", "Text survives"), ("image", "red")))
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
