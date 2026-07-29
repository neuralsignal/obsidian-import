"""Tests for ExtractionResult and MediaFile dict serialization."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.extraction_result import ExtractionResult, MediaFile


class TestMediaFileDictRoundTrip:
    def test_round_trip(self) -> None:
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="img.png", media_type="image/png")
        assert MediaFile.from_dict(mf.to_dict()) == mf

    def test_to_dict_values(self) -> None:
        mf = MediaFile(source_path=Path("/a/b.jpg"), filename="b.jpg", media_type="image/jpeg")
        d = mf.to_dict()
        assert d == {"source_path": "/a/b.jpg", "filename": "b.jpg", "media_type": "image/jpeg"}

    @given(
        filename=st.text(min_size=1, max_size=50).filter(lambda s: "\x00" not in s),
        media_type=st.sampled_from(["image/png", "image/jpeg", "image/gif", "image/webp"]),
    )
    def test_round_trip_property(self, filename: str, media_type: str) -> None:
        mf = MediaFile(source_path=Path(f"/tmp/{filename}"), filename=filename, media_type=media_type)
        assert MediaFile.from_dict(mf.to_dict()) == mf


class TestExtractionResultDictRoundTrip:
    def test_round_trip_empty_media(self) -> None:
        er = ExtractionResult(markdown="# Hello", media_files=())
        assert ExtractionResult.from_dict(er.to_dict()) == er

    def test_round_trip_with_media(self) -> None:
        mf = MediaFile(source_path=Path("/tmp/img.png"), filename="img.png", media_type="image/png")
        er = ExtractionResult(markdown="# Doc\n\n![[img.png]]", media_files=(mf,))
        assert ExtractionResult.from_dict(er.to_dict()) == er

    def test_to_dict_structure(self) -> None:
        mf = MediaFile(source_path=Path("/x.png"), filename="x.png", media_type="image/png")
        er = ExtractionResult(markdown="md", media_files=(mf,))
        d = er.to_dict()
        assert d["markdown"] == "md"
        assert len(d["media_files"]) == 1
        assert d["media_files"][0]["filename"] == "x.png"

    @given(markdown=st.text(min_size=0, max_size=200))
    def test_round_trip_property(self, markdown: str) -> None:
        er = ExtractionResult(markdown=markdown, media_files=())
        assert ExtractionResult.from_dict(er.to_dict()) == er
