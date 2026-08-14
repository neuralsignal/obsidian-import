"""Tests for splicing anydoc media embeds into anydoc's markdown."""

from pathlib import Path
from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from obsidian_import.anydoc_placement import place_media_embeds
from obsidian_import.anydoc_spans import block_spans
from obsidian_import.extraction_result import MediaFile


def _media(filename: str) -> MediaFile:
    return MediaFile(source_path=Path("/tmp") / filename, filename=filename, media_type="image")


def _text(value: str) -> SimpleNamespace:
    return SimpleNamespace(kind="text", text=value, alt=None, content=None, source=None)


def _image(asset_id: int, alt: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        kind="image",
        text=None,
        alt=alt,
        content=None,
        source=SimpleNamespace(kind="asset", asset_id=asset_id, url=None),
    )


def _block(kind: str, content: list | None = None, **fields) -> SimpleNamespace:
    return SimpleNamespace(
        kind=kind,
        content=content,
        blocks=fields.get("blocks"),
        list=fields.get("list"),
        table=fields.get("table"),
        lang=fields.get("lang"),
        text=fields.get("text"),
        level=fields.get("level"),
    )


def _document(blocks: list) -> SimpleNamespace:
    return SimpleNamespace(blocks=blocks, assets=[], notes=[])


class TestBlockSpans:
    def test_splits_on_blank_lines(self):
        markdown = "First block\n\nSecond block\n"

        spans = block_spans(markdown)

        assert [markdown[start:end] for start, end in spans] == ["First block", "Second block"]

    def test_keeps_fenced_code_whole(self):
        markdown = "Intro\n\n```python\na = 1\n\nb = 2\n```\n\nOutro\n"

        spans = block_spans(markdown)

        assert [markdown[start:end] for start, end in spans] == [
            "Intro",
            "```python\na = 1\n\nb = 2\n```",
            "Outro",
        ]

    def test_multiline_table_is_one_block(self):
        markdown = "| a | b |\n| --- | --- |\n| 1 | 2 |\n"

        spans = block_spans(markdown)

        assert len(spans) == 1

    @given(
        paragraphs=st.lists(
            st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=10),
            min_size=1,
            max_size=6,
        )
    )
    def test_spans_reconstruct_the_paragraphs(self, paragraphs):
        markdown = "\n\n".join(paragraphs) + "\n"

        spans = block_spans(markdown)

        assert [markdown[start:end] for start, end in spans] == paragraphs


