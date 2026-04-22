"""Tests for file discovery with tmp_path fixtures."""

from pathlib import Path
from unittest.mock import patch

from obsidian_import.config import (
    BackendsConfig,
    DirectoryConfig,
    ExtractionConfig,
    ImportConfig,
    InputConfig,
    MediaConfig,
    OutputConfig,
    PassthroughConfig,
)
from obsidian_import.discovery import DiscoveredFile, _is_excluded, discover_files


def _make_config(directories: tuple[DirectoryConfig, ...]) -> ImportConfig:
    return ImportConfig(
        input=InputConfig(directories=directories),
        output=OutputConfig(
            directory="./out",
            frontmatter=True,
            metadata_fields=("title",),
        ),
        backends=BackendsConfig(
            pdf="native",
            docx="native",
            pptx="native",
            xlsx="native",
            csv="native",
            json="native",
            yaml="native",
            image="native",
            default="native",
        ),
        extraction=ExtractionConfig(timeout_seconds=120, max_file_size_mb=100, xlsx_max_rows_per_sheet=500),
        passthrough=PassthroughConfig(extensions=(), paths=(), patterns=()),
        media=MediaConfig(
            extract_images=True,
            image_format="png",
            image_max_dimension=0,
            image_max_bytes=50_000_000,
            image_max_pixels=50_000_000,
            image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
        ),
    )


class TestDiscoverFiles:
    def test_finds_matching_files(self, tmp_path):
        (tmp_path / "doc.pdf").write_bytes(b"fake pdf")
        (tmp_path / "doc.docx").write_bytes(b"fake docx")
        (tmp_path / "readme.txt").write_text("not matched")

        config = _make_config((DirectoryConfig(path=str(tmp_path), extensions=(".pdf", ".docx"), exclude=()),))

        files = list(discover_files(config))
        extensions = {f.extension for f in files}
        assert extensions == {".pdf", ".docx"}
        assert len(files) == 2

    def test_respects_exclude_patterns(self, tmp_path):
        (tmp_path / "good.pdf").write_bytes(b"pdf")
        (tmp_path / "bad.pdf").write_bytes(b"pdf")

        config = _make_config((DirectoryConfig(path=str(tmp_path), extensions=(".pdf",), exclude=("bad.*",)),))

        files = list(discover_files(config))
        assert len(files) == 1
        assert files[0].path.name == "good.pdf"

    def test_skips_files_exceeding_max_size(self, tmp_path):
        (tmp_path / "small.pdf").write_bytes(b"x" * 100)
        (tmp_path / "huge.pdf").write_bytes(b"x" * (2 * 1024 * 1024))

        config = ImportConfig(
            input=InputConfig(directories=(DirectoryConfig(path=str(tmp_path), extensions=(".pdf",), exclude=()),)),
            output=OutputConfig(directory="./out", frontmatter=True, metadata_fields=("title",)),
            backends=BackendsConfig(
                pdf="native",
                docx="native",
                pptx="native",
                xlsx="native",
                csv="native",
                json="native",
                yaml="native",
                image="native",
                default="native",
            ),
            extraction=ExtractionConfig(timeout_seconds=120, max_file_size_mb=1, xlsx_max_rows_per_sheet=500),
            passthrough=PassthroughConfig(extensions=(), paths=(), patterns=()),
            media=MediaConfig(
                extract_images=True,
                image_format="png",
                image_max_dimension=0,
                image_max_bytes=50_000_000,
                image_max_pixels=50_000_000,
                image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
            ),
        )

        files = list(discover_files(config))
        assert len(files) == 1
        assert files[0].path.name == "small.pdf"

    def test_nonexistent_directory_yields_nothing(self, tmp_path):
        config = _make_config((DirectoryConfig(path=str(tmp_path / "nonexistent"), extensions=(".pdf",), exclude=()),))
        files = list(discover_files(config))
        assert files == []

    def test_discovered_file_attributes(self, tmp_path):
        (tmp_path / "test.xlsx").write_bytes(b"x" * 42)
        config = _make_config((DirectoryConfig(path=str(tmp_path), extensions=(".xlsx",), exclude=()),))

        files = list(discover_files(config))
        assert len(files) == 1
        f = files[0]
        assert isinstance(f, DiscoveredFile)
        assert f.extension == ".xlsx"
        assert f.size_bytes == 42
        assert f.source_directory == str(tmp_path)

    def test_recursive_discovery(self, tmp_path):
        subdir = tmp_path / "sub" / "deep"
        subdir.mkdir(parents=True)
        (subdir / "nested.pdf").write_bytes(b"pdf")
        (tmp_path / "top.pdf").write_bytes(b"pdf")

        config = _make_config((DirectoryConfig(path=str(tmp_path), extensions=(".pdf",), exclude=()),))

        files = list(discover_files(config))
        assert len(files) == 2

    def test_skips_symlinks(self, tmp_path):
        """Symlinks are skipped to prevent traversal outside input directory."""
        (tmp_path / "real.pdf").write_bytes(b"pdf")

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.pdf").write_bytes(b"secret")

        (tmp_path / "link.pdf").symlink_to(outside / "secret.pdf")

        config = _make_config((DirectoryConfig(path=str(tmp_path), extensions=(".pdf",), exclude=()),))

        files = list(discover_files(config))
        names = {f.path.name for f in files}
        assert "real.pdf" in names
        assert "link.pdf" not in names

    def test_skips_file_resolving_outside_base(self, tmp_path):
        """Files whose resolved path escapes the base directory are skipped (line 45)."""
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir()
        (scan_dir / "good.pdf").write_bytes(b"pdf")

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "escaped.pdf").write_bytes(b"secret")

        config = _make_config((DirectoryConfig(path=str(scan_dir), extensions=(".pdf",), exclude=()),))

        original_resolve = Path.resolve
        escaped_path = outside / "escaped.pdf"

        def patched_resolve(self, strict=False):
            if self.name == "good.pdf" and str(scan_dir) in str(self):
                return escaped_path
            return original_resolve(self, strict=strict)

        with patch.object(Path, "resolve", patched_resolve):
            files = list(discover_files(config))

        names = {f.path.name for f in files}
        assert "escaped.pdf" not in names


class TestIsExcluded:
    def test_filename_match_branch(self):
        """Pattern matching bare filename rather than relative path (line 73)."""
        base = Path("/project/docs")
        path = base / "subdir" / "report.pdf"
        assert _is_excluded(path, base, ("report.pdf",)) is True

    def test_filename_no_match(self):
        base = Path("/project/docs")
        path = base / "subdir" / "other.pdf"
        assert _is_excluded(path, base, ("report.pdf",)) is False
