# parser.py
# Universal file parser — converts structured files (JSON, Markdown, MDX)
# into translatable Block lists and reassembles them post-translation.

import html
import re
import logging
from typing import Any, Callable, Optional

from .models import Block

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(content: str, file_type: str) -> tuple[list[Block], Any]:
    file_type = file_type.lower()
    if file_type == "json":
        return _parse_json(content)
    elif file_type in ("markdown", "mdx"):
        return _parse_markdown(content), None
    raise ValueError(f"Unsupported file type: {file_type}")


def reassemble_file(blocks: list[Block], file_type: str, extra: Any = None) -> str:
    file_type = file_type.lower()
    if file_type == "json":
        if extra is None:
            raise ValueError("Reassembling JSON requires the 'extra' placeholder_table.")
        return _reassemble_json(blocks, extra)
    elif file_type in ("markdown", "mdx"):
        return _reassemble_markdown(blocks)
    raise ValueError(f"Unsupported file type: {file_type}")


# ---------------------------------------------------------------------------
# Shared Block Helpers
# ---------------------------------------------------------------------------

def _append_block(blocks: list[Block], text: str, should_translate: bool, key: str | None = None) -> None:
    if not text:
        return
    if blocks and not should_translate and not blocks[-1].should_translate:
        blocks[-1].text += text
    else:
        blocks.append(Block(text=text, should_translate=should_translate, key=key))


# ---------------------------------------------------------------------------
# JSON Parsing & Reassembly
# ---------------------------------------------------------------------------

_JSON_PATTERN = re.compile(r'(\s*"(?:\\.|[^"\\])*"\s*:\s*")((?:\\.|[^"\\])*?)(")')
_PH_PATTERN = re.compile(r"\{[^{}]+\}")
_PH_RESTORE_PATTERN = re.compile(r"<ph(\d+)\s*/>")


def _parse_json(content: str) -> tuple[list[Block], dict[str, str]]:
    blocks: list[Block] = []
    placeholder_table: dict[str, str] = {}
    last_index = 0

    def _replace_ph(m: re.Match) -> str:
        tag = f"<ph{len(placeholder_table) + 1}/>"
        placeholder_table[tag] = m.group(0)
        return tag

    for match in _JSON_PATTERN.finditer(content):
        _append_block(blocks, content[last_index:match.end(1)], False)
        value_text = match.group(2).replace(r'\"', '"')
        value_with_ph = _PH_PATTERN.sub(_replace_ph, value_text)
        _append_block(blocks, value_with_ph, True)
        last_index = match.end(2)

    if last_index < len(content):
        _append_block(blocks, content[last_index:], False)

    return blocks, placeholder_table


def _reassemble_json(blocks: list[Block], placeholder_table: dict[str, str]) -> str:
    result = []
    for b in blocks:
        if b.should_translate:
            text = _PH_RESTORE_PATTERN.sub(
                lambda m: placeholder_table.get(f"<ph{m.group(1)}/>", m.group(0)),
                b.text,
            )
            text = html.unescape(text)
            text = text.replace('"', r'\"')
            result.append(text)
        else:
            result.append(b.text)
    return "".join(result)


# ---------------------------------------------------------------------------
# Markdown / MDX Parsing & Reassembly
# ---------------------------------------------------------------------------

_FM_PATTERN = re.compile(r"^---\n([\s\S]*?)\n---\n?", re.MULTILINE)
_KV_PATTERN = re.compile(
    r"(^\s*(?:title|description|summary):\s*)([^\n]*)(\n?)",
    re.MULTILINE | re.IGNORECASE,
)
_MD_SYNTAX_PATTERN = re.compile(
    r"(```[\s\S]*?```)|"
    r"(`[^`]+`)|"
    r"(<[^>]+>)|"
    r"(!?\[.*?\]\(.*?\))|"
    r"(^\s*#{1,6}\s*)|"
    r"(^\s*[-*+]\s+)|"
    r"(^\s*\d+\.\s+)|"
    r"(^\s*>\s+)|"
    r"(\*{1,3}|_{1,3}|~~)|"
    r"(^\s*\|?[\s:-]*---[\s:-]*\|[|\s:-]*$)|"
    r"(\|)|"
    r"(\n+)",
    re.MULTILINE,
)
_LINK_IMAGE_PATTERN = re.compile(r"(!?)\[(.*?)\]\((.*?)\)")


def _parse_markdown(content: str) -> list[Block]:
    blocks: list[Block] = []
    match = _FM_PATTERN.match(content)

    if match:
        _parse_front_matter_block(blocks, match.group(0))
        body_text = content[match.end():]
    else:
        body_text = content

    if body_text:
        _parse_markdown_body(blocks, body_text)

    return blocks


def _parse_front_matter_block(blocks: list[Block], fm_text: str) -> None:
    last_index = 0

    for match in _KV_PATTERN.finditer(fm_text):
        start, end = match.span()
        if start > last_index:
            _append_block(blocks, fm_text[last_index:start], False)

        key_part, val_part, newline_part = match.groups()
        _append_block(blocks, key_part, False)

        stripped = val_part.strip()
        if stripped:
            leading_len = len(val_part) - len(val_part.lstrip())
            trailing_len = len(val_part) - len(val_part.rstrip())
            if leading_len:
                _append_block(blocks, val_part[:leading_len], False)
            _append_block(blocks, stripped, True)
            if trailing_len:
                _append_block(blocks, val_part[-trailing_len:], False)
        elif val_part:
            _append_block(blocks, val_part, False)

        if newline_part:
            _append_block(blocks, newline_part, False)

        last_index = end

    if last_index < len(fm_text):
        _append_block(blocks, fm_text[last_index:], False)


def _parse_markdown_body(blocks: list[Block], body_text: str) -> None:
    last_index = 0

    def _add_prose(text: str) -> None:
        if not text:
            return
        stripped = text.strip()
        if not stripped:
            _append_block(blocks, text, False)
            return

        leading_len = len(text) - len(text.lstrip())
        trailing_len = len(text) - len(text.rstrip())
        if leading_len:
            _append_block(blocks, text[:leading_len], False)
        _append_block(blocks, stripped, True)
        if trailing_len:
            _append_block(blocks, text[-trailing_len:], False)

    for match in _MD_SYNTAX_PATTERN.finditer(body_text):
        start, end = match.span()
        if start > last_index:
            _add_prose(body_text[last_index:start])

        matched_text = match.group(0)
        link_match = _LINK_IMAGE_PATTERN.fullmatch(matched_text)

        if link_match:
            is_image, link_text, url = link_match.groups()
            if is_image:
                _append_block(blocks, "!", False)
            _append_block(blocks, "[", False)
            _add_prose(link_text)
            _append_block(blocks, f"]({url})", False)
        else:
            _append_block(blocks, matched_text, False)

        last_index = end

    if last_index < len(body_text):
        _add_prose(body_text[last_index:])


def _reassemble_markdown(blocks: list[Block]) -> str:
    return "".join(
        html.unescape(b.text) if b.should_translate else b.text
        for b in blocks
    )