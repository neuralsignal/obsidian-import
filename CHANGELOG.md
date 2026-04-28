# Changelog

## [Unreleased]

### Security

* bump pypdf >=6.10.2 to address multiple High-severity DoS CVEs (CVE-2026-40260, GHSA-jj6c-8h6c-hppx, GHSA-4pxv-j86v-mhcw, GHSA-7gw9-cf7v-778f, GHSA-x284-j5p8-9c5p) ([#126](https://github.com/neuralsignal/obsidian-import/issues/126))

## [1.0.4](https://github.com/neuralsignal/obsidian-import/compare/v1.0.3...v1.0.4) (2026-04-13)


### Bug Fixes

* add extract_images parameter to config_for_backend ([#85](https://github.com/neuralsignal/obsidian-import/issues/85)) ([fbc9def](https://github.com/neuralsignal/obsidian-import/commit/fbc9def4758157115d5c4ddfde80b41db7ff5834))
* bump pypdf &gt;=6.9.2 to address CVE-2026-33699 infinite loop DoS ([#94](https://github.com/neuralsignal/obsidian-import/issues/94)) ([67e2286](https://github.com/neuralsignal/obsidian-import/commit/67e2286e571153ef898dcf06bc2396c8416e3e58))
* correct exception type in native_pdf.py and add missing test ([cdcd0d3](https://github.com/neuralsignal/obsidian-import/commit/cdcd0d3fa3fda5d70e95340ee2fe08757f28b8a3))
* decompose _extract_page_images to reduce cyclomatic complexity ([#102](https://github.com/neuralsignal/obsidian-import/issues/102)) ([a4547bd](https://github.com/neuralsignal/obsidian-import/commit/a4547bd6f44fd7c5e2135fd707b06cbf375c25ec))
* extract shared attempt_save_image helper to eliminate DRY violation ([#99](https://github.com/neuralsignal/obsidian-import/issues/99)) ([964354d](https://github.com/neuralsignal/obsidian-import/commit/964354db8e21be4c6f4fe6cde8ef5637eec98037))
* replace hand-rolled YAML escaping with PyYAML serializer ([#75](https://github.com/neuralsignal/obsidian-import/issues/75)) ([37535e0](https://github.com/neuralsignal/obsidian-import/commit/37535e0a2a6d94ee7dc5b5c3aeb52b7c5576b369))
* resolve merge conflict — reapply exception narrowing to refactored code ([f8d8165](https://github.com/neuralsignal/obsidian-import/commit/f8d8165329e0a382b192118abde93fc4dbe9e976))
* validate image bytes size and format before Pillow processing ([#74](https://github.com/neuralsignal/obsidian-import/issues/74)) ([ba5be45](https://github.com/neuralsignal/obsidian-import/commit/ba5be45887f7e561488da84bd87082d09e34de64))

## [1.0.3](https://github.com/neuralsignal/obsidian-import/compare/v1.0.2...v1.0.3) (2026-03-27)


### Bug Fixes

* address security and code quality issues ([#14](https://github.com/neuralsignal/obsidian-import/issues/14), [#37](https://github.com/neuralsignal/obsidian-import/issues/37), [#59](https://github.com/neuralsignal/obsidian-import/issues/59), [#63](https://github.com/neuralsignal/obsidian-import/issues/63), [#64](https://github.com/neuralsignal/obsidian-import/issues/64)) ([4845e67](https://github.com/neuralsignal/obsidian-import/commit/4845e67d5b9a44b6bd50220ce4396e206385ffd1))
* address security and code quality issues ([#14](https://github.com/neuralsignal/obsidian-import/issues/14), [#37](https://github.com/neuralsignal/obsidian-import/issues/37), [#59](https://github.com/neuralsignal/obsidian-import/issues/59), [#63](https://github.com/neuralsignal/obsidian-import/issues/63), [#64](https://github.com/neuralsignal/obsidian-import/issues/64)) ([9c9fb18](https://github.com/neuralsignal/obsidian-import/commit/9c9fb18446d193b342bb5466938e15147e69019c))
* bump pypdf &gt;=6.9.1 to address CVE-2026-33123 DoS vulnerability ([#55](https://github.com/neuralsignal/obsidian-import/issues/55)) ([b9e2a8c](https://github.com/neuralsignal/obsidian-import/commit/b9e2a8c78d416d7fe98388fec6f3d3cdaf789ffe))
* strengthen type annotations and simplify docling availability check ([00f951b](https://github.com/neuralsignal/obsidian-import/commit/00f951b8f336b6f97e6d0089da3be2e807966056))
* strengthen type annotations and simplify docling check ([86dfa39](https://github.com/neuralsignal/obsidian-import/commit/86dfa3980764d4fa19fcf1b620a7ad653dcd2c60))


### Documentation

* sync documentation with codebase ([f797c3d](https://github.com/neuralsignal/obsidian-import/commit/f797c3d65adba67ab01e36ebdc953765c57e6f0c))

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
