"""Tests for anydoc backend (mock anydoc)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsidian_import.exceptions import BackendNotAvailableError


class TestAnydocExtract:
    def test_extracts_text(self, tmp_path: Path) -> None:
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake-pdf-content")

        mock_anydoc = MagicMock()
        mock_anydoc.to_markdown.return_value = "# Report\n\nExtracted content from PDF."

        with patch.dict("sys.modules", {"anydoc": mock_anydoc}):
            import importlib

            import obsidian_import.backends.anydoc as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30, isolation="thread")

        assert "Extracted content" in result
        mock_anydoc.to_markdown.assert_called_once_with(str(test_file))

    def test_empty_result_returns_message(self, tmp_path: Path) -> None:
        test_file = tmp_path / "empty.docx"
        test_file.write_bytes(b"fake-docx-content")

        mock_anydoc = MagicMock()
        mock_anydoc.to_markdown.return_value = ""

        with patch.dict("sys.modules", {"anydoc": mock_anydoc}):
            import importlib

            import obsidian_import.backends.anydoc as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30, isolation="thread")

        assert "No text content" in result
        assert "empty.docx" in result

    def test_whitespace_only_returns_message(self, tmp_path: Path) -> None:
        test_file = tmp_path / "blank.pptx"
        test_file.write_bytes(b"fake-pptx-content")

        mock_anydoc = MagicMock()
        mock_anydoc.to_markdown.return_value = "   \n\n  "

        with patch.dict("sys.modules", {"anydoc": mock_anydoc}):
            import importlib

            import obsidian_import.backends.anydoc as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30, isolation="thread")

        assert "No text content" in result

    def test_missing_dependency_raises(self) -> None:
        with (
            patch.dict("sys.modules", {"anydoc": None}),
            pytest.raises(BackendNotAvailableError, match="anydoc is not installed"),
        ):
            import importlib

            import obsidian_import.backends.anydoc as mod

            importlib.reload(mod)
            mod.extract(Path("/tmp/test.pdf"), timeout_seconds=30, isolation="thread")

    def test_none_result_returns_message(self, tmp_path: Path) -> None:
        test_file = tmp_path / "null.xlsx"
        test_file.write_bytes(b"fake-xlsx-content")

        mock_anydoc = MagicMock()
        mock_anydoc.to_markdown.return_value = None

        with patch.dict("sys.modules", {"anydoc": mock_anydoc}):
            import importlib

            import obsidian_import.backends.anydoc as mod

            importlib.reload(mod)
            result = mod.extract(test_file, timeout_seconds=30, isolation="thread")

        assert "No text content" in result


class TestAnydocRegistryDispatch:
    def test_anydoc_dispatch_for_pdf(self) -> None:
        from obsidian_import.config import BackendsConfig
        from obsidian_import.registry import get_backend_module

        backends = BackendsConfig(
            pdf="anydoc",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            html="native",
            default="native",
        )
        module = get_backend_module(".pdf", backends)
        assert module.__name__ == "obsidian_import.backends.anydoc"

    def test_anydoc_as_default_for_unknown_extension(self) -> None:
        from obsidian_import.config import BackendsConfig
        from obsidian_import.registry import get_backend_module

        backends = BackendsConfig(
            pdf="native",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            html="native",
            default="anydoc",
        )
        module = get_backend_module(".rtf", backends)
        assert module.__name__ == "obsidian_import.backends.anydoc"

    def test_anydoc_dispatch_for_all_configured_formats(self) -> None:
        from obsidian_import.config import BackendsConfig
        from obsidian_import.registry import get_backend_module

        backends = BackendsConfig(
            pdf="anydoc",
            docx="anydoc",
            pptx="anydoc",
            xlsx="anydoc",
            csv="anydoc",
            json="native",
            yaml="native",
            image="native",
            html="markitdown",
            default="anydoc",
        )
        for ext in (".pdf", ".docx", ".pptx", ".xlsx", ".csv"):
            module = get_backend_module(ext, backends)
            assert module.__name__ == "obsidian_import.backends.anydoc", f"Failed for {ext}"

    def test_anydoc_backend_check_available(self) -> None:
        from obsidian_import.registry import check_backend_available

        available, message = check_backend_available("anydoc", ".pdf")
        assert isinstance(available, bool)
        assert isinstance(message, str)
