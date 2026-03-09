"""Tests for markitdown backend (mock markitdown)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsidian_import.exceptions import BackendNotAvailableError


class TestMarkitdownExtract:
    def test_extracts_text(self, tmp_path):
        test_file = tmp_path / "doc.html"
        test_file.write_text("<html><body>Hello</body></html>")

        mock_result = MagicMock()
        mock_result.text_content = "# Hello\n\nExtracted content."

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        mock_markitdown_cls = MagicMock(return_value=mock_converter)

        with patch.dict("sys.modules", {"markitdown": MagicMock(MarkItDown=mock_markitdown_cls)}):
            # Reimport to pick up the mocked module
            import importlib

            import obsidian_import.backends.markitdown as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30)

        assert "Extracted content" in result

    def test_empty_result_returns_message(self, tmp_path):
        test_file = tmp_path / "empty.html"
        test_file.write_text("")

        mock_result = MagicMock()
        mock_result.text_content = ""

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        mock_markitdown_cls = MagicMock(return_value=mock_converter)

        with patch.dict("sys.modules", {"markitdown": MagicMock(MarkItDown=mock_markitdown_cls)}):
            import importlib

            import obsidian_import.backends.markitdown as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30)

        assert "No text content" in result

    def test_missing_dependency_raises(self):
        with (
            patch.dict("sys.modules", {"markitdown": None}),
            pytest.raises(BackendNotAvailableError, match="markitdown is not installed"),
        ):
            import importlib

            import obsidian_import.backends.markitdown as mod

            importlib.reload(mod)
            mod.extract(Path("/tmp/test.html"), timeout_seconds=30)
