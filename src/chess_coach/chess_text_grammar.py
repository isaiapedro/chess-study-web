"""
Universal chess-text grammar for PDF / OCR book notes.

Layer 1 — token heads: squares and pawn advances are never move numbers.
Layer 2 — score-line segmentation: structure first, short variation cues second.
Figurine OCR stays in notation_dict (lookup only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Rule A — move heads (square ≠ move number)
# ---------------------------------------------------------------------------

# Digit after [a-h] or '-' is a rank in a5. / a4-a5. / exd5., not "5.Nf3".
MOVE_HEAD_RE = re.compile(
    r"(?:(?<![a-h\-])(?P<num>\d{1,3})\s*(?P<dots>\.\.\.|\.\.(?!\.)|\.)"
    r"|(?<!\d)(?P<bare>\.\.\.))\s*"
)

MOVE_TOKEN = (
    r"(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*|"
    r"[NBRQK]x?[a-h][1-8](?:=[NBRQ])?[+#?!]*)"
)

MOVE_LABEL_RE = re.compile(
    rf"(?P<num>\d+)\.(?P<dots>\.\.\s*|\.\s*\.\s*|\s*\.\.\s*)?\s*(?P<move>{MOVE_TOKEN})",
    re.I,
)

# Scoped variation cues (secondary; not an 80-word endslist).
_VARIATION_CUE_RE = re.compile(
    r"(?i)\b(?:if|after|with|followed\s+by|instead\s+of|manoeuvre|maneuver|"
    r"continuation(?:\s+is)?|different\s+continuation|such\s+as|"
    r"for\s+example|example|rather\s+than|better\s+was|"
    r"but\s+not|or)\s+$"
)

# Score-only region after a sentence that is still a sideline (not a new mainline).
_VARIATION_TAIL_START_RE = re.compile(
    r"(?is)\s*(?:"
    r"(?:A\s+)?(?:possible\s+)?continuation\s+is\b|"
    r"(?:A\s+)?different\s+continuation\b|"
    r"such\s+as\b|"
    r"Better\s+was\b|"
    r"For\s+example\b:?|"
    r"Example\b:?|"
    r"followed\s+by\b|"
    r"(?:the\s+)?(?:typical\s+)?(?:manoeuvre|maneuver)\b|"
    r"with\s+(?:a\s+)?(?:possible\s+)?continuation\b|"
    r"If\s+\d+\.(?:\.\.)?"
    r")"
)

_COACHING_OPEN_RE = re.compile(
    r"(?:"
    r"The opening stage|White has |Black has |Threatening |Better was |"
    r"Precision is|This game|This example|We have reached|The best |"
    r"Learning objective|In Black's favour|In White's favour|Not only|"
    r"A better |An alternative|Instead |A simple |An interesting |"
    r"Something to note|There is nothing|Getting ready|Now the |"
    r"Followed by|Black is |White is |Black cannot|White can |"
    r"His original|In his analysis|After analyzing|The reader |"
    r"Ignoring the|Creating a|Preparing |"
    r"This prophylactic|Again,? White|And as I said|Black must |"
    r"It was preferable|Once again|The battle is|The only move|"
    r"We are close|The most accurate|Aiming for|Covering the |"
    r"And as usually|A better defence|Black missed|Weak is |"
    r"Of course |It [a-z]+ |deserves |"
    r"The (?:knight|bishop|rook|queen|king|pawn|piece) |"
    r"But now|Suicidal is |"
    r"If |When |While |Although |Though |Should |"
    r"[!?]+\s*(?:A |The |This |White |Black |It |There )"
    r")",
    re.I,
)

_PROSE_BANG_RE = re.compile(r"(?<=[a-z]{2})[!?…]+[\"'”’)\]]*\s+")


def normalize_move_head(num: str | None, dots: str | None, bare: str | None = None) -> str:
    if bare:
        return "..."
    if (dots or "").startswith(".."):
        return f"{num}..."
    return f"{num}."


def normalize_ellipsis_forms(text: str) -> str:
    """
    Rule B order: bullet / dot-bullet ellipsis → glue → White two-dot.

    Call before tokenizing move heads.
    """
    if not text:
        return ""
    out = text
    out = re.sub(r"[•·∙⋅]{2,}", "...", out)
    out = re.sub(r"\.\s*[•·∙⋅]+\s*\.", "...", out)
    out = re.sub(r"[•·∙⋅]\s*\.\s*[•·∙⋅]", "...", out)
    # "17 •.• cxd5" / "17 • • • cxd5"
    out = re.sub(
        r"\b(\d+)\s*[•·∙⋅]\s*\.\s*[•·∙⋅]\s*",
        r"\1... ",
        out,
    )
    out = re.sub(r"\b(\d+)\s*\.\s*[•·∙⋅]+\s*\.\s*", r"\1... ", out)
    out = re.sub(r"\b(\d+)\s+[•·∙⋅]+\s*\.\s*", r"\1... ", out)
    out = re.sub(r"\b(\d+)\s+[•·∙⋅]+\s*[•·∙⋅]\s*", r"\1... ", out)
    # Three spaced dots before two-dot rules: "44 .. . SAN" → "44... SAN"
    out = re.sub(r"\b(\d+)\s*\.\s*\.\s*\.\s*", r"\1... ", out)
    out = re.sub(r"\b(\d+)\s*\.\s*\.\.\s*", r"\1...", out)
    out = re.sub(r"\b(\d+)\s+\.\.\.?\s*", r"\1...", out)
    out = re.sub(r"\b(\d+)\s*\.\s*\.\s+", r"\1... ", out)
    # Spaced two-dot before glyph/piece with no trailing space: "39 . .igl"
    out = re.sub(
        r"\b(\d+)\s*\.\s*\.(?!\.)(?=\s*[NBRQK1lI'\"%@&§a-z])",
        r"\1. ",
        out,
    )
    # Exactly two dots before a piece: OCR for White "24.Bd3"
    out = re.sub(
        r"\b(\d+)\.\.(?!\.)(?=[NBRQK]|[1lI'\"%@&§]|id|if|il|lt|l')",
        r"\1.",
        out,
    )
    # Leftover fourth dot after ellipsis: 44... . / 44.... → 44...
    out = re.sub(r"\b(\d+)\.{3}\s*\.(?!\.)", r"\1...", out)
    out = re.sub(r"\b(\d+)\.{4,}", r"\1...", out)
    return out


def inside_parens(text: str, pos: int, *, sentence_start: int = 0) -> bool:
    depth = 0
    for ch in text[sentence_start:pos]:
        if ch in "({":
            depth += 1
        elif ch in ")}":
            depth = max(0, depth - 1)
    return depth > 0


def last_prose_sentence_end(before: str) -> int | None:
    """Index just after last prose sentence terminator in `before`."""
    ends: list[int] = []
    for m in re.finditer(r"\.", before):
        i = m.start()
        if i + 1 < len(before) and not before[i + 1].isspace() and before[i + 1] not in "\"'”’)":
            continue
        j = i - 1
        while j >= 0 and before[j].isdigit():
            j -= 1
        if j < i - 1:
            if j < 0 or not before[j].isalpha():
                continue
        elif j < 0 or not (before[j].islower() or before[j] in ") ]\"'"):
            continue
        k = m.end()
        while k < len(before) and before[k] in "\"'”’)]":
            k += 1
        while k < len(before) and before[k].isspace():
            k += 1
        ends.append(k)
    for m in _PROSE_BANG_RE.finditer(before):
        ends.append(m.end())
    return max(ends) if ends else None


def trailing_is_score_only(before: str) -> bool:
    """True when text after last sentence is empty or only move notation."""
    end = last_prose_sentence_end(before)
    tail = before[end:] if end is not None else before
    tail = re.sub(r"\ba\s+b\s+c\s+d\s+e\s+f\s+g\s+h\b", " ", tail, flags=re.I)
    tail = re.sub(r"\d{2,3}\s+Family\b[^\n]*", " ", tail)
    if not tail.strip():
        return True
    rest = MOVE_LABEL_RE.sub(" ", tail)
    rest = re.sub(rf"\b{MOVE_TOKEN}\b", " ", rest, flags=re.I)
    rest = re.sub(r"[0-9.!?\s\-–—,;:]+", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    return not re.search(r"[A-Za-z]", rest)


def score_tail_is_variation(before: str) -> bool:
    """
    True when the score-only tail after the last sentence is a sideline run
    introduced by 'for example' / 'continuation is' / similar — not a new mainline.
    """
    end = last_prose_sentence_end(before)
    region = before[end:] if end is not None else before
    if _VARIATION_TAIL_START_RE.match(region):
        return True
    # Cue may sit just before the sentence-ending period ("position. For example: 28...")
    # already covered by match on region. Also: cue glued with no capital after period.
    head = region.lstrip()[:120]
    if re.match(
        r"(?i)(?:for\s+example|example|a\s+possible\s+continuation|"
        r"a\s+different\s+continuation|different\s+continuation|"
        r"such\s+as|continuation\s+is|followed\s+by)\b",
        head,
    ):
        return True
    return False


def _ply_continues(prev_fm: int, prev_side: str, nxt_fm: int, nxt_side: str) -> bool:
    """True when nxt is the next ply after prev (White then Black, or next White)."""
    if prev_side == "white":
        return nxt_fm == prev_fm and nxt_side == "black"
    return nxt_fm == prev_fm + 1 and nxt_side == "white"


def soft_wrapped_variation_continue(text: str, match: re.Match[str]) -> bool:
    """
    Soft line-wrap mid-variation: '... was 30...bxa5\\n31.Qxa5' must not open
    a new score line. Previous non-whitespace ends with a SAN; next label is
    the consecutive ply.

    Also: White label + bare reply before wrap — ``37.Ra1!? Rxa1\\n38.Rxa1``.
    """
    before = text[: match.start()]
    if not re.search(r"\n\s*$", before):
        return False
    stripped = before.rstrip()
    if not re.search(rf"(?i)(?:{MOVE_TOKEN})$", stripped):
        return False
    labels = list(MOVE_LABEL_RE.finditer(stripped))
    if not labels:
        return False
    last = labels[-1]
    gap = stripped[last.end() :].strip()
    if gap:
        # One bare Black reply after a White label, then soft-wrap to next White.
        if _label_side(last) != "white":
            return False
        if not re.fullmatch(rf"(?i){MOVE_TOKEN}", gap):
            return False
        return (
            int(match.group("num")) == int(last.group("num")) + 1
            and _label_side(match) == "white"
        )
    return _ply_continues(
        int(last.group("num")),
        _label_side(last),
        int(match.group("num")),
        _label_side(match),
    )


def continues_after_paren_sideline(text: str, match: re.Match[str]) -> bool:
    """
    After ``... 36.Qf2 (or 36.Rxf7+ …) 36...Rxb5``, the move after ``)`` continues
    the outer variation — do not open a new score line.
    """
    before = text[: match.start()].rstrip()
    if not before.endswith(")") and not before.endswith("}"):
        return False
    depth = 0
    start = -1
    for i in range(len(before) - 1, -1, -1):
        ch = before[i]
        if ch in ")}":
            depth += 1
        elif ch in "({":
            depth -= 1
            if depth == 0:
                start = i
                break
    if start < 0:
        return False
    outer = before[:start].rstrip()
    labels = list(MOVE_LABEL_RE.finditer(outer))
    if not labels:
        return False
    last = labels[-1]
    gap = outer[last.end() :].strip()
    if gap and not re.fullmatch(rf"(?i)(?:{MOVE_TOKEN}\s*)+", gap):
        return False
    return _ply_continues(
        int(last.group("num")),
        _label_side(last),
        int(match.group("num")),
        _label_side(match),
    )


def can_open_score_line(text: str, match: re.Match[str]) -> bool:
    """
    Structural open: not in parens; after sentence / score-only tail;
    not immediately after a scoped variation cue;
    not mid-sideline after 'for example' / 'continuation is';
    not soft-wrapped continuation of an inline variation;
    not the next ply after a parenthetical sideline.
    """
    if inside_parens(text, match.start(), sentence_start=last_prose_sentence_end(text[: match.start()]) or 0):
        return False
    # Full prefix for variation-tail detection (200-char window is too short for long sidelines).
    before_full = text[: match.start()]
    before = before_full[-200:] if len(before_full) > 200 else before_full
    # "studying with:\n17..." is a mainline transition, not "with 17..." variation.
    transition_with = bool(re.search(r"(?i)\bwith:\s*$", before_full))
    before_soft = re.sub(r"[,:;\"'”’)\]]+\s*$", " ", before)
    if not transition_with and _VARIATION_CUE_RE.search(before_soft):
        return False
    if match.start() == 0:
        return True
    # Sideline move-runs must not start a new note, even after newline soft-wrap.
    if score_tail_is_variation(before_full):
        return False
    if soft_wrapped_variation_continue(text, match):
        return False
    if continues_after_paren_sideline(text, match):
        return False
    if trailing_is_score_only(before_full):
        return True
    # Paragraph / real sentence break (not SAN annotation ?! / !? on a move)
    if re.search(r"(?:\.\s*|\n\s*)$", before):
        return True
    return False


@dataclass(frozen=True)
class ScoreMove:
    fullmove: int
    side: str  # white | black
    san: str
    start: int
    end: int


@dataclass(frozen=True)
class ScoreLineNote:
    """Commentary belonging to the last move of a closed score line."""

    fullmove: int
    side: str
    san: str
    text: str
    label_start: int
    label_end: int


def _label_side(match: re.Match[str]) -> str:
    return "black" if match.group("dots") else "white"


def segment_score_lines(text: str) -> tuple[str, list[ScoreLineNote]]:
    """
    Split cleaned book text into preamble + notes.

    Score line opens at a structural move label, continues through consecutive
    plies (same or +1 fullmove), ends at prose; prose attaches to last move.
    """
    if not text:
        return "", []
    matches = list(MOVE_LABEL_RE.finditer(text))
    opens = [m for m in matches if can_open_score_line(text, m)]
    if len(opens) < 2:
        # Last resort: paragraph-start labels
        opens = []
        for m in matches:
            if inside_parens(text, m.start(), sentence_start=last_prose_sentence_end(text[: m.start()]) or 0):
                continue
            before = text[max(0, m.start() - 3) : m.start()]
            if m.start() == 0 or re.search(r"(?:\.\s*|\n\s*)$", before):
                opens.append(m)
    if not opens:
        return text.strip(), []

    preamble = text[: opens[0].start()].strip()
    notes: list[ScoreLineNote] = []

    # Group opens into score lines: consecutive opens that form a continuous
    # score (e.g. 27...Bf6 then 28.Qd2) share one note on the last move.
    i = 0
    while i < len(opens):
        group = [opens[i]]
        j = i + 1
        while j < len(opens):
            prev = group[-1]
            nxt = opens[j]
            # Only glue if nothing but whitespace between labels
            gap = text[prev.end() : nxt.start()]
            if gap.strip():
                break
            prev_fm = int(prev.group("num"))
            nxt_fm = int(nxt.group("num"))
            if nxt_fm < prev_fm or nxt_fm > prev_fm + 1:
                break
            group.append(nxt)
            j += 1

        last = group[-1]
        prose_start = last.end()
        # Informator eval after SAN is move annotation, not prose lead-in
        m_ev = re.match(r"\s*(?:\+-|-\+|±|∓)", text[prose_start:])
        if m_ev:
            prose_start += m_ev.end()
        prose_end = opens[j].start() if j < len(opens) else min(len(text), prose_start + 8000)
        # If next open is mid-prose variation that somehow got in, still cut there
        prose = text[prose_start:prose_end].strip()
        prose = re.sub(r"^(?:\+-|-\+|±|∓)\s*", "", prose)

        # Skip empty / label-only crumbs; keep short coaching cues ("But now:")
        if prose and not MOVE_LABEL_RE.fullmatch(prose):
            if len(prose) >= 12 or _COACHING_OPEN_RE.match(prose):
                notes.append(
                    ScoreLineNote(
                        fullmove=int(last.group("num")),
                        side=_label_side(last),
                        san=last.group("move"),
                        text=prose[:8000],
                        label_start=last.start(),
                        label_end=last.end(),
                    )
                )
        i = j

    return preamble, notes


def move_head_matches(text: str) -> list[re.Match[str]]:
    """All Rule-A move heads in text (for OCR walk / tests)."""
    return list(MOVE_HEAD_RE.finditer(text or ""))
