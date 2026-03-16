# obsidian-import

Extract files (PDF, DOCX, PPTX, XLSX) into Obsidian-flavored Markdown.

The mirror of [obsidian-export](https://github.com/neuralsignal/obsidian-export): where obsidian-export converts Obsidian notes to PDF/DOCX, obsidian-import converts external documents into Obsidian-ready markdown with YAML frontmatter.

## Features

- **Native backends** for PDF (pdfplumber + pypdf), DOCX (defusedxml), PPTX (python-pptx), XLSX (openpyxl), CSV, JSON, YAML, and image files
- **Optional backends**: markitdown (fallback for HTML and other formats) and docling (high-quality ML-based extraction)
- **Embedded media extraction**: images embedded in PDF, DOCX, and PPTX are extracted and linked as Obsidian wikilinks
- **Pass-through mode**: copy files as-is without extraction (configurable by extension, glob, or regex)
- **Config-driven** backend selection per file type
- **Glob-based file discovery** with exclude patterns
- **Obsidian-flavored output** with YAML frontmatter
- **CLI**: `convert`, `discover`, `batch`, `doctor` commands
- **Configurable timeout and size limits** per extraction

## Quick Example

```bash
# Single file
obsidian-import convert report.pdf --output vault/imports/report.md

# Batch extraction
obsidian-import batch --config config.yaml

# Check backend availability
obsidian-import doctor
```

```python
from pathlib import Path
from obsidian_import import extract_file
from obsidian_import.config import config_for_backend, load_config
from obsidian_import.output import format_output

# Load from a YAML file
config = load_config(Path("config.yaml"))
doc = extract_file(Path("report.pdf"), config)
markdown = format_output(doc, config.output)

# Or use a convenience helper for quick single-backend extraction
config = config_for_backend("native", timeout_seconds=60, max_file_size_mb=50, xlsx_max_rows_per_sheet=500)
doc = extract_file(Path("report.pdf"), config)
```

## Pipeline

```
discover → extract → format → output (Obsidian .md)
```

## Related Packages

- [obsidian-export](https://github.com/neuralsignal/obsidian-export) — Convert Obsidian notes to PDF/DOCX
