"""Backend registry: extension -> extractor dispatch."""

from __future__ import annotations

import importlib
import inspect
import logging
import types
from pathlib import Path

from obsidian_import.config import BackendsConfig, MediaConfig
from obsidian_import.exceptions import BackendNotAvailableError, UnsupportedFormatError
from obsidian_import.extraction_result import ExtractionResult

log = logging.getLogger(__name__)

_EXTENSION_TO_CONFIG_KEY: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".svg": "image",
    ".webp": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".html": "html",
    ".htm": "html",
}

_BACKEND_MODULES: dict[str, str | dict[str, str]] = {
    "native": {
        ".pdf": "obsidian_import.backends.native_pdf",
        ".docx": "obsidian_import.backends.native_docx",
        ".pptx": "obsidian_import.backends.native_pptx",
        ".xlsx": "obsidian_import.backends.native_xlsx",
        ".csv": "obsidian_import.backends.native_csv",
        ".json": "obsidian_import.backends.native_json",
        ".yaml": "obsidian_import.backends.native_yaml",
        ".yml": "obsidian_import.backends.native_yaml",
        ".png": "obsidian_import.backends.native_image",
        ".jpg": "obsidian_import.backends.native_image",
        ".jpeg": "obsidian_import.backends.native_image",
        ".gif": "obsidian_import.backends.native_image",
        ".svg": "obsidian_import.backends.native_image",
        ".webp": "obsidian_import.backends.native_image",
        ".bmp": "obsidian_import.backends.native_image",
        ".tiff": "obsidian_import.backends.native_image",
    },
    "markitdown": "obsidian_import.backends.markitdown",
    "docling": "obsidian_import.backends.docling",
}


def _resolve_module_path(backend_name: str, extension: str) -> str:
    """Resolve the dotted module path for a backend and extension.

    Raises UnsupportedFormatError if the backend name or extension is invalid.
    """
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

    return module_path


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

    module_path = _resolve_module_path(backend_name, extension)
    return importlib.import_module(module_path)


def extract_with_backend(
    path: Path,
    backends: BackendsConfig,
    timeout_seconds: int,
    media_config: MediaConfig,
    **kwargs: object,
) -> ExtractionResult:
    """Extract a file using the appropriate backend.

    Dispatches to the configured backend based on file extension.
    Format-specific kwargs (e.g. max_rows_per_sheet for xlsx) are filtered to
    only those the chosen backend's extract() function accepts. If a kwarg is
    dropped, a warning is emitted so the capability gap is visible.
    """
    extension = path.suffix.lower()
    module = get_backend_module(extension, backends)

    sig = inspect.signature(module.extract)
    accepted = set(sig.parameters.keys()) - {"path", "timeout_seconds", "media_config"}
    unsupported = {k for k in kwargs if k not in accepted}
    if unsupported:
        backend_name = module.__name__.split(".")[-1]
        log.warning(
            "backend '%s' does not support %s for %s; these options are ignored",
            backend_name,
            sorted(unsupported),
            extension,
        )
    filtered_kwargs = {k: v for k, v in kwargs.items() if k not in unsupported}

    if "media_config" in sig.parameters:
        result = module.extract(path, timeout_seconds=timeout_seconds, media_config=media_config, **filtered_kwargs)
    else:
        result = module.extract(path, timeout_seconds=timeout_seconds, **filtered_kwargs)

    if isinstance(result, str):
        return ExtractionResult(markdown=result, media_files=())
    return result


def check_backend_available(backend_name: str, extension: str) -> tuple[bool, str]:
    """Check if a backend is available (its dependencies are installed).

    Returns (available, message).
    """
    try:
        module_path = _resolve_module_path(backend_name, extension)
    except UnsupportedFormatError as exc:
        return False, str(exc)

    try:
        importlib.import_module(module_path)
        return True, f"{backend_name} backend available"
    except (ImportError, BackendNotAvailableError) as exc:
        return False, f"{backend_name} backend not available: {exc}"
