"""Shared test helpers and fixtures."""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

from obsidian_import.config import MediaConfig


def make_test_docx(path: Path, text: str) -> None:
    """Create a minimal .docx file with given text."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("word/document.xml", xml)


def make_config_yaml(tmp_path: Path, input_dir: Path | None) -> Path:
    """Create a config YAML file. Uses input_dir or tmp_path as default."""
    d = input_dir or tmp_path
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
input:
  directories:
    - path: {d}
      extensions: [".docx"]
      exclude: []
output:
  directory: {tmp_path / "out"}
  frontmatter: true
  metadata_fields: [title]
backends:
  pdf: native
  docx: native
  pptx: native
  xlsx: native
  default: native
extraction:
  timeout_seconds: 120
  max_file_size_mb: 100
  xlsx_max_rows_per_sheet: 500
""")
    return config_file


def make_png_bytes(width: int, height: int, mode: str = "RGB") -> bytes:
    """Create minimal PNG image bytes."""
    color: str | tuple[int, ...] = (255, 0, 0, 128) if mode == "RGBA" else (128,) if mode == "L" else "red"
    img = Image.new(mode, (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_test_media_config() -> MediaConfig:
    """Return a standard test MediaConfig."""
    return MediaConfig(extract_images=True, image_format="png", image_max_dimension=0)


def make_pil_image(width: int, height: int, color: str) -> Image.Image:
    """Create a PIL image for testing."""
    return Image.new("RGB", (width, height), color=color)


def pil_to_bytes(img: Image.Image) -> bytes:
    """Convert PIL image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def mock_pptx_presentation(slides_data: list[dict]) -> MagicMock:
    """Build a mock Presentation with the given slide data."""
    prs = MagicMock()
    prs.slide_width = 9144000
    prs.slide_height = 6858000

    mock_slides = []
    for data in slides_data:
        slide = MagicMock()
        title_shape = MagicMock()
        title_shape.text = data.get("title", "")

        if data.get("title"):
            slide.shapes.title = title_shape
        else:
            slide.shapes.title = None

        shapes = []
        for text in data.get("body_texts", []):
            shape = MagicMock()
            shape.has_text_frame = True
            shape.has_table = False
            shape.shape_type = 1
            para = MagicMock()
            para.text = text
            para.level = 0
            shape.text_frame.paragraphs = [para]
            shapes.append(shape)

        if data.get("title"):
            shapes.insert(0, title_shape)
            title_shape.has_text_frame = True
            title_shape.has_table = False
            title_shape.shape_type = 1

        slide.shapes.__iter__ = MagicMock(return_value=iter(shapes))
        slide.shapes.__len__ = MagicMock(return_value=len(shapes))
        slide.has_notes_slide = False
        mock_slides.append(slide)

    prs.slides = mock_slides
    return prs
