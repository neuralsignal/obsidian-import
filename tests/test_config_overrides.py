"""Tests for config_from_overrides and the extraction.isolation config field."""

from __future__ import annotations

from pathlib import Path

import pytest

from obsidian_import import config_from_overrides as config_from_overrides_pkg
from obsidian_import.config import (
    ImportConfig,
    config_from_overrides,
    default_config,
    load_config,
)
from obsidian_import.exceptions import ConfigError
from obsidian_import.timeout import VALID_ISOLATION_MODES, run_with_timeout


class TestConfigFromOverrides:
    def test_exported_from_package_root(self) -> None:
        assert config_from_overrides_pkg is config_from_overrides

    def test_empty_overrides_equals_defaults(self) -> None:
        assert config_from_overrides({}) == default_config()

    def test_returns_import_config(self) -> None:
        config = config_from_overrides({})
        assert isinstance(config, ImportConfig)

    def test_nested_override_deep_merges(self) -> None:
        config = config_from_overrides({"extraction": {"max_file_size_mb": 7}})
        assert config.extraction.max_file_size_mb == 7
        # Sibling keys keep their defaults.
        assert config.extraction.timeout_seconds == default_config().extraction.timeout_seconds

    def test_backend_override(self) -> None:
        config = config_from_overrides({"backends": {"pdf": "markitdown"}})
        assert config.backends.pdf == "markitdown"
        assert config.backends.docx == "native"

    def test_invalid_overrides_raise_config_error(self) -> None:
        with pytest.raises(ConfigError):
            config_from_overrides({"input": {"directories": ["/bare/string"]}})


class TestIsolationConfig:
    def test_default_isolation_is_thread(self) -> None:
        assert default_config().extraction.isolation == "thread"

    def test_override_to_process(self) -> None:
        config = config_from_overrides({"extraction": {"isolation": "process"}})
        assert config.extraction.isolation == "process"

    def test_invalid_isolation_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="isolation"):
            config_from_overrides({"extraction": {"isolation": "fiber"}})

    def test_load_config_without_isolation_defaults_to_thread(self, tmp_path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("extraction:\n  timeout_seconds: 60\n")
        config = load_config(config_file)
        assert config.extraction.isolation == "thread"

    def test_config_accepts_every_mode_run_with_timeout_supports(self) -> None:
        """Config validation and run_with_timeout share one mode list."""
        for mode in VALID_ISOLATION_MODES:
            config = config_from_overrides({"extraction": {"isolation": mode}})
            assert config.extraction.isolation == mode

    def test_config_and_timeout_reject_with_identical_message(self) -> None:
        """One source of truth: both validation boundaries produce the same error."""
        with pytest.raises(ConfigError) as config_exc:
            config_from_overrides({"extraction": {"isolation": "fiber"}})
        with pytest.raises(ConfigError) as timeout_exc:
            run_with_timeout(str, ("x",), timeout_seconds=5, label="test", path=Path("/tmp/f.txt"), isolation="fiber")
        assert str(config_exc.value) == str(timeout_exc.value)
