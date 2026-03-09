"""Tests for Click CLI commands."""

import zipfile

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


class TestConvertCommand:
    def test_convert_to_stdout(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Test content</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)

        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path)])
        assert result.exit_code == 0
        assert "Test content" in result.output

    def test_convert_to_file(self, tmp_path):
        docx_path = tmp_path / "test.docx"
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        with zipfile.ZipFile(str(docx_path), "w") as zf:
            zf.writestr("word/document.xml", xml)

        out_path = tmp_path / "output.md"
        runner = CliRunner()
        result = runner.invoke(main, ["convert", str(docx_path), "--output", str(out_path)])
        assert result.exit_code == 0
        assert out_path.exists()
        assert "Hello" in out_path.read_text()


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
