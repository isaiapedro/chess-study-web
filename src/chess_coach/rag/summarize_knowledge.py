from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from chess_coach.masters_db import LocalMastersDB
from chess_coach.ontology.tag import tag_text_patterns
from chess_coach.rag.chunking import detect_themes, load_book_chunks
from chess_coach.rag.embeddings import get_embedder
from chess_coach.rag.ingest import get_collection, ingest_path
from chess_coach.rag.synthesize_annotated import synthesize_annotated

SUMMARY_PROMPT = """You write short chess knowledge cards for a RAG coach.

From the book excerpt, write 2–4 sentences that teach ONE concrete idea
(structure, attack, imbalance, plan, or tactic motif). No fluff. No move lists
longer than 3 plies. Do not invent game results. Plain English.

Return ONLY the summary text."""

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
ECO_HINT_RE = re.compile(r"\b([A-E]\d{2})\b")
_JUNK_RE = re.compile(
    r"(?:www\.|https?://|blog\s*spot|qualitychess\.co|quality chess uk|"
    r"\bcontents\b|\bforeword\b|\bkeys to symbol|"
    r"\bcopyright\b|\ball rights reserved\b|\bfirst edition\b|\bisbn\b|"
    r"introduction within chess literature)",
    re.I,
)
_TEACH_WORDS = (
    "pawn chain",
    "isolani",
    "hanging pawns",
    "minority attack",
    "open file",
    "passed pawn",
    "king safety",
    "piece activity",
    "pawn break",
    "maroczy",
    "hedgehog",
    "outpost",
    "initiative",
    "prophylaxis",
    "exchange",
    "attack",
    "defence",
    "defense",
    "structure",
    "plan",
    "break",
    "centre",
    "center",
    "castle",
)
_MOVE_RE = re.compile(
    r"\b(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?)\b"
)
MAX_SUMMARY = 420


def chunk_is_teachable(text: str) -> bool:
    """Drop TOC / publisher chrome before summarizing."""
    body = (text or "").strip()
    if len(body) < 160:
        return False
    head = body[:500]
    if _JUNK_RE.search(head):
        return False
    digits = sum(c.isdigit() for c in body)
    if digits / max(len(body), 1) > 0.16:
        return False
    lowered = body.lower()
    teach_hits = sum(1 for w in _TEACH_WORDS if w in lowered)
    move_hits = len(_MOVE_RE.findall(body))
    if teach_hits < 2 and move_hits < 2:
        return False
    short_nums = len(re.findall(r"\b\d{1,3}\b", body))
    if short_nums > 40:
        return False
    return True


def summary_is_teachable(text: str) -> bool:
    body = (text or "").strip()
    if len(body) < 70:
        return False
    if _JUNK_RE.search(body):
        return False
    if sum(c.isdigit() for c in body) / max(len(body), 1) >= 0.12:
        return False
    lowered = body.lower()
    teach_hits = sum(1 for w in _TEACH_WORDS if w in lowered)
    move_hits = len(_MOVE_RE.findall(body))
    return teach_hits >= 1 or move_hits >= 1


@dataclass
class KnowledgeSummary:
    summary_id: str
    text: str
    book: str
    chapter: str
    themes: list[str]
    patterns: list[str]
    eco_hints: list[str]
    similar_games: list[str]
    source_path: str
    source_chunk_id: str


def _clip(text: str, limit: int = MAX_SUMMARY) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


