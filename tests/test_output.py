"""Tests for frontmatter formatting and metadata."""

from pathlib import Path

from obsidian_import.config import OutputConfig
from obsidian_import.output import ExtractedDocument, format_output, output_path_for


def _make_doc(title: str, markdown: str) -> ExtractedDocument:
    return ExtractedDocument(
        source_path=Path("/tmp/test.pdf"),
        markdown=markdown,
        title=title,
        file_type="pdf",
        page_count=3,
        associated_files=(),
        media_files=(),
    )


def _make_config(frontmatter: bool) -> OutputConfig:
    return OutputConfig(
        directory="./out",
        frontmatter=frontmatter,
        metadata_fields=("title", "source", "original_path", "file_type", "page_count"),
    )


class TestFormatOutput:
    def test_includes_frontmatter(self):
        result = format_output(_make_doc("Test Doc", "# Hello\n\nContent here."), _make_config(True))
        assert result.startswith("---\n")
        assert "title: Test Doc" in result
        assert "source:" in result
        assert "file_type: pdf" in result
        assert "page_count: 3" in result

    def test_no_frontmatter(self):
        result = format_output(_make_doc("Test Doc", "# Hello\n\nContent here."), _make_config(False))
        assert not result.startswith("---")
        assert "# Hello" in result

    def test_includes_markdown_body(self):
        result = format_output(_make_doc("Test Doc", "# Hello\n\nContent here."), _make_config(True))
        assert "Content here." in result

    def test_page_count_none_omitted(self):
        doc = ExtractedDocument(
            source_path=Path("/tmp/test.docx"),
            markdown="text",
            title="Doc",
            file_type="docx",
            page_count=None,
            associated_files=(),
            media_files=(),
        )
        result = format_output(doc, _make_config(True))
        assert "page_count" not in result

    def test_extracted_at_present(self):
        config = OutputConfig(
            directory="./out",
            frontmatter=True,
            metadata_fields=("extracted_at",),
        )
        result = format_output(_make_doc("Test Doc", "# Hello"), config)
        assert "extracted_at:" in result

    def test_special_chars_in_title_escaped(self):
        doc = _make_doc('Title: "quoted"', "# Hello")
        result = format_output(doc, _make_config(True))
        assert 'title: "Title' in result


class TestOutputPathFor:
    def test_computes_md_extension(self):
        path = output_path_for(Path("/data/report.pdf"), "./extracted")
        assert path == Path("extracted/report.md")

    def test_preserves_stem(self):
        path = output_path_for(Path("/some/file.docx"), "/out")
        assert path.stem == "file"
        assert path.suffix == ".md"
