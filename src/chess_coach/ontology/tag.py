from __future__ import annotations

from chess_coach.ontology.load import load_ontology


def tag_text_patterns(
    text: str,
    *,
    ontology_dir: str | None = None,
    book_patterns: list[str] | None = None,
    min_score: int = 2,
    limit: int = 6,
) -> list[str]:
    """
    Keyword/alias tagger for book chunks → ontology pattern IDs.
    `book_patterns` from .themes.yaml lowers the bar (need weaker keyword evidence).
    """
    lowered = " ".join((text or "").lower().split())
    if len(lowered) < 40:
        return []
    catalog = load_ontology(ontology_dir)
    declared = {p for p in (book_patterns or []) if p in catalog}
    scored: list[tuple[int, str]] = []
    for pattern in catalog.values():
        score = 0
        needles = list(pattern.keywords) + list(pattern.aliases) + [pattern.label]
        for kw in needles:
            k = (kw or "").lower().strip()
            if len(k) < 4:
                continue
            if k in lowered:
                score += 2 if len(k) >= 12 else 1
        token = pattern.id.split(".")[-1].replace("_", " ")
        if len(token) >= 4 and token in lowered:
            score += 2
        for prefix in pattern.eco_prefixes:
            if prefix.lower() in lowered:
                score += 2
        threshold = 1 if pattern.id in declared else min_score
        if pattern.id in declared and score > 0:
            score += 1
        if score >= threshold:
            scored.append((score, pattern.id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [pid for _, pid in scored[:limit]]
