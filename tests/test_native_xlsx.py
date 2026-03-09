"""Tests for XLSX extraction (mock openpyxl)."""

from unittest.mock import MagicMock, patch

from obsidian_import.backends.native_xlsx import extract


def _mock_workbook(sheets: dict[str, list[list]]) -> MagicMock:
    """Build a mock workbook with the given sheet data."""
    wb = MagicMock()
    wb.sheetnames = list(sheets.keys())

    mock_sheets = {}
    for name, rows in sheets.items():
        ws = MagicMock()
        ws.iter_rows.return_value = iter(rows)
        mock_sheets[name] = ws

    wb.__getitem__ = MagicMock(side_effect=lambda name: mock_sheets[name])
    return wb


class TestNativeXlsxExtract:
    def test_extracts_basic_sheet(self, tmp_path):
        xlsx_path = tmp_path / "test.xlsx"
        xlsx_path.write_bytes(b"fake xlsx")

        wb = _mock_workbook(
            {
                "Sheet1": [
                    ("Name", "Age"),
                    ("Alice", 30),
                    ("Bob", 25),
                ]
            }
        )

        with patch("openpyxl.load_workbook", return_value=wb):
            result = extract(xlsx_path, timeout_seconds=30, max_rows_per_sheet=500)

        assert "# test" in result
        assert "Sheet: Sheet1" in result
        assert "Name" in result
        assert "Alice" in result
        assert "|" in result

    def test_multiple_sheets(self, tmp_path):
        xlsx_path = tmp_path / "multi.xlsx"
        xlsx_path.write_bytes(b"fake xlsx")

        wb = _mock_workbook(
            {
                "Data": [("Col1",), ("val1",)],
                "Summary": [("Total",), ("100",)],
            }
        )

        with patch("openpyxl.load_workbook", return_value=wb):
            result = extract(xlsx_path, timeout_seconds=30, max_rows_per_sheet=500)

        assert "Sheet: Data" in result
        assert "Sheet: Summary" in result

    def test_empty_sheet_skipped(self, tmp_path):
        xlsx_path = tmp_path / "empty.xlsx"
        xlsx_path.write_bytes(b"fake xlsx")

        wb = _mock_workbook(
            {
                "Empty": [(None, None), (None, None)],
                "HasData": [("A",), ("B",)],
            }
        )

        with patch("openpyxl.load_workbook", return_value=wb):
            result = extract(xlsx_path, timeout_seconds=30, max_rows_per_sheet=500)

        assert "Empty" not in result
        assert "HasData" in result

    def test_truncation_on_max_rows(self, tmp_path):
        xlsx_path = tmp_path / "big.xlsx"
        xlsx_path.write_bytes(b"fake xlsx")

        rows = [("header",)] + [("row",)] * 10
        wb = _mock_workbook({"Sheet1": rows})

        with patch("openpyxl.load_workbook", return_value=wb):
            result = extract(xlsx_path, timeout_seconds=30, max_rows_per_sheet=5)

        assert "Truncated" in result

    def test_pipe_chars_escaped(self, tmp_path):
        xlsx_path = tmp_path / "pipes.xlsx"
        xlsx_path.write_bytes(b"fake xlsx")

        wb = _mock_workbook({"Sheet1": [("A|B",), ("C|D",)]})

        with patch("openpyxl.load_workbook", return_value=wb):
            result = extract(xlsx_path, timeout_seconds=30, max_rows_per_sheet=500)

        assert "A\\|B" in result
