from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from chess_coach.features import ECO_FAMILY, THEME_KEYWORDS, _PATTERN_THEME, _THEME_TO_PATTERN
from chess_coach.ontology.load import get_pattern, load_ontology
from chess_coach.ontology.tag import tag_text_patterns
from chess_coach.rag.chunking import detect_themes, load_book_chunks
from chess_coach.rag.embeddings import get_embedder
from chess_coach.rag.ingest import get_collection
from chess_coach.rag.summarize_knowledge import (
    _bookwalk_game_labels,
    _eco_hints,
    _extractive_summary,
    _link_similar_games,
    chunk_is_teachable,
    select_summary_source_chunks,
    summary_is_teachable,
)

KEY_SUMMARY_PROMPT = """You write chess topic cards for a soft knowledge key.

Key: {label} ({key_id})
Key family: {key_type}

Below: elected book excerpts already filed under this key, plus related game citations.

Write ONE structured summary. Use these section headings when material exists (skip empty):
## Openings
## Structures
## Move types and motifs
## Conditional positions
## Plans and ideas
## Games and notes

Group ideas by sets of related games when citations appear. Plain English.
No fluff. No invented results. Move lists at most 3 plies.
Return ONLY the markdown summary."""

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
_SAFE_KEY_RE = re.compile(r"[^a-z0-9._-]+")
_MOVE_MOTIF_HINTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("motif.sacrifice", "Sacrifice", ("sacrifice", "sac ", "exchange sac", "deflection", "attraction")),
    ("motif.pin_and_skewer", "Pin and Skewer", ("pin", "skewer", "pinned")),
    ("motif.discovered_attack", "Discovered Attack", ("discovered attack", "discovered check", "battery")),
    ("motif.intermediate_move", "Zwischenzug", ("zwischenzug", "intermezzo", "intermediate move")),
    ("attack.king_safety", "King Safety / Attack", ("king safety", "attack on the king", "kingside attack")),
    ("attack.opposite_side_castling", "Opposite-Side Castling", ("opposite-side", "opposite side castling", "pawn storm")),
    ("attack.greek_gift", "Greek Gift", ("greek gift", "bxh7", "bxh2")),
    ("attack.f7_f2_vulnerability", "f7/f2 Vulnerability", ("f7", "f2")),
    ("attack.initiative", "Initiative", ("initiative", "seize the tempo")),
    ("positional.outpost", "Outpost", ("outpost", "strong square")),
    ("positional.prophylaxis", "Prophylaxis", ("prophylaxis", "preventive")),
    ("positional.pawn_break", "Pawn Break", ("pawn break", "break with", "undermining")),
    ("positional.two_weaknesses", "Two Weaknesses", ("two weaknesses", "second weakness")),
    ("piece.blockade", "Blockade", ("blockade", "blockading")),
    ("piece.seventh_rank_invasion", "Seventh-Rank Invasion", ("seventh rank", "7th rank", "rook on the seventh")),
    ("piece.rerouting", "Rerouting", ("rerouting", "worst-placed piece")),
    ("methodology.candidate_moves", "Candidate Moves", ("candidate moves",)),
    ("methodology.prophylactic_thinking", "Prophylactic Thinking", ("what does my opponent want",)),
]
MAX_EXCERPT = 700
MAX_SUMMARY = 1800
DEFAULT_MAX_EXCERPTS = 16
DEFAULT_MIN_CHUNKS = 2


@dataclass(frozen=True)
class SoftKey:
    key_id: str
    key_type: str
    label: str


@dataclass
class BucketEntry:
    chunk_id: str
    book: str
    chapter: str
    text: str
    themes: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    eco_hints: list[str] = field(default_factory=list)
    games: list[str] = field(default_factory=list)
    source_path: str = ""


