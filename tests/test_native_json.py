"""Tests for native JSON backend."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.native_json import extract
from obsidian_import.exceptions import ExtractionError


class TestNativeJsonExtract:
    def test_extracts_simple_json(self, tmp_path):
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value", "number": 42}')
        result = extract(json_file, timeout_seconds=10)

        assert "# config" in result
        assert "```json" in result
        assert '"key": "value"' in result
        assert '"number": 42' in result
        assert "```" in result

    def test_extracts_array(self, tmp_path):
        json_file = tmp_path / "list.json"
        json_file.write_text("[1, 2, 3]")
        result = extract(json_file, timeout_seconds=10)
        assert "```json" in result

    def test_pretty_prints_compact_json(self, tmp_path):
        json_file = tmp_path / "compact.json"
        json_file.write_text('{"a":1,"b":{"c":2}}')
        result = extract(json_file, timeout_seconds=10)
        assert "  " in result  # indentation present

    def test_invalid_json_raises(self, tmp_path):
        json_file = tmp_path / "bad.json"
        json_file.write_text("{not valid json}")
        with pytest.raises(ExtractionError, match="JSON"):
            extract(json_file, timeout_seconds=10)

    def test_unicode_preserved(self, tmp_path):
        json_file = tmp_path / "unicode.json"
        json_file.write_text('{"emoji": "\u2764\ufe0f", "kanji": "\u6f22\u5b57"}')
        result = extract(json_file, timeout_seconds=10)
        assert "\u2764\ufe0f" in result
        assert "\u6f22\u5b57" in result


class TestNativeJsonProperties:
    @given(data=st.dictionaries(st.text(min_size=1, max_size=10), st.integers()))
    @settings(max_examples=50)
    def test_output_contains_fenced_code_block(self, data: dict) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            result = extract(Path(f.name), timeout_seconds=10)
        assert "```json" in result
        assert result.rstrip().endswith("```")
