"""Tests for CLI batch command."""

from unittest.mock import patch

from click.testing import CliRunner
from conftest import make_config_yaml, make_test_docx

from obsidian_import.cli import main
from obsidian_import.discovery import DiscoveredFile
from obsidian_import.exceptions import ObsidianImportError


class TestBatchCommand:
    def test_batch_extracts_files(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        docx_path = input_dir / "test.docx"
        make_test_docx(docx_path, "Batch content")

        config_file = make_config_yaml(tmp_path, input_dir)
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
        make_test_docx(docx_path, "content")

        config_file = make_config_yaml(tmp_path, input_dir)
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
        make_test_docx(docx_path, "content")

        config_file = make_config_yaml(tmp_path, input_dir)
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
        make_test_docx(docx_path, "content")

        config_file = make_config_yaml(tmp_path, input_dir)
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
        make_test_docx(docx_path, "Content")

        config_file = make_config_yaml(tmp_path, input_dir)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["batch", "--config", str(config_file)],
        )
        assert result.exit_code == 0
        assert "Done:" in result.output