@dataclass
class KeyBucket:
    key: SoftKey
    entries: list[BucketEntry] = field(default_factory=list)
    games: list[str] = field(default_factory=list)

    def append_entry(self, entry: BucketEntry) -> None:
        if any(e.chunk_id == entry.chunk_id for e in self.entries):
            return
        self.entries.append(entry)
        for g in entry.games:
            if g not in self.games:
                self.games.append(g)


@dataclass
class KeySummary:
    key_id: str
    key_type: str
    label: str
    text: str
    chunk_ids: list[str]
    books: list[str]
    games: list[str]
    themes: list[str]
    patterns: list[str]
    eco_hints: list[str]
    entry_count: int


def _safe_key_id(value: str) -> str:
    cleaned = _SAFE_KEY_RE.sub("_", (value or "").lower().strip("._-"))
    return cleaned.strip("_") or "unknown"


def _theme_to_soft_key(theme: str, ontology_dir: str | None = None) -> SoftKey | None:
    t = (theme or "").strip().lower()
    if not t or t in {"opening", "endgame"}:
        return None
    mapped = _THEME_TO_PATTERN.get(t)
    if mapped:
        return _pattern_to_soft_key(mapped, ontology_dir)
    if t in {"ruy lopez", "italian", "nimzo-indian"}:
        return SoftKey(f"opening.{_safe_key_id(t)}", "opening", t.title())
    return SoftKey(f"theme.{_safe_key_id(t)}", "theme", t.title())


def _pattern_to_soft_key(pattern_id: str, ontology_dir: str | None = None) -> SoftKey | None:
    pid = (pattern_id or "").strip()
    if not pid:
        return None
    pattern = get_pattern(pid, ontology_dir)
    if pattern:
        if pid.startswith("opening."):
            key_type = "opening"
        elif pid.startswith("structure."):
            key_type = "structure"
        elif pid.startswith("endgame."):
            key_type = "endgame"
        elif pid.startswith("imbalance."):
            key_type = "imbalance"
        elif pid.startswith("positional."):
            key_type = "positional"
        elif pid.startswith("piece."):
            key_type = "piece"
        elif pid.startswith("attack."):
            key_type = "attack"
        elif pid.startswith("motif."):
            key_type = "motif"
        elif pid.startswith("methodology."):
            key_type = "methodology"
        else:
            key_type = (pattern.family or "motif").split("_")[0]
        return SoftKey(pid, key_type, pattern.label or pid)
    if "." in pid:
        head = pid.split(".", 1)[0]
        return SoftKey(pid, head, pid.replace(".", " ").replace("_", " ").title())
    return SoftKey(f"motif.{_safe_key_id(pid)}", "motif", pid)


def _eco_family_keys(ecos: list[str]) -> list[SoftKey]:
    out: list[SoftKey] = []
    seen: set[str] = set()
    for eco in ecos:
        letter = (eco or "")[:1].upper()
        if letter not in ECO_FAMILY or letter in seen:
            continue
        seen.add(letter)
        out.append(
            SoftKey(
                f"eco.{letter.lower()}",
                "opening",
                f"ECO {letter}: {ECO_FAMILY[letter]}",
            )
        )
    return out


def _move_motif_keys(text: str) -> list[SoftKey]:
    lowered = (text or "").lower()
    out: list[SoftKey] = []
    for key_id, label, needles in _MOVE_MOTIF_HINTS:
        if any(n in lowered for n in needles):
            head = key_id.split(".", 1)[0]
            out.append(SoftKey(key_id, head, label))
    return out


