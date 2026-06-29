# Changelog

## [1.2.1](https://github.com/neuralsignal/obsidian-import/compare/v1.2.0...v1.2.1) (2026-06-16)


### Bug Fixes

* add missing isolation arg to TestDecompressionBombGuard extract() calls ([592a115](https://github.com/neuralsignal/obsidian-import/commit/592a115804ca2eb5c3bf308330b5822aa0e33383))
* add missing isolation arg to TestDecompressionBombGuard tests ([b830426](https://github.com/neuralsignal/obsidian-import/commit/b8304269f7ca9f1fae1e7ae38a1072f0bd968191))
* bump pypdf lower bound to &gt;=6.12.0 for CVE-2026-48155/48156 ([#232](https://github.com/neuralsignal/obsidian-import/issues/232)) ([c3189e7](https://github.com/neuralsignal/obsidian-import/commit/c3189e7b5daf91af5eac5ab535730242bb683a4c))
* pass missing isolation argument in TestDecompressionBombGuard tests ([#228](https://github.com/neuralsignal/obsidian-import/issues/228)) ([1ed867b](https://github.com/neuralsignal/obsidian-import/commit/1ed867b3656d6878ae5687647fd4e850ebc49a4d))

## [1.2.0](https://github.com/neuralsignal/obsidian-import/compare/v1.1.2...v1.2.0) (2026-06-11)


### Features

* extraction guards — size limit at entry, process isolation, public config API ([1f24d66](https://github.com/neuralsignal/obsidian-import/commit/1f24d66c953a1945f4cb27bf99c7f704cc6e0dbd))
* extraction guards — size limit at entry, process isolation, public config API (1.2.0) ([ecce207](https://github.com/neuralsignal/obsidian-import/commit/ecce2078fef58c4a5becd237f3bd7b1ef5f7a858))


### Bug Fixes

* replace assert isinstance() with explicit runtime type checks in registry.py ([#206](https://github.com/neuralsignal/obsidian-import/issues/206)) ([2ee0ee8](https://github.com/neuralsignal/obsidian-import/commit/2ee0ee81c74058c3900f4cf8153ed7790339bee7))
* replace assert isinstance() with explicit runtime type guards in registry.py ([13e27aa](https://github.com/neuralsignal/obsidian-import/commit/13e27aa648aefcb2171cfb495aa669ea163f66f2))
* replace assert isinstance() with explicit runtime type guards in registry.py ([#206](https://github.com/neuralsignal/obsidian-import/issues/206)) ([c1d2e85](https://github.com/neuralsignal/obsidian-import/commit/c1d2e8573774dcf5805773d4dc58255231da74b0))

## [1.2.0](https://github.com/neuralsignal/obsidian-import/compare/v1.1.2...v1.2.0) (2026-06-11)


### Features

* enforce max_file_size_mb at the extract_file/extract_text entry points — oversized files raise ExtractionError instantly before backend dispatch, instead of running into the extraction timeout when callers bypass discover_files
* add config_from_overrides() public API: build an ImportConfig from a partial overrides dict deep-merged onto the bundled defaults (the supported path for library consumers such as m365-extract)
* add extraction.isolation config ("thread" | "process", default "thread"): process mode runs each extraction in a separate spawned process that is killed on timeout — true cancellation and memory isolation for long-running daemons
* include the source file size in ExtractionTimeoutError messages alongside label, timeout, and path


### Bug Fixes

* process isolation enforces the deadline on every parent-side wait: receiving the payload is bounded by a watchdog that kills a stalled child, and the worker is reaped (bounded join, then kill) on success, error, and interrupt paths — a child kept alive by a leftover non-daemon thread can no longer block the caller indefinitely
* worker exceptions that cannot survive the pickle round-trip are reported as ExtractionError with the original message, instead of escaping as a raw TypeError that aborted CLI batch runs; payloads that still fail to unpickle parent-side are wrapped defensively
* the extraction worker process is no longer daemonic, so backends may spawn their own worker processes (e.g. docling's torch DataLoader)
* stat() failures in the entry-point size guard (file vanished between discovery and extraction) raise ExtractionError, keeping the ObsidianImportError contract so CLI batch runs print FAIL and continue
* the "process died without a result" error now explains the `if __name__ == "__main__":` guard required for script consumers under spawn

## [1.1.2](https://github.com/neuralsignal/obsidian-import/compare/v1.1.1...v1.1.2) (2026-05-20)


### Bug Fixes

* call _cleanup_temp_source in copy_media_files to remove temp dirs ([6682e90](https://github.com/neuralsignal/obsidian-import/commit/6682e904eb9b28c1b8c5e9eb7db6d8fedcb13da7))
* clean up temp dirs created by save_media_to_temp after media copy ([#176](https://github.com/neuralsignal/obsidian-import/issues/176)) ([026e76c](https://github.com/neuralsignal/obsidian-import/commit/026e76cd50d40d564e48293965ee2155897da107))
* sanitize PDF form field values against markdown injection ([#171](https://github.com/neuralsignal/obsidian-import/issues/171)) ([9b22822](https://github.com/neuralsignal/obsidian-import/commit/9b228228261aa993c260397e912f66f2841d916e))
* serialize Image.MAX_IMAGE_PIXELS mutation with threading.Lock ([#194](https://github.com/neuralsignal/obsidian-import/issues/194)) ([3b389c6](https://github.com/neuralsignal/obsidian-import/commit/3b389c668159a6e95603c67d463073196e99606a))


### Documentation

* add cleanup side-effect to copy_media_files docstring and CHANGELOG entry ([152709b](https://github.com/neuralsignal/obsidian-import/commit/152709b7648beb57e408c0d497db2b10dea09c1d))

## [1.1.1](https://github.com/neuralsignal/obsidian-import/compare/v1.1.0...v1.1.1) (2026-05-11)


### Bug Fixes

* scope Image.MAX_IMAGE_PIXELS mutation to _process_image_bytes lifetime ([#163](https://github.com/neuralsignal/obsidian-import/issues/163)) ([037974c](https://github.com/neuralsignal/obsidian-import/commit/037974c302e6dc9e7d4421455c5c6a477d4c482c))

## [1.1.0](https://github.com/neuralsignal/obsidian-import/compare/v1.0.4...v1.1.0) (2026-04-28)


### Features

* add .html as a first-class backend config key ([4602f1b](https://github.com/neuralsignal/obsidian-import/commit/4602f1b3587140ad959e66cabce4c3819f47165a))
* add .html as a first-class backend config key ([e64b82f](https://github.com/neuralsignal/obsidian-import/commit/e64b82fadf8b16d38d4df3229565034b8ddae1fb))


### Bug Fixes

* add decompression bomb guard with configurable image_max_pixels ([#113](https://github.com/neuralsignal/obsidian-import/issues/113)) ([bb840be](https://github.com/neuralsignal/obsidian-import/commit/bb840bedc4cfcc6a7f9d8c3a9060ca86be05a028))
* bump Pillow lower bound to &gt;=12.2 for CVE-2026-40192 ([#127](https://github.com/neuralsignal/obsidian-import/issues/127)) ([35f9167](https://github.com/neuralsignal/obsidian-import/commit/35f9167534c39d33f708efb27f96ae10f05b741a))
* bump pypdf lower bound to 6.10.2 for DoS CVE fixes ([e49878e](https://github.com/neuralsignal/obsidian-import/commit/e49878eb49e8ad0d5fb3752ff002509a48dc4cbf)), closes [#126](https://github.com/neuralsignal/obsidian-import/issues/126)
* correct misleading native extensions list and add .htm dispatch test ([afa2521](https://github.com/neuralsignal/obsidian-import/commit/afa2521197814126ce991fa1c77ba3c0d81d5391))
* scope try/except per XObject iteration in _extract_page_images ([#120](https://github.com/neuralsignal/obsidian-import/issues/120)) ([2d8a820](https://github.com/neuralsignal/obsidian-import/commit/2d8a8204f8f85d08209d02a3d120c96859a33b0e))

## [Unreleased]

### Bug Fixes

* clean up temp dirs created by save_media_to_temp after media copy ([#176](https://github.com/neuralsignal/obsidian-import/issues/176))

### Security

* serialize Image.MAX_IMAGE_PIXELS mutation with threading.Lock for thread safety ([#194](https://github.com/neuralsignal/obsidian-import/issues/194))
* track PYSEC-2025-217 in transformers (transitive via docling): X-CLIP checkpoint deserialization RCE, no fix available as of 2026-06-29 ([#251](https://github.com/neuralsignal/obsidian-import/issues/251))
* bump pip floor to >=26.1 for CVE-2026-6357 ([#183](https://github.com/neuralsignal/obsidian-import/issues/183))
* bump pytest floor to >=9.0.3 for CVE-2025-71176 ([#184](https://github.com/neuralsignal/obsidian-import/issues/184))
* pin cryptography >=46.0.7 for CVE-2026-39892 ([#181](https://github.com/neuralsignal/obsidian-import/issues/181))
* drop direct twisted dep to remove CVE-2026-42304 exposure ([#185](https://github.com/neuralsignal/obsidian-import/issues/185))
* track CVE-2026-3219 in pip (build-only dep, no fix available yet) ([#182](https://github.com/neuralsignal/obsidian-import/issues/182))
* track PYSEC-2026-139 in torch (transitive via docling, deserialization vuln, no fix available) ([#200](https://github.com/neuralsignal/obsidian-import/issues/200))
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
