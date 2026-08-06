# Backends

obsidian-import uses a backend system to handle different file formats. Each backend is a module that knows how to extract text from specific file types.

## Available Backends

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `anydoc` (default) | .pdf, .doc/.docx, .ppt/.pptx, .xls/.xlsx, .odt/.ods/.odp, .rtf, .epub, .csv | Core (included) | Best all-round document conversion |
| `native` | .pdf, .docx, .pptx, .xlsx, .csv, .json, .yaml, images | Core (included) | Good for text-heavy documents; the only backend that pulls images out of PDFs |
| `markitdown` | Any | `pip install obsidian-import[markitdown]` | Good fallback for HTML and other formats |
| `docling` | Any | `pip install obsidian-import[docling]` | Best for complex layouts and tables |

## anydoc (default)

[anydoc](https://github.com/firecrawl/anydoc) is a Rust document converter that
ships as a compiled wheel — no model downloads and no extra install step — and
it is the default for every document format. It also covers formats no native
backend reads: legacy Office files (`.doc`, `.xls`, `.ppt`), OpenDocument
(`.odt`, `.ods`, `.odp`), `.rtf`, and `.epub`. Those extensions have no
`backends` key of their own, so they are dispatched by `backends.default`.

Two behaviors differ from the native backends:

- **PDF extraction is text only.** anydoc converts PDF straight to Markdown and
  exposes no image model for it, so `media.extract_images` has no effect on
  PDFs. Set `pdf: native` to keep per-page image extraction. anydoc does no
  OCR, so an image-only (scanned) PDF raises an extraction error instead of
  producing an empty note.
- **`extraction.xlsx_max_rows_per_sheet` does not apply.** The option is logged
  as ignored for `.xlsx` files; set `xlsx: native` to cap rows per sheet.

Embedded images in Word, PowerPoint, Excel, OpenDocument, and EPUB files are
extracted into the note's media folder and embedded at the end of the note.
anydoc's Markdown holds no reference to an embedded image, so the wikilinks
cannot be placed at the position the image occupied in the source.

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

> **Security note:** The docling backend depends on `transformers`, which has a known deserialization vulnerability (PYSEC-2025-217) in the X-CLIP checkpoint flow. Only process documents from trusted sources when using this backend.

## Backend Selection

Configure which backend to use per file type in `config.yaml`:

```yaml
backends:
  pdf: native      # keep pdfplumber page headings and PDF image extraction
  docx: anydoc
  pptx: anydoc
  xlsx: anydoc
  default: anydoc
```

The `default` key specifies the fallback backend for file extensions not explicitly listed.

## Checking Availability

Use the `doctor` command to check which backends are installed and functional:

```bash
obsidian-import doctor
```