def _sid(parts: list[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _extractive_summary(raw: str, themes: list[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", raw.strip())
    keep: list[str] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40:
            continue
        if re.fullmatch(r"[\d\s\.…\-–—]+", s):
            continue
        keep.append(s)
        if len(keep) >= 3:
            break
    body = " ".join(keep) if keep else raw[:280]
    theme_bit = f" Themes: {', '.join(themes[:4])}." if themes else ""
    return _clip(body + theme_bit)


def _ollama_summary(raw: str, config: dict[str, Any]) -> str | None:
    host = str(config.get("ollama_host") or "http://localhost:11434").rstrip("/")
    model = str(config.get("chat_model") or "qwen3:8b")
    excerpt = raw[:1600]
    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SUMMARY_PROMPT},
                        {"role": "user", "content": excerpt},
                    ],
                },
            )
            response.raise_for_status()
            message = response.json().get("message") or {}
            content = str(message.get("content") or "").strip()
            content = _THINK_RE.sub("", content).strip()
            if len(content) < 40:
                return None
            return _clip(content)
    except Exception:
        return None


def _eco_hints(text: str, themes: list[str]) -> list[str]:
    found = [m.group(1).upper() for m in ECO_HINT_RE.finditer(text or "")]
    # Theme → coarse ECO family hints for similarity seeding
    theme_blob = " ".join(themes).lower()
    if "sicilian" in theme_blob:
        found.extend(["B90", "B70", "B80"])
    if "french" in theme_blob:
        found.extend(["C00", "C11"])
    if "caro" in theme_blob:
        found.extend(["B12", "B18"])
    if "king" in theme_blob and "indian" in theme_blob:
        found.extend(["E60", "E90"])
    if "queen's gambit" in theme_blob or "qgd" in theme_blob or "queens_gambit" in theme_blob:
        found.extend(["D30", "D37"])
    if "ruy" in theme_blob or "lopez" in theme_blob:
        found.extend(["C60", "C90"])
    if "italian" in theme_blob:
        found.extend(["C50", "C54"])
    if "english" in theme_blob:
        found.extend(["A20", "A25"])
    if "iqp" in theme_blob or "isolated" in theme_blob:
        found.extend(["D26", "D42"])
    out: list[str] = []
    for eco in found:
        if eco not in out:
            out.append(eco)
    return out[:6]


def _link_similar_games(
    ecos: list[str],
    config: dict[str, Any],
    *,
    per_eco: int = 2,
) -> list[str]:
    masters_cfg = config.get("masters") or {}
    if not masters_cfg.get("enabled", True):
        return []
    index_path = Path(masters_cfg.get("index_path") or "")
    pgn_dir = Path(masters_cfg.get("pgn_dir") or "") if masters_cfg.get("pgn_dir") else None
    if not index_path.is_file():
        return []
    db = LocalMastersDB(index_path, pgn_dir)
    labels: list[str] = []
    for eco in ecos:
        for hit in db.find_by_eco(eco, limit=per_eco):
            label = f"{hit.white} vs {hit.black} {hit.year or ''} ({hit.eco})".strip()
            if label not in labels:
                labels.append(label)
            if len(labels) >= 4:
                return labels
    return labels


def _bookwalk_game_labels(config: dict[str, Any], themes: list[str]) -> list[str]:
    """Soft-match annotated bookwalk headers when themes overlap chapter naming."""
    rag = config.get("rag") or {}
    root = Path(__file__).resolve().parents[3]
    directory = Path(rag.get("annotated_pgn_dir", "data/annotated/bookwalk"))
    if not directory.is_absolute():
        directory = (root / directory).resolve()
    if not directory.is_dir():
        return []
    theme_set = {t.lower().replace("_", " ") for t in themes}
    labels: list[str] = []
    for path in sorted(directory.glob("*_bookwalk.pgn"))[:80]:
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            continue
        blob = head.lower()
        if theme_set and not any(t in blob for t in theme_set if len(t) > 3):
            # still allow Chess Structures family files when structure themes present
            if not any(k in " ".join(theme_set) for k in ("iqp", "hanging", "pawn", "file", "chain")):
                continue
        white = re.search(r'\[White\s+"([^"]+)"\]', head)
        black = re.search(r'\[Black\s+"([^"]+)"\]', head)
        year = re.search(r'\[Date\s+"([^"]+)"\]', head)
        eco = re.search(r'\[ECO\s+"([^"]+)"\]', head)
        if not (white and black):
            continue
        y = (year.group(1)[:4] if year else "")
        e = eco.group(1) if eco else ""
        label = f"{white.group(1)} vs {black.group(1)} {y} ({e}) [bookwalk]".strip()
        labels.append(label)
        if len(labels) >= 2:
            break
    return labels


