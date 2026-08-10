"""
Canonical chess notation reference for OCR / uncommon glyph cleanup.

Squares, piece letters, move annotations (!/? family), and Informator-style
position evaluations. OCR_ALIASES maps scan garbage → canonical forms.
"""

from __future__ import annotations

import re
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
    "+": "check",
    "#": "checkmate",
}

# Longest first so replacements prefer ?? / !! / ?! / !? over single ? / !
NOTATION_MARK_ORDER: Final[tuple[str, ...]] = ("??", "!!", "?!", "!?", "?", "!", "+", "#")

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
# OCR figurine glyphs → SAN piece (or piece+file). Longest match wins.
# Used mid-prose ("'Wie2, ltJc4") and at numbered-move tokens.
# ---------------------------------------------------------------------------

PIECE_OCR_GLYPHS: Final[dict[str, str]] = {
    # Full-token → complete SAN
    "%'m": "Qf8",
    "%'M": "Qf8",
    "l'hcl": "Rxc1",
    "l'kl": "Rc1",
    "J.fl": "Bf2",
    "J.f1": "Bf2",
    "J.fI": "Bf2",
    "J.£6": "Bf6",
    "J.f6": "Bf6",
    # Queen OCR: "f?" figurine salad (Quality Chess)
    "f?": "Q",
    # Queen figurines (Quality Chess / ChessBase)
    "'Wie": "Qe",
    "Wie": "Qe",
    "Wid": "Qd",
    "'Wi": "Q",
    "'l!": "Q",
    "°1W": "Q",
    "1!f/": "Q",
    "1!f": "Q",
    "'!ti": "Q",
    "'!tí": "Q",
    "'{!i": "Q",
    "'{!": "Q",
    "'(!i": "Q",
    "1W": "Q",
    "lW": "Q",
    "%'": "Q",
    # Knight figurines
    "ltJ": "N",
    "l/J": "N",
    "ll'l": "N",
    "lt'l": "N",
    "ltl'": "N",
    "llil": "N",
    "liJ": "N",
    "llJ": "N",
    "l2J": "N",
    "0.J": "N",
    "4J": "N",
    "lll": "N",
    "lil": "N",
    "ill": "N",
    "ttl": "N",
    "ttI": "N",
    "tli": "N",
    "l0": "N",
    # Rook figurines
    "l'hc": "Rxc",
    "l'k": "Rc",
    "l'h": "R",
    'l"k': "R",
    "i'!": "R",
    ":§:": "R",
    "E:": "R",
    "E'.": "R",
    "E'": "R",
    "El": "R",
    ".§": "R",
    "§": "R",
    "ilx": "Rx",
    "llx": "Rx",
    "!:i": "R",
    "!:": "R",
    # King figurines
    "'itl": "K",
    "itl": "K",
    "'it>": "K",
    "it>": "K",
    "'tt>": "K",
    "tt>": "K",
    # Queen leftovers
    "'Ml'": "Q",
    "'Ml": "Q",
    # Bishop figurines
    "1'.": "B",
    "1'": "B",
    ".i.": "B",
    "i.": "B",
    "&.": "B",
    "&": "B",
}

# Distinctive multi-char glyphs safe to rewrite mid-prose (not English words).
PIECE_OCR_PROSE_SAFE: Final[frozenset[str]] = frozenset(
    {
        "%'m",
        "%'M",
        "%'",
        "'Wie",
        "Wie",
        "Wid",
        "'Wi",
        "'!ti",
        "'!tí",
        "'{!i",
        "'{!",
        "'(!i",
        "ltJ",
        "l/J",
        "ll'l",
        "lt'l",
        "ltl'",
        "llil",
        "liJ",
        "llJ",
        "l2J",
        "0.J",
        "4J",
        "lll",
        "lil",
        "ill",
        "ttl",
        "ttI",
        "tli",
        "l0",
        "!:i",
        "!:",
        "l'hcl",
        "l'hc",
        "l'kl",
        "l'k",
        "l'h",
        'l"k',
        "i'!",
        ":§:",
        "E:",
        "E'.",
        "E'",
        "El",
        ".§",
        "'itl",
        "itl",
        "'Ml'",
        "'Ml",
        "§",
        "ilx",
        "llx",
        "1'.",
        ".i.",
        "J.fl",
        "J.f1",
        "J.fI",
        "J.£6",
        "J.f6",
        "f?",
    }
)

