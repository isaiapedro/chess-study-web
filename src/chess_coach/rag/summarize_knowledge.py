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


def evenly_spaced_indices(n: int, k: int) -> list[int]:
    """Pick k distinct indices covering [0, n) as evenly as possible."""
    if n <= 0 or k <= 0:
        return []
    if k >= n:
        return list(range(n))
    if k == 1:
        return [n // 2]
    out: list[int] = []
    seen: set[int] = set()
    for i in range(k):
        idx = round(i * (n - 1) / (k - 1))
        idx = max(0, min(n - 1, idx))
        if idx in seen:
            for delta in range(1, n):
                for cand in (idx + delta, idx - delta):
                    if 0 <= cand < n and cand not in seen:
                        idx = cand
                        break
                else:
                    continue
                break
        seen.add(idx)
        out.append(idx)
    return sorted(out)


def select_summary_source_chunks(
    chunks: list[Any],
    max_chunks: int | None,
) -> list[Any]:
    """
    Choose teachable chunks across the *whole* book.

    Prefer chapter-balanced sampling when headings exist; otherwise even
    stride through the full teachable list (not front-of-PDF only).
    """
    teachable = [c for c in chunks if chunk_is_teachable(getattr(c, "text", "") or "")]
    if not teachable:
        return []
    if max_chunks is None or max_chunks <= 0 or len(teachable) <= max_chunks:
        return teachable

    by_chapter: dict[str, list[Any]] = {}
    order: list[str] = []
    for chunk in teachable:
        key = str(getattr(chunk, "chapter", "") or "body").strip() or "body"
        if key not in by_chapter:
            order.append(key)
            by_chapter[key] = []
        by_chapter[key].append(chunk)

    if len(order) <= 1:
        idxs = evenly_spaced_indices(len(teachable), max_chunks)
        return [teachable[i] for i in idxs]

    # At least one per chapter when budget allows, then fill by chapter size.
    selected: list[Any] = []
    used: set[int] = set()

    def add_chunk(chunk: Any) -> bool:
        cid = id(chunk)
        if cid in used:
            return False
        used.add(cid)
        selected.append(chunk)
        return True

    if max_chunks >= len(order):
        for key in order:
            add_chunk(by_chapter[key][len(by_chapter[key]) // 2])
    else:
        chapter_idxs = evenly_spaced_indices(len(order), max_chunks)
        for ci in chapter_idxs:
            group = by_chapter[order[ci]]
            add_chunk(group[len(group) // 2])
        return selected[:max_chunks]

    remaining = max_chunks - len(selected)
    if remaining <= 0:
        return selected[:max_chunks]

    weights = [len(by_chapter[k]) for k in order]
    total_w = sum(weights) or 1
    quotas = [max(0, round(remaining * w / total_w)) for w in weights]
    # Fix rounding so quotas sum to remaining
    while sum(quotas) > remaining:
        for i in range(len(quotas)):
            if quotas[i] > 0 and sum(quotas) > remaining:
                quotas[i] -= 1
    while sum(quotas) < remaining:
        richest = max(range(len(order)), key=lambda i: weights[i] - quotas[i])
        quotas[richest] += 1

    for key, quota in zip(order, quotas):
        group = by_chapter[key]
        unused = [c for c in group if id(c) not in used]
        if not unused or quota <= 0:
            continue
        idxs = evenly_spaced_indices(len(unused), min(quota, len(unused)))
        for i in idxs:
            add_chunk(unused[i])
            if len(selected) >= max_chunks:
                return selected[:max_chunks]

    if len(selected) < max_chunks:
        for chunk in teachable:
            add_chunk(chunk)
            if len(selected) >= max_chunks:
                break
    return selected[:max_chunks]


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
    selected = select_summary_source_chunks(chunks, max_chunks)
    out: list[KnowledgeSummary] = []
    for chunk in selected:
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


def load_summaries_jsonl(path: Path) -> list[KnowledgeSummary]:
    if not path.is_file():
        return []
    out: list[KnowledgeSummary] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                KnowledgeSummary(
                    summary_id=str(row.get("id") or ""),
                    text=str(row.get("text") or ""),
                    book=str(row.get("book") or ""),
                    chapter=str(row.get("chapter") or ""),
                    themes=list(row.get("themes") or []),
                    patterns=list(row.get("patterns") or []),
                    eco_hints=list(row.get("eco_hints") or []),
                    similar_games=list(row.get("similar_games") or []),
                    source_path=str(row.get("source_path") or ""),
                    source_chunk_id=str(row.get("source_chunk_id") or ""),
                )
            )
    return [s for s in out if s.summary_id and s.text]


def _book_jsonl_path(out_dir: Path, file_path: Path) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", file_path.stem.lower()).strip("_")[:60]
    return out_dir / f"{slug}.jsonl"


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
    if not summaries:
        if reset:
            get_summaries_collection(config)
        return 0
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
    force: bool = False,
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

    per_book_cap = None if max_chunks_per_book == 0 else max_chunks_per_book
    total_embedded = 0
    skipped_existing = 0

    if reset:
        print("Resetting summaries Chroma collection…", flush=True)
        embed_summaries([], config, reset=True, allow_hash_fallback=allow_hash_fallback)

    for idx, file_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] summarizing {file_path.name}", flush=True)
        jsonl_path = _book_jsonl_path(out_dir, file_path)
        existing = load_summaries_jsonl(jsonl_path)
        enough = (
            per_book_cap is not None
            and bool(existing)
            and len(existing) >= per_book_cap
        )
        if not force and not reset and enough:
            print(
                f"  SKIP already summarized ({len(existing)} in {jsonl_path.name}) — embedding batch",
                flush=True,
            )
            total_embedded += embed_summaries(
                existing,
                config,
                reset=False,
                allow_hash_fallback=allow_hash_fallback,
            )
            skipped_existing += 1
            continue

        try:
            summaries = summarize_book_chunks(
                file_path,
                config,
                use_llm=use_llm,
                max_chunks=per_book_cap,
            )
        except Exception as exc:
            print(f"  SKIP {exc}", flush=True)
            continue
        print(f"  {len(summaries)} summaries", flush=True)
        write_summaries_jsonl(summaries, jsonl_path)
        total_embedded += embed_summaries(
            summaries,
            config,
            reset=False,
            allow_hash_fallback=allow_hash_fallback,
        )

    if skipped_existing:
        print(
            f"Skipped LLM for {skipped_existing} books with existing jsonl "
            f"(use --force / --reset-summaries to redo)",
            flush=True,
        )
    return total_embedded


def run_knowledge_pipeline(
    books_path: Path,
    config: dict[str, Any],
    *,
    skip_ingest: bool = False,
    skip_summarize: bool = False,
    skip_key_buckets: bool = False,
    skip_annotated: bool = False,
    use_llm: bool = True,
    max_chunks_per_book: int | None = 24,
    allow_hash_fallback: bool = False,
    reset_summaries: bool = False,
    force_ingest: bool = False,
    force_summarize: bool = False,
    force_key_buckets: bool = False,
) -> dict[str, int]:
    """
    PDF ingest → per-chunk summaries → soft-key buckets + key summaries
    → optional annotated bookwalk synthesize.
    """
    from chess_coach.rag.key_bucket_summarize import summarize_by_key_path

    stats = {"ingested": 0, "summaries": 0, "key_summaries": 0, "annotated": 0}
    if not skip_ingest:
        print("=== 1/4 ingest PDFs ===", flush=True)
        stats["ingested"] = ingest_path(
            books_path,
            config,
            reset=False,
            allow_hash_fallback=allow_hash_fallback,
            force=force_ingest,
        )
    if not skip_summarize:
        print("=== 2/4 summarize + link PGN + embed ===", flush=True)
        stats["summaries"] = summarize_knowledge_path(
            books_path,
            config,
            use_llm=use_llm,
            max_chunks_per_book=max_chunks_per_book,
            reset=reset_summaries,
            allow_hash_fallback=allow_hash_fallback,
            force=force_summarize or reset_summaries,
        )
    if not skip_key_buckets:
        print("=== 3/4 soft-key buckets + LLM key summaries ===", flush=True)
        key_stats = summarize_by_key_path(
            books_path,
            config,
            use_llm=use_llm,
            max_chunks_per_book=max_chunks_per_book if max_chunks_per_book else 48,
            force=force_key_buckets or reset_summaries,
            reset=reset_summaries,
            allow_hash_fallback=allow_hash_fallback,
        )
        stats["key_summaries"] = int(key_stats.get("embedded") or 0)
    if not skip_annotated:
        print("=== 4/4 synthesize annotated bookwalk positions ===", flush=True)
        try:
            stats["annotated"] = synthesize_annotated(
                config, allow_hash_fallback=allow_hash_fallback
            )
        except Exception as exc:
            print(f"annotated synthesize skipped: {exc}", flush=True)
    return stats
