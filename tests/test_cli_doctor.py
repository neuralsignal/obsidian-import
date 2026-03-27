"""Tests for CLI doctor and discover commands."""

from unittest.mock import patch

from click.testing import CliRunner

from obsidian_import.cli import main


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
