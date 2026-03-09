# Backends

obsidian-import uses a backend system to handle different file formats. Each backend is a module that knows how to extract text from specific file types.

## Available Backends

| Backend | Extensions | Dependencies | Quality |
|---------|-----------|--------------|---------|
| `native` | .pdf, .docx, .pptx, .xlsx | Core (included) | Good for text-heavy documents |
| `markitdown` | Any | `pip install obsidian-import[markitdown]` | Good fallback for HTML, CSV, etc. |
| `docling` | Any | `pip install obsidian-import[docling]` | Best for complex layouts and tables |

## Native Backends

The native backends are included with the base install and require no additional dependencies.

### PDF (`native_pdf`)

Uses **pdfplumber** for text extraction and **pypdf** for metadata. Extracts text page-by-page with `## Page N` headings.

### DOCX (`native_docx`)

Uses **defusedxml** for safe XML parsing. Extracts paragraph text, headings, and basic structure from Word documents.

### PPTX (`native_pptx`)

Uses **python-pptx** to extract text from PowerPoint slides. Each slide becomes a `## Slide N` section.

### XLSX (`native_xlsx`)

Uses **openpyxl** to extract spreadsheet data. Each sheet becomes a section with data rendered as markdown tables. Row count is limited by `xlsx_max_rows_per_sheet` in the configuration.

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