def extract_soft_keys(
    text: str,
    *,
    themes: list[str] | None = None,
    patterns: list[str] | None = None,
    eco_hints: list[str] | None = None,
    ontology_dir: str | None = None,
) -> list[SoftKey]:
    """Soft keys from themes, ontology patterns, ECO families, text motifs."""
    merged: dict[str, SoftKey] = {}

    def add(key: SoftKey | None) -> None:
        if key is None or not key.key_id:
            return
        if key.key_id not in merged:
            merged[key.key_id] = key

    for theme in themes or []:
        add(_theme_to_soft_key(theme, ontology_dir))
    for pid in patterns or []:
        add(_pattern_to_soft_key(pid, ontology_dir))
        mapped = _PATTERN_THEME.get(pid)
        if mapped:
            add(_theme_to_soft_key(mapped, ontology_dir))
    for key in _eco_family_keys(eco_hints or []):
        add(key)
    for key in _move_motif_keys(text):
        add(key)
    return list(merged.values())


def _clip(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


def _sid(parts: list[str]) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _dedupe_labels(labels: list[str], limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def build_key_buckets(
    chunks: list[Any],
    config: dict[str, Any],
    *,
    max_chunks: int | None = None,
) -> dict[str, KeyBucket]:
    """Elect teachable chunks, assign soft keys, append into key documents."""
    ont_dir = (config.get("ontology") or {}).get("dir")
    selected = select_summary_source_chunks(chunks, max_chunks)
    buckets: dict[str, KeyBucket] = {}

    for chunk in selected:
        text = getattr(chunk, "text", "") or ""
        if not chunk_is_teachable(text):
            continue
        themes = detect_themes(text, getattr(chunk, "themes", None) or [])
        patterns = tag_text_patterns(
            text,
            ontology_dir=ont_dir,
            book_patterns=getattr(chunk, "book_patterns", None) or [],
        )
        ecos = _eco_hints(text, themes)
        games = _dedupe_labels(
            _link_similar_games(ecos, config) + _bookwalk_game_labels(config, themes),
            limit=6,
        )
        keys = extract_soft_keys(
            text,
            themes=themes,
            patterns=patterns,
            eco_hints=ecos,
            ontology_dir=ont_dir,
        )
        if not keys:
            keys = [SoftKey("theme.general", "theme", "General middlegame")]
        entry = BucketEntry(
            chunk_id=str(getattr(chunk, "chunk_id", "") or _sid([text[:80]])),
            book=str(getattr(chunk, "book", "") or ""),
            chapter=str(getattr(chunk, "chapter", "") or "body"),
            text=_clip(text, MAX_EXCERPT),
            themes=themes,
            patterns=patterns,
            eco_hints=ecos,
            games=games,
            source_path=str(getattr(chunk, "source_path", "") or ""),
        )
        for key in keys:
            bucket = buckets.get(key.key_id)
            if bucket is None:
                bucket = KeyBucket(key=key)
                buckets[key.key_id] = bucket
            bucket.append_entry(entry)

    return buckets


def write_key_buckets(buckets: dict[str, KeyBucket], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for key_id, bucket in sorted(buckets.items()):
        path = out_dir / f"{_safe_key_id(key_id)}.json"
        payload = {
            "key_id": bucket.key.key_id,
            "key_type": bucket.key.key_type,
            "label": bucket.key.label,
            "games": bucket.games,
            "entry_count": len(bucket.entries),
            "entries": [
                {
                    "chunk_id": e.chunk_id,
                    "book": e.book,
                    "chapter": e.chapter,
                    "text": e.text,
                    "themes": e.themes,
                    "patterns": e.patterns,
                    "eco_hints": e.eco_hints,
                    "games": e.games,
                    "source_path": e.source_path,
                }
                for e in bucket.entries
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written += 1
    index = {
        "keys": [
            {
                "key_id": b.key.key_id,
                "key_type": b.key.key_type,
                "label": b.key.label,
                "entry_count": len(b.entries),
                "game_count": len(b.games),
            }
            for _, b in sorted(buckets.items())
        ]
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return written


def load_key_buckets(bucket_dir: Path) -> dict[str, KeyBucket]:
    if not bucket_dir.is_dir():
        return {}
    out: dict[str, KeyBucket] = {}
    for path in sorted(bucket_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = SoftKey(
            str(row.get("key_id") or path.stem),
            str(row.get("key_type") or "theme"),
            str(row.get("label") or path.stem),
        )
        bucket = KeyBucket(key=key, games=list(row.get("games") or []))
        for e in row.get("entries") or []:
            bucket.append_entry(
                BucketEntry(
                    chunk_id=str(e.get("chunk_id") or ""),
                    book=str(e.get("book") or ""),
                    chapter=str(e.get("chapter") or "body"),
                    text=str(e.get("text") or ""),
                    themes=list(e.get("themes") or []),
                    patterns=list(e.get("patterns") or []),
                    eco_hints=list(e.get("eco_hints") or []),
                    games=list(e.get("games") or []),
                    source_path=str(e.get("source_path") or ""),
                )
            )
        if bucket.entries:
            out[key.key_id] = bucket
    return out


def _bucket_prompt_body(
    bucket: KeyBucket,
    *,
    max_excerpts: int = DEFAULT_MAX_EXCERPTS,
) -> str:
    lines: list[str] = []
    if bucket.games:
        lines.append("Related games:")
        for g in bucket.games[:8]:
            lines.append(f"- {g}")
        lines.append("")
    lines.append("Excerpts:")
    for i, entry in enumerate(bucket.entries[:max_excerpts], start=1):
        games = ", ".join(entry.games[:3]) if entry.games else "none"
        lines.append(
            f"[{i}] book={entry.book} chapter={entry.chapter} games={games}\n{entry.text}"
        )
    return "\n\n".join(lines)


def _ollama_key_summary(bucket: KeyBucket, config: dict[str, Any], body: str) -> str | None:
    host = str(config.get("ollama_host") or "http://localhost:11434").rstrip("/")
    model = str(config.get("chat_model") or "qwen3:8b")
    system = KEY_SUMMARY_PROMPT.format(
        label=bucket.key.label,
        key_id=bucket.key.key_id,
        key_type=bucket.key.key_type,
    )
    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": body[:12000]},
                    ],
                },
            )
            response.raise_for_status()
            message = response.json().get("message") or {}
            content = str(message.get("content") or "").strip()
            content = _THINK_RE.sub("", content).strip()
            if len(content) < 80:
                return None
            return _clip(content, MAX_SUMMARY)
    except Exception:
        return None


def _extractive_key_summary(bucket: KeyBucket) -> str:
    themes = []
    for e in bucket.entries[:6]:
        themes.extend(e.themes)
    joined = " ".join(e.text for e in bucket.entries[:4])
    body = _extractive_summary(joined, themes[:6])
    sections = [
        f"# {bucket.key.label}",
        "",
        "## Plans and ideas",
        body,
    ]
    if bucket.games:
        sections.extend(["", "## Games and notes", *[f"- {g}" for g in bucket.games[:6]]])
    return _clip("\n".join(sections), MAX_SUMMARY)


def summarize_key_bucket(
    bucket: KeyBucket,
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    max_excerpts: int = DEFAULT_MAX_EXCERPTS,
) -> KeySummary | None:
    if len(bucket.entries) < 1:
        return None
    body = _bucket_prompt_body(bucket, max_excerpts=max_excerpts)
    text = None
    if use_llm:
        text = _ollama_key_summary(bucket, config, body)
    if not text:
        text = _extractive_key_summary(bucket)
    if not summary_is_teachable(text) and len(text) < 80:
        return None
    themes: list[str] = []
    patterns: list[str] = []
    ecos: list[str] = []
    books: list[str] = []
    for e in bucket.entries:
        for t in e.themes:
            if t not in themes:
                themes.append(t)
        for p in e.patterns:
            if p not in patterns:
                patterns.append(p)
        for eco in e.eco_hints:
            if eco not in ecos:
                ecos.append(eco)
        if e.book and e.book not in books:
            books.append(e.book)
    return KeySummary(
        key_id=bucket.key.key_id,
        key_type=bucket.key.key_type,
        label=bucket.key.label,
        text=text,
        chunk_ids=[e.chunk_id for e in bucket.entries],
        books=books,
        games=list(bucket.games),
        themes=themes[:12],
        patterns=patterns[:12],
        eco_hints=ecos[:8],
        entry_count=len(bucket.entries),
    )


def write_key_summaries_jsonl(summaries: list[KeySummary], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for s in summaries:
            handle.write(
                json.dumps(
                    {
                        "id": _sid([s.key_id, s.text[:80]]),
                        "key_id": s.key_id,
                        "key_type": s.key_type,
                        "label": s.label,
                        "text": s.text,
                        "chunk_ids": s.chunk_ids,
                        "books": s.books,
                        "games": s.games,
                        "themes": s.themes,
                        "patterns": s.patterns,
                        "eco_hints": s.eco_hints,
                        "entry_count": s.entry_count,
                        "source_kind": "key_summary",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def load_key_summaries_jsonl(path: Path) -> list[KeySummary]:
    if not path.is_file():
        return []
    out: list[KeySummary] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = str(row.get("text") or "")
            key_id = str(row.get("key_id") or "")
            if not text or not key_id:
                continue
            out.append(
                KeySummary(
                    key_id=key_id,
                    key_type=str(row.get("key_type") or "theme"),
                    label=str(row.get("label") or key_id),
                    text=text,
                    chunk_ids=list(row.get("chunk_ids") or []),
                    books=list(row.get("books") or []),
                    games=list(row.get("games") or []),
                    themes=list(row.get("themes") or []),
                    patterns=list(row.get("patterns") or []),
                    eco_hints=list(row.get("eco_hints") or []),
                    entry_count=int(row.get("entry_count") or 0),
                )
            )
    return out


def get_key_summaries_collection(config: dict[str, Any]):
    rag = dict(config.get("rag") or {})
    name = rag.get("key_summaries_collection", "chess_knowledge_key_summaries")
    cfg = {**config, "rag": {**rag, "collection": name}}
    return get_collection(cfg)


def embed_key_summaries(
    summaries: list[KeySummary],
    config: dict[str, Any],
    *,
    reset: bool = False,
    allow_hash_fallback: bool = False,
) -> int:
    rag = config.setdefault("rag", {})
    if reset:
        from chromadb import PersistentClient

        client = PersistentClient(path=str(rag["persist_dir"]))
        name = rag.get("key_summaries_collection", "chess_knowledge_key_summaries")
        try:
            client.delete_collection(name)
        except Exception:
            pass
    if not summaries:
        if reset:
            get_key_summaries_collection(config)
        return 0
    collection = get_key_summaries_collection(config)
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
        print(f"  upserted key summaries {len(batch_ids)} (total={total})", flush=True)
        batch_ids, batch_docs, batch_meta = [], [], []

    for s in summaries:
        doc_id = _sid([s.key_id, s.text[:80]])
        meta = {
            "key_id": s.key_id,
            "key_type": s.key_type,
            "label": s.label,
            "themes": ",".join(s.themes),
            "patterns": ",".join(s.patterns),
            "eco_hints": ",".join(s.eco_hints),
            "books": ",".join(s.books),
            "games": " || ".join(s.games[:8]),
            "entry_count": s.entry_count,
            "source_kind": "key_summary",
            "quality": "key_summary",
        }
        batch_ids.append(doc_id)
        batch_docs.append(s.text)
        batch_meta.append(meta)
        if len(batch_ids) >= 8:
            flush()
    flush()
    return total


def _resolve_rag_dir(config: dict[str, Any], key: str, default: str) -> Path:
    root = Path(__file__).resolve().parents[3]
    out = Path((config.get("rag") or {}).get(key, default))
    if not out.is_absolute():
        out = (root / out).resolve()
    return out


def summarize_by_key_path(
    path: Path,
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    max_chunks_per_book: int | None = 48,
    max_excerpts_per_key: int = DEFAULT_MAX_EXCERPTS,
    min_chunks_per_key: int = DEFAULT_MIN_CHUNKS,
    force: bool = False,
    reset: bool = False,
    allow_hash_fallback: bool = False,
) -> dict[str, int]:
    """
    Elect chunks → soft-key documents (append) → LLM summary per key → embed.
    """
    # Touch ontology so missing dirs fail early with a clear empty catalog.
    load_ontology((config.get("ontology") or {}).get("dir"))
    _ = THEME_KEYWORDS

    bucket_dir = _resolve_rag_dir(config, "key_buckets_dir", "data/knowledge_key_buckets")
    summary_dir = _resolve_rag_dir(config, "key_summaries_dir", "data/knowledge_key_summaries")
    summary_jsonl = summary_dir / "by_key.jsonl"

    files: list[Path]
    if path.is_dir():
        files = sorted(
            [p for p in path.rglob("*") if p.suffix.lower() in {".pdf", ".txt"} and p.is_file()]
        )
    else:
        files = [path]

    per_book_cap = None if max_chunks_per_book == 0 else max_chunks_per_book
    merged: dict[str, KeyBucket] = {} if force or reset else load_key_buckets(bucket_dir)

    for idx, file_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] key-bucket elect {file_path.name}", flush=True)
        chunk_cfg = config.get("chunk") or {}
        try:
            chunks = load_book_chunks(
                file_path,
                max_chars=int(chunk_cfg.get("max_chars", 700)),
                overlap_chars=int(chunk_cfg.get("overlap_chars", 80)),
            )
        except Exception as exc:
            print(f"  SKIP {exc}", flush=True)
            continue
        book_buckets = build_key_buckets(chunks, config, max_chunks=per_book_cap)
        print(f"  {len(book_buckets)} keys touched from {file_path.name}", flush=True)
        for key_id, bucket in book_buckets.items():
            target = merged.get(key_id)
            if target is None:
                merged[key_id] = bucket
                continue
            for entry in bucket.entries:
                target.append_entry(entry)

    write_key_buckets(merged, bucket_dir)
    print(f"Wrote {len(merged)} key documents → {bucket_dir}", flush=True)

    existing = [] if force or reset else load_key_summaries_jsonl(summary_jsonl)
    existing_by_key = {s.key_id: s for s in existing}
    summaries: list[KeySummary] = []
    llm_runs = 0
    skipped = 0

    eligible = [
        b
        for b in sorted(merged.values(), key=lambda x: x.key.key_id)
        if len(b.entries) >= min_chunks_per_key
    ]
    for i, bucket in enumerate(eligible, start=1):
        if not force and not reset and bucket.key.key_id in existing_by_key:
            summaries.append(existing_by_key[bucket.key.key_id])
            skipped += 1
            continue
        print(
            f"[{i}/{len(eligible)}] summarize key {bucket.key.key_id} "
            f"({len(bucket.entries)} chunks, {len(bucket.games)} games)",
            flush=True,
        )
        summary = summarize_key_bucket(
            bucket,
            config,
            use_llm=use_llm,
            max_excerpts=max_excerpts_per_key,
        )
        if summary is None:
            print("  SKIP empty/unusable summary", flush=True)
            continue
        summaries.append(summary)
        llm_runs += 1

    write_key_summaries_jsonl(summaries, summary_jsonl)
    embedded = embed_key_summaries(
        summaries,
        config,
        reset=reset,
        allow_hash_fallback=allow_hash_fallback,
    )
    print(
        f"Key summaries: {len(summaries)} written "
        f"(llm/extractive={llm_runs}, reused={skipped}) → embedded {embedded}",
        flush=True,
    )
    return {
        "keys": len(merged),
        "summaries": len(summaries),
        "embedded": embedded,
        "llm_runs": llm_runs,
        "reused": skipped,
    }
