"""
Custom chess-font glyph detection via PyMuPDF ``page.get_text("dict")``.

Older Quality Chess PDFs embed piece figurines as letter-like glyphs in fonts
such as ChessMerida / ChessAlpha. Plain ``get_text("text")`` maps those to
wrong Unicode (often U+FFFD or Latin lookalikes). Inspect ``font`` + ``c`` /
span characters and map to SAN piece letters before OCR cleanup.
"""

from __future__ import annotations

import re
from typing import Any, Callable

# Common Quality Chess / Informator figurine font name fragments → piece letter.
_CHESS_FONT_HINTS = re.compile(
    r"(?i)chess|merida|figurine|alpha|cases|goodcompanion|magnetic"
)

# Default codepoint/char → piece when the span font is a chess figurine face.
# Merida-style faces often encode KQRBNP on Latin letters; books vary — callers
# may pass an override map from a calibrated sample page.
_DEFAULT_FIGURINE_CHAR_MAP: dict[str, str] = {
    "k": "K",
    "K": "K",
    "q": "Q",
    "Q": "Q",
    "r": "R",
    "R": "R",
    "b": "B",
    "B": "B",
    "n": "N",
    "N": "N",
    "p": "",
    "P": "",
    "l": "N",
    "t": "N",
    "i": "B",
    "j": "R",
    "w": "Q",
    "y": "Q",
}


def is_chess_figurine_font(fontname: str | None) -> bool:
    return bool(fontname and _CHESS_FONT_HINTS.search(fontname))


def map_figurine_char(
    ch: str,
    fontname: str | None,
    *,
    char_map: dict[str, str] | None = None,
) -> str:
    """
    Map one character from a chess font span to a SAN piece letter (or ``\"\"``).

    Non-figurine fonts return ``ch`` unchanged.
    """
    if not ch or not is_chess_figurine_font(fontname):
        return ch
    table = char_map or _DEFAULT_FIGURINE_CHAR_MAP
    if ch in table:
        return table[ch]
    if len(ch) == 1 and ord(ch) in range(0xE000, 0xF900):
        # Private-use figurines — unknown without a calibrated map.
        return "\ufffd"
    return table.get(ch.lower(), ch)


def spans_from_dict_page(page_dict: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Flatten PyMuPDF ``get_text('dict')`` page into ``(text, fontname)`` spans."""
    out: list[tuple[str, str | None]] = []
    for block in page_dict.get("blocks") or []:
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines") or []:
            for span in line.get("spans") or []:
                text = span.get("text") or ""
                if not text:
                    continue
                out.append((text, span.get("font")))
    return out


def rewrite_spans_with_font_glyphs(
    spans: list[tuple[str, str | None]],
    *,
    char_map: dict[str, str] | None = None,
) -> str:
    """Join spans, remapping figurine-font characters to SAN piece letters."""
    parts: list[str] = []
    for text, font in spans:
        if not is_chess_figurine_font(font):
            parts.append(text)
            continue
        parts.append(
            "".join(map_figurine_char(ch, font, char_map=char_map) for ch in text)
        )
    return "".join(parts)


def extract_page_text_with_font_glyphs(
    page: Any,
    *,
    char_map: dict[str, str] | None = None,
    get_text: Callable[..., Any] | None = None,
) -> str:
    """
    Extract one PDF page as text with chess-font glyphs mapped to piece letters.

    ``page`` is a PyMuPDF page (duck-typed: needs ``get_text``). Prefer this over
    raw ``page.get_text(\"text\")`` when figurine fonts are present.
    """
    getter = get_text or (lambda *a, **k: page.get_text(*a, **k))
    page_dict = getter("dict")
    if not isinstance(page_dict, dict):
        return str(getter("text") or "")
    spans = spans_from_dict_page(page_dict)
    if not any(is_chess_figurine_font(font) for _t, font in spans):
        return str(getter("text") or "")
    return rewrite_spans_with_font_glyphs(spans, char_map=char_map)
