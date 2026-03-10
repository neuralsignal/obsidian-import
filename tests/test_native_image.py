"""Tests for native image backend."""

from obsidian_import.backends.native_image import extract, is_image_extension


class TestNativeImageExtract:
    def test_produces_wikilink_embed(self, tmp_path):
        img = tmp_path / "diagram.png"
        img.write_bytes(b"\x89PNG\r\n")
        result = extract(img, timeout_seconds=10)
        assert result == "![[diagram.png]]"

    def test_preserves_original_filename(self, tmp_path):
        img = tmp_path / "My Photo (1).jpg"
        img.write_bytes(b"\xff\xd8\xff")
        result = extract(img, timeout_seconds=10)
        assert result == "![[My Photo (1).jpg]]"

    def test_svg_file(self, tmp_path):
        svg = tmp_path / "icon.svg"
        svg.write_text("<svg></svg>")
        result = extract(svg, timeout_seconds=10)
        assert result == "![[icon.svg]]"


class TestIsImageExtension:
    def test_common_image_formats(self):
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff"]:
            assert is_image_extension(ext) is True

    def test_non_image_formats(self):
        for ext in [".pdf", ".docx", ".csv", ".md", ".txt"]:
            assert is_image_extension(ext) is False

    def test_case_insensitive(self):
        assert is_image_extension(".PNG") is True
        assert is_image_extension(".Jpg") is True
