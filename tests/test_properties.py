"""Property-based tests using hypothesis for pure functions."""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.config import _deep_merge
from obsidian_import.discovery import _is_excluded
from obsidian_import.output import output_path_for


class TestDeepMergeProperties:
    @given(
        base=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
        override=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
    )
    @settings(max_examples=100)
    def test_override_keys_present_in_result(self, base: dict, override: dict) -> None:
        """Every key in override must appear in the merged result."""
        merged = _deep_merge(base, override)
        for key in override:
            assert key in merged

    @given(base=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()))
    @settings(max_examples=50)
    def test_empty_override_is_identity(self, base: dict) -> None:
        """Merging with an empty dict produces the original."""
        assert _deep_merge(base, {}) == base

    @given(override=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()))
    @settings(max_examples=50)
    def test_empty_base_returns_override(self, override: dict) -> None:
        """Merging into an empty base produces the override."""
        assert _deep_merge({}, override) == override

    @given(
        base=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
        override=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
    )
    @settings(max_examples=100)
    def test_override_wins_on_conflict(self, base: dict, override: dict) -> None:
        """For shared keys, override value wins."""
        merged = _deep_merge(base, override)
        for key in override:
            assert merged[key] == override[key]

    @given(
        base=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
        override=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
    )
    @settings(max_examples=100)
    def test_base_only_keys_preserved(self, base: dict, override: dict) -> None:
        """Keys only in base are preserved."""
        merged = _deep_merge(base, override)
        for key in base:
            if key not in override:
                assert merged[key] == base[key]


class TestIsExcludedProperties:
    @given(filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))))
    @settings(max_examples=50)
    def test_no_patterns_never_excludes(self, filename: str) -> None:
        """An empty exclude list never excludes any file."""
        base = Path("/base")
        path = base / filename
        assert _is_excluded(path, base, ()) is False

    @given(filename=st.from_regex(r"[a-z]{1,10}\.[a-z]{1,4}", fullmatch=True))
    @settings(max_examples=50)
    def test_star_dot_star_excludes_everything(self, filename: str) -> None:
        """The pattern '*.*' excludes any file with an extension."""
        base = Path("/base")
        path = base / filename
        assert _is_excluded(path, base, ("*.*",)) is True


class TestOutputPathForProperties:
    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        ext=st.sampled_from([".pdf", ".docx", ".pptx", ".xlsx"]),
    )
    @settings(max_examples=100)
    def test_always_produces_md_suffix(self, stem: str, ext: str) -> None:
        """Output path always has .md extension."""
        source = Path(f"/data/{stem}{ext}")
        result = output_path_for(source, "/out", source_root=None)
        assert result.suffix == ".md"

    @given(
        stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        ext=st.sampled_from([".pdf", ".docx", ".pptx", ".xlsx"]),
    )
    @settings(max_examples=100)
    def test_preserves_stem(self, stem: str, ext: str) -> None:
        """Output path preserves the original file stem."""
        source = Path(f"/data/{stem}{ext}")
        result = output_path_for(source, "/out", source_root=None)
        assert result.stem == stem
