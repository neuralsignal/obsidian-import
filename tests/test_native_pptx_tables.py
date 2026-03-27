"""Tests for PPTX table extraction."""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.native_pptx import _extract_table


class TestExtractTable:
    def test_empty_rows_returns_empty_string(self):
        table = MagicMock()
        table.rows = []
        assert _extract_table(table) == ""

    def test_single_row_table(self):
        table = MagicMock()
        row = MagicMock()
        cell_a, cell_b = MagicMock(), MagicMock()
        cell_a.text = "A"
        cell_b.text = "B"
        row.cells = [cell_a, cell_b]
        table.rows = [row]

        result = _extract_table(table)
        assert "| A | B |" in result
        assert "| --- | --- |" in result

    @given(
        data=st.lists(
            st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=50)
    def test_extract_table_property_row_count(self, data):
        table = MagicMock()
        mock_rows = []
        for row_data in data:
            row = MagicMock()
            cells = []
            for text in row_data:
                cell = MagicMock()
                cell.text = text
                cells.append(cell)
            row.cells = cells
            mock_rows.append(row)
        table.rows = mock_rows

        result = _extract_table(table)
        lines = result.strip().split("\n")
        assert len(lines) == 1 + 1 + max(0, len(data) - 1)

    @given(
        data=st.lists(
            st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=50)
    def test_extract_table_property_all_lines_are_pipe_delimited(self, data):
        table = MagicMock()
        mock_rows = []
        for row_data in data:
            row = MagicMock()
            cells = []
            for text in row_data:
                cell = MagicMock()
                cell.text = text
                cells.append(cell)
            row.cells = cells
            mock_rows.append(row)
        table.rows = mock_rows

        result = _extract_table(table)
        for line in result.strip().split("\n"):
            assert line.startswith("|")
            assert line.endswith("|")
