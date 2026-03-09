"""Configuration dataclasses for obsidian-import."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from obsidian_import.exceptions import ConfigError


@dataclass(frozen=True)
class DirectoryConfig:
    path: str
    extensions: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class InputConfig:
    directories: tuple[DirectoryConfig, ...]


@dataclass(frozen=True)
class OutputConfig:
    directory: str
    frontmatter: bool
    metadata_fields: tuple[str, ...]


@dataclass(frozen=True)
class BackendsConfig:
    pdf: str
    docx: str
    pptx: str
    xlsx: str
    default: str


@dataclass(frozen=True)
class ExtractionConfig:
    timeout_seconds: int
    max_file_size_mb: int
    xlsx_max_rows_per_sheet: int


@dataclass(frozen=True)
class ImportConfig:
    input: InputConfig
    output: OutputConfig
    backends: BackendsConfig
    extraction: ExtractionConfig


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. override wins on conflicts."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_default_yaml() -> dict[str, Any]:
    """Load the bundled default.yaml."""
    ref = resources.files("obsidian_import") / "defaults" / "default.yaml"
    return yaml.safe_load(ref.read_text(encoding="utf-8"))


def _build_config(raw: dict[str, Any], config_dir: Path | None) -> ImportConfig:
    """Build ImportConfig from a raw dict. Resolve relative paths if config_dir given."""
    if config_dir is not None and not config_dir.is_absolute():
        config_dir = config_dir.resolve()

    try:
        input_raw = raw["input"]
        output_raw = raw["output"]
        backends_raw = raw["backends"]
        extraction_raw = raw["extraction"]
    except KeyError as exc:
        raise ConfigError(f"Missing required config section: {exc}") from exc

    directories: list[DirectoryConfig] = []
    for d in input_raw.get("directories", []):
        if isinstance(d, str):
            raise ConfigError(
                f"Directory entry '{d}' must be a dict with 'path', 'extensions', and 'exclude' keys, "
                "not a bare string. Specify extensions and exclude explicitly in your config."
            )
        try:
            directories.append(
                DirectoryConfig(
                    path=d["path"],
                    extensions=tuple(d["extensions"]),
                    exclude=tuple(d["exclude"]),
                )
            )
        except KeyError as exc:
            raise ConfigError(
                f"Directory config missing required key {exc}. "
                "Each directory must have 'path', 'extensions', and 'exclude'."
            ) from exc

    return ImportConfig(
        input=InputConfig(directories=tuple(directories)),
        output=OutputConfig(
            directory=output_raw["directory"],
            frontmatter=output_raw["frontmatter"],
            metadata_fields=tuple(output_raw["metadata_fields"]),
        ),
        backends=BackendsConfig(
            pdf=backends_raw["pdf"],
            docx=backends_raw["docx"],
            pptx=backends_raw["pptx"],
            xlsx=backends_raw["xlsx"],
            default=backends_raw["default"],
        ),
        extraction=ExtractionConfig(
            timeout_seconds=int(extraction_raw["timeout_seconds"]),
            max_file_size_mb=int(extraction_raw["max_file_size_mb"]),
            xlsx_max_rows_per_sheet=int(extraction_raw["xlsx_max_rows_per_sheet"]),
        ),
    )


def default_config() -> ImportConfig:
    """Return ImportConfig with all defaults from bundled default.yaml."""
    return _build_config(_load_default_yaml(), config_dir=None)


def load_config(path: Path) -> ImportConfig:
    """Load config from YAML file, merging on top of bundled defaults.

    Users can write minimal YAML with only overrides. Relative paths in
    config are resolved relative to the config file's directory.
    """
    user_raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not user_raw:
        user_raw = {}
    base = _load_default_yaml()
    merged = _deep_merge(base, user_raw)
    return _build_config(merged, config_dir=path.parent)
