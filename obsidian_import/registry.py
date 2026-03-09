"""Backend registry: extension -> extractor dispatch."""

from __future__ import annotations

import importlib
import types
from pathlib import Path

from obsidian_import.config import BackendsConfig
from obsidian_import.exceptions import BackendNotAvailableError, UnsupportedFormatError

_EXTENSION_TO_CONFIG_KEY: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
}

_BACKEND_MODULES: dict[str, str | dict[str, str]] = {
    "native": {
        ".pdf": "obsidian_import.backends.native_pdf",
        ".docx": "obsidian_import.backends.native_docx",
        ".pptx": "obsidian_import.backends.native_pptx",
        ".xlsx": "obsidian_import.backends.native_xlsx",
    },
    "markitdown": "obsidian_import.backends.markitdown",
    "docling": "obsidian_import.backends.docling",
}


def get_backend_module(extension: str, backends: BackendsConfig) -> types.ModuleType:
    """Resolve the backend module for a given file extension.

    Returns the module object with an `extract()` function.
    Raises UnsupportedFormatError if no backend is available.
    """
    config_key = _EXTENSION_TO_CONFIG_KEY.get(extension)
    if config_key is not None:
        backend_name = getattr(backends, config_key)
    else:
        backend_name = backends.default

    if backend_name == "native":
        native_map = _BACKEND_MODULES["native"]
        if not isinstance(native_map, dict) or extension not in native_map:
            raise UnsupportedFormatError(
                f"No native backend for extension '{extension}'. "
                f"Supported native extensions: {', '.join(_EXTENSION_TO_CONFIG_KEY.keys())}"
            )
        module_path = native_map[extension]
    elif backend_name in ("markitdown", "docling"):
        module_path = _BACKEND_MODULES[backend_name]
        if not isinstance(module_path, str):
            raise UnsupportedFormatError(f"Invalid backend module config for '{backend_name}'")
    else:
        raise UnsupportedFormatError(f"Unknown backend '{backend_name}' for extension '{extension}'")

    return importlib.import_module(module_path)


def extract_with_backend(path: Path, backends: BackendsConfig, timeout_seconds: int, **kwargs: object) -> str:
    """Extract a file using the appropriate backend.

    Dispatches to the configured backend based on file extension.
    """
    extension = path.suffix.lower()
    module = get_backend_module(extension, backends)

    return module.extract(path, timeout_seconds=timeout_seconds, **kwargs)


def check_backend_available(backend_name: str, extension: str) -> tuple[bool, str]:
    """Check if a backend is available (its dependencies are installed).

    Returns (available, message).
    """
    if backend_name == "native":
        native_map = _BACKEND_MODULES["native"]
        if not isinstance(native_map, dict) or extension not in native_map:
            return False, f"No native backend for {extension}"
        module_path = native_map[extension]
    elif backend_name in ("markitdown", "docling"):
        module_path = _BACKEND_MODULES[backend_name]
    else:
        return False, f"Unknown backend: {backend_name}"

    if not isinstance(module_path, str):
        return False, f"Invalid backend module config for '{backend_name}'"

    try:
        importlib.import_module(module_path)
        return True, f"{backend_name} backend available"
    except (ImportError, BackendNotAvailableError) as exc:
        return False, f"{backend_name} backend not available: {exc}"
