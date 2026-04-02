"""Tests for docling image extraction and wikilink replacement."""

from pathlib import Path
from unittest.mock import MagicMock

from conftest import make_pil_image
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.docling import (
    _extract_docling_images,
    _replace_image_refs_with_wikilinks,
)
from obsidian_import.config import MediaConfig
from obsidian_import.extraction_result import MediaFile

_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


class TestExtractDoclingImages:
    def test_empty_pictures_list(self) -> None:
        doc = MagicMock()
        doc.pictures = []
        result = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert result == []

    def test_no_pictures_attribute(self) -> None:
        doc = MagicMock()
        doc.pictures = None
        result = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert result == []

    def test_successful_extraction(self) -> None:
        pil_img = make_pil_image(20, 20, "green")
        pic = MagicMock()
        pic.get_image.return_value = pil_img

        doc = MagicMock()
        doc.pictures = [pic]

        result = _extract_docling_images(doc, Path("report.pdf"), _TEST_MEDIA_CONFIG)
        assert len(result) == 1
        assert result[0].media_type == "image"
        assert "fig" in result[0].filename
        assert result[0].source_path.exists()


class TestReplaceImageRefsWithWikilinks:
    def test_replaces_single_image_ref(self) -> None:
        media_files = [MediaFile(source_path=Path("/tmp/img.png"), filename="fig_img1.png", media_type="image")]
        text = "Before ![alt](path/to/img.png) after"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "report")
        assert "![[report/fig_img1.png]]" in result
        assert "Before" in result
        assert "after" in result

    def test_replaces_multiple_image_refs(self) -> None:
        media_files = [
            MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image"),
            MediaFile(source_path=Path("/tmp/b.png"), filename="b.png", media_type="image"),
        ]
        text = "![first](x.png) text ![second](y.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "doc")
        assert "![[doc/a.png]]" in result
        assert "![[doc/b.png]]" in result

    def test_no_media_files_preserves_original(self) -> None:
        text = "![alt](path.png)"
        result = _replace_image_refs_with_wikilinks(text, [], "doc")
        assert result == text

    def test_more_refs_than_files(self) -> None:
        media_files = [
            MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image"),
        ]
        text = "![img1](x.png) ![img2](y.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), "doc")
        assert "![[doc/a.png]]" in result
        assert "![img2](y.png)" in result


class TestReplaceImageRefsProperties:
    @given(
        doc_stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
            lambda s: s + ".png"
        ),
    )
    @settings(max_examples=50)
    def test_replacement_contains_doc_stem(self, doc_stem: str, filename: str) -> None:
        media_files = [MediaFile(source_path=Path("/tmp/x.png"), filename=filename, media_type="image")]
        text = "![alt](ref.png)"
        result = _replace_image_refs_with_wikilinks(text, list(media_files), doc_stem)
        assert f"![[{doc_stem}/{filename}]]" in result

    @given(
        n_files=st.integers(min_value=0, max_value=5),
        n_refs=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_replacement_count_matches_min_of_files_and_refs(self, n_files: int, n_refs: int) -> None:
        media_files = [
            MediaFile(source_path=Path(f"/tmp/{i}.png"), filename=f"img{i}.png", media_type="image")
            for i in range(n_files)
        ]
        refs = " ".join(f"![alt{i}](ref{i}.png)" for i in range(n_refs))
        result = _replace_image_refs_with_wikilinks(refs, list(media_files), "doc")
        expected_replacements = min(n_files, n_refs)
        assert result.count("![[doc/") == expected_replacements