_PIECE_OCR_ORDERED: Final[tuple[tuple[str, str], ...]] = tuple(
    sorted(PIECE_OCR_GLYPHS.items(), key=lambda kv: (-len(kv[0]), kv[0]))
)
_PIECE_OCR_PROSE_ORDERED: Final[tuple[tuple[str, str], ...]] = tuple(
    (g, PIECE_OCR_GLYPHS[g])
    for g, _ in _PIECE_OCR_ORDERED
    if g in PIECE_OCR_PROSE_SAFE
)

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
    # Check: Quality Chess / Informator often OCR '+' as 't' after SAN
    "t": "+",
    # Checkmate: keep explicit; rare OCR of mate glyph as H after SAN handled in ocr_chess
    "#": "#",
    # Informator slightly-better often OCR'd as ASCII or junk
    "+=": "⩲",
    "=+": "⩱",
    ";i;": "⩲",
    ";I;": "⩲",
    ";!;": "⩲",
    ";t": "⩲",
    "!;!;": "⩲",
    "!;i;": "⩲",
    "!?;!;": "!? ⩲",
    "!?;i;": "!? ⩲",
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

_FULL_SAN_REPL_RE = re.compile(r"^[NBRQK][a-h]?[1-8]?x?[a-h][1-8]$")
# Square / capture / rank; OCR often spaces file/rank ("c 6", "f 4"); optional "-c6".
_SAN_CONT_RE = re.compile(
    r"^\s*(?:"
    r"[a-h]?\s*[1-8]?\s*x\s*[a-h]\s*[1-8]|"
    r"[a-h]\s*[1-8]|"
    r"[a-h][lI1-8sS]|"
    r"x\s*[a-h]|"
    r"[1-8]"
    r")(?:-\s*[a-h]\s*[1-8])?[+#?!]*"
)


def apply_piece_ocr_prefix(token: str) -> str:
    """Replace leading OCR figurine glyph with SAN piece (longest match)."""
    t = token or ""
    if not t:
        return t
    for glyph, repl in _PIECE_OCR_ORDERED:
        n = len(glyph)
        if n > len(t):
            continue
        head, rest = t[:n], t[n:]
        if head != glyph and head.lower() != glyph.lower():
            continue
        if _FULL_SAN_REPL_RE.match(repl):
            if not rest or re.fullmatch(r"[+#?!]*", rest):
                return repl + rest
            continue
        if not rest.strip():
            continue
        m = _SAN_CONT_RE.match(rest)
        if m or (
            re.fullmatch(r"[NBRQK][a-h]", repl) and re.match(r"^\s*[1-8]", rest)
        ):
            # Drop OCR space between figurine and square: "lil b4" → "Nb4"
            cont = rest.lstrip() if rest[:1].isspace() else rest
            return repl + cont
    return t


def replace_piece_ocr_glyphs(text: str) -> str:
    """
    Rewrite OCR figurine tokens mid-prose via PIECE_OCR_GLYPHS.

    Example: \"'Wie2, ltJc4\" → \"Qe2, Nc4\".
    Also: \"lllb4-c6\", \"lil b4\" (space), after bare \"...\".
    Only prose-safe multi-char glyphs; requires SAN-ish continuation.
    """
    if not text:
        return ""
    out = text
    for glyph, repl in _PIECE_OCR_PROSE_ORDERED:
        flags = re.I if glyph[:1].isalpha() else 0
        if _FULL_SAN_REPL_RE.match(repl):
            out = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(glyph)}(?![A-Za-z0-9])",
                repl,
                out,
                flags=flags,
            )
            continue
        # Optional space between glyph and square (OCR "lil b4", "lilc 6")
        out = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(glyph)}\s*"
            rf"(?=(?:[a-h]?\s*[1-8]?\s*x\s*[a-h]\s*[1-8]|[a-h]\s*[1-8]|[a-h][lI1-8sS]|x\s*[a-h]|[1-8])"
            rf"(?:-\s*[a-h]\s*[1-8])?[+#?!]*)",
            repl,
            out,
            flags=flags,
        )
    return out


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
