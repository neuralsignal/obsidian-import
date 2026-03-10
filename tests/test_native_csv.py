"""Tests for native CSV backend."""

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.native_csv import _escape_cell, extract


class TestNativeCsvExtract:
    def test_extracts_simple_csv(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("Name,Age,City\nAlice,30,NYC\nBob,25,LA\n")
        result = extract(csv_file, timeout_seconds=10)

        assert "# data" in result
        assert "| Name | Age | City |" in result
        assert "| --- | --- | --- |" in result
        assert "| Alice | 30 | NYC |" in result
        assert "| Bob | 25 | LA |" in result

    def test_empty_csv(self, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")
        result = extract(csv_file, timeout_seconds=10)
        assert "Empty CSV" in result

    def test_single_row_csv(self, tmp_path):
        csv_file = tmp_path / "headers.csv"
        csv_file.write_text("A,B,C\n")
        result = extract(csv_file, timeout_seconds=10)
        assert "| A | B | C |" in result
        assert "| --- | --- | --- |" in result

    def test_pipe_chars_escaped(self, tmp_path):
        csv_file = tmp_path / "pipes.csv"
        csv_file.write_text("Header\nvalue|with|pipes\n")
        result = extract(csv_file, timeout_seconds=10)
        assert "\\|" in result

    def test_ragged_rows_padded(self, tmp_path):
        csv_file = tmp_path / "ragged.csv"
        csv_file.write_text("A,B,C\n1,2\n")
        result = extract(csv_file, timeout_seconds=10)
        assert "| 1 | 2 |  |" in result


class TestEscapeCellProperties:
    @given(value=st.text())
    @settings(max_examples=100)
    def test_no_unescaped_pipes(self, value: str) -> None:
        result = _escape_cell(value)
        stripped = result.replace("\\|", "")
        assert "|" not in stripped

    @given(value=st.text())
    @settings(max_examples=100)
    def test_no_newlines_in_output(self, value: str) -> None:
        result = _escape_cell(value)
        assert "\n" not in result
