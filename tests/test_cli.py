"""Tests for Click CLI commands."""

import zipfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from obsidian_import.cli import _copy_associated_files, _resolve_config, main
from obsidian_import.config import default_config
from obsidian_import.discovery import DiscoveredFile
from obsidian_import.exceptions import ObsidianImportError
from obsidian_import.extraction_result import MediaFile
from obsidian_import.output import ExtractedDocument


def _make_docx(path: Path, text: str) -> None:
    """Create a minimal .docx file with given text."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("word/document.xml", xml)


def _make_config_yaml(tmp_path: Path, input_dir: Path | None) -> Path:
    """Create a config YAML file. Uses input_dir or tmp_path as default."""
    d = input_dir or tmp_path
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
input:
  directories:
    - path: {d}
      extensions: [".docx"]
      exclude: []
output:
  directory: {tmp_path / "out"}
  frontmatter: true
  metadata_fields: [title]
backends:
  pdf: native
  docx: native
  pptx: native
  xlsx: native
  default: native
extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500
""")
    return config_file


class TestResolveConfig:
    def test_with_none_returns_default(self):
        cfg = _resolve_config(None)
        expected = default_config()
        assert cfg.output.frontmatter == expected.output.frontmatter

    def test_with_path_calls_load_config(self, tmp_path):
        config_file = _make_config_yaml(tmp_path, tmp_path)
        cfg = _resolve_config(str(config_file))
        assert cfg.output.frontmatter is True


