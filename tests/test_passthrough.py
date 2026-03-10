"""Tests for pass-through file matching and copying."""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.config import PassthroughConfig
from obsidian_import.exceptions import OutputConflictError
from obsidian_import.passthrough import copy_passthrough, matches_passthrough


class TestMatchesPassthrough:
    def test_no_rules_never_matches(self):
        cfg = PassthroughConfig(extensions=(), paths=(), patterns=())
        assert matches_passthrough(Path("/data/file.md"), cfg) is False

    def test_extension_match(self):
        cfg = PassthroughConfig(extensions=(".md",), paths=(), patterns=())
        assert matches_passthrough(Path("/data/notes.md"), cfg) is True

    def test_extension_no_match(self):
        cfg = PassthroughConfig(extensions=(".md",), paths=(), patterns=())
        assert matches_passthrough(Path("/data/report.pdf"), cfg) is False

    def test_extension_case_insensitive(self):
        cfg = PassthroughConfig(extensions=(".md",), paths=(), patterns=())
        assert matches_passthrough(Path("/data/README.MD"), cfg) is True

    def test_path_glob_match(self):
        cfg = PassthroughConfig(extensions=(), paths=("**/*.md",), patterns=())
        assert matches_passthrough(Path("/data/notes/readme.md"), cfg) is True

    def test_path_glob_no_match(self):
        cfg = PassthroughConfig(extensions=(), paths=("notes/**",), patterns=())
        assert matches_passthrough(Path("/data/other/file.md"), cfg) is False

    def test_regex_pattern_match(self):
        cfg = PassthroughConfig(extensions=(), paths=(), patterns=(r".*\.generated\..*",))
        assert matches_passthrough(Path("/data/file.generated.md"), cfg) is True

    def test_regex_pattern_no_match(self):
        cfg = PassthroughConfig(extensions=(), paths=(), patterns=(r".*\.generated\..*",))
        assert matches_passthrough(Path("/data/file.md"), cfg) is False

    def test_or_logic_across_rule_types(self):
        cfg = PassthroughConfig(
            extensions=(".canvas",),
            paths=("raw/**",),
            patterns=(r".*\.template\..*",),
        )
        assert matches_passthrough(Path("/vault/drawing.canvas"), cfg) is True
        assert matches_passthrough(Path("raw/notes.txt"), cfg) is True
        assert matches_passthrough(Path("/data/my.template.md"), cfg) is True
        assert matches_passthrough(Path("/data/report.pdf"), cfg) is False

    def test_multiple_extensions(self):
        cfg = PassthroughConfig(extensions=(".md", ".markdown", ".canvas"), paths=(), patterns=())
        assert matches_passthrough(Path("a.md"), cfg) is True
        assert matches_passthrough(Path("b.markdown"), cfg) is True
        assert matches_passthrough(Path("c.canvas"), cfg) is True
        assert matches_passthrough(Path("d.txt"), cfg) is False


class TestCopyPassthrough:
    def test_copies_file(self, tmp_path):
        src = tmp_path / "source" / "note.md"
        src.parent.mkdir()
        src.write_text("# Hello")
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()

        result = copy_passthrough(src, dest_dir)

        assert result == dest_dir / "note.md"
        assert result.read_text() == "# Hello"

    def test_preserves_binary_content(self, tmp_path):
        src = tmp_path / "image.png"
        content = bytes(range(256))
        src.write_bytes(content)
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()

        result = copy_passthrough(src, dest_dir)
        assert result.read_bytes() == content

    def test_conflict_raises(self, tmp_path):
        src = tmp_path / "note.md"
        src.write_text("new content")
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()
        (dest_dir / "note.md").write_text("existing content")

        with pytest.raises(OutputConflictError, match="note.md"):
            copy_passthrough(src, dest_dir)


class TestMatchesPassthroughProperties:
    @given(
        ext=st.sampled_from([".md", ".csv", ".json", ".yaml", ".canvas"]),
        stem=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @settings(max_examples=50)
    def test_extension_match_is_deterministic(self, ext: str, stem: str) -> None:
        cfg = PassthroughConfig(extensions=(ext,), paths=(), patterns=())
        path = Path(f"/data/{stem}{ext}")
        assert matches_passthrough(path, cfg) is True

    @given(
        stem=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )
    @settings(max_examples=50)
    def test_empty_config_never_matches(self, stem: str) -> None:
        cfg = PassthroughConfig(extensions=(), paths=(), patterns=())
        path = Path(f"/data/{stem}.txt")
        assert matches_passthrough(path, cfg) is False
