"""Tests for extension dispatch and missing backend handling."""

import types
from pathlib import Path
from unittest.mock import patch

import pytest

from obsidian_import.config import BackendsConfig, MediaConfig
from obsidian_import.exceptions import UnsupportedFormatError
from obsidian_import.registry import check_backend_available, extract_with_backend, get_backend_module

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


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
        default="native",
    )


class TestGetBackendModule:
    def test_pdf_returns_native_pdf(self):
        module = get_backend_module(".pdf", _native_backends())
        assert hasattr(module, "extract")
        assert module.__name__ == "obsidian_import.backends.native_pdf"

    def test_docx_returns_native_docx(self):
        module = get_backend_module(".docx", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_docx"

    def test_pptx_returns_native_pptx(self):
        module = get_backend_module(".pptx", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_pptx"

    def test_xlsx_returns_native_xlsx(self):
        module = get_backend_module(".xlsx", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_xlsx"

    def test_csv_returns_native_csv(self):
        module = get_backend_module(".csv", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_csv"

    def test_json_returns_native_json(self):
        module = get_backend_module(".json", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_json"

    def test_yaml_returns_native_yaml(self):
        module = get_backend_module(".yaml", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_yaml"

    def test_yml_returns_native_yaml(self):
        module = get_backend_module(".yml", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_yaml"

    def test_png_returns_native_image(self):
        module = get_backend_module(".png", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_image"

    def test_jpg_returns_native_image(self):
        module = get_backend_module(".jpg", _native_backends())
        assert module.__name__ == "obsidian_import.backends.native_image"

    def test_unknown_extension_uses_default(self):
        backends = BackendsConfig(
            pdf="native",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            default="markitdown",
        )
        module = get_backend_module(".html", backends)
        assert module.__name__ == "obsidian_import.backends.markitdown"

    def test_unknown_extension_native_default_raises(self):
        with pytest.raises(UnsupportedFormatError, match="No native backend"):
            get_backend_module(".html", _native_backends())

    def test_unknown_backend_name_raises(self):
        backends = BackendsConfig(
            pdf="nonexistent",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            default="native",
        )
        with pytest.raises(UnsupportedFormatError, match="Unknown backend"):
            get_backend_module(".pdf", backends)


class TestExtractWithBackend:
    def _markitdown_backends(self) -> BackendsConfig:
        return BackendsConfig(
            pdf="markitdown",
            docx="markitdown",
            pptx="markitdown",
            xlsx="markitdown",
            csv="markitdown",
            json="markitdown",
            yaml="markitdown",
            image="markitdown",
            default="markitdown",
        )

    def test_unsupported_kwarg_is_dropped_and_warned(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """max_rows_per_sheet must not reach markitdown.extract() which doesn't accept it."""
        xlsx_file = tmp_path / "test.xlsx"
        xlsx_file.write_bytes(b"fake")

        fake_module = types.ModuleType("obsidian_import.backends.markitdown")
        fake_module.extract = lambda path, timeout_seconds: "extracted"  # type: ignore[attr-defined]

        import logging

        with (
            patch("obsidian_import.registry.get_backend_module", return_value=fake_module),
            caplog.at_level(logging.WARNING, logger="obsidian_import.registry"),
        ):
            result = extract_with_backend(
                xlsx_file,
                backends=self._markitdown_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                max_rows_per_sheet=100,
            )

        assert result.markdown == "extracted"
        assert any("max_rows_per_sheet" in r.message for r in caplog.records)

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
            extract_with_backend(
                xlsx_file,
                backends=_native_backends(),
                timeout_seconds=30,
                media_config=_TEST_MEDIA_CONFIG,
                max_rows_per_sheet=42,
            )

        assert received["max_rows_per_sheet"] == 42


class TestCheckBackendAvailable:
    def test_native_pdf_available(self):
        available, message = check_backend_available("native", ".pdf")
        assert available is True

    def test_native_unknown_extension(self):
        available, message = check_backend_available("native", ".xyz")
        assert available is False

    def test_unknown_backend(self):
        available, message = check_backend_available("nonexistent", ".pdf")
        assert available is False
