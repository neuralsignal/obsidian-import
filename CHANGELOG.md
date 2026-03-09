# Changelog

## 0.1.0 (2026-03-09)

Initial release.

- Native backends: PDF (pdfplumber+pypdf), DOCX (defusedxml), PPTX (python-pptx), XLSX (openpyxl)
- Optional backends: markitdown (fallback), docling (high-quality)
- Config-driven backend selection per file type
- Glob-based file discovery with exclude patterns
- Obsidian-flavored markdown output with YAML frontmatter
- Click CLI: convert, discover, batch, doctor
- YAML configuration with deep-merge defaults
