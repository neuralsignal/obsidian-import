"""Tests for obsidian_import public API: extract_file, extract_text, _estimate_page_count."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import import _estimate_page_count, extract_file, extract_text
from obsidian_import.config import ImportConfig, default_config
from obsidian_import.extraction_result import ExtractionResult, MediaFile


def _config() -> ImportConfig:
    return default_config()


# ---------------------------------------------------------------------------
# _estimate_page_count
# ---------------------------------------------------------------------------


class TestEstimatePageCount:
    def test_non_pdf_returns_none(self) -> None:
        assert _estimate_page_count("anything", ".docx") is None

    def test_pdf_no_page_headings_returns_none(self) -> None:
        assert _estimate_page_count("Hello world", ".pdf") is None

    def test_pdf_with_page_headings(self) -> None:
        md = "## Page 1\ntext\n## Page 2\nmore"
        assert _estimate_page_count(md, ".pdf") == 2

    @given(n=st.integers(min_value=1, max_value=50))
    def test_pdf_page_count_property(self, n: int) -> None:
        md = "\n".join(f"## Page {i}\ncontent" for i in range(1, n + 1))
        assert _estimate_page_count(md, ".pdf") == n


# ---------------------------------------------------------------------------
# extract_file
# ---------------------------------------------------------------------------


class TestExtractFile:
    def test_xlsx_forwards_max_rows_per_sheet(self) -> None:
        config = _config()
        fake_result = ExtractionResult(markdown="table data", media_files=())

        with patch("obsidian_import.extract_with_backend", return_value=fake_result) as mock:
            doc = extract_file(Path("/tmp/sheet.xlsx"), config)
            call_kwargs = mock.call_args
            assert call_kwargs.kwargs["max_rows_per_sheet"] == config.extraction.xlsx_max_rows_per_sheet
            assert doc.markdown == "table data"

    def test_image_file_sets_associated_files(self) -> None:
        config = _config()
        fake_result = ExtractionResult(markdown="![img](data)", media_files=())
        path = Path("/tmp/photo.png")

        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            doc = extract_file(path, config)
            assert doc.associated_files == (path,)

    def test_non_image_file_has_no_associated_files(self) -> None:
        config = _config()
        fake_result = ExtractionResult(markdown="text", media_files=())

        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            doc = extract_file(Path("/tmp/report.pdf"), config)
            assert doc.associated_files == ()

    def test_media_files_appended_as_wikilinks(self) -> None:
        config = _config()
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="img.png", media_type="image/png")
        fake_result = ExtractionResult(markdown="content", media_files=(mf,))

        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            doc = extract_file(Path("/tmp/report.pdf"), config)
            assert "![[report/img.png]]" in doc.markdown

    def test_media_wikilink_not_duplicated(self) -> None:
        config = _config()
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="img.png", media_type="image/png")
        existing_md = "content\n\n![[report/img.png]]"
        fake_result = ExtractionResult(markdown=existing_md, media_files=(mf,))

        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            doc = extract_file(Path("/tmp/report.pdf"), config)
            assert doc.markdown.count("![[report/img.png]]") == 1


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_returns_plain_markdown(self) -> None:
        config = _config()
        fake_result = ExtractionResult(markdown="hello world", media_files=())

        with patch("obsidian_import.extract_with_backend", return_value=fake_result):
            text = extract_text(Path("/tmp/doc.pdf"), config)
            assert text == "hello world"

    def test_xlsx_forwards_max_rows_per_sheet(self) -> None:
        config = _config()
        fake_result = ExtractionResult(markdown="table", media_files=())

        with patch("obsidian_import.extract_with_backend", return_value=fake_result) as mock:
            extract_text(Path("/tmp/sheet.xlsx"), config)
            assert mock.call_args.kwargs["max_rows_per_sheet"] == config.extraction.xlsx_max_rows_per_sheet
