"""Tests for extract_with_backend and backend kwarg forwarding."""

import logging
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from conftest import make_test_media_config

from obsidian_import.config import BackendsConfig
from obsidian_import.registry import ExtractionContext, extract_with_backend

_TEST_MEDIA_CONFIG = make_test_media_config()


def _native_backends() -> BackendsConfig:
    return BackendsConfig(
        pdf="native",
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


def _markitdown_backends() -> BackendsConfig:
    return BackendsConfig(
        pdf="markitdown",
        docx="markitdown",
        pptx="markitdown",
        xlsx="markitdown",
        csv="markitdown",
        json="markitdown",
        yaml="markitdown",
        image="markitdown",
        html="markitdown",
        default="markitdown",
    )


class TestExtractWithBackend:
    def test_unsupported_kwarg_is_dropped_and_warned(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """max_rows_per_sheet must not reach markitdown.extract() which doesn't accept it."""
        xlsx_file = tmp_path / "test.xlsx"
        xlsx_file.write_bytes(b"fake")

        fake_module = types.ModuleType("obsidian_import.backends.markitdown")
        fake_module.extract = lambda path, timeout_seconds: "extracted"  # type: ignore[attr-defined]

        with (
            patch("obsidian_import.registry.get_backend_module", return_value=fake_module),
            caplog.at_level(logging.WARNING, logger="obsidian_import.registry"),
        ):
            ctx = ExtractionContext(
                backends=_markitdown_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                isolation="thread",
            )
            result = extract_with_backend(xlsx_file, ctx, max_rows_per_sheet=100)

        assert result.markdown == "extracted"
        assert any("max_rows_per_sheet" in r.message for r in caplog.records)

    def test_unsupported_kwarg_warns_once_per_configuration(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A batch run must report a capability gap once, not once per file."""
        fake_module = types.ModuleType("obsidian_import.backends.markitdown")
        fake_module.extract = lambda path, timeout_seconds: "extracted"  # type: ignore[attr-defined]

        ctx = ExtractionContext(
            backends=_markitdown_backends(),
            timeout_seconds=30,
            media_config=_TEST_MEDIA_CONFIG,
            isolation="thread",
        )
        with (
            patch("obsidian_import.registry.get_backend_module", return_value=fake_module),
            caplog.at_level(logging.WARNING, logger="obsidian_import.registry"),
        ):
            for name in ("one.xlsx", "two.xlsx", "three.xlsx"):
                sheet = tmp_path / name
                sheet.write_bytes(b"fake")
                extract_with_backend(sheet, ctx, max_rows_per_sheet=100)

        assert sum("max_rows_per_sheet" in r.message for r in caplog.records) == 1

    def test_supported_kwarg_is_forwarded(self, tmp_path: Path) -> None:
        """max_rows_per_sheet must be forwarded when the backend accepts it."""
        xlsx_file = tmp_path / "test.xlsx"
        xlsx_file.write_bytes(b"fake")

        received: dict = {}
        fake_module = types.ModuleType("obsidian_import.backends.native_xlsx")

        def fake_extract(path: Path, timeout_seconds: int, max_rows_per_sheet: int) -> str:
            received["max_rows_per_sheet"] = max_rows_per_sheet
            return "extracted"

        fake_module.extract = fake_extract  # type: ignore[attr-defined]

        with patch("obsidian_import.registry.get_backend_module", return_value=fake_module):
            ctx = ExtractionContext(
                backends=_native_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                isolation="thread",
            )
            extract_with_backend(xlsx_file, ctx, max_rows_per_sheet=42)

        assert received["max_rows_per_sheet"] == 42
