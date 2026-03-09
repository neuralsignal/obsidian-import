# Quick Start

## Single File Extraction

Extract a single file to Obsidian-flavored markdown:

```bash
obsidian-import convert report.pdf --output vault/imports/report.md
```

### Python API

```python
from pathlib import Path
from obsidian_import import extract_file
from obsidian_import.config import load_config
from obsidian_import.output import format_output

config = load_config(Path("config.yaml"))
doc = extract_file(Path("report.pdf"), config)
markdown = format_output(doc, config.output)
Path("output.md").write_text(markdown)
```

## Batch Extraction

Extract all files matching a configuration:

```bash
obsidian-import batch --config config.yaml
```

### Discover files first

Preview which files will be extracted:

```bash
obsidian-import discover --config config.yaml
```

### Python API

```python
from pathlib import Path
from obsidian_import import extract_file, discover_files
from obsidian_import.config import load_config
from obsidian_import.output import format_output

config = load_config(Path("config.yaml"))

for file in discover_files(config):
    print(f"{file.extension}  {file.size_bytes:,} bytes  {file.path}")
    doc = extract_file(file.path, config)
    markdown = format_output(doc, config.output)
    output_path = Path("extracted") / f"{file.path.stem}.md"
    output_path.write_text(markdown)
```

## Check Backend Availability

Verify which backends are installed and functional:

```bash
obsidian-import doctor
```

## Raw Text Extraction

If you only need the extracted text without frontmatter or metadata:

```python
from pathlib import Path
from obsidian_import import extract_text
from obsidian_import.config import load_config

config = load_config(Path("config.yaml"))
text = extract_text(Path("report.pdf"), config)
```
