"""Tests for extension dispatch and missing backend handling."""

import importlib.util
from unittest.mock import patch

import pytest

from obsidian_import.config import BackendsConfig
from obsidian_import.exceptions import UnsupportedFormatError
from obsidian_import.registry import (
    _BACKEND_MODULES,
    _resolve_module_path,
    check_backend_available,
    get_backend_module,
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
        html="native",
        default="native",
    )


def _anydoc_backends() -> BackendsConfig:
    return BackendsConfig(
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
            html="native",
            default="markitdown",
        )
        module = get_backend_module(".rtf", backends)
        assert module.__name__ == "obsidian_import.backends.markitdown"

    def test_unknown_extension_native_default_raises(self):
        with pytest.raises(UnsupportedFormatError, match="No native backend"):
            get_backend_module(".rtf", _native_backends())

    def test_html_returns_configured_backend(self):
        backends = BackendsConfig(
            pdf="native",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            html="markitdown",
            default="native",
        )
        module = get_backend_module(".html", backends)
        assert module.__name__ == "obsidian_import.backends.markitdown"

    def test_htm_returns_configured_backend(self):
        backends = BackendsConfig(
            pdf="native",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            html="markitdown",
            default="native",
        )
        module = get_backend_module(".htm", backends)
        assert module.__name__ == "obsidian_import.backends.markitdown"

    def test_html_native_raises(self):
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
            html="native",
            default="native",
        )
        with pytest.raises(UnsupportedFormatError, match="Unknown backend"):
            get_backend_module(".pdf", backends)

    @pytest.mark.parametrize("extension", [".pdf", ".docx", ".pptx", ".xlsx", ".csv"])
    def test_anydoc_serves_every_document_extension(self, extension):
        module = get_backend_module(extension, _anydoc_backends())
        assert module.__name__ == "obsidian_import.backends.anydoc"

    @pytest.mark.parametrize("extension", [".rtf", ".epub", ".odt", ".doc", ".xls", ".ppt"])
    def test_unregistered_extensions_reach_anydoc_via_default(self, extension):
        module = get_backend_module(extension, _anydoc_backends())
        assert module.__name__ == "obsidian_import.backends.anydoc"


class TestResolveModulePath:
    def test_native_map_misconfigured_raises(self):
        with (
            patch.dict(_BACKEND_MODULES, {"native": "not-a-dict"}),
            pytest.raises(UnsupportedFormatError, match="native backend map misconfigured"),
        ):
            _resolve_module_path("native", ".pdf")

    def test_non_native_module_path_misconfigured_raises(self):
        with (
            patch.dict(_BACKEND_MODULES, {"markitdown": {"unexpected": "dict"}}),
            pytest.raises(UnsupportedFormatError, match="backend module path misconfigured"),
        ):
            _resolve_module_path("markitdown", ".pdf")


class TestCheckBackendAvailable:
    def test_native_pdf_available(self):
        available, message = check_backend_available("native", ".pdf")
        assert available is True

    def test_anydoc_available(self):
        available, message = check_backend_available("anydoc", ".pdf")
        assert available is True
        assert "anydoc backend available" in message

    def test_uninstalled_dependency_is_reported_missing(self):
        real_find_spec = importlib.util.find_spec

        def missing_anydoc(name, *args, **kwargs):
            return None if name == "anydoc" else real_find_spec(name, *args, **kwargs)

        with patch("obsidian_import.registry.importlib.util.find_spec", side_effect=missing_anydoc):
            available, message = check_backend_available("anydoc", ".pdf")

        assert available is False
        assert "anydoc is not installed" in message

    def test_native_unknown_extension(self):
        available, message = check_backend_available("native", ".xyz")
        assert available is False

    def test_unknown_backend(self):
        available, message = check_backend_available("nonexistent", ".pdf")
        assert available is False

    def test_import_error_returns_false(self):
        """ImportError during import returns (False, ...) (lines 152-153)."""
        with patch("obsidian_import.registry.importlib.import_module", side_effect=ImportError("no such module")):
            available, message = check_backend_available("native", ".pdf")
        assert available is False
        assert "not available" in message
