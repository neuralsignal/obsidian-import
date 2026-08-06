"""Tests for configuration loading, merging, and frozen dataclasses."""

import pytest

from obsidian_import.config import (
    ImportConfig,
    _build_backends_config,
    _build_config,
    _build_extraction_config,
    _build_input_config,
    _build_media_config,
    _build_output_config,
    _build_passthrough_config,
    _deep_merge,
    _load_default_yaml,
    config_for_backend,
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

    def test_default_document_backends_are_anydoc(self):
        config = default_config()
        assert config.backends.pdf == "anydoc"
        assert config.backends.docx == "anydoc"
        assert config.backends.pptx == "anydoc"
        assert config.backends.xlsx == "anydoc"
        assert config.backends.csv == "anydoc"
        assert config.backends.default == "anydoc"

    def test_formats_anydoc_cannot_read_stay_native(self):
        # anydoc reads document formats only: JSON, YAML, and images have no
        # anydoc parser, so those keys keep the native backends.
        config = default_config()
        assert config.backends.json == "native"
        assert config.backends.yaml == "native"
        assert config.backends.image == "native"

    def test_default_html_backend_is_markitdown(self):
        # Native has no .html handler; defaulting html to markitdown keeps
        # default-configured callers working out of the box.
        config = default_config()
        assert config.backends.html == "markitdown"

    def test_default_passthrough_empty(self):
        config = default_config()
        assert config.passthrough.extensions == ()
        assert config.passthrough.paths == ()
        assert config.passthrough.patterns == ()

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


class TestConfigForBackend:
    def test_returns_import_config(self):
        config = config_for_backend("markitdown", 60, 50, 200, False)
        assert isinstance(config, ImportConfig)

    def test_all_backends_match(self):
        config = config_for_backend("markitdown", 60, 50, 200, False)
        assert config.backends.pdf == "markitdown"
        assert config.backends.docx == "markitdown"
        assert config.backends.pptx == "markitdown"
        assert config.backends.xlsx == "markitdown"
        assert config.backends.csv == "markitdown"
        assert config.backends.json == "markitdown"
        assert config.backends.yaml == "markitdown"
        assert config.backends.image == "markitdown"
        assert config.backends.html == "markitdown"
        assert config.backends.default == "markitdown"

    def test_extraction_params_match(self):
        config = config_for_backend("native", 90, 75, 300, False)
        assert config.extraction.timeout_seconds == 90
        assert config.extraction.max_file_size_mb == 75
        assert config.extraction.xlsx_max_rows_per_sheet == 300

    def test_extract_images_false(self):
        config = config_for_backend("native", 60, 50, 200, False)
        assert config.media.extract_images is False

    def test_extract_images_true(self):
        config = config_for_backend("native", 60, 50, 200, True)
        assert config.media.extract_images is True

    def test_frozen(self):
        config = config_for_backend("native", 60, 50, 200, False)
        with pytest.raises(AttributeError):
            config.extraction = None  # type: ignore[misc]


class TestBuildConfig:
    def test_relative_config_dir_resolved(self):
        """Relative config_dir is resolved to absolute (line 101)."""
        from pathlib import Path

        raw = _load_default_yaml()
        raw["input"]["directories"] = [{"path": "/tmp/test", "extensions": [".pdf"], "exclude": []}]
        config = _build_config(raw, config_dir=Path("relative/path"))
        assert isinstance(config, ImportConfig)

    def test_missing_section_raises_config_error(self):
        with pytest.raises(ConfigError, match="Missing required config section"):
            _build_config({"input": {}, "output": {}, "backends": {}}, config_dir=None)

    def test_missing_media_section_raises_config_error(self):
        raw = _load_default_yaml()
        del raw["media"]
        with pytest.raises(ConfigError, match="Missing required config section"):
            _build_config(raw, config_dir=None)

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


class TestBuildInputConfig:
    def test_empty_directories(self):
        result = _build_input_config({"directories": []})
        assert result.directories == ()

    def test_valid_directory(self):
        raw = {"directories": [{"path": "/docs", "extensions": [".pdf", ".docx"], "exclude": ["*.tmp"]}]}
        result = _build_input_config(raw)
        assert len(result.directories) == 1
        assert result.directories[0].path == "/docs"
        assert result.directories[0].extensions == (".pdf", ".docx")
        assert result.directories[0].exclude == ("*.tmp",)

    def test_multiple_directories(self):
        raw = {
            "directories": [
                {"path": "/a", "extensions": [".pdf"], "exclude": []},
                {"path": "/b", "extensions": [".docx"], "exclude": ["~$*"]},
            ]
        }
        result = _build_input_config(raw)
        assert len(result.directories) == 2

    def test_bare_string_raises(self):
        with pytest.raises(ConfigError, match="must be a dict"):
            _build_input_config({"directories": ["/tmp/docs"]})

    def test_missing_extensions_raises(self):
        with pytest.raises(ConfigError, match="missing required key"):
            _build_input_config({"directories": [{"path": "/tmp", "exclude": []}]})

    def test_missing_exclude_raises(self):
        with pytest.raises(ConfigError, match="missing required key"):
            _build_input_config({"directories": [{"path": "/tmp", "extensions": [".pdf"]}]})

    def test_no_directories_key_defaults_empty(self):
        result = _build_input_config({})
        assert result.directories == ()


class TestBuildOutputConfig:
    def test_valid_output(self):
        raw = {"directory": "./out", "frontmatter": True, "metadata_fields": ["title", "source"]}
        result = _build_output_config(raw)
        assert result.directory == "./out"
        assert result.frontmatter is True
        assert result.metadata_fields == ("title", "source")

    def test_frontmatter_false(self):
        raw = {"directory": "/output", "frontmatter": False, "metadata_fields": []}
        result = _build_output_config(raw)
        assert result.frontmatter is False
        assert result.metadata_fields == ()


class TestBuildBackendsConfig:
    def test_all_explicit(self):
        raw = {
            "pdf": "native",
            "docx": "native",
            "pptx": "native",
            "xlsx": "native",
            "csv": "native",
            "json": "native",
            "yaml": "native",
            "image": "native",
            "html": "markitdown",
            "default": "native",
        }
        result = _build_backends_config(raw)
        assert result.pdf == "native"
        assert result.html == "markitdown"
        assert result.default == "native"

    def test_optional_keys_fall_back_to_default(self):
        raw = {"pdf": "native", "docx": "native", "pptx": "native", "xlsx": "native", "default": "markitdown"}
        result = _build_backends_config(raw)
        assert result.csv == "markitdown"
        assert result.json == "markitdown"
        assert result.yaml == "markitdown"
        assert result.image == "markitdown"
        assert result.html == "markitdown"

    def test_html_falls_back_to_default(self):
        raw = {"pdf": "a", "docx": "a", "pptx": "a", "xlsx": "a", "default": "fallback"}
        result = _build_backends_config(raw)
        assert result.html == "fallback"


class TestBuildExtractionConfig:
    def test_valid_extraction(self):
        raw = {"timeout_seconds": 60, "max_file_size_mb": 50, "xlsx_max_rows_per_sheet": 200, "isolation": "thread"}
        result = _build_extraction_config(raw)
        assert result.timeout_seconds == 60
        assert result.max_file_size_mb == 50
        assert result.xlsx_max_rows_per_sheet == 200
        assert result.isolation == "thread"

    def test_values_cast_to_int(self):
        raw = {
            "timeout_seconds": "90",
            "max_file_size_mb": "75",
            "xlsx_max_rows_per_sheet": "300",
            "isolation": "process",
        }
        result = _build_extraction_config(raw)
        assert result.timeout_seconds == 90
        assert result.max_file_size_mb == 75

    def test_invalid_isolation_raises(self):
        raw = {"timeout_seconds": 60, "max_file_size_mb": 50, "xlsx_max_rows_per_sheet": 200, "isolation": "fiber"}
        with pytest.raises(ConfigError, match="isolation"):
            _build_extraction_config(raw)


class TestBuildPassthroughConfig:
    def test_empty_passthrough(self):
        result = _build_passthrough_config({})
        assert result.extensions == ()
        assert result.paths == ()
        assert result.patterns == ()

    def test_valid_passthrough(self):
        raw = {"extensions": [".md", ".canvas"], "paths": ["raw/**"], "patterns": [r".*\.gen\..*"]}
        result = _build_passthrough_config(raw)
        assert result.extensions == (".md", ".canvas")
        assert result.paths == ("raw/**",)
        assert len(result.patterns) == 1

    def test_invalid_regex_raises(self):
        with pytest.raises(ConfigError, match="Invalid regex"):
            _build_passthrough_config({"patterns": ["[invalid"]})

    def test_multiple_patterns_validated(self):
        raw = {"patterns": [r"ok_pattern", "[bad"]}
        with pytest.raises(ConfigError, match="Invalid regex"):
            _build_passthrough_config(raw)


class TestBuildMediaConfig:
    def test_valid_media(self):
        raw = {
            "extract_images": True,
            "image_format": "png",
            "image_max_dimension": 1024,
            "image_max_bytes": 5000000,
            "image_max_pixels": 5000000,
            "image_allowed_formats": ["PNG", "JPEG"],
        }
        result = _build_media_config(raw)
        assert result.extract_images is True
        assert result.image_format == "png"
        assert result.image_max_dimension == 1024
        assert result.image_allowed_formats == frozenset({"PNG", "JPEG"})

    def test_extract_images_false(self):
        raw = {
            "extract_images": False,
            "image_format": "jpeg",
            "image_max_dimension": 0,
            "image_max_bytes": 1000,
            "image_max_pixels": 1000,
            "image_allowed_formats": [],
        }
        result = _build_media_config(raw)
        assert result.extract_images is False
        assert result.image_allowed_formats == frozenset()

    def test_values_cast_to_int(self):
        raw = {
            "extract_images": 1,
            "image_format": "png",
            "image_max_dimension": "512",
            "image_max_bytes": "1000",
            "image_max_pixels": "2000",
            "image_allowed_formats": ["PNG"],
        }
        result = _build_media_config(raw)
        assert result.image_max_dimension == 512
        assert result.image_max_bytes == 1000


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

    def test_passthrough_config_from_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
passthrough:
  extensions: [".md", ".canvas"]
  paths: ["raw/**"]
  patterns: [".*\\\\.generated\\\\..*"]
""")
        config = load_config(config_file)
        assert config.passthrough.extensions == (".md", ".canvas")
        assert config.passthrough.paths == ("raw/**",)
        assert len(config.passthrough.patterns) == 1

    def test_invalid_passthrough_regex_raises(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
passthrough:
  extensions: []
  paths: []
  patterns: ["[invalid"]
""")
        with pytest.raises(ConfigError, match="Invalid regex"):
            load_config(config_file)

    def test_new_backend_keys_override(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
backends:
  csv: markitdown
  json: markitdown
  yaml: markitdown
  image: markitdown
  html: native
""")
        config = load_config(config_file)
        assert config.backends.csv == "markitdown"
        assert config.backends.json == "markitdown"
        assert config.backends.yaml == "markitdown"
        assert config.backends.image == "markitdown"
        assert config.backends.html == "native"

    def test_new_backend_keys_take_bundled_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert config.backends.csv == "anydoc"
        assert config.backends.json == "native"
        assert config.backends.yaml == "native"
        assert config.backends.image == "native"

    def test_html_backend_falls_back_to_default_when_omitted(self):
        # A raw dict with no html key: the html slot gracefully defaults to
        # the configured `default`. Defensive fallback for callers that build
        # configs programmatically without going through load_config.
        raw = _load_default_yaml()
        del raw["backends"]["html"]
        raw["backends"]["default"] = "markitdown"
        config = _build_config(raw, config_dir=None)
        assert config.backends.html == "markitdown"
