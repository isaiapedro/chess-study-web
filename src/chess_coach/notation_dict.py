"""
Canonical chess notation reference for OCR / uncommon glyph cleanup.

Squares, piece letters, move annotations (!/? family), and Informator-style
position evaluations. OCR_ALIASES maps scan garbage → canonical forms.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Squares: a1–h8
# ---------------------------------------------------------------------------

FILES: Final[tuple[str, ...]] = ("a", "b", "c", "d", "e", "f", "g", "h")
RANKS: Final[tuple[str, ...]] = ("1", "2", "3", "4", "5", "6", "7", "8")
SQUARES: Final[tuple[str, ...]] = tuple(f + r for r in RANKS for f in FILES)
SQUARES_SET: Final[frozenset[str]] = frozenset(SQUARES)

# ---------------------------------------------------------------------------
# Pieces (SAN letters; pawns have no letter in SAN)
# ---------------------------------------------------------------------------

PIECES: Final[dict[str, str]] = {
    "N": "knight",
    "B": "bishop",
    "R": "rook",
    "Q": "queen",
    "K": "king",
}
PIECE_LETTERS: Final[frozenset[str]] = frozenset(PIECES)
PAWN: Final[str] = ""  # SAN omits letter for pawn moves

# ---------------------------------------------------------------------------
# Move notation marks (NAG / book annotations) — worst → best within ? / !
# ---------------------------------------------------------------------------

NOTATION_MARKS: Final[dict[str, str]] = {
    "??": "blunder",
    "?": "mistake",
    "?!": "inaccuracy",
    "!?": "dubious/interesting move",
    "!": "good move",
    "!!": "brilliant move",
}

# Longest first so replacements prefer ?? / !! / ?! / !? over single ? / !
NOTATION_MARK_ORDER: Final[tuple[str, ...]] = ("??", "!!", "?!", "!?", "?", "!")

# ---------------------------------------------------------------------------
# Position evaluation (Informator / Quality Chess style)
# ---------------------------------------------------------------------------

POSITION_EVAL: Final[dict[str, str]] = {
    "=": "equal",
    "⩲": "slightly better for white",
    "⩱": "slightly better for black",
    "±": "clearly better for white",
    "∓": "clearly better for black",
    "+-": "white is winning",
    "-+": "black is winning",
    "∞": "unclear",
    "=/∞": "compensation",
}

# Narrow no-break spaces sometimes used in print: + − / − +
POSITION_EVAL_DISPLAY: Final[dict[str, str]] = {
    "+-": "+ −",
    "-+": "− +",
}

# ---------------------------------------------------------------------------
# OCR / ASCII aliases → canonical key in NOTATION_MARKS or POSITION_EVAL
# ---------------------------------------------------------------------------

OCR_ALIASES: Final[dict[str, str]] = {
    # Move marks (! misread as f / l / 1 / i)
    "?f": "?!",
    "?F": "?!",
    "?l": "?!",
    "?I": "?!",
    "?1": "?!",
    "!f": "!?",
    "!F": "!?",
    "!l": "!?",
    "!I": "!?",
    "!1": "!?",
    # Informator slightly-better often OCR'd as ASCII or junk
    "+=": "⩲",
    "=+": "⩱",
    ";i;": "⩲",
    ";I;": "⩲",
    "+/-": "±",
    "-/+": "∓",
    "+/−": "±",
    "−/+": "∓",
    "+-": "+-",
    "-+": "-+",
    "+ −": "+-",
    "− +": "-+",
    "+\u2009−": "+-",
    "−\u2009+": "-+",
    "=/oo": "=/∞",
    "=∞": "=/∞",
    "=/inf": "=/∞",
    "infinity": "∞",
    "unclear": "∞",
}


def is_square(token: str) -> bool:
    return (token or "").strip().lower() in SQUARES_SET


def is_piece_letter(token: str) -> bool:
    t = (token or "").strip()
    return len(t) == 1 and t.upper() in PIECE_LETTERS


def normalize_notation_mark(token: str) -> str | None:
    """Return canonical !/? mark, or None if not a known mark / alias."""
    raw = (token or "").strip()
    if not raw:
        return None
    if raw in NOTATION_MARKS:
        return raw
    mapped = OCR_ALIASES.get(raw) or OCR_ALIASES.get(raw.lower())
    if mapped in NOTATION_MARKS:
        return mapped
    return None


def normalize_position_eval(token: str) -> str | None:
    """Return canonical eval symbol, or None if unknown."""
    raw = (token or "").strip()
    if not raw:
        return None
    if raw in POSITION_EVAL:
        return raw
    mapped = OCR_ALIASES.get(raw)
    if mapped is None:
        mapped = OCR_ALIASES.get(raw.replace(" ", ""))
    if mapped in POSITION_EVAL:
        return mapped
    # Already ASCII +- / -+ stored as canonical
    if mapped in ("+-", "-+") and mapped in POSITION_EVAL:
        return mapped
    return None


def describe_mark(token: str) -> str | None:
    key = normalize_notation_mark(token)
    return NOTATION_MARKS.get(key) if key else None


def describe_eval(token: str) -> str | None:
    key = normalize_position_eval(token)
    return POSITION_EVAL.get(key) if key else None
