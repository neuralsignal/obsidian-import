"""Tests for CLI convert command and config resolution."""

from unittest.mock import patch

from click.testing import CliRunner
from conftest import make_config_yaml, make_test_docx

from obsidian_import.cli import _copy_associated_files, _resolve_config, main
from obsidian_import.config import default_config
from obsidian_import.extraction_result import MediaFile
from obsidian_import.output import ExtractedDocument


class TestResolveConfig:
    def test_with_none_returns_default(self):
        cfg = _resolve_config(None)
        expected = default_config()
        assert cfg.output.frontmatter == expected.output.frontmatter

    def test_with_path_calls_load_config(self, tmp_path):
        config_file = make_config_yaml(tmp_path, tmp_path)
        cfg = _resolve_config(str(config_file))
        assert cfg.output.frontmatter is True


class TestConvertCommand:
    def test_convert_to_stdout(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        make_test_docx(docx_path, "Test content")

        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path)])
        assert result.exit_code == 0
        assert "Test content" in result.output

    def test_convert_to_file(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        make_test_docx(docx_path, "Hello")

        out_path = tmp_path / "output.md"
        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path), "--output", str(out_path)])
        assert result.exit_code == 0
        assert out_path.exists()
        assert "Hello" in out_path.read_text()

    def test_convert_with_output_copies_media(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        make_test_docx(docx_path, "Content")

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
        make_test_docx(docx_path, "Content")

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
        make_test_docx(docx_path, "Configured")

        config_file = make_config_yaml(tmp_path, tmp_path)
        out_path = tmp_path / "output.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["convert", str(docx_path), "--output", str(out_path), "--config", str(config_file)],
        )
        assert result.exit_code == 0
        assert out_path.exists()


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
