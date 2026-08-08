# Backends

obsidian-import uses a backend system to handle different file formats. Each backend is a module that knows how to extract text from specific file types.

## Available Backends

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `anydoc` (default) | .doc/.docx, .ppt/.pptx, .xls/.xlsx, .odt/.ods/.odp, .rtf, .epub, .csv, .pdf (opt-in) | Core (included) | Best all-round document conversion |
| `native` | .pdf, .docx, .pptx, .xlsx, .csv, .json, .yaml, images | Core (included) | Good for text-heavy documents; the only backend that pulls images out of PDFs |
| `markitdown` | Any | `pip install obsidian-import[markitdown]` | Good fallback for HTML and other formats |
| `docling` | Any | `pip install obsidian-import[docling]` | Best for complex layouts and tables |

## anydoc (default)

[anydoc](https://github.com/firecrawl/anydoc) is a Rust document converter that
ships as a compiled wheel — no model downloads and no extra install step — and
it is the default for every document format except PDF (see below). It also
covers formats no native backend reads: legacy Office files (`.doc`, `.xls`,
`.ppt`), OpenDocument (`.odt`, `.ods`, `.odp`), `.rtf`, and `.epub`. Those
extensions have no `backends` key of their own, so they are dispatched by
`backends.default`.

### Embedded images

Images in Word, PowerPoint, Excel, OpenDocument, and EPUB files are extracted
into the note's media folder and embedded as `![[note/asset_imgN.png]]` at the
position they occupied in the source document, including images inside table
cells, list items, and block quotes (those are embedded directly after the
table, list, or quote that holds them).

anydoc renders an embedded image as its alt text — or as nothing when it has
none — and has no option to emit an image reference, so there is nothing in its
Markdown to rewrite into a wikilink. The embeds are instead spliced in by
matching anydoc's Markdown blocks against the document model that carries the
images, block by block. If the two ever stop lining up, placement stops there
and the remaining images are embedded at the end of the note rather than at a
guessed position.

Matching allows for the three ways anydoc's Markdown carries text its document
model does not: list markers rendered into the item text (`1. `, `- c. `,
`- iii. `), the blank line it puts before nested list items, and blocks with no
model block of their own, such as the `<a id="..."></a>` it emits for a
referenced footnote target. Up to two such unclaimed blocks in a row are
skipped before alignment gives up.

### PDF is not on anydoc by default

anydoc parses PDF straight to Markdown and exposes no document model for it,
which costs three things the native PDF backend provides:

- embedded page images (`media.extract_images` has no effect on anydoc PDFs)
- the `## Page N` headings
- the `page_count` frontmatter field, which is derived from those headings

anydoc also does no OCR, so an image-only (scanned) PDF raises an extraction
error instead of producing an empty note. The bundled default is therefore
`pdf: native`; set `pdf: anydoc` to convert PDFs with anydoc anyway.

### xlsx row cap

`extraction.xlsx_max_rows_per_sheet` does not apply to anydoc — it is reported
as an ignored option for `.xlsx` files. Set `xlsx: native` to cap rows per
sheet.

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
