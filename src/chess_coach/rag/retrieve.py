from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from chess_coach.features import PositionFeatures, extract_features, narrative_seed_for_key
from chess_coach.ontology.cards import pattern_keyword_set
from chess_coach.ontology.load import expand_related
from chess_coach.rag.embeddings import get_embedder
from chess_coach.rag.ingest import get_collection
from chess_coach.rag.summarize_knowledge import (
    get_summaries_collection,
    summary_is_teachable,
)
from chess_coach.rag.synthesize_annotated import fen_key, get_annotated_collection

SourceKind = Literal["knowledge_summary", "annotated_game", "book"]


@dataclass
class Passage:
    text: str
    book: str
    chapter: str
    themes: list[str]
    score: float
    source_path: str = ""
    matched_patterns: list[str] | None = None
    source: SourceKind = "book"
    quality: str = ""
    game: str = ""
    san: str = ""
    fen: str = ""
    similar_games: str = ""


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


def _score_hits(
    *,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    distances: list[float],
    features: PositionFeatures,
    pattern_ids: list[str],
    keywords: set[str],
    want_opening: bool,
    min_score: float,
    source_default: SourceKind,
    query_fen_key: str = "",
    query_eco: str = "",
) -> list[Passage]:
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

        quality = str(meta.get("quality") or "")
        if quality == "curated":
            score += 0.12
        elif quality == "draft":
            score += 0.02
        elif quality == "summary":
            score += 0.1

        meta_fen_key = str(meta.get("fen_key") or "")
        if query_fen_key and meta_fen_key and query_fen_key == meta_fen_key:
            score += 0.2
            keyword_hit = True
        meta_eco = str(meta.get("eco") or "")
        if query_eco and meta_eco and query_eco.upper() == meta_eco.upper():
            score += 0.06
        eco_hints = [e for e in str(meta.get("eco_hints", "")).split(",") if e]
        if query_eco and query_eco.upper() in {e.upper() for e in eco_hints}:
            score += 0.1
            keyword_hit = True
        # Smart PGN similarity: same ECO family letter
        if query_eco and eco_hints:
            q_family = query_eco[0].upper()
            if any(e[:1].upper() == q_family for e in eco_hints):
                score += 0.04

        source_raw = str(meta.get("source_kind") or source_default)
        if source_raw == "knowledge_summary":
            source: SourceKind = "knowledge_summary"
        elif source_raw == "annotated_game":
            source = "annotated_game"
        else:
            source = "book"

        if pattern_ids and not pat_hit and similarity < 0.40 and source == "book":
            continue
        if score < min_score:
            continue
        if similarity < 0.32 and not keyword_hit and source == "book":
            continue

        similar_games = str(meta.get("similar_games") or "")
        text_out = doc or ""
        if source == "knowledge_summary" and similar_games:
            first_game = similar_games.split("||")[0].strip()
            if first_game and first_game.lower() not in text_out.lower():
                text_out = _clip_tip(f"{text_out} cf. {first_game}")

        game_label = str(meta.get("game") or "")
        if not game_label and similar_games:
            game_label = similar_games.split("||")[0].strip()[:80]

        passages.append(
            Passage(
                text=text_out,
                book=book,
                chapter=chapter,
                themes=themes,
                score=score,
                source_path=str(meta.get("source_path", "")),
                matched_patterns=matched or None,
                source=source,
                quality=quality,
                game=game_label,
                san=str(meta.get("san") or ""),
                fen=str(meta.get("fen") or ""),
                similar_games=similar_games,
            )
        )
    passages.sort(key=lambda p: p.score, reverse=True)
    return passages


def _clip_tip(text: str, limit: int = 420) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


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

    return _score_hits(
        documents=documents,
        metadatas=metadatas,
        distances=distances,
        features=features,
        pattern_ids=pattern_ids,
        keywords=keywords,
        want_opening=want_opening,
        min_score=min_score,
        source_default="book",
        query_eco=features.eco,
    )[:top_k]


def merge_retrieve_pools(
    *,
    annotated: list[Passage],
    summaries: list[Passage],
    books: list[Passage],
    top_k: int,
    allow_books: bool,
) -> list[Passage]:
    merged: list[Passage] = []
    seen_text: set[str] = set()

    def _add(pool: list[Passage]) -> None:
        for p in pool:
            if p.source == "knowledge_summary" and not summary_is_teachable(p.text):
                continue
            key = re.sub(r"\s+", " ", p.text.lower())[:80]
            if key in seen_text:
                continue
            seen_text.add(key)
            merged.append(p)
            if len(merged) >= top_k:
                return

    curated = [p for p in annotated if p.quality == "curated"]
    other_ann = [p for p in annotated if p.quality != "curated"]
    _add(curated)
    if len(merged) < top_k:
        _add(other_ann)
    if len(merged) < top_k:
        _add(summaries)
    if len(merged) < top_k and allow_books:
        _add(books)
    return merged[:top_k]


