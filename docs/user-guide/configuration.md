# Configuration

obsidian-import uses a YAML configuration file for all settings. Pass it to the CLI with `--config` or load it programmatically with `load_config()`.

## Full Configuration Reference

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

## Sections

### `input`

Defines where to find files for batch extraction.

| Field | Type | Description |
|-------|------|-------------|
| `directories` | list | List of directory entries to scan |
| `directories[].path` | string | Absolute or relative path to scan |
| `directories[].extensions` | list[string] | File extensions to include (e.g., `[".pdf", ".docx"]`) |
| `directories[].exclude` | list[string] | Glob patterns to exclude (e.g., `["*.tmp", "~$*"]`) |

### `output`

Controls the format and location of extracted markdown files.

| Field | Type | Description |
|-------|------|-------------|
| `directory` | string | Output directory for batch extraction |
| `frontmatter` | bool | Include YAML frontmatter in output |
| `metadata_fields` | list[string] | Which metadata fields to include in frontmatter |

### `backends`

Maps file extensions to extraction backends. See [Backends](backends.md) for details.

| Field | Type | Description |
|-------|------|-------------|
| `pdf` | string | Backend for `.pdf` files |
| `docx` | string | Backend for `.docx` files |
| `pptx` | string | Backend for `.pptx` files |
| `xlsx` | string | Backend for `.xlsx` files |
| `default` | string | Fallback backend for unlisted extensions |

Valid values: `native`, `markitdown`, `docling`.

### `extraction`

Controls extraction behavior.

| Field | Type | Description |
|-------|------|-------------|
| `timeout_seconds` | int | Maximum seconds per file extraction |
| `max_file_size_mb` | int | Maximum file size in megabytes |
| `xlsx_max_rows_per_sheet` | int | Maximum rows to extract per Excel sheet |

## Loading Configuration

### CLI

```bash
obsidian-import batch --config config.yaml
```

### Python

```python
from pathlib import Path
from obsidian_import.config import load_config

config = load_config(Path("config.yaml"))
```