class TestDoctorCommand:
    def test_doctor_runs(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code in (0, 1)
        assert "native (pdf)" in result.output

    def test_doctor_shows_native_backends(self):
        runner = CliRunner()
        result = runner.invoke(main, ["doctor"])
        assert "native (docx)" in result.output
        assert "native (xlsx)" in result.output

    def test_doctor_native_unavailable_exits_1(self):
        runner = CliRunner()
        with patch(
            "obsidian_import.cli.check_backend_available",
            return_value=(False, "not found"),
        ):
            result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 1
        assert "Some required backends are missing" in result.output

    def test_doctor_import_error_exits_1(self):
        runner = CliRunner()
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "pdfplumber":
                raise ImportError("no pdfplumber")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            result = runner.invoke(main, ["doctor"])
        assert "MISSING" in result.output
        assert result.exit_code == 1

    def test_doctor_all_ok_exits_0(self):
        runner = CliRunner()
        with patch(
            "obsidian_import.cli.check_backend_available",
            return_value=(True, "ok"),
        ):
            result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "All required backends available" in result.output


class TestConvertCommand:
    def test_convert_to_stdout(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        _make_docx(docx_path, "Test content")

        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path)])
        assert result.exit_code == 0
        assert "Test content" in result.output

    def test_convert_to_file(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        _make_docx(docx_path, "Hello")

        out_path = tmp_path / "output.md"
        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path), "--output", str(out_path)])
        assert result.exit_code == 0
        assert out_path.exists()
        assert "Hello" in out_path.read_text()

    def test_convert_with_output_copies_media(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        _make_docx(docx_path, "Content")

        media_file = MediaFile(
            source_path=tmp_path / "img.png",
            filename="img.png",
            media_type="image/png",
        )
        doc = ExtractedDocument(
            source_path=docx_path,
            markdown="Content",
            title="test",
            file_type=".docx",
            page_count=1,
            associated_files=(),
            media_files=(media_file,),
        )

        out_path = tmp_path / "output.md"
        runner = CliRunner()
        with (
            patch("obsidian_import.cli.extract_file", return_value=doc),
            patch("obsidian_import.cli.format_output", return_value="Content"),
            patch("obsidian_import.cli.copy_media_files") as mock_copy,
        ):
            result = runner.invoke(main, ["convert", str(docx_path), "--output", str(out_path)])

        assert result.exit_code == 0
        mock_copy.assert_called_once()

    def test_convert_stdout_with_media_warns(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        _make_docx(docx_path, "Content")

        media_file = MediaFile(
            source_path=tmp_path / "img.png",
            filename="img.png",
            media_type="image/png",
        )
        doc = ExtractedDocument(
            source_path=docx_path,
            markdown="Content",
            title="test",
            file_type=".docx",
            page_count=1,
            associated_files=(),
            media_files=(media_file,),
        )

        runner = CliRunner()
        with (
            patch("obsidian_import.cli.extract_file", return_value=doc),
            patch("obsidian_import.cli.format_output", return_value="Content"),
            patch("obsidian_import.cli.log") as mock_log,
        ):
            result = runner.invoke(main, ["convert", str(docx_path)])

        assert result.exit_code == 0
        mock_log.warning.assert_called_once()
        assert "media files" in mock_log.warning.call_args[0][0].lower()

    def test_convert_with_config_path(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        _make_docx(docx_path, "Configured")

        config_file = _make_config_yaml(tmp_path, tmp_path)
        out_path = tmp_path / "output.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["convert", str(docx_path), "--output", str(out_path), "--config", str(config_file)],
        )
        assert result.exit_code == 0
        assert out_path.exists()


class TestBatchCommand:
    def test_batch_extracts_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        _make_docx(docx_path, "Batch content")

        config_file = _make_config_yaml(tmp_path, input_dir)
        out_dir = tmp_path / "batch_out"

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["batch", "--config", str(config_file), "--output-dir", str(out_dir)],
        )
        assert result.exit_code == 0
        assert "OK" in result.output
        assert "1 extracted" in result.output

    def test_batch_passthrough_copy(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        _make_docx(docx_path, "content")

        config_file = _make_config_yaml(tmp_path, input_dir)
        out_dir = tmp_path / "batch_out"

        discovered = DiscoveredFile(
            path=docx_path,
            extension=".docx",
            size_bytes=100,
            source_directory=str(input_dir),
        )
        dest = out_dir / "test.docx"

        runner = CliRunner()
        with (
            patch("obsidian_import.cli.discover_files", return_value=[discovered]),
            patch("obsidian_import.cli.matches_passthrough", return_value=True),
            patch("obsidian_import.cli.copy_passthrough", return_value=dest),
        ):
            result = runner.invoke(
                main,
                ["batch", "--config", str(config_file), "--output-dir", str(out_dir)],
            )
        assert result.exit_code == 0
        assert "COPY" in result.output
        assert "1 copied" in result.output

    def test_batch_extraction_failure(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        _make_docx(docx_path, "content")

        config_file = _make_config_yaml(tmp_path, input_dir)
        out_dir = tmp_path / "batch_out"

        discovered = DiscoveredFile(
            path=docx_path,
            extension=".docx",
            size_bytes=100,
            source_directory=str(input_dir),
        )

        runner = CliRunner()
        with (
            patch("obsidian_import.cli.discover_files", return_value=[discovered]),
            patch("obsidian_import.cli.matches_passthrough", return_value=False),
            patch(
                "obsidian_import.cli.extract_file",
                side_effect=ObsidianImportError("extraction failed"),
            ),
        ):
            result = runner.invoke(
                main,
                ["batch", "--config", str(config_file), "--output-dir", str(out_dir)],
            )
        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert "1 failed" in result.output

    def test_batch_passthrough_failure(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        _make_docx(docx_path, "content")

        config_file = _make_config_yaml(tmp_path, input_dir)
        out_dir = tmp_path / "batch_out"

        discovered = DiscoveredFile(
            path=docx_path,
            extension=".docx",
            size_bytes=100,
            source_directory=str(input_dir),
        )

        runner = CliRunner()
        with (
            patch("obsidian_import.cli.discover_files", return_value=[discovered]),
            patch("obsidian_import.cli.matches_passthrough", return_value=True),
            patch(
                "obsidian_import.cli.copy_passthrough",
                side_effect=ObsidianImportError("copy failed"),
            ),
        ):
            result = runner.invoke(
                main,
                ["batch", "--config", str(config_file), "--output-dir", str(out_dir)],
            )
        assert result.exit_code == 0
        assert "FAIL" in result.output
        assert "1 failed" in result.output

    def test_batch_uses_config_output_dir(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        _make_docx(docx_path, "Content")

        config_file = _make_config_yaml(tmp_path, input_dir)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["batch", "--config", str(config_file)],
        )
        assert result.exit_code == 0
        assert "Done:" in result.output


class TestCopyAssociatedFiles:
    def test_copies_each_file(self, tmp_path):
        src1 = tmp_path / "img1.png"
        src2 = tmp_path / "img2.png"
        src1.write_bytes(b"png1")
        src2.write_bytes(b"png2")

        dest_dir = tmp_path / "out"
        dest_dir.mkdir()

        with patch("obsidian_import.cli.copy_passthrough") as mock_copy:
            _copy_associated_files((src1, src2), dest_dir)

        assert mock_copy.call_count == 2
        mock_copy.assert_any_call(src1, dest_dir)
        mock_copy.assert_any_call(src2, dest_dir)

    def test_empty_list_no_calls(self, tmp_path):
        dest_dir = tmp_path / "out"
        dest_dir.mkdir()

        with patch("obsidian_import.cli.copy_passthrough") as mock_copy:
            _copy_associated_files((), dest_dir)

        mock_copy.assert_not_called()


class TestDiscoverCommand:
    def test_discover_requires_config(self):
        runner = CliRunner()
        result = runner.invoke(main, ["discover"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_discover_with_config(self, tmp_path):
        (tmp_path / "doc.pdf").write_bytes(b"fake")
        config_file = tmp_path / "config.yaml"
        config_file.write_text(f"""
input:
  directories:
    - path: {tmp_path}
      extensions: [".pdf"]
      exclude: []
output:
  directory: ./out
  frontmatter: true
  metadata_fields: [title]
backends:
  pdf: native
  docx: native
  pptx: native
  xlsx: native
  default: native
extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500
""")
        runner = CliRunner()
        result = runner.invoke(main, ["discover", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "1 files found" in result.output
