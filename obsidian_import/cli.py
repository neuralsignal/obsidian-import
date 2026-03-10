"""CLI for obsidian-import."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import click

from obsidian_import import discover_files, extract_file
from obsidian_import.config import default_config, load_config
from obsidian_import.exceptions import ObsidianImportError
from obsidian_import.media import copy_media_files
from obsidian_import.output import format_output, output_path_for
from obsidian_import.passthrough import copy_passthrough, matches_passthrough
from obsidian_import.registry import check_backend_available

log = logging.getLogger(__name__)


def _resolve_config(config_path: str | None) -> object:
    """Load config from path or use defaults."""
    if config_path is not None:
        return load_config(Path(config_path))
    return default_config()


@click.group()
def main() -> None:
    """Extract files into Obsidian-flavored Markdown."""


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "output_path", type=click.Path(), help="Output file path (default: stdout)")
@click.option("--config", "config_path", type=click.Path(exists=True), help="Config YAML file")
def convert(path: str, output_path: str | None, config_path: str | None) -> None:
    """Extract a single file to Obsidian markdown."""
    config = _resolve_config(config_path)
    source = Path(path)

    doc = extract_file(source, config)
    formatted = format_output(doc, config.output)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(formatted, encoding="utf-8")
        _copy_associated_files(doc.associated_files, out.parent)
        if doc.media_files:
            copy_media_files(doc.media_files, out.parent, config.media.media_subfolder)
        click.echo(f"Extracted: {source} -> {out}")
    else:
        if doc.media_files:
            log.warning(
                "Media files extracted but no output directory specified; "
                "%d media files cannot be copied to stdout mode",
                len(doc.media_files),
            )
        click.echo(formatted)


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True), help="Config YAML file")
def discover(config_path: str) -> None:
    """List files matching configured input directories and extensions."""
    config = load_config(Path(config_path))

    count = 0
    for f in discover_files(config):
        size_kb = f.size_bytes / 1024
        click.echo(f"  {f.extension:6s}  {size_kb:8.1f} KB  {f.path}")
        count += 1

    click.echo(f"\n{count} files found.")


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True), help="Config YAML file")
@click.option("--output-dir", type=click.Path(), help="Override output directory from config")
def batch(config_path: str, output_dir: str | None) -> None:
    """Extract all discovered files to Obsidian markdown."""
    config = load_config(Path(config_path))

    target_dir = output_dir if output_dir else config.output.directory
    out_dir = Path(target_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0
    passthrough_count = 0

    for discovered in discover_files(config):
        if matches_passthrough(discovered.path, config.passthrough):
            try:
                dest = copy_passthrough(discovered.path, out_dir)
                click.echo(f"  COPY  {discovered.path} -> {dest}")
                passthrough_count += 1
            except ObsidianImportError as exc:
                click.echo(f"  FAIL  {discovered.path}: {exc}", err=True)
                failed += 1
            continue

        try:
            doc = extract_file(discovered.path, config)
            formatted = format_output(doc, config.output)
            out_path = output_path_for(discovered.path, target_dir)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(formatted, encoding="utf-8")
            _copy_associated_files(doc.associated_files, out_path.parent)
            if doc.media_files:
                copy_media_files(doc.media_files, out_path.parent, config.media.media_subfolder)
            click.echo(f"  OK  {discovered.path} -> {out_path}")
            success += 1
        except ObsidianImportError as exc:
            click.echo(f"  FAIL  {discovered.path}: {exc}", err=True)
            failed += 1

    click.echo(f"\nDone: {success} extracted, {passthrough_count} copied, {failed} failed.")


@main.command()
def doctor() -> None:
    """Check backend availability."""
    checks = [
        ("native (pdf)", "native", ".pdf"),
        ("native (docx)", "native", ".docx"),
        ("native (pptx)", "native", ".pptx"),
        ("native (xlsx)", "native", ".xlsx"),
        ("native (csv)", "native", ".csv"),
        ("native (json)", "native", ".json"),
        ("native (yaml)", "native", ".yaml"),
        ("native (image)", "native", ".png"),
        ("markitdown", "markitdown", ".pdf"),
        ("docling", "docling", ".pdf"),
    ]

    all_ok = True
    for label, backend, ext in checks:
        available, message = check_backend_available(backend, ext)
        status = "OK" if available else "MISSING"
        click.echo(f"  {label:20s}  [{status}]  {message}")
        if not available and backend == "native":
            all_ok = False

    tools = {
        "pdfplumber": "PDF text extraction",
        "defusedxml": "DOCX XML parsing (secure)",
        "pptx": "PPTX extraction (python-pptx)",
        "openpyxl": "XLSX extraction",
    }

    click.echo("\nPython packages:")
    for pkg, purpose in tools.items():
        try:
            __import__(pkg)
            path = shutil.which(pkg) or "(importable)"
            click.echo(f"  {pkg:20s}  {path}")
        except ImportError:
            click.echo(f"  {pkg:20s}  MISSING — {purpose}")
            all_ok = False

    if all_ok:
        click.echo("\nAll required backends available.")
    else:
        click.echo("\nSome required backends are missing.")
        raise SystemExit(1)


def _copy_associated_files(files: tuple[Path, ...], dest_dir: Path) -> None:
    """Copy associated files (e.g. images) to the output directory.

    Delegates to copy_passthrough for each file, raising OutputConflictError
    if a destination file already exists.
    """
    for src in files:
        copy_passthrough(src, dest_dir)
