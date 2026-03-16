# Backends

obsidian-import uses a backend system to handle different file formats. Each backend is a module that knows how to extract text from specific file types.

## Available Backends

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `native` | .pdf, .docx, .pptx, .xlsx, .csv, .json, .yaml, images | Core (included) | Good for text-heavy documents |
| `markitdown` | Any | `pip install obsidian-import[markitdown]` | Good fallback for HTML and other formats |
| `docling` | Any | `pip install obsidian-import[docling]` | Best for complex layouts and tables |

## Native Backends

The native backends are included with the base install and require no additional dependencies beyond the core install.

### PDF (`native_pdf`)

Uses **pdfplumber** for text extraction and **pypdf** for metadata. Extracts text page-by-page with `## Page N` headings. When `media.extract_images` is enabled, embedded images are extracted and linked as Obsidian wikilinks.

### DOCX (`native_docx`)

Uses **defusedxml** for safe XML parsing. Extracts paragraph text, headings, and basic structure from Word documents. Supports embedded image extraction when `media.extract_images` is enabled.

### PPTX (`native_pptx`)

Uses **python-pptx** to extract text from PowerPoint slides. Each slide becomes a `## Slide N` section. Supports embedded image extraction when `media.extract_images` is enabled.

### XLSX (`native_xlsx`)

Uses **openpyxl** to extract spreadsheet data. Each sheet becomes a section with data rendered as markdown tables. Row count is limited by `xlsx_max_rows_per_sheet` in the configuration.

### CSV (`native_csv`)

Extracts CSV files as markdown tables using Python's built-in `csv` module.

### JSON (`native_json`)

Renders JSON files as fenced code blocks using Python's built-in `json` module.

### YAML (`native_yaml`)

Renders YAML files as fenced code blocks using **pyyaml**.

### Image (`native_image`)

Embeds image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.tiff`) directly as Obsidian wikilinks (`![[filename]]`) and copies the source image to the output directory.

## Optional Backends

### markitdown

A fallback backend that handles formats not covered by native backends (HTML, CSV, etc.). Install with:

```bash
pip install obsidian-import[markitdown]
```

### docling

A high-quality ML-based extraction backend. Best for documents with complex layouts, tables, and mixed content. Install with:

```bash
pip install obsidian-import[docling]
```

## Backend Selection

Configure which backend to use per file type in `config.yaml`:

```yaml
backends:
  pdf: native
  docx: native
  pptx: native
  xlsx: native
  default: native
```

The `default` key specifies the fallback backend for file extensions not explicitly listed.

## Checking Availability

Use the `doctor` command to check which backends are installed and functional:

```bash
obsidian-import doctor
```
