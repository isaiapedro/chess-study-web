from __future__ import annotations

import re

from chess_coach.analyze import CriticalMoment
from chess_coach.rag.retrieve import Passage

_JUNK_RE = re.compile(
    r"(?:www\.|https?://|blog\s*spot|chessbase\.com|"
    r"introduction within chess literature|"
    r"how they have evolved through the years|"
    r"early in the 21st|"
    r"ultimately,\s*opening theory comprises|"
    r"within chess literature there is a huge)",
    re.I,
)
_MOVE_RE = re.compile(
    r"\b(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)\b"
)


def passage_is_concrete(passage: Passage, moment: CriticalMoment) -> bool:
    """Reject generic intros; require move/ECO/opening overlap with this ply."""
    text = " ".join((passage.text or "").split())
    if len(text) < 90:
        return False
    if _JUNK_RE.search(text):
        return False
    # OCR garbage / truncated mid-word dumps
    if re.search(r"\b\w{1,2}\xad\w", text):
        return False

    lowered = text.lower()
    feats = moment.features
    hit = False
    if feats.eco and feats.eco.lower() in lowered:
        hit = True
    if feats.opening:
        # require a meaningful chunk of the opening name
        tokens = [t for t in re.findall(r"[a-zA-Z]{4,}", feats.opening.lower()) if t not in {"with", "from", "game"}]
        if tokens and sum(1 for t in tokens if t in lowered) >= min(2, len(tokens)):
            hit = True
    played = (moment.played_san or "").rstrip("?!+#")
    if played and re.search(rf"\b{re.escape(played)}\b", text):
        hit = True
    best = (moment.best_san or "").rstrip("?!+#")
    if best and best != played and re.search(rf"\b{re.escape(best)}\b", text):
        hit = True
    moves = _MOVE_RE.findall(text)
    if len(moves) >= 3:
        hit = True
    # thematic: king's indian / isolani etc. only if theme word appears AND some moves
    for theme in feats.themes:
        if theme in {"opening", "endgame"}:
            continue
        if theme.lower() in lowered and len(moves) >= 2:
            hit = True
            break
    return hit


def filter_passages(
    passages: list[Passage],
    moment: CriticalMoment,
    *,
    used_fingerprints: set[str] | None = None,
    limit: int = 2,
) -> list[Passage]:
    used = used_fingerprints if used_fingerprints is not None else set()
    out: list[Passage] = []
    for passage in passages:
        if not passage_is_concrete(passage, moment):
            continue
        fp = re.sub(r"\s+", " ", (passage.text or "")[:160]).lower()
        if fp in used:
            continue
        used.add(fp)
        out.append(passage)
        if len(out) >= limit:
            break
    return out
