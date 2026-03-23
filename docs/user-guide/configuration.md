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
  csv: native        # built-in csv module
  json: native       # built-in json module
  yaml: native       # pyyaml
  image: native      # Pillow
  default: native    # fallback for unlisted extensions

extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500

media:
  extract_images: true
  image_format: png
  image_max_dimension: 0   # 0 = no limit

passthrough:
  extensions: []
  paths: []
  patterns: []
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
| `csv` | string | Backend for `.csv` files |
| `json` | string | Backend for `.json` files |
| `yaml` | string | Backend for `.yaml` / `.yml` files |
| `image` | string | Backend for image files (`.png`, `.jpg`, `.gif`, etc.) |
| `default` | string | Fallback backend for unlisted extensions |

Valid values: `native`, `markitdown`, `docling`.

### `extraction`

Controls extraction behavior.

| Field | Type | Description |
|-------|------|-------------|
| `timeout_seconds` | int | Maximum seconds per file extraction |
| `max_file_size_mb` | int | Maximum file size in megabytes |
| `xlsx_max_rows_per_sheet` | int | Maximum rows to extract per Excel sheet |

### `media`

Controls embedded image extraction from documents.

| Field | Type | Description |
|-------|------|-------------|
| `extract_images` | bool | Extract embedded images from PDF, DOCX, and PPTX files |
| `image_format` | string | Output format for extracted images (`png`, `jpg`) |
| `image_max_dimension` | int | Maximum width or height in pixels; `0` means no limit |

When `extract_images` is enabled, images are saved to a per-document folder (`<output_dir>/<doc_stem>/`) and linked in the markdown as Obsidian wikilinks (`![[doc_stem/page1_img0.png]]`).

### `passthrough`

Files matching any passthrough rule are copied as-is to the output directory without extraction. Rules are evaluated with OR logic — a file matching any single rule is passed through.

| Field | Type | Description |
|-------|------|-------------|
| `extensions` | list[string] | File extensions to copy without extraction (e.g., `[".md", ".canvas"]`) |
| `paths` | list[string] | Glob patterns matched against the full file path |
| `patterns` | list[string] | Regular expression patterns matched against the full file path |

```yaml
passthrough:
  extensions: [".md", ".canvas"]
  paths: ["notes/raw/**"]
  patterns: [".*\\.generated\\..*"]
```

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
