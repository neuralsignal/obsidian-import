"""Tests for configuration loading, merging, and frozen dataclasses."""

import pytest

from obsidian_import.config import (
    ImportConfig,
    _build_config,
    _deep_merge,
    _load_default_yaml,
    default_config,
    load_config,
)
from obsidian_import.exceptions import ConfigError


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        assert _deep_merge(base, override) == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        assert _deep_merge(base, override) == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_new_key(self):
        base = {"a": 1}
        override = {"b": 2}
        assert _deep_merge(base, override) == {"a": 1, "b": 2}

    def test_empty_override(self):
        base = {"a": 1}
        assert _deep_merge(base, {}) == {"a": 1}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"a": 1}
        override = {"a": {"nested": True}}
        assert _deep_merge(base, override) == {"a": {"nested": True}}


class TestLoadDefaultYaml:
    def test_returns_dict(self):
        raw = _load_default_yaml()
        assert isinstance(raw, dict)

    def test_has_required_sections(self):
        raw = _load_default_yaml()
        assert "input" in raw
        assert "output" in raw
        assert "backends" in raw
        assert "extraction" in raw


class TestDefaultConfig:
    def test_returns_import_config(self):
        config = default_config()
        assert isinstance(config, ImportConfig)

    def test_default_backends_are_native(self):
        config = default_config()
        assert config.backends.pdf == "native"
        assert config.backends.docx == "native"
        assert config.backends.pptx == "native"
        assert config.backends.xlsx == "native"

    def test_default_timeout(self):
        config = default_config()
        assert config.extraction.timeout_seconds == 120

    def test_default_max_rows(self):
        config = default_config()
        assert config.extraction.xlsx_max_rows_per_sheet == 500

    def test_frozen(self):
        config = default_config()
        with pytest.raises(AttributeError):
            config.extraction = None  # type: ignore[misc]


class TestBuildConfig:
    def test_missing_section_raises_config_error(self):
        with pytest.raises(ConfigError, match="Missing required config section"):
            _build_config({"input": {}, "output": {}, "backends": {}}, config_dir=None)

    def test_string_directory_raises_config_error(self):
        raw = _load_default_yaml()
        raw["input"]["directories"] = ["/tmp/docs"]
        with pytest.raises(ConfigError, match="must be a dict"):
            _build_config(raw, config_dir=None)

    def test_dict_directory_with_all_keys(self):
        raw = _load_default_yaml()
        raw["input"]["directories"] = [{"path": "/tmp", "extensions": [".pdf"], "exclude": ["*.tmp"]}]
        config = _build_config(raw, config_dir=None)
        assert config.input.directories[0].extensions == (".pdf",)
        assert config.input.directories[0].exclude == ("*.tmp",)

    def test_dict_directory_missing_extensions_raises(self):
        raw = _load_default_yaml()
        raw["input"]["directories"] = [{"path": "/tmp", "exclude": []}]
        with pytest.raises(ConfigError, match="missing required key"):
            _build_config(raw, config_dir=None)

    def test_dict_directory_missing_exclude_raises(self):
        raw = _load_default_yaml()
        raw["input"]["directories"] = [{"path": "/tmp", "extensions": [".pdf"]}]
        with pytest.raises(ConfigError, match="missing required key"):
            _build_config(raw, config_dir=None)


class TestLoadConfig:
    def test_load_from_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
input:
  directories:
    - path: /tmp/test
      extensions: [".pdf", ".docx"]
      exclude: []
output:
  directory: ./out
  frontmatter: false
  metadata_fields:
    - title
backends:
  pdf: native
  docx: native
  pptx: native
  xlsx: native
  default: native
extraction:
  timeout_seconds: 60
  max_file_size_mb: 50
  xlsx_max_rows_per_sheet: 100
"""
        )
        config = load_config(config_file)
        assert config.extraction.timeout_seconds == 60
        assert config.output.frontmatter is False

    def test_empty_file_uses_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert isinstance(config, ImportConfig)
