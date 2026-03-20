# Changelog

## [1.0.2](https://github.com/neuralsignal/obsidian-import/compare/v1.0.1...v1.0.2) (2026-03-20)


### Bug Fixes

* eliminate hidden mutation side-effect in _match_image_ref ([#41](https://github.com/neuralsignal/obsidian-import/issues/41)) ([e6dc690](https://github.com/neuralsignal/obsidian-import/commit/e6dc690d45ed3c0ce79e2604095dfcb4b7f6e49b))

## [1.0.1](https://github.com/neuralsignal/obsidian-import/compare/v1.0.0...v1.0.1) (2026-03-17)


### Bug Fixes

* add upper-bound version pins for markitdown and docling optional deps ([ef63111](https://github.com/neuralsignal/obsidian-import/commit/ef6311154ed6cf98ea79025b39268974646baf05)), closes [#30](https://github.com/neuralsignal/obsidian-import/issues/30)
* add upper-bound version pins for markitdown and docling optional… ([4471a29](https://github.com/neuralsignal/obsidian-import/commit/4471a293b4a3534d6e285f131d9bc849b561f489))
* bump Pillow to &gt;=12.1,&lt;13 to address CVE-2026-25990 ([#29](https://github.com/neuralsignal/obsidian-import/issues/29)) ([ee2cc8e](https://github.com/neuralsignal/obsidian-import/commit/ee2cc8e4b69d2fbf261860f29996693f9ecbb2fe))
* move stdlib xml.etree.ElementTree import to TYPE_CHECKING block ([#17](https://github.com/neuralsignal/obsidian-import/issues/17)) ([829cea3](https://github.com/neuralsignal/obsidian-import/commit/829cea3c440ac591aa791d79b4edd5325e1e4b6d))
* regenerate pixi.lock in release-please PR ([c4f6c76](https://github.com/neuralsignal/obsidian-import/commit/c4f6c76f0fd977797bae2ad7d945745418c806c7))
* regenerate pixi.lock in release-please PR ([1ea1ccb](https://github.com/neuralsignal/obsidian-import/commit/1ea1ccb19ab2bf7dcc610c57e6057372ba21167d))

## 1.0.0 (2026-03-12)

- feat: embedded media extraction for PDF, DOCX, PPTX (per-document media folders with wikilinks)
- feat: `config_for_backend()` convenience API for quick single-backend configuration
- feat: `MediaConfig` for image extraction settings (format, max dimension, enable/disable)
- deps: added Pillow>=10.0,<12
- BREAKING: `ImportConfig` requires `media: MediaConfig` field
- BREAKING: backend `extract()` returns `ExtractionResult` (with `.markdown` and `.media_files`) instead of `str`

## 0.2.0 (2026-03-10)

- Native backends for CSV, JSON, YAML, and image files
- Image embedding: generates Obsidian `![[filename]]` wikilinks and copies source images to vault
- Pass-through mode: copy files as-is without extraction (configurable by extension, glob, regex)
- Per-extension backend configuration (`backends.csv`, `backends.json`, `backends.yaml`, `backends.image`)
- `OutputConflictError` exception for destination file conflicts

## 0.1.0 (2026-03-09)

Initial release.

- Native backends: PDF (pdfplumber+pypdf), DOCX (defusedxml), PPTX (python-pptx), XLSX (openpyxl)
- Optional backends: markitdown (fallback), docling (high-quality)
- Config-driven backend selection per file type
- Glob-based file discovery with exclude patterns
- Obsidian-flavored markdown output with YAML frontmatter
- Click CLI: convert, discover, batch, doctor
- YAML configuration with deep-merge defaults
