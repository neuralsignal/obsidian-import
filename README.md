# obsidian-import

Extract files (PDF, DOCX, PPTX, XLSX, CSV, JSON, YAML, images) into Obsidian-flavored Markdown.

The mirror of [obsidian-export](https://github.com/neuralsignal/obsidian-export): where obsidian-export converts Obsidian notes to PDF/DOCX, obsidian-import converts external documents into Obsidian-ready markdown with YAML frontmatter.

## Installation

```bash
pip install obsidian-import
```

With optional backends:

```bash
pip install obsidian-import[markitdown]    # fallback for HTML, etc.
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
from obsidian_import import extract_file, extract_text, discover_files, config_for_backend
from obsidian_import.config import load_config
from obsidian_import.output import format_output

config = load_config(Path("config.yaml"))

# Single file (full document with frontmatter)
doc = extract_file(Path("report.pdf"), config)
markdown = format_output(doc, config.output)

# Quick text extraction (no config file needed)
config = config_for_backend("markitdown", timeout_seconds=60, max_file_size_mb=50, xlsx_max_rows_per_sheet=500, extract_images=False)
text = extract_text(Path("report.pdf"), config)

# Batch discovery
for file in discover_files(config):
    print(f"{file.extension}  {file.size_bytes:,} bytes  {file.path}")
```

### `config_for_backend()` — Quick Configuration

For consumers that just need text extraction without managing the full config surface:

```python
from obsidian_import import extract_text, config_for_backend

config = config_for_backend(
    backend="markitdown",
    timeout_seconds=60,
    max_file_size_mb=50,
    xlsx_max_rows_per_sheet=500,
    extract_images=False,
)
text = extract_text(Path("document.docx"), config)
```

This sets all backends to the specified backend name. All parameters are required — no hidden defaults.

## Configuration

Create a `config.yaml`:

```yaml
input:
  directories:
    - path: /path/to/documents
      extensions: [".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".json", ".yaml", ".png", ".jpg"]
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
  csv: native        # stdlib csv -> GFM table
  json: native       # stdlib json -> fenced code block
  yaml: native       # PyYAML -> fenced code block
  image: native      # Obsidian ![[wikilink]] embed
  default: native    # fallback for unknown extensions

extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500

# Pass-through: copy files as-is without extraction
passthrough:
  extensions: [".md", ".markdown", ".canvas"]
  paths: ["raw/**"]
  patterns: []
```

## Backend Selection

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `native` | .pdf, .docx, .pptx, .xlsx, .csv, .json, .yaml/.yml, images | Core (included) | Good for text-heavy documents |
| `markitdown` | Any | `[markitdown]` extra | Good fallback for HTML, etc. |
| `docling` | Any | `[docling]` extra | Best for complex layouts, tables |

### Format-Specific Behavior

| Format | Native Backend Output |
|--------|----------------------|
| PDF | Page-by-page markdown with tables and metadata |
| DOCX | Headings, paragraphs, and tables from XML |
| PPTX | Slide-by-slide with titles, body text, and notes |
| XLSX | Sheet-by-sheet GFM markdown tables |
| CSV | GFM markdown table |
| JSON | Pretty-printed fenced code block |
| YAML/YML | Fenced code block |
| Images (PNG, JPG, GIF, SVG, WEBP, BMP, TIFF) | Obsidian wikilink embed `![[image.png]]` |

## Pass-Through Mode

Files matching pass-through rules are copied to the output directory as-is, without extraction or conversion. This is useful for:

- `.md` files that are already Obsidian-ready
- `.csv`, `.json`, `.yaml` files used by Obsidian plugins (e.g., Dataview)
- Any file type where transformation is unwanted

Pass-through rules are evaluated before backend dispatch. A file matches if it hits **any** rule (OR logic):

```yaml
passthrough:
  # Extension list (cheapest check, runs first)
  extensions: [".md", ".markdown", ".canvas"]

  # fnmatch patterns (matched against full source path string;
  # '*' matches '/', so '**/' is not needed for directory traversal)
  paths: ["notes/raw/**", "**/*.template.*"]

  # Regex patterns (matched against full source path string)
  patterns: [".*\\.generated\\..*"]
```

Decision tree:

```
File discovered
  |
  +- matches passthrough? -> COPY as-is (no .md wrapper)
  |
  +- NO -> backend dispatch -> extract -> write .md
```

## Media Extraction

PDF, DOCX, and PPTX files can contain embedded images. Enable media extraction to save these as separate files alongside the markdown output:

```yaml
media:
  extract_images: true     # enable/disable embedded image extraction
  image_format: png        # output format: png, jpg, webp
  image_max_dimension: 0   # max width/height in px (0 = no resize)
```

Extracted images are saved in per-document media folders (`<doc-stem>/`) and referenced via Obsidian wikilinks (`![[doc-stem/image_001.png]]`).

To disable media extraction (e.g., for text-only pipelines), set `extract_images: false` in your config YAML or pass `extract_images=False` to `config_for_backend()`.

## Image Handling

Images are handled differently from text documents. The native image backend generates an Obsidian wikilink embed:

```markdown
---
title: diagram
source: obsidian-import
file_type: png
---

![[diagram.png]]
```

The image file is automatically copied alongside the `.md` output so Obsidian can render it inline. Supported formats: PNG, JPG, JPEG, GIF, SVG, WEBP, BMP, TIFF.

## CLI Reference

| Command | Description |
|---------|-------------|
| `obsidian-import convert <path>` | Extract a single file |
| `obsidian-import discover --config <yaml>` | List matching files |
| `obsidian-import batch --config <yaml>` | Extract all discovered files (with pass-through) |
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

- [obsidian-export](https://github.com/neuralsignal/obsidian-export) -- Convert Obsidian notes to PDF/DOCX
- [agentic-brain](https://github.com/neuralsignal/agentic-brain) -- Agentic knowledge management (consumes both packages)

## License

MIT