def summarize_book_chunks(
    path: Path,
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    max_chunks: int | None = None,
) -> list[KnowledgeSummary]:
    chunk_cfg = config.get("chunk") or {}
    ont_dir = (config.get("ontology") or {}).get("dir")
    chunks = load_book_chunks(
        path,
        max_chars=int(chunk_cfg.get("max_chars", 700)),
        overlap_chars=int(chunk_cfg.get("overlap_chars", 80)),
    )
    # Scan deeper than max_chunks so TOC pages can be skipped.
    scan_limit = None
    if max_chunks is not None:
        scan_limit = max(max_chunks * 8, max_chunks)
        chunks = chunks[:scan_limit]
    out: list[KnowledgeSummary] = []
    for chunk in chunks:
        if not chunk_is_teachable(chunk.text):
            continue
        themes = detect_themes(chunk.text, chunk.themes)
        patterns = tag_text_patterns(
            chunk.text, ontology_dir=ont_dir, book_patterns=getattr(chunk, "book_patterns", None) or []
        )
        text = None
        if use_llm:
            text = _ollama_summary(chunk.text, config)
        if not text:
            text = _extractive_summary(chunk.text, themes)
        if not summary_is_teachable(text):
            continue
        if len(text) < 40:
            continue
        ecos = _eco_hints(f"{chunk.text}\n{text}", themes)
        similar = _link_similar_games(ecos, config)
        similar.extend(_bookwalk_game_labels(config, themes))
        # dedupe preserve order
        seen: set[str] = set()
        similar_u = []
        for g in similar:
            if g not in seen:
                seen.add(g)
                similar_u.append(g)
        sid = _sid([chunk.chunk_id, text[:80]])
        out.append(
            KnowledgeSummary(
                summary_id=sid,
                text=text,
                book=chunk.book,
                chapter=chunk.chapter,
                themes=themes,
                patterns=patterns,
                eco_hints=ecos,
                similar_games=similar_u[:4],
                source_path=chunk.source_path,
                source_chunk_id=chunk.chunk_id,
            )
        )
        if max_chunks is not None and len(out) >= max_chunks:
            break
    return out


def get_summaries_collection(config: dict[str, Any]):
    rag = dict(config.get("rag") or {})
    name = rag.get("summaries_collection", "chess_knowledge_summaries")
    cfg = {**config, "rag": {**rag, "collection": name}}
    return get_collection(cfg)


