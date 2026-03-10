"""Image handling: copy to vault and generate Obsidian wikilink embed.

Supports PNG, JPG, JPEG, GIF, SVG, WEBP. Images are referenced with
Obsidian's ![[filename]] syntax rather than extracted as text.
"""

from __future__ import annotations

from pathlib import Path

_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".bmp",
        ".tiff",
    }
)


def extract(path: Path, timeout_seconds: int, **kwargs: object) -> str:
    """Generate an Obsidian-flavored markdown embed for an image file.

    Returns markdown with a wikilink embed (![[filename]]).
    The image file itself must be copied to the vault separately.
    """
    return f"![[{path.name}]]"


def is_image_extension(extension: str) -> bool:
    """Check if an extension is a recognized image format."""
    return extension.lower() in _IMAGE_EXTENSIONS
