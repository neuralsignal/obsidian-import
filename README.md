# obsidian-import

Extract files (PDF, DOCX, PPTX, XLSX) into Obsidian-flavored Markdown.

The mirror of [obsidian-export](https://github.com/neuralsignal/obsidian-export): where obsidian-export converts Obsidian notes to PDF/DOCX, obsidian-import converts external documents into Obsidian-ready markdown with YAML frontmatter.

## Installation

```bash
pip install obsidian-import
```

With optional backends:

```bash
pip install obsidian-import[markitdown]    # fallback for HTML, CSV, etc.
pip install obsidian-import[docling]       # high-quality ML-based extraction
```

## Quick Start

### Single file

```bash
obsidian-import convert report.pdf --output vault/imports/report.md
```

### Batch extraction

```bash
obsidian-import batch --config config.yaml
```

### Check backend availability

```bash
obsidian-import doctor
```

## Python API

```python
from pathlib import Path
from obsidian_import import extract_file, discover_files
from obsidian_import.config import load_config
from obsidian_import.output import format_output

config = load_config(Path("config.yaml"))

# Single file
doc = extract_file(Path("report.pdf"), config)
markdown = format_output(doc, config.output)

# Batch discovery
for file in discover_files(config):
    print(f"{file.extension}  {file.size_bytes:,} bytes  {file.path}")
```

## Configuration

Create a `config.yaml`:

```yaml
input:
  directories:
    - path: /path/to/documents
      extensions: [".pdf", ".docx", ".pptx", ".xlsx"]
      exclude: ["*.tmp", "~$*"]

output:
  directory: ./extracted
  frontmatter: true
  metadata_fields:
    - title
    - source
    - original_path
    - file_type
    - extracted_at
    - page_count

backends:
  pdf: native        # pdfplumber + pypdf
  docx: native       # defusedxml
  pptx: native       # python-pptx
  xlsx: native       # openpyxl
  default: native    # fallback for unknown extensions

extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500
```

## Backend Selection

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `native` | .pdf, .docx, .pptx, .xlsx | Core (included) | Good for text-heavy documents |
| `markitdown` | Any | `[markitdown]` extra | Good fallback for HTML, CSV, etc. |
| `docling` | Any | `[docling]` extra | Best for complex layouts, tables |

## CLI Reference

| Command | Description |
|---------|-------------|
| `obsidian-import convert <path>` | Extract a single file |
| `obsidian-import discover --config <yaml>` | List matching files |
| `obsidian-import batch --config <yaml>` | Extract all discovered files |
| `obsidian-import doctor` | Check backend availability |

## Output Format

Extracted files are written as Obsidian-flavored markdown with YAML frontmatter:

```markdown
---
title: Annual Report
source: obsidian-import
original_path: /documents/report.pdf
file_type: pdf
extracted_at: 2026-03-09T10:30:00Z
page_count: 12
---

# Annual Report

## Page 1

Content extracted from the first page...
```

## Related Packages

- [obsidian-export](https://github.com/neuralsignal/obsidian-export) — Convert Obsidian notes to PDF/DOCX
- [agentic-brain](https://github.com/neuralsignal/agentic-brain) — Agentic knowledge management (consumes both packages)

## License

MIT
