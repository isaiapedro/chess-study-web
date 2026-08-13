from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess
import chess.pgn
import yaml

from chess_coach.features import extract_features
from chess_coach.ontology.tag import tag_text_patterns
from chess_coach.rag.embeddings import get_embedder
from chess_coach.rag.ingest import get_collection

BOOK_COMMENT_RE = re.compile(
    r"\[Book:(curated|draft)\|([^\]]+)\]\s*(.*?)(?=\s*\|\s*\[Engine/RAG\]|\Z)",
    re.DOTALL | re.IGNORECASE,
)

MAX_TEXT_CHARS = 400


@dataclass
class AnnotatedChunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


def fen_key(fen: str) -> str:
    return fen.split(" ")[0] if fen else ""


def _clip(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


def _chunk_id(parts: list[str]) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _load_yaml_notes(yaml_path: Path) -> dict[tuple[int, str, str], dict[str, Any]]:
    if not yaml_path.is_file():
        return {}
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    out: dict[tuple[int, str, str], dict[str, Any]] = {}
    book = str(data.get("source_book") or data.get("book") or "")
    chapter = str(data.get("chapter") or "")
    quality = "curated" if str(data.get("source") or "").lower() == "curated" else "draft"
    for note in data.get("notes") or []:
        try:
            fullmove = int(note.get("fullmove"))
        except (TypeError, ValueError):
            continue
        side = str(note.get("side") or "").lower()
        san = str(note.get("san") or "").strip()
        text = str(note.get("text") or "").strip()
        if not san or not text:
            continue
        out[(fullmove, side, san)] = {
            "text": text,
            "book": book,
            "chapter": chapter,
            "quality": quality,
        }
    return out


def _parse_book_comment(comment: str) -> tuple[str, str, str] | None:
    if not comment:
        return None
    match = BOOK_COMMENT_RE.search(comment)
    if not match:
        return None
    quality = match.group(1).lower()
    book = match.group(2).strip()
    text = match.group(3).strip()
    if not text:
        return None
    return quality, book, text


def extract_chunks_from_pgn(
    path: Path,
    *,
    ontology_dir: str | None = None,
) -> list[AnnotatedChunk]:
    yaml_path = path.with_suffix(".book_notes.yaml")
    if not yaml_path.is_file():
        alt = Path(str(path).replace(".pgn", ".book_notes.yaml"))
        if alt.is_file():
            yaml_path = alt
    yaml_notes = _load_yaml_notes(yaml_path)

    with path.open(encoding="utf-8", errors="replace") as handle:
        game = chess.pgn.read_game(handle)
    if game is None:
        return []

    headers = game.headers
    white = headers.get("White", "")
    black = headers.get("Black", "")
    year = (headers.get("Date") or "")[:4]
    eco = headers.get("ECO", "")
    opening = headers.get("Opening", "") or headers.get("BookChapter", "")
    source = headers.get("Source", "")
    book_chapter = headers.get("BookChapter", "")
    game_label = f"{white}_vs_{black}_{year}".replace(" ", "_")

    chunks: list[AnnotatedChunk] = []
    board = game.board()
    node = game
    ply = 0

    while node.variations:
        next_node = node.variation(0)
        move = next_node.move
        fen_before = board.fen()
        fullmove = board.fullmove_number
        side = "white" if board.turn == chess.WHITE else "black"
        san = board.san(move)
        board.push(move)
        ply += 1

        yaml_hit = yaml_notes.get((fullmove, side, san))
        quality = ""
        book = ""
        chapter = book_chapter
        text = ""
        if yaml_hit:
            quality = str(yaml_hit.get("quality") or "curated")
            book = str(yaml_hit.get("book") or "")
            chapter = str(yaml_hit.get("chapter") or chapter)
            text = str(yaml_hit.get("text") or "")
        else:
            parsed = _parse_book_comment(next_node.comment or "")
            if parsed:
                quality, book, text = parsed

        if not text:
            node = next_node
            continue

        clipped = _clip(text)
        if len(clipped) < 40:
            node = next_node
            continue

        features = extract_features(
            fen_before,
            eco=eco,
            opening=opening,
            played_san=san,
            ontology_dir=ontology_dir,
        )
        patterns = tag_text_patterns(
            clipped, ontology_dir=ontology_dir, book_patterns=features.patterns
        )
        themes = list(dict.fromkeys([*features.themes, *features.patterns]))
        cid = _chunk_id(
            [str(path.resolve()), str(ply), fen_key(fen_before), san, quality]
        )
        meta = {
            "fen": fen_before,
            "fen_key": fen_key(fen_before),
            "san": san,
            "ply": ply,
            "fullmove": fullmove,
            "side": side,
            "eco": eco,
            "opening": opening,
            "themes": ",".join(themes),
            "patterns": ",".join(patterns or features.patterns),
            "white": white,
            "black": black,
            "year": year,
            "game": game_label,
            "masters_source": source,
            "book": book or "annotated",
            "chapter": chapter,
            "quality": quality or "draft",
            "source_path": str(path.resolve()),
            "source_kind": "annotated_game",
        }
        chunks.append(AnnotatedChunk(chunk_id=cid, text=clipped, metadata=meta))
        node = next_node

    return chunks


def get_annotated_collection(config: dict[str, Any]):
    rag = dict(config.get("rag") or {})
    annotated_name = rag.get("annotated_collection", "chess_annotated_positions")
    cfg = {**config, "rag": {**rag, "collection": annotated_name}}
    return get_collection(cfg)


def synthesize_annotated(
    config: dict[str, Any],
    *,
    pgn_dir: Path | None = None,
    reset: bool = False,
    allow_hash_fallback: bool = False,
) -> int:
    rag = config.setdefault("rag", {})
    ont_dir = (config.get("ontology") or {}).get("dir")
    root = Path(__file__).resolve().parents[3]
    directory = pgn_dir or Path(rag.get("annotated_pgn_dir", "data/annotated/bookwalk"))
    if not directory.is_absolute():
        directory = (root / directory).resolve()

    if reset:
        from chromadb import PersistentClient

        client = PersistentClient(path=str(rag["persist_dir"]))
        name = rag.get("annotated_collection", "chess_annotated_positions")
        try:
            client.delete_collection(name)
        except Exception:
            pass

    collection = get_annotated_collection(config)
    embedder = get_embedder(
        config["ollama_host"],
        config["embed_model"],
        allow_fallback=allow_hash_fallback,
    )
    print(f"Using embedder: {type(embedder).__name__}", flush=True)
    print(f"Scanning {directory}", flush=True)

    files = sorted(directory.glob("*_bookwalk.pgn"))
    if not files:
        files = sorted(directory.glob("*.pgn"))
    total = 0
    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_meta: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal total, batch_ids, batch_docs, batch_meta
        if not batch_ids:
            return
        embeddings = embedder.embed(batch_docs)
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
            embeddings=embeddings,
        )
        total += len(batch_ids)
        print(f"  upserted {len(batch_ids)} (total={total})", flush=True)
        batch_ids, batch_docs, batch_meta = [], [], []

    for idx, path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] {path.name}", flush=True)
        try:
            chunks = extract_chunks_from_pgn(path, ontology_dir=ont_dir)
        except Exception as exc:
            print(f"  SKIP {exc}", flush=True)
            continue
        print(f"  {len(chunks)} annotated plies", flush=True)
        for chunk in chunks:
            batch_ids.append(chunk.chunk_id)
            batch_docs.append(chunk.text)
            batch_meta.append(chunk.metadata)
            if len(batch_ids) >= 8:
                flush()
    flush()
    print(f"Synthesized {total} annotated position chunks into {rag.get('annotated_collection')}")
    return total
