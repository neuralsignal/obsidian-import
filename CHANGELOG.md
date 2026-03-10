# Changelog

## 0.2.0 (2026-03-10)

- Native backends for CSV, JSON, YAML, and image files
- Image embedding: generates Obsidian `![[filename]]` wikilinks and copies source images to vault
- Pass-through mode: copy files as-is without extraction (configurable by extension, glob, regex)
- Per-extension backend configuration (`backends.csv`, `backends.json`, `backends.yaml`, `backends.image`)
- `OutputConflictError` exception for destination file conflicts

## 0.1.0 (2026-03-09)

Initial release.

- Native backends: PDF (pdfplumber+pypdf), DOCX (defusedxml), PPTX (python-pptx), XLSX (openpyxl)
- Optional backends: markitdown (fallback), docling (high-quality)
- Config-driven backend selection per file type
- Glob-based file discovery with exclude patterns
- Obsidian-flavored markdown output with YAML frontmatter
- Click CLI: convert, discover, batch, doctor
- YAML configuration with deep-merge defaults