def retrieve_for_position(
    fen: str,
    config: dict[str, Any],
    *,
    themes: list[str] | None = None,
    phase: str | None = None,
    san: str = "",
    best_san: str = "",
    eco: str = "",
    opening: str = "",
    want_count: int = 2,
    narrative: str = "",
    tactical_kind: str = "",
    tactical_head: str = "",
    trap_square: str = "",
    piece_label: str = "",
    drop_cp: int | None = None,
) -> list[Passage]:
    """
    Annotated bookwalk first, then knowledge summaries, then raw book chunks
    only for unresolved opening/ECO theory.
    """
    rag = config.get("rag") or {}
    ont_dir = (config.get("ontology") or {}).get("dir")
    features = extract_features(
        fen,
        eco=eco,
        opening=opening,
        played_san=san,
        best_san=best_san,
        delta_cp=drop_cp,
        ontology_dir=ont_dir,
        tactical_kind=tactical_kind,
        tactical_head=tactical_head,
        trap_square=trap_square,
        piece_label=piece_label,
    )
    if themes:
        merged_themes = list(dict.fromkeys([*themes, *features.themes]))
        features.themes = merged_themes
    if phase:
        features.phase = phase
    if narrative:
        features.narrative = narrative

    want_opening = features.phase == "opening" or "opening" in features.themes
    top_k = max(1, min(int(want_count), 4))
    annotated_k = max(top_k, int(rag.get("annotated_top_k", top_k + 1)))
    summary_k = max(top_k, int(rag.get("summaries_top_k", top_k + 2)))
    book_k = int(rag.get("top_k", 4))
    min_sum = float(rag.get("min_score_summaries", 0.36))
    min_ann = float(rag.get("min_score_annotated", 0.38))
    min_book = float(rag.get("min_score", 0.42))
    if want_opening:
        min_book = max(min_book, float(rag.get("min_score_opening", 0.45)))

    pattern_ids = expand_related(
        features.patterns,
        hops=int((config.get("ontology") or {}).get("expand_hops", 1)),
        ontology_dir=ont_dir,
        limit=8,
    )
    keywords = pattern_keyword_set(pattern_ids, ontology_dir=ont_dir)
    query = features.query_text()
    if not narrative and not san and themes:
        keyish = next((t for t in themes if "." in t), "")
        if keyish:
            query = narrative_seed_for_key(
                keyish, opening=opening, eco=eco
            )

    try:
        embedder = get_embedder(
            config["ollama_host"], config["embed_model"], allow_fallback=False
        )
    except Exception:
        return []
    query_embedding = embedder.embed([query])[0]
    q_fen = fen_key(fen)
    q_eco = features.eco or eco

    summaries: list[Passage] = []
    try:
        sum_coll = get_summaries_collection(config)
        if sum_coll.count() > 0:
            raw = sum_coll.query(
                query_embeddings=[query_embedding],
                n_results=min(max(summary_k * 6, summary_k), max(sum_coll.count(), 1)),
                include=["documents", "metadatas", "distances"],
            )
            summaries = _score_hits(
                documents=(raw.get("documents") or [[]])[0],
                metadatas=(raw.get("metadatas") or [[]])[0],
                distances=(raw.get("distances") or [[]])[0],
                features=features,
                pattern_ids=pattern_ids,
                keywords=keywords,
                want_opening=want_opening,
                min_score=min_sum,
                source_default="knowledge_summary",
                query_fen_key=q_fen,
                query_eco=q_eco,
            )
    except Exception:
        summaries = []

    annotated: list[Passage] = []
    try:
        ann_coll = get_annotated_collection(config)
        if ann_coll.count() > 0:
            raw = ann_coll.query(
                query_embeddings=[query_embedding],
                n_results=min(max(annotated_k * 6, annotated_k), max(ann_coll.count(), 1)),
                include=["documents", "metadatas", "distances"],
            )
            annotated = _score_hits(
                documents=(raw.get("documents") or [[]])[0],
                metadatas=(raw.get("metadatas") or [[]])[0],
                distances=(raw.get("distances") or [[]])[0],
                features=features,
                pattern_ids=pattern_ids,
                keywords=keywords,
                want_opening=want_opening,
                min_score=min_ann,
                source_default="annotated_game",
                query_fen_key=q_fen,
                query_eco=q_eco,
            )
    except Exception:
        annotated = []

    books: list[Passage] = []
    try:
        book_coll = get_collection(config)
        if book_coll.count() > 0:
            raw = book_coll.query(
                query_embeddings=[query_embedding],
                n_results=min(max(book_k * 5, book_k), max(book_coll.count(), 1)),
                include=["documents", "metadatas", "distances"],
            )
            books = _score_hits(
                documents=(raw.get("documents") or [[]])[0],
                metadatas=(raw.get("metadatas") or [[]])[0],
                distances=(raw.get("distances") or [[]])[0],
                features=features,
                pattern_ids=pattern_ids,
                keywords=keywords,
                want_opening=want_opening,
                min_score=min_book,
                source_default="book",
                query_eco=q_eco,
            )
    except Exception:
        books = []

    allow_books = want_opening and not tactical_kind and features.phase == "opening"
    return merge_retrieve_pools(
        annotated=annotated,
        summaries=summaries,
        books=books,
        top_k=top_k,
        allow_books=allow_books,
    )


def passages_to_nuggets(passages: list[Passage]) -> list[dict[str, Any]]:
    nuggets: list[dict[str, Any]] = []
    for i, p in enumerate(passages):
        label = p.book
        if p.game:
            label = f"{p.book} · {p.game.replace('_', ' ')}"
        elif p.chapter:
            label = f"{p.book} · {p.chapter}"
        card_id = f"rag:{p.source}:{p.quality or 'book'}:{i}"
        nuggets.append(
            {
                "cardId": card_id,
                "label": label[:80],
                "text": p.text,
                "book": p.book,
                "game": p.game,
                "source": p.source,
                "quality": p.quality,
                "score": round(p.score, 4),
            }
        )
    return nuggets
