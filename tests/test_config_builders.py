"""Tests for config builder functions (_build_*) used during config construction."""

from pathlib import Path

import pytest

from obsidian_import.config import (
    _build_backends_config,
    _build_config,
    _build_extraction_config,
    _build_input_config,
    _build_media_config,
    _build_output_config,
    _build_passthrough_config,
    _load_default_yaml,
)
from obsidian_import.exceptions import ConfigError


class TestBuildConfig:
    def test_relative_config_dir_resolved(self):
        """Relative config_dir is resolved to absolute (line 101)."""
        raw = _load_default_yaml()
        raw["input"]["directories"] = [{"path": "/tmp/test", "extensions": [".pdf"], "exclude": []}]
        config = _build_config(raw, config_dir=Path("relative/path"))
        from obsidian_import.config import ImportConfig

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
