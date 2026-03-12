"""Tests for frontmatter formatting, output path computation, and media dir."""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.config import OutputConfig
from obsidian_import.output import ExtractedDocument, format_output, media_dir_for, output_path_for


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

    def test_backslash_escaped_in_quoted_value(self):
        doc = _make_doc('Report: "Sales\\Revenue"', "# Hello")
        result = format_output(doc, _make_config(True))
        assert 'title: "Report: \\"Sales\\\\Revenue\\""' in result

    def test_backslash_only_no_quoting_needed(self):
        doc = _make_doc("plain title", "# Hello")
        result = format_output(doc, _make_config(True))
        assert "title: plain title" in result

    def test_backslash_with_colon_triggers_escaping(self):
        doc = _make_doc("C:\\Users\\report: final", "# Hello")
        result = format_output(doc, _make_config(True))
        assert 'title: "C:\\\\Users\\\\report: final"' in result


class TestOutputPathFor:
    def test_computes_md_extension_no_source_root(self):
        path = output_path_for(Path("/data/report.pdf"), "./extracted", source_root=None)
        assert path == Path("extracted/report.md")

    def test_preserves_stem_no_source_root(self):
        path = output_path_for(Path("/some/file.docx"), "/out", source_root=None)
        assert path.stem == "file"
        assert path.suffix == ".md"

    def test_preserves_relative_structure_with_source_root(self):
        source = Path("/docs/projects/report.pdf")
        root = Path("/docs")
        path = output_path_for(source, "/vault", source_root=root)
        assert path == Path("/vault/projects/report.md")

    def test_nested_directory_preservation(self):
        source = Path("/input/a/b/c/deep.docx")
        root = Path("/input")
        path = output_path_for(source, "/output", source_root=root)
        assert path == Path("/output/a/b/c/deep.md")

    def test_file_at_root_level(self):
        source = Path("/input/toplevel.pdf")
        root = Path("/input")
        path = output_path_for(source, "/output", source_root=root)
        assert path == Path("/output/toplevel.md")


class TestOutputPathForProperties:
    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        ext=st.sampled_from([".pdf", ".docx", ".pptx", ".xlsx"]),
    )
    @settings(max_examples=50)
    def test_output_always_has_md_extension(self, stem: str, ext: str) -> None:
        source = Path(f"/input/{stem}{ext}")
        path = output_path_for(source, "/output", source_root=None)
        assert path.suffix == ".md"

    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        ext=st.sampled_from([".pdf", ".docx", ".pptx"]),
    )
    @settings(max_examples=50)
    def test_output_preserves_stem(self, stem: str, ext: str) -> None:
        source = Path(f"/input/{stem}{ext}")
        path = output_path_for(source, "/output", source_root=None)
        assert path.stem == stem

    @given(
        subdir=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        stem=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @settings(max_examples=50)
    def test_source_root_preserves_subdirectory(self, subdir: str, stem: str) -> None:
        source = Path(f"/input/{subdir}/{stem}.pdf")
        root = Path("/input")
        path = output_path_for(source, "/output", source_root=root)
        assert subdir in str(path)
        assert path.suffix == ".md"


class TestMediaDirFor:
    def test_returns_stem_named_directory(self):
        source = Path("/docs/report.pdf")
        result = media_dir_for(source, Path("/vault"))
        assert result == Path("/vault/report")

    def test_different_stems(self):
        assert media_dir_for(Path("/a/slides.pptx"), Path("/out")) == Path("/out/slides")
        assert media_dir_for(Path("/b/notes.docx"), Path("/out")) == Path("/out/notes")


class TestMediaDirForProperties:
    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        ext=st.sampled_from([".pdf", ".docx", ".pptx"]),
    )
    @settings(max_examples=50)
    def test_media_dir_uses_document_stem(self, stem: str, ext: str) -> None:
        source = Path(f"/input/{stem}{ext}")
        result = media_dir_for(source, Path("/output"))
        assert result.name == stem
        assert result.parent == Path("/output")