def write_summaries_jsonl(summaries: list[KnowledgeSummary], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for s in summaries:
            handle.write(
                json.dumps(
                    {
                        "id": s.summary_id,
                        "text": s.text,
                        "book": s.book,
                        "chapter": s.chapter,
                        "themes": s.themes,
                        "patterns": s.patterns,
                        "eco_hints": s.eco_hints,
                        "similar_games": s.similar_games,
                        "source_path": s.source_path,
                        "source_chunk_id": s.source_chunk_id,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def embed_summaries(
    summaries: list[KnowledgeSummary],
    config: dict[str, Any],
    *,
    reset: bool = False,
    allow_hash_fallback: bool = False,
) -> int:
    rag = config.setdefault("rag", {})
    if reset:
        from chromadb import PersistentClient

        client = PersistentClient(path=str(rag["persist_dir"]))
        name = rag.get("summaries_collection", "chess_knowledge_summaries")
        try:
            client.delete_collection(name)
        except Exception:
            pass
    collection = get_summaries_collection(config)
    embedder = get_embedder(
        config["ollama_host"],
        config["embed_model"],
        allow_fallback=allow_hash_fallback,
    )
    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_meta: list[dict[str, Any]] = []
    total = 0

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
        print(f"  upserted summaries {len(batch_ids)} (total={total})", flush=True)
        batch_ids, batch_docs, batch_meta = [], [], []

    for s in summaries:
        meta = {
            "book": s.book,
            "chapter": s.chapter,
            "themes": ",".join(s.themes),
            "patterns": ",".join(s.patterns),
            "eco_hints": ",".join(s.eco_hints),
            "similar_games": " || ".join(s.similar_games),
            "source_path": s.source_path,
            "source_chunk_id": s.source_chunk_id,
            "source_kind": "knowledge_summary",
            "quality": "summary",
        }
        batch_ids.append(s.summary_id)
        batch_docs.append(s.text)
        batch_meta.append(meta)
        if len(batch_ids) >= 8:
            flush()
    flush()
    return total


def summarize_knowledge_path(
    path: Path,
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    max_chunks_per_book: int | None = 24,
    reset: bool = False,
    allow_hash_fallback: bool = False,
    jsonl_dir: Path | None = None,
) -> int:
    root = Path(__file__).resolve().parents[3]
    out_dir = jsonl_dir or Path(config.get("rag", {}).get("summaries_dir", "data/knowledge_summaries"))
    if not out_dir.is_absolute():
        out_dir = (root / out_dir).resolve()

    files: list[Path]
    if path.is_dir():
        files = sorted(
            [p for p in path.rglob("*") if p.suffix.lower() in {".pdf", ".txt"} and p.is_file()]
        )
    else:
        files = [path]

    all_summaries: list[KnowledgeSummary] = []
    for idx, file_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] summarizing {file_path.name}", flush=True)
        try:
            summaries = summarize_book_chunks(
                file_path,
                config,
                use_llm=use_llm,
                max_chunks=max_chunks_per_book,
            )
        except Exception as exc:
            print(f"  SKIP {exc}", flush=True)
            continue
        print(f"  {len(summaries)} summaries", flush=True)
        slug = re.sub(r"[^a-z0-9]+", "_", file_path.stem.lower()).strip("_")[:60]
        write_summaries_jsonl(summaries, out_dir / f"{slug}.jsonl")
        all_summaries.extend(summaries)

    return embed_summaries(
        all_summaries,
        config,
        reset=reset,
        allow_hash_fallback=allow_hash_fallback,
    )


def run_knowledge_pipeline(
    books_path: Path,
    config: dict[str, Any],
    *,
    skip_ingest: bool = False,
    skip_summarize: bool = False,
    skip_annotated: bool = False,
    use_llm: bool = True,
    max_chunks_per_book: int | None = 24,
    allow_hash_fallback: bool = False,
    reset_summaries: bool = False,
) -> dict[str, int]:
    """
    PDF ingest → knowledge summaries (+ PGN links) → embed RAG
    → optional annotated bookwalk synthesize.
    """
    stats = {"ingested": 0, "summaries": 0, "annotated": 0}
    if not skip_ingest:
        print("=== 1/3 ingest PDFs ===", flush=True)
        stats["ingested"] = ingest_path(
            books_path,
            config,
            reset=False,
            allow_hash_fallback=allow_hash_fallback,
        )
    if not skip_summarize:
        print("=== 2/3 summarize + link PGN + embed ===", flush=True)
        stats["summaries"] = summarize_knowledge_path(
            books_path,
            config,
            use_llm=use_llm,
            max_chunks_per_book=max_chunks_per_book,
            reset=reset_summaries,
            allow_hash_fallback=allow_hash_fallback,
        )
    if not skip_annotated:
        print("=== 3/3 synthesize annotated bookwalk positions ===", flush=True)
        try:
            stats["annotated"] = synthesize_annotated(
                config, allow_hash_fallback=allow_hash_fallback
            )
        except Exception as exc:
            print(f"annotated synthesize skipped: {exc}", flush=True)
    return stats
