# obsidian-import

Extract files (PDF, DOCX, PPTX, XLSX) into Obsidian-flavored Markdown.

The mirror of [obsidian-export](https://github.com/neuralsignal/obsidian-export): where obsidian-export converts Obsidian notes to PDF/DOCX, obsidian-import converts external documents into Obsidian-ready markdown with YAML frontmatter.

## Features

- **Native backends** for PDF (pdfplumber + pypdf), DOCX (defusedxml), PPTX (python-pptx), XLSX (openpyxl)
- **Optional backends**: markitdown (fallback for HTML, CSV, etc.) and docling (high-quality ML-based extraction)
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
from obsidian_import.config import load_config
from obsidian_import.output import format_output

config = load_config(Path("config.yaml"))
doc = extract_file(Path("report.pdf"), config)
markdown = format_output(doc, config.output)
```

## Pipeline

```
discover → extract → format → output (Obsidian .md)
```

## Related Packages

- [obsidian-export](https://github.com/neuralsignal/obsidian-export) — Convert Obsidian notes to PDF/DOCX