class TestPlaceMediaEmbeds:
    def test_image_only_block_lands_between_its_neighbours(self):
        document = _document(
            [
                _block("paragraph", [_text("Before the figure.")]),
                _block("paragraph", [_image(0)]),
                _block("paragraph", [_text("After the figure.")]),
            ]
        )

        placed = place_media_embeds(
            "Before the figure.\n\nAfter the figure.\n", document, {0: _media("asset_img1.png")}, "doc"
        )

        assert placed == "Before the figure.\n\n![[doc/asset_img1.png]]\n\nAfter the figure.\n"

    def test_image_inside_a_rendered_block_follows_it(self):
        document = _document(
            [
                _block("paragraph", [_text("See"), _image(0, alt="the chart")]),
                _block("paragraph", [_text("Tail.")]),
            ]
        )

        placed = place_media_embeds("See the chart\n\nTail.\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "See the chart\n\n![[doc/asset_img1.png]]\n\nTail.\n"

    def test_image_in_a_table_cell_follows_the_table(self):
        cell = SimpleNamespace(kind="origin", cell=SimpleNamespace(blocks=[_block("paragraph", [_image(0)])]))
        header = SimpleNamespace(kind="origin", cell=SimpleNamespace(blocks=[_block("paragraph", [_text("h")])]))
        table = _block("table", None, table=SimpleNamespace(grid=[[header], [cell]], header_rows=1, kind="data"))
        document = _document([table, _block("paragraph", [_text("Tail.")])])
        markdown = "| h |\n| --- |\n|  |\n\nTail.\n"

        placed = place_media_embeds(markdown, document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "| h |\n| --- |\n|  |\n\n![[doc/asset_img1.png]]\n\nTail.\n"

    def test_trailing_image_block_lands_after_the_last_block(self):
        document = _document([_block("paragraph", [_text("Body.")]), _block("paragraph", [_image(0)])])

        placed = place_media_embeds("Body.\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "Body.\n\n![[doc/asset_img1.png]]\n"

    def test_several_images_in_one_block_keep_their_order(self):
        document = _document([_block("paragraph", [_image(0), _image(1)]), _block("paragraph", [_text("Tail.")])])
        media = {0: _media("asset_img1.png"), 1: _media("asset_img2.png")}

        placed = place_media_embeds("Tail.\n", document, media, "doc")

        assert placed == "![[doc/asset_img1.png]]\n![[doc/asset_img2.png]]\n\nTail.\n"

    def test_rule_block_does_not_shift_placement(self):
        document = _document(
            [
                _block("paragraph", [_text("Above.")]),
                _block("rule"),
                _block("paragraph", [_image(0)]),
                _block("paragraph", [_text("Below.")]),
            ]
        )

        placed = place_media_embeds("Above.\n\n---\n\nBelow.\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "Above.\n\n---\n\n![[doc/asset_img1.png]]\n\nBelow.\n"

    def test_misaligned_markdown_leaves_the_text_untouched(self):
        # The markdown does not match the model, so no position can be trusted:
        # the embed is left to extract_file, which appends it.
        document = _document(
            [
                _block("paragraph", [_text("Text the markdown does not contain")]),
                _block("paragraph", [_image(0)]),
            ]
        )

        placed = place_media_embeds("Entirely different output\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "Entirely different output\n"

    def test_image_in_a_list_item_follows_the_list(self):
        item = SimpleNamespace(blocks=[_block("paragraph", [_text("Item one"), _image(0)])])
        listing = _block("list", None, list=SimpleNamespace(marker="bullet", start=1, items=[item]))
        document = _document([listing, _block("paragraph", [_text("Tail.")])])

        placed = place_media_embeds("- Item one\n\nTail.\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "- Item one\n\n![[doc/asset_img1.png]]\n\nTail.\n"

    def test_image_in_a_block_quote_follows_the_quote(self):
        quote = _block("block_quote", None, blocks=[_block("paragraph", [_text("Quoted"), _image(0)])])
        document = _document([quote, _block("paragraph", [_text("Tail.")])])

        placed = place_media_embeds("> Quoted\n\nTail.\n", document, {0: _media("asset_img1.png")}, "doc")

        assert placed == "> Quoted\n\n![[doc/asset_img1.png]]\n\nTail.\n"

    def test_code_block_and_link_keep_alignment(self):
        link = SimpleNamespace(
            kind="link",
            text=None,
            alt=None,
            content=[_text("the docs")],
            source=None,
            target=SimpleNamespace(kind="external", value="https://example.com"),
        )
        document = _document(
            [
                _block("code_block", None, lang="python", text="value = 1"),
                _block("paragraph", [_text("Read"), link]),
                _block("paragraph", [_image(0)]),
                _block("paragraph", [_text("Tail.")]),
            ]
        )
        markdown = "```python\nvalue = 1\n```\n\nRead [the docs](https://example.com)\n\nTail.\n"

        placed = place_media_embeds(markdown, document, {0: _media("asset_img1.png")}, "doc")

        assert placed == (
            "```python\nvalue = 1\n```\n\nRead [the docs](https://example.com)\n\n![[doc/asset_img1.png]]\n\nTail.\n"
        )

    def test_external_image_is_left_to_anydoc(self):
        external = SimpleNamespace(
            kind="image",
            text=None,
            alt="remote",
            content=None,
            source=SimpleNamespace(kind="external", asset_id=None, url="https://example.com/i.png"),
        )
        document = _document([_block("paragraph", [external]), _block("paragraph", [_text("Tail.")])])
        markdown = "![remote](https://example.com/i.png)\n\nTail.\n"

        placed = place_media_embeds(markdown, document, {0: _media("asset_img1.png")}, "doc")

        assert placed == markdown

    def test_asset_without_a_media_file_is_skipped(self):
        document = _document([_block("paragraph", [_image(7)]), _block("paragraph", [_text("Tail.")])])

        placed = place_media_embeds("Tail.\n", document, {}, "doc")

        assert placed == "Tail.\n"

    @given(
        image_positions=st.lists(st.booleans(), min_size=1, max_size=8),
    )
    def test_every_image_is_embedded_exactly_once(self, image_positions):
        # A document of paragraphs, some of which are image-only blocks.
        blocks: list = []
        paragraphs: list[str] = []
        media: dict[int, MediaFile] = {}
        for index, is_image in enumerate(image_positions):
            if is_image:
                blocks.append(_block("paragraph", [_image(index)]))
                media[index] = _media(f"asset_img{index}.png")
            else:
                text = f"paragraph number {index}"
                blocks.append(_block("paragraph", [_text(text)]))
                paragraphs.append(text)
        markdown = "\n\n".join(paragraphs) + "\n" if paragraphs else ""

        placed = place_media_embeds(markdown, _document(blocks), media, "doc")

        assert placed.count("![[") == len(media)
        for media_file in media.values():
            assert placed.count(f"![[doc/{media_file.filename}]]") == 1
        for text in paragraphs:
            assert text in placed
