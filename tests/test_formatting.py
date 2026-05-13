"""Tests for the shared markdown table rendering function."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.formatting import make_media_wikilink, render_markdown_table, sanitize_markdown_inline


class TestSanitizeMarkdownInline:
    def test_strips_newlines(self) -> None:
        assert sanitize_markdown_inline("line1\nline2") == "line1 line2"

    def test_strips_crlf(self) -> None:
        assert sanitize_markdown_inline("a\r\nb") == "a b"

    def test_strips_cr(self) -> None:
        assert sanitize_markdown_inline("a\rb") == "a b"

    def test_escapes_asterisks(self) -> None:
        assert sanitize_markdown_inline("**bold**") == r"\*\*bold\*\*"

    def test_escapes_underscores(self) -> None:
        assert sanitize_markdown_inline("_italic_") == r"\_italic\_"

    def test_escapes_backticks(self) -> None:
        assert sanitize_markdown_inline("`code`") == r"\`code\`"

    def test_escapes_hash(self) -> None:
        assert sanitize_markdown_inline("## heading") == r"\#\# heading"

    def test_escapes_pipes(self) -> None:
        assert sanitize_markdown_inline("a|b") == r"a\|b"

    def test_escapes_angle_brackets(self) -> None:
        assert sanitize_markdown_inline("<script>") == r"\<script\>"

    def test_escapes_square_brackets(self) -> None:
        assert sanitize_markdown_inline("[link](url)") == r"\[link\](url)"

    def test_escapes_backslashes(self) -> None:
        assert sanitize_markdown_inline("a\\b") == "a\\\\b"

    def test_plain_text_unchanged(self) -> None:
        assert sanitize_markdown_inline("hello world") == "hello world"

    def test_heading_injection_via_newline(self) -> None:
        result = sanitize_markdown_inline("\n\n## Injected Heading")
        assert "\n" not in result
        assert "## " not in result

    def test_thematic_break_injection(self) -> None:
        result = sanitize_markdown_inline("\n\n---")
        assert "\n" not in result


class TestSanitizeMarkdownInlineProperties:
    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_no_newlines_in_output(self, text: str) -> None:
        result = sanitize_markdown_inline(text)
        assert "\n" not in result
        assert "\r" not in result

    @given(text=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_no_unescaped_markdown_chars(self, text: str) -> None:
        result = sanitize_markdown_inline(text)
        i = 0
        while i < len(result):
            if result[i] == "\\":
                i += 2
                continue
            assert result[i] not in "*_`#|<>[]\\", f"unescaped '{result[i]}' at position {i}"
            i += 1


class TestMakeMediaWikilink:
    def test_basic_wikilink(self) -> None:
        assert make_media_wikilink("report", "image_001.png") == "![[report/image_001.png]]"

    @given(
        doc_stem=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        filename=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @settings(max_examples=100)
    def test_wikilink_format(self, doc_stem: str, filename: str) -> None:
        result = make_media_wikilink(doc_stem, filename)
        assert result.startswith("![[")
        assert result.endswith("]]")
        assert f"{doc_stem}/{filename}" in result

    @given(
        doc_stem=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        filename=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    )
    @settings(max_examples=100)
    def test_wikilink_exact_structure(self, doc_stem: str, filename: str) -> None:
        result = make_media_wikilink(doc_stem, filename)
        assert result == f"![[{doc_stem}/{filename}]]"


class TestRenderMarkdownTable:
    def test_basic_table(self) -> None:
        """A simple 2-column table renders correctly."""
        rows = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        result = render_markdown_table(rows)
        assert result == ("| Name | Age |\n| --- | --- |\n| Alice | 30 |\n| Bob | 25 |")

    def test_empty_rows_returns_empty(self) -> None:
        """An empty input produces an empty string."""
        assert render_markdown_table([]) == ""

    def test_header_only(self) -> None:
        """A single-row table renders header and separator only."""
        rows = [["A", "B"]]
        result = render_markdown_table(rows)
        assert result == "| A | B |\n| --- | --- |"

    def test_pipe_characters_escaped(self) -> None:
        """Pipe characters in cell content are escaped."""
        rows = [["Header"], ["value|with|pipes"]]
        result = render_markdown_table(rows)
        assert "\\|" in result
        assert "value\\|with\\|pipes" in result

    def test_newlines_replaced(self) -> None:
        """Newline characters in cell content are replaced with spaces."""
        rows = [["Header"], ["line1\nline2"]]
        result = render_markdown_table(rows)
        assert "\n" not in result.split("\n")[2]
        assert "line1 line2" in result

    def test_uneven_rows_padded(self) -> None:
        """Rows shorter than the longest are padded with empty cells."""
        rows = [["A", "B", "C"], ["only_one"]]
        result = render_markdown_table(rows)
        lines = result.split("\n")
        assert lines[2] == "| only_one |  |  |"

    def test_all_empty_cells_returns_empty(self) -> None:
        """Rows with zero-length columns produce empty string."""
        rows = [[], []]
        assert render_markdown_table(rows) == ""


class TestRenderMarkdownTableProperties:
    @given(
        rows=st.lists(
            st.lists(
                st.text(
                    min_size=0,
                    max_size=20,
                    alphabet=st.characters(
                        whitelist_categories=("L", "N", "P", "Z"),
                        blacklist_characters=("\n", "\r"),
                    ),
                ),
                min_size=1,
                max_size=5,
            ),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_output_has_correct_line_count(self, rows: list[list[str]]) -> None:
        """Output always has exactly len(rows) + 1 lines (header + separator + data rows)."""
        result = render_markdown_table(rows)
        if not result:
            return
        lines = result.split("\n")
        assert len(lines) == len(rows) + 1

    @given(
        rows=st.lists(
            st.lists(
                st.text(
                    min_size=0,
                    max_size=20,
                    alphabet=st.characters(
                        whitelist_categories=("L", "N", "Z"),
                    ),
                ),
                min_size=1,
                max_size=5,
            ),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_every_line_starts_and_ends_with_pipe(self, rows: list[list[str]]) -> None:
        """Every line of the output starts and ends with a pipe character."""
        result = render_markdown_table(rows)
        if not result:
            return
        for line in result.split("\n"):
            assert line.startswith("|")
            assert line.endswith("|")

    @given(
        rows=st.lists(
            st.lists(
                st.text(
                    min_size=0,
                    max_size=10,
                    alphabet=st.characters(whitelist_categories=("L", "N")),
                ),
                min_size=1,
                max_size=5,
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_no_unescaped_pipes_in_cells(self, rows: list[list[str]]) -> None:
        """No cell content contains an unescaped pipe character after rendering."""
        result = render_markdown_table(rows)
        if not result:
            return
        for line in result.split("\n"):
            inner = line[1:-1]
            cells = inner.split(" | ")
            for cell in cells:
                stripped = cell.strip()
                if stripped == "---":
                    continue
                assert "|" not in stripped.replace("\\|", "")
