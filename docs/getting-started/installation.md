# Installation

## From PyPI

```bash
pip install obsidian-import
```

### Optional backends

Install extras for additional backend support:

```bash
# markitdown — fallback for HTML, CSV, and other formats
pip install obsidian-import[markitdown]

# docling — high-quality ML-based extraction for complex layouts
pip install obsidian-import[docling]
```

## Development Setup

Clone the repository and install with [pixi](https://pixi.sh/):

```bash
git clone https://github.com/neuralsignal/obsidian-import.git
cd obsidian-import
pixi install
```

### Pre-commit hooks

Install pre-commit hooks for automatic linting and formatting:

```bash
pixi run pre-commit-install
```

### Running tests

```bash
pixi run test
```

### Linting and formatting

```bash
pixi run lint
pixi run format-check
pixi run format
```

## Requirements

- Python >= 3.12
- Core dependencies are installed automatically: pyyaml, click, pdfplumber, pypdf, defusedxml, python-pptx, openpyxl
