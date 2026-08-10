from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chess_coach.features import PositionFeatures
from chess_coach.ontology.cards import pattern_keyword_set
from chess_coach.ontology.load import expand_related
from chess_coach.rag.embeddings import get_embedder
from chess_coach.rag.ingest import get_collection


@dataclass
class Passage:
    text: str
    book: str
    chapter: str
    themes: list[str]
    score: float
    source_path: str = ""
    matched_patterns: list[str] | None = None


_OPENING_BOOK_HINTS = (
    "opening",
    "openings",
    "sicilian",
    "french",
    "caro",
    "indian",
    "nimzo",
    "ruy",
    "lopez",
    "italian",
    "english",
    "gambit",
    "theory",
    "repertoire",
)


def _theme_bonus(passage_themes: list[str], query_themes: list[str]) -> float:
    if not query_themes:
        return 0.0
    overlap = set(t.lower() for t in passage_themes) & set(t.lower() for t in query_themes)
    if not overlap:
        return 0.0
    return 0.08 * len(overlap)


def _opening_book_bonus(book: str, chapter: str, *, want_opening: bool) -> float:
    if not want_opening:
        return 0.0
    blob = f"{book} {chapter}".lower()
    return 0.04 if any(h in blob for h in _OPENING_BOOK_HINTS) else 0.0


def _pattern_bonus(
    lowered: str,
    pattern_ids: list[str],
    keywords: set[str],
    meta_patterns: list[str],
) -> tuple[float, list[str], bool]:
    """Boost passages tagged at ingest and/or mentioning ontology keywords."""
    if not pattern_ids and not keywords and not meta_patterns:
        return 0.0, [], False
    matched: list[str] = []
    bonus = 0.0
    hit = False
    meta_set = set(meta_patterns)
    for pid in pattern_ids:
        if pid in meta_set:
            matched.append(pid)
            bonus += 0.18
            hit = True
            continue
        token = pid.split(".")[-1].replace("_", " ")
        if token and token in lowered:
            matched.append(pid)
            bonus += 0.12
            hit = True
    for key in keywords:
        if len(key) < 4:
            continue
        if key in lowered:
            hit = True
            bonus += 0.05
            break
    return min(bonus, 0.35), matched, hit


def retrieve_passages(
    features: PositionFeatures,
    config: dict[str, Any],
    *,
    k: int | None = None,
) -> list[Passage]:
    rag = config["rag"]
    ont_dir = (config.get("ontology") or {}).get("dir")
    want_opening = features.phase == "opening" or "opening" in features.themes
    if k is not None:
        top_k = k
    elif want_opening:
        top_k = int(rag.get("top_k_opening", rag.get("top_k", 4) + 2))
    else:
        top_k = int(rag.get("top_k", 4))
    min_score = float(rag.get("min_score", 0.42))
    if want_opening:
        min_score = max(min_score, float(rag.get("min_score_opening", 0.45)))
    collection = get_collection(config)
    if collection.count() == 0:
        return []

    pattern_ids = expand_related(
        features.patterns,
        hops=int((config.get("ontology") or {}).get("expand_hops", 1)),
        ontology_dir=ont_dir,
        limit=8,
    )
    keywords = pattern_keyword_set(pattern_ids, ontology_dir=ont_dir)

    query = features.query_text()
    embedder = get_embedder(config["ollama_host"], config["embed_model"], allow_fallback=False)
    query_embedding = embedder.embed([query])[0]

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(max(top_k * 5, top_k), max(collection.count(), 1)),
        include=["documents", "metadatas", "distances"],
    )
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    passages: list[Passage] = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        meta = meta or {}
        themes = [t for t in str(meta.get("themes", "")).split(",") if t]
        book = str(meta.get("book", "unknown"))
        chapter = str(meta.get("chapter", ""))
        similarity = 1.0 - float(dist)
        lowered = (doc or "").lower()
        meta_patterns = [p for p in str(meta.get("patterns", "")).split(",") if p]
        pat_bonus, matched, pat_hit = _pattern_bonus(
            lowered, pattern_ids, keywords, meta_patterns
        )
        score = (
            similarity
            + _theme_bonus(themes, [t for t in features.themes if t != "opening"])
            + _opening_book_bonus(book, chapter, want_opening=want_opening)
            + pat_bonus
        )
        keyword_hit = pat_hit
        for theme in features.themes:
            if theme == "opening":
                continue
            if theme.lower() in lowered:
                keyword_hit = True
                score += 0.06
                break
        if features.opening:
            tokens = [t for t in features.opening.lower().split() if len(t) > 3][:3]
            if tokens and all(t in lowered for t in tokens[:2]):
                keyword_hit = True
                score += 0.1
        if features.eco and features.eco.lower() in lowered:
            keyword_hit = True
            score += 0.08
        # Prefer ontology-tagged hits: soft floor when patterns fired
        if pattern_ids and not pat_hit and similarity < 0.40:
            continue
        if score < min_score:
            continue
        if similarity < 0.32 and not keyword_hit:
            continue
        passages.append(
            Passage(
                text=doc or "",
                book=book,
                chapter=chapter,
                themes=themes,
                score=score,
                source_path=str(meta.get("source_path", "")),
                matched_patterns=matched or None,
            )
        )

    passages.sort(key=lambda p: p.score, reverse=True)
    return passages[:top_k]
