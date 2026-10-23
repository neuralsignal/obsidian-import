"""Tests for docling image extraction and wikilink replacement."""

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import make_pil_image
from hypothesis import given, settings
from hypothesis import strategies as st

from obsidian_import.backends.docling import (
    _extract_docling_images,
    _replace_image_refs_with_wikilinks,
    extract,
)
from obsidian_import.config import MediaConfig
from obsidian_import.extraction_result import MediaFile


class TestDoclingSecurityWarning:
    def test_extract_emits_pysec_2026_139_warning(self) -> None:
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "extracted text"
        mock_doc.pictures = []
        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with (
            patch("obsidian_import.backends.docling.importlib.util.find_spec", return_value=True),
            patch("obsidian_import.backends.docling._build_converter", return_value=mock_converter),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            extract(Path("test.pdf"), 60, "thread", _TEST_MEDIA_CONFIG)

        pysec_warnings = [w for w in caught if "PYSEC-2026-139" in str(w.message)]
        assert len(pysec_warnings) == 1


_TEST_MEDIA_CONFIG = MediaConfig(
    extract_images=True,
    image_format="png",
    image_max_dimension=0,
    image_max_bytes=50_000_000,
    image_max_pixels=50_000_000,
    image_allowed_formats=frozenset({"PNG", "JPEG", "GIF", "BMP", "TIFF", "WEBP"}),
)


class TestExtractDoclingImages:
    def test_empty_pictures_list(self) -> None:
        doc = MagicMock()
        doc.pictures = []
        media_files, ref_to_media = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert media_files == []
        assert ref_to_media == {}

    def test_no_pictures_attribute(self) -> None:
        doc = MagicMock()
        doc.pictures = None
        media_files, ref_to_media = _extract_docling_images(doc, Path("test.pdf"), _TEST_MEDIA_CONFIG)
        assert media_files == []
        assert ref_to_media == {}

    def test_successful_extraction(self) -> None:
        pil_img = make_pil_image(20, 20, "green")
        pic = MagicMock()
        pic.get_image.return_value = pil_img
        pic.self_ref = "#/pictures/0"

        doc = MagicMock()
        doc.pictures = [pic]

        media_files, ref_to_media = _extract_docling_images(doc, Path("report.pdf"), _TEST_MEDIA_CONFIG)
        assert len(media_files) == 1
        assert media_files[0].media_type == "image"
        assert "fig" in media_files[0].filename
        assert media_files[0].source_path.exists()
        assert "#/pictures/0" in ref_to_media
        assert ref_to_media["#/pictures/0"] is media_files[0]


class TestReplaceImageRefsWithWikilinks:
    def test_replaces_single_image_ref(self) -> None:
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="fig_img1.png", media_type="image")
        ref_to_media = {"path/to/img.png": mf}
        text = "Before ![alt](path/to/img.png) after"
        result = _replace_image_refs_with_wikilinks(text, ref_to_media, "report")
        assert "![[report/fig_img1.png]]" in result
        assert "Before" in result
        assert "after" in result

    def test_replaces_multiple_image_refs(self) -> None:
        mf_a = MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image")
        mf_b = MediaFile(source_path=Path("/tmp/b.png"), filename="b.png", media_type="image")
        ref_to_media = {"x.png": mf_a, "y.png": mf_b}
        text = "![first](x.png) text ![second](y.png)"
        result = _replace_image_refs_with_wikilinks(text, ref_to_media, "doc")
        assert "![[doc/a.png]]" in result
        assert "![[doc/b.png]]" in result

    def test_no_media_files_preserves_original(self) -> None:
        text = "![alt](path.png)"
        result = _replace_image_refs_with_wikilinks(text, {}, "doc")
        assert result == text

    def test_unmatched_ref_preserves_original(self) -> None:
        mf = MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image")
        ref_to_media = {"x.png": mf}
        text = "![img1](x.png) ![img2](y.png)"
        result = _replace_image_refs_with_wikilinks(text, ref_to_media, "doc")
        assert "![[doc/a.png]]" in result
        assert "![img2](y.png)" in result

    def test_out_of_order_refs_matched_correctly(self) -> None:
        """URL-based lookup resolves correctly regardless of reference order."""
        mf_a = MediaFile(source_path=Path("/tmp/a.png"), filename="a.png", media_type="image")
        mf_b = MediaFile(source_path=Path("/tmp/b.png"), filename="b.png", media_type="image")
        ref_to_media = {"#/pictures/0": mf_a, "#/pictures/1": mf_b}
        text = "![second](#/pictures/1) then ![first](#/pictures/0)"
        result = _replace_image_refs_with_wikilinks(text, ref_to_media, "doc")
        assert result == "![[doc/b.png]] then ![[doc/a.png]]"


class TestReplaceImageRefsProperties:
    @given(
        doc_stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
        filename=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))).map(
            lambda s: s + ".png"
        ),
    )
    @settings(max_examples=50)
    def test_replacement_contains_doc_stem(self, doc_stem: str, filename: str) -> None:
        mf = MediaFile(source_path=Path("/tmp/x.png"), filename=filename, media_type="image")
        ref_to_media = {"ref.png": mf}
        text = "![alt](ref.png)"
        result = _replace_image_refs_with_wikilinks(text, ref_to_media, doc_stem)
        assert f"![[{doc_stem}/{filename}]]" in result

    @given(
        n_matched=st.integers(min_value=0, max_value=5),
        n_extra_refs=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=50)
    def test_replacement_count_matches_mapped_refs(self, n_matched: int, n_extra_refs: int) -> None:
        ref_to_media = {
            f"ref{i}.png": MediaFile(source_path=Path(f"/tmp/{i}.png"), filename=f"img{i}.png", media_type="image")
            for i in range(n_matched)
        }
        n_refs = n_matched + n_extra_refs
        refs = " ".join(f"![alt{i}](ref{i}.png)" for i in range(n_refs))
        result = _replace_image_refs_with_wikilinks(refs, ref_to_media, "doc")
        assert result.count("![[doc/") == n_matched
