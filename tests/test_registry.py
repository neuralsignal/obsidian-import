"""Tests for extension dispatch and missing backend handling."""

import pytest

from obsidian_import.config import BackendsConfig
from obsidian_import.exceptions import UnsupportedFormatError
from obsidian_import.registry import check_backend_available, get_backend_module


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
