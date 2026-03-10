"""Tests for native YAML backend."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.native_yaml import extract
from obsidian_import.exceptions import ExtractionError


class TestNativeYamlExtract:
    def test_extracts_simple_yaml(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("name: test\nversion: 1\n")
        result = extract(yaml_file, timeout_seconds=10)

        assert "# config" in result
        assert "```yaml" in result
        assert "name: test" in result
        assert "```" in result

    def test_extracts_nested_yaml(self, tmp_path):
        yaml_file = tmp_path / "nested.yaml"
        yaml_file.write_text("parent:\n  child: value\n  list:\n    - a\n    - b\n")
        result = extract(yaml_file, timeout_seconds=10)
        assert "```yaml" in result
        assert "child: value" in result

    def test_yml_extension(self, tmp_path):
        yaml_file = tmp_path / "data.yml"
        yaml_file.write_text("key: value\n")
        result = extract(yaml_file, timeout_seconds=10)
        assert "# data" in result

    def test_invalid_yaml_raises(self, tmp_path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(":\n  - :\n    - :\n      {{invalid")
        with pytest.raises(ExtractionError, match="YAML"):
            extract(yaml_file, timeout_seconds=10)

    def test_unicode_preserved(self, tmp_path):
        yaml_file = tmp_path / "i18n.yaml"
        yaml_file.write_text("greeting: \u3053\u3093\u306b\u3061\u306f\n")
        result = extract(yaml_file, timeout_seconds=10)
        assert "\u3053\u3093\u306b\u3061\u306f" in result


class TestNativeYamlProperties:
    @given(
        data=st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))), st.integers()
        )
    )
    @settings(max_examples=50)
    def test_output_ends_with_closing_fence(self, data: dict) -> None:
        import tempfile
        from pathlib import Path

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(data, f)
            f.flush()
            result = extract(Path(f.name), timeout_seconds=10)
        assert "```yaml" in result
        assert result.rstrip().endswith("```")
