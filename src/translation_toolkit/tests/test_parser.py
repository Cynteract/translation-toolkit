import pytest
from translation_toolkit.parser import parse_file, reassemble_file


def test_json_round_trip():
    raw_json = '{\n  "greeting": "Hello, world!",\n  "app_name": "Translation Toolkit"\n}'
    blocks, extra = parse_file(raw_json, "json")
    assert reassemble_file(blocks, "json", extra=extra) == raw_json


def test_markdown_round_trip():
    raw_md = (
        "---\n"
        "title: My Document\n"
        "draft: false\n"
        "---\n"
        "# Main Heading\n\n"
        "This is a paragraph with **bold** and *italic* text.\n\n"
        "- List item 1\n"
        "- List item 2\n"
    )
    blocks, extra = parse_file(raw_md, "markdown")
    assert reassemble_file(blocks, "markdown", extra=extra) == raw_md


def test_json_back_to_back_placeholders():
    raw_json = '{\n  "template": "Hello {first_name}{last_name}, your balance is {balance}!"\n}'
    blocks, extra = parse_file(raw_json, "json")
    assert len(extra) == 3
    assert "{first_name}" in extra.values()
    assert "{last_name}" in extra.values()
    assert "{balance}" in extra.values()
    assert reassemble_file(blocks, "json", extra=extra) == raw_json


def test_markdown_link_with_leading_trailing_spaces():
    raw_md = "Click [  visit our site  ](https://example.com) to learn more."
    blocks, extra = parse_file(raw_md, "markdown")
    translatable_prose = [b.text for b in blocks if b.should_translate]
    assert "visit our site" in translatable_prose
    assert "  visit our site  " not in translatable_prose
    assert reassemble_file(blocks, "markdown") == raw_md


def test_markdown_empty_front_matter_keys_and_fence_boundary():
    # Empty key right before the fence
    raw_md_fence = "---\ntitle: Real Title\ndescription:\n---\n# Post Content"
    blocks, _ = parse_file(raw_md_fence, "markdown")
    translatable_text = [b.text for b in blocks if b.should_translate]
    assert "---" not in translatable_text
    assert "Real Title" in translatable_text
    assert reassemble_file(blocks, "markdown") == raw_md_fence

    # Empty key followed immediately by another key
    raw_md_adjacent = "---\ntitle:\ndescription: Valid Description\n---\nBody text."
    blocks, _ = parse_file(raw_md_adjacent, "markdown")
    translatable_text = [b.text for b in blocks if b.should_translate]
    assert "Valid Description" in translatable_text
    assert "description: Valid Description" not in translatable_text
    assert reassemble_file(blocks, "markdown") == raw_md_adjacent


def test_json_missing_extra_raises_error():
    blocks, _ = parse_file('{"key": "value"}', "json")
    with pytest.raises(ValueError, match="Reassembling JSON requires"):
        reassemble_file(blocks, "json", extra=None)