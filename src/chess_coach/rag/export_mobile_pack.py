from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chess
import chess.pgn

from chess_coach.features import narrative_seed_for_key
from chess_coach.masters_db import LocalMastersDB
from chess_coach.rag.key_bucket_summarize import (
    get_key_summaries_collection,
    load_key_summaries_jsonl,
)
from chess_coach.rag.summarize_key_ideas import load_key_ideas_jsonl
from chess_coach.rag.canon_key_meta import key_meta, note_compact
from chess_coach.rag.bookwalk_passages import (
    load_bookwalk_passages,
    passage_fingerprint,
    passage_to_note,
    passages_by_key,
)
from chess_coach.rag.metrics_voice import adapt_compact, adapt_summary
from chess_coach.rag.note_fen_enrich import (
    build_model_game_fen_index,
    enrich_gpt_notes_with_fens,
)
from chess_coach.rag.offline_llm_comments import (
    generate_offline_comment_notes,
    load_metrics_json,
    merge_notes_schema,
    write_notes_schema,
)
from chess_coach.rag.summarize_knowledge import (
    get_summaries_collection,
    summary_is_teachable,
)

MAX_TEXT_KEY = 1400
MAX_TEXT_CHUNK = 360
MAX_ENTRIES = 300
MAX_LINES_PER_ENTRY = 4
LINE_PLIES = 10
GAMES_PER_ECO = 60
MAX_NOTES_PER_KEY = 12
MAX_NOTE_TEXT = 420
MAX_NOTES_PER_BOOK = 6
MAX_BOOKWALK_NOTES_PER_KEY = 40
MAX_GPT_NOTES_PER_KEY = 4
PACK_VERSION = 11
CANON_KEY = re.compile(
    r"^(structure|opening|endgame|imbalance|positional|piece|motif|attack|methodology)\."
)


def pack_key_narrative(
    key_id: str,
    *,
    label: str = "",
    opening: str = "",
    eco: str = "",
) -> str:
    return narrative_seed_for_key(key_id, label=label, opening=opening, eco=eco)


def _clean_slot_text(raw: str) -> str:
    """Single tip clause: strip bullets / Apply-the-lesson wrappers."""
    lines: list[str] = []
    for ln in str(raw or "").splitlines():
        ln = re.sub(r"^[-•*]\s*", "", ln).strip()
        ln = re.sub(r"^Apply the lesson:\s*", "", ln, flags=re.I).strip()
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            lines.append(ln)
    if not lines:
        return ""
    if len(lines) >= 2 and len(lines[0]) < 48 and len(lines[1]) > len(lines[0]):
        pick = lines[1]
    else:
        pick = max(lines, key=len)
    return pick[:160]


def _ensure_note_slots(
    note: dict[str, Any], *, key_id: str, principle: str
) -> dict[str, str]:
    """Tip-structure slots: worked / attention / lesson / plan."""
    del key_id  # reserved for future metric-voice slot adapt
    raw = note.get("slots") or {}
    slots: dict[str, str] = {}
    if isinstance(raw, dict):
        for k in ("worked", "attention", "lesson", "plan"):
            v = _clean_slot_text(str(raw.get(k) or ""))
            if v:
                slots[k] = v
    if slots.get("lesson") and slots.get("attention") and slots.get("worked"):
        return slots
    text = str(note.get("text") or "")
    bullets = [
        _clean_slot_text(ln)
        for ln in text.splitlines()
        if ln.strip()
    ]
    bullets = [b for b in bullets if len(b) >= 12][:4]
    principle_c = _clean_slot_text(principle)
    if not slots.get("worked"):
        slots["worked"] = principle_c or (bullets[0] if bullets else "")
    if not slots.get("attention"):
        slots["attention"] = (
            bullets[1] if len(bullets) > 1 else (bullets[0] if bullets else principle_c)
        )
    if not slots.get("lesson"):
        slots["lesson"] = (bullets[0] if bullets else principle_c)
    if not slots.get("plan") and len(bullets) > 2:
        slots["plan"] = bullets[2]
    return {k: v for k, v in slots.items() if v}


def _ensure_note_conditions(note: dict[str, Any], key_id: str) -> list[dict[str, Any]]:
    raw = note.get("conditions")
    if isinstance(raw, list) and raw:
        return [dict(c) for c in raw if isinstance(c, dict)][:12]
    out: list[dict[str, Any]] = [{"softKey": key_id, "polarity": "any"}]
    for theme in note.get("themes") or []:
        t = str(theme).strip()
        if "." in t:
            out.append({"softKey": t, "polarity": "any"})
        elif t:
            out.append({"theme": t, "polarity": "any"})
    for feat in note.get("features") or []:
        f = str(feat).strip()
        if f:
            out.append({"feature": f, "polarity": "any"})
    for op in note.get("openings") or []:
        o = str(op).strip()
        if o:
            out.append({"opening": o, "polarity": "any"})
    return out[:12]


def _clip(text: str, limit: int) -> str:
    raw = (text or "").strip()
    if raw.startswith("- ") or "\n- " in raw:
        lines = [
            re.sub(r"\s+", " ", ln).strip()
            for ln in raw.splitlines()
            if ln.strip()
        ]
        cleaned = "\n".join(lines)
    else:
        cleaned = re.sub(r"\s+", " ", raw)
        cleaned = cleaned.replace(" ## ", "\n## ").replace("# ", "# ", 1)
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


def _mainline_sans(pgn_text: str, max_plies: int = LINE_PLIES) -> list[str]:
    try:
        game = chess.pgn.read_game(__import__("io").StringIO(pgn_text))
    except Exception:
        return []
    if game is None:
        return []
    board = game.board()
    node = game
    sans: list[str] = []
    while node.variations and len(sans) < max_plies:
        nxt = node.variation(0)
        try:
            sans.append(board.san(nxt.move))
            board.push(nxt.move)
        except Exception:
            break
        node = nxt
    return sans


def frequent_lines_for_eco(
    db: LocalMastersDB,
    eco: str,
    *,
    games: int = GAMES_PER_ECO,
    plies: int = LINE_PLIES,
    top_n: int = MAX_LINES_PER_ENTRY,
) -> list[dict[str, Any]]:
    hits = db.find_by_eco(eco, limit=games)
    counter: Counter[str] = Counter()
    for hit in hits:
        try:
            pgn = db.fetch_pgn(hit)
        except OSError:
            continue
        sans = _mainline_sans(pgn, max_plies=plies)
        if len(sans) < 4:
            continue
        line = " ".join(sans)
        counter[line] += 1
    out: list[dict[str, Any]] = []
    for line, count in counter.most_common(top_n):
        if count < 2:
            continue
        out.append({"sanLine": line, "count": int(count), "eco": eco})
    return out


def _split_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "")
    return [p.strip() for p in text.split(",") if p.strip()]


def _load_key_summaries_from_chroma(config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        coll = get_key_summaries_collection(config)
    except Exception:
        return []
    total = coll.count()
    if total <= 0:
        return []
    rows: list[dict[str, Any]] = []
    offset = 0
    batch = 64
    while offset < total:
        raw = coll.get(
            include=["documents", "metadatas"],
            limit=batch,
            offset=offset,
        )
        ids = raw.get("ids") or []
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        if not ids:
            break
        for i, doc, meta in zip(ids, docs, metas):
            meta = meta or {}
            text = _clip(doc or "", MAX_TEXT_KEY)
            if len(text) < 60:
                continue
            key_id = str(meta.get("key_id") or "")
            themes = _split_csv(meta.get("themes"))
            patterns = _split_csv(meta.get("patterns"))
            if key_id and key_id not in patterns:
                patterns = [key_id, *patterns]
            books = _split_csv(meta.get("books"))
            games_raw = str(meta.get("games") or "")
            games = [g.strip() for g in games_raw.split("||") if g.strip()]
            rows.append(
                {
                    "id": str(i),
                    "text": text,
                    "book": books[0] if books else str(meta.get("label") or "key"),
                    "books": books,
                    "chapter": str(meta.get("key_type") or ""),
                    "themes": themes,
                    "patterns": patterns,
                    "eco_hints": _split_csv(meta.get("eco_hints")),
                    "key_id": key_id,
                    "key_type": str(meta.get("key_type") or ""),
                    "label": str(meta.get("label") or key_id or "topic"),
                    "games": games[:8],
                    "source_kind": "key_summary",
                }
            )
        offset += len(ids)
    return rows


def _note_is_teachable(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 60:
        return False
    if not re.search(
        r"\b(pawn|king|queen|rook|bishop|knight|attack|plan|structure|"
        r"file|break|castle|develop|endgame|opening|sacrifice|pin|"
        r"blockade|passer|isolani|iqp|outpost)\b",
        t,
        re.I,
    ):
        return False
    return True


_IDEAS_BY_KEY: dict[str, list[dict[str, Any]]] | None = None


def _ideas_jsonl_path(config: dict[str, Any]) -> Path:
    root = Path(__file__).resolve().parents[3]
    ideas_dir = Path(
        (config.get("rag") or {}).get("key_ideas_dir", "data/knowledge_key_ideas")
    )
    if not ideas_dir.is_absolute():
        ideas_dir = (root / ideas_dir).resolve()
    return ideas_dir / "by_key_ideas.jsonl"


def _load_ideas_by_key(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    global _IDEAS_BY_KEY
    if _IDEAS_BY_KEY is not None:
        return _IDEAS_BY_KEY
    by_key: dict[str, list[dict[str, Any]]] = {}
    for idea in load_key_ideas_jsonl(_ideas_jsonl_path(config)):
        if not idea.summary or len(idea.summary) < 40:
            continue
        ecos = [
            str(x).strip().upper()
            for x in idea.openings
            if re.fullmatch(r"[A-E]\d{2}", str(x).strip().upper() or "")
        ]
        opening_labels = [
            str(x).strip()
            for x in idea.openings
            if str(x).strip() and not re.fullmatch(r"[A-E]\d{2}", str(x).strip().upper())
        ]
        note = {
            "id": idea.idea_id,
            "text": _clip(idea.summary, MAX_NOTE_TEXT),
            "book": idea.source_books[0] if idea.source_books else idea.label,
            "themes": list(idea.themes)[:8],
            "ecoHints": (ecos or opening_labels)[:4],
            "patterns": [p for p in [idea.key_id, idea.principle] if p][:8],
            "principle": idea.principle,
            "phase": idea.phase,
            "fens": list(idea.fens)[:4],
            "sanLines": list(idea.san_lines)[:4],
            "openings": list(idea.openings)[:4],
            "games": list(idea.games)[:4],
            "specificity": int(getattr(idea, "specificity", 3) or 3),
            "features": list(getattr(idea, "features", None) or [])[:12],
            "compact": note_compact(idea.key_id, len(by_key.get(idea.key_id) or [])),
            "slots": dict(getattr(idea, "slots", None) or {}),
            "conditions": list(getattr(idea, "conditions", None) or [])[:12],
        }
        by_key.setdefault(idea.key_id, []).append(note)
    _IDEAS_BY_KEY = by_key
    return by_key


def _load_key_idea_notes(config: dict[str, Any], key_id: str) -> list[dict[str, Any]]:
    if not key_id:
        return []
    return list(_load_ideas_by_key(config).get(key_id) or [])[:MAX_NOTES_PER_KEY]


def _load_bucket_notes(
    config: dict[str, Any],
    key_id: str,
) -> list[dict[str, Any]]:
    """Pull diversified teachable excerpts from the key document bucket."""
    if not key_id:
        return []
    root = Path(__file__).resolve().parents[3]
    bucket_dir = Path(
        (config.get("rag") or {}).get("key_buckets_dir", "data/knowledge_key_buckets")
    )
    if not bucket_dir.is_absolute():
        bucket_dir = (root / bucket_dir).resolve()
    path = bucket_dir / f"{key_id}.json"
    if not path.is_file():
        # safe filename may replace dots? keys use dots as-is in write_key_buckets
        safe = re.sub(r"[^\w.\-]+", "_", key_id)
        path = bucket_dir / f"{safe}.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_entries = list(payload.get("entries") or [])
    candidates: list[dict[str, Any]] = []
    for e in raw_entries:
        text = _clip(str(e.get("text") or ""), MAX_NOTE_TEXT)
        if not _note_is_teachable(text):
            continue
        candidates.append(
            {
                "id": str(e.get("chunk_id") or ""),
                "text": text,
                "book": str(e.get("book") or ""),
                "themes": list(e.get("themes") or [])[:8],
                "ecoHints": [str(x).upper() for x in (e.get("eco_hints") or []) if x][:4],
                "patterns": list(e.get("patterns") or [])[:8],
            }
        )
    if not candidates:
        return []

    # Diversify across books (round-robin), cap per book + total.
    by_book: dict[str, list[dict[str, Any]]] = {}
    for n in candidates:
        by_book.setdefault(n["book"] or "unknown", []).append(n)
    for book, rows in by_book.items():
        by_book[book] = rows[:MAX_NOTES_PER_BOOK]

    books = sorted(by_book.keys(), key=lambda b: (-len(by_book[b]), b))
    picked: list[dict[str, Any]] = []
    idx = 0
    while len(picked) < MAX_NOTES_PER_KEY:
        progressed = False
        for book in books:
            rows = by_book[book]
            if idx >= len(rows):
                continue
            picked.append(rows[idx])
            progressed = True
            if len(picked) >= MAX_NOTES_PER_KEY:
                break
        if not progressed:
            break
        idx += 1
    return picked


def _load_key_summaries_from_jsonl(config: dict[str, Any]) -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parents[3]
    summary_dir = Path(
        (config.get("rag") or {}).get("key_summaries_dir", "data/knowledge_key_summaries")
    )
    if not summary_dir.is_absolute():
        summary_dir = (root / summary_dir).resolve()
    path = summary_dir / "by_key.jsonl"
    rows: list[dict[str, Any]] = []
    for s in load_key_summaries_jsonl(path):
        text = _clip(s.text, MAX_TEXT_KEY)
        if len(text) < 60:
            continue
        patterns = list(s.patterns)
        if s.key_id and s.key_id not in patterns:
            patterns = [s.key_id, *patterns]
        notes = _load_key_idea_notes(config, s.key_id) or _load_bucket_notes(
            config, s.key_id
        )
        rows.append(
            {
                "id": f"key:{s.key_id}",
                "text": text,
                "book": s.books[0] if s.books else s.label,
                "books": list(s.books),
                "chapter": s.key_type,
                "themes": list(s.themes),
                "patterns": patterns,
                "eco_hints": list(s.eco_hints),
                "key_id": s.key_id,
                "key_type": s.key_type,
                "label": s.label,
                "games": list(s.games)[:8],
                "source_kind": "key_summary",
                "notes": notes,
            }
        )
    return rows


def _load_chunk_summaries_from_chroma(config: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        coll = get_summaries_collection(config)
    except Exception:
        return []
    total = coll.count()
    if total <= 0:
        return []
    rows: list[dict[str, Any]] = []
    offset = 0
    batch = 64
    while offset < total:
        raw = coll.get(
            include=["documents", "metadatas"],
            limit=batch,
            offset=offset,
        )
        ids = raw.get("ids") or []
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        if not ids:
            break
        for i, doc, meta in zip(ids, docs, metas):
            meta = meta or {}
            text = _clip(doc or "", MAX_TEXT_CHUNK)
            if not summary_is_teachable(text):
                continue
            rows.append(
                {
                    "id": str(i),
                    "text": text,
                    "book": str(meta.get("book") or "book"),
                    "books": [str(meta.get("book") or "book")],
                    "chapter": str(meta.get("chapter") or ""),
                    "themes": _split_csv(meta.get("themes")),
                    "patterns": _split_csv(meta.get("patterns")),
                    "eco_hints": _split_csv(meta.get("eco_hints")),
                    "key_id": "",
                    "key_type": "",
                    "label": str(meta.get("book") or "book"),
                    "games": [],
                    "source_kind": "knowledge_summary",
                }
            )
        offset += len(ids)
    return rows


def _load_chunk_summaries_from_jsonl(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        if path.name == "by_key.jsonl":
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _clip(str(obj.get("text") or ""), MAX_TEXT_CHUNK)
            if not summary_is_teachable(text):
                continue
            book = str(obj.get("book") or "book")
            rows.append(
                {
                    "id": str(obj.get("id") or path.stem),
                    "text": text,
                    "book": book,
                    "books": [book],
                    "chapter": str(obj.get("chapter") or ""),
                    "themes": list(obj.get("themes") or []),
                    "patterns": list(obj.get("patterns") or []),
                    "eco_hints": list(obj.get("eco_hints") or []),
                    "key_id": "",
                    "key_type": "",
                    "label": book,
                    "games": list(obj.get("similar_games") or [])[:4],
                    "source_kind": "knowledge_summary",
                }
            )
    return rows


def _load_canon_gpt_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    """GPT book notes + compact glossary only (no OCR bucket excerpts)."""
    from chess_coach.rag.canon_key_notes import CANON_KEY_NOTES
    from chess_coach.rag.canon_key_meta import key_meta, note_compact

    idea_notes = _load_ideas_by_key(config)
    rows: list[dict[str, Any]] = []
    for key_id, curated in sorted(CANON_KEY_NOTES.items()):
        if not CANON_KEY.match(key_id):
            continue
        meta = key_meta(key_id)
        compact = adapt_compact(key_id, str(meta.get("compact") or ""))
        model_game = str(meta.get("model_game") or "")
        key_type = key_id.split(".", 1)[0]
        label = key_id.split(".", 1)[-1].replace("_", " ").title()
        notes = list(idea_notes.get(key_id) or [])
        if not notes:
            for i, n in enumerate(curated):
                principle = str(n.get("principle") or label)
                summary = adapt_summary(
                    key_id,
                    str(n.get("summary") or ""),
                    principle=principle,
                )
                notes.append(
                    {
                        "id": f"{key_id}#{i}",
                        "text": _clip(summary, MAX_NOTE_TEXT),
                        "book": label,
                        "themes": list(n.get("themes") or [])[:8],
                        "ecoHints": [],
                        "patterns": [key_id, principle][:8],
                        "principle": principle,
                        "phase": n.get("phase") or "any",
                        "fens": [],
                        "sanLines": list(n.get("san_lines") or [])[:2],
                        "openings": list(n.get("openings") or [])[:4],
                        "games": list(n.get("games") or [])[:2],
                        "specificity": int(n.get("specificity") or 3),
                        "features": list(n.get("features") or [])[:12],
                        "compact": adapt_compact(
                            key_id, note_compact(key_id, i)
                        ),
                        "slots": dict(n.get("slots") or {}),
                        "conditions": list(n.get("conditions") or [])[:12],
                    }
                )
        # Ensure compact + directive voice on ideas-loaded notes
        for i, note in enumerate(notes):
            principle = str(note.get("principle") or label)
            raw_text = str(note.get("text") or "")
            note["text"] = _clip(
                adapt_summary(key_id, raw_text, principle=principle),
                MAX_NOTE_TEXT,
            )
            raw_c = str(note.get("compact") or note_compact(key_id, i) or "")
            note["compact"] = adapt_compact(key_id, raw_c)
            note["slots"] = _ensure_note_slots(
                note, key_id=key_id, principle=principle
            )
            note["conditions"] = _ensure_note_conditions(note, key_id)
            # Overall lessons only — drop game anecdotes from tip payload.
            note["games"] = []
            note["sanLines"] = []
        notes = [n for n in notes if str(n.get("text") or "").strip()][
            :MAX_GPT_NOTES_PER_KEY
        ]
        if not notes:
            continue
        # Card text = GPT compact glossary (not OCR key summary)
        text = compact or " ".join(str(n.get("text") or "") for n in notes[:2])
        rows.append(
            {
                "id": f"key:{key_id}",
                "text": _clip(text, MAX_TEXT_KEY),
                "book": label,
                "books": [],
                "chapter": key_type,
                "themes": list(dict.fromkeys(
                    [t for n in notes for t in (n.get("themes") or [])]
                ))[:12],
                "patterns": [key_id],
                "eco_hints": [
                    x
                    for n in notes
                    for x in (n.get("ecoHints") or n.get("openings") or [])
                    if re.fullmatch(r"[A-E]\d{2}", str(x).strip().upper() or "")
                ][:4],
                "key_id": key_id,
                "key_type": key_type,
                "label": label,
                "games": [model_game] if model_game else [],
                "source_kind": "gpt-book-notes",
                "notes": notes,
                "compactDefinition": compact,
                "modelGame": model_game,
            }
        )
    return rows


def load_export_rows(
    config: dict[str, Any],
    *,
    source: str = "auto",
) -> tuple[list[dict[str, Any]], str]:
    """
    source: auto | key | chunk
    auto/key → GPT canon book notes only.
    """
    mode = (source or "auto").strip().lower()
    if mode in {"auto", "key"}:
        rows = _load_canon_gpt_rows(config)
        if rows:
            rows.sort(key=lambda r: (str(r.get("key_type") or ""), str(r.get("key_id") or "")))
            return rows, "key"
    return [], mode


def build_mobile_pack(
    config: dict[str, Any],
    *,
    max_entries: int = MAX_ENTRIES,
    attach_frequent_lines: bool = True,
    attach_bookwalk: bool = True,
    bookwalk_dir: Path | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    rows, used_source = load_export_rows(config, source=source)
    print(f"  source={used_source} candidates={len(rows)}", flush=True)

    bookwalk_by_key: dict[str, list] = {}
    all_passages: list = []
    model_fen_index: dict = {}
    if attach_bookwalk:
        all_passages = load_bookwalk_passages(bookwalk_dir)
        bookwalk_by_key = passages_by_key(all_passages)
        model_fen_index = build_model_game_fen_index(all_passages)
        print(
            f"  bookwalk passages={len(all_passages)} keys={len(bookwalk_by_key)}",
            flush=True,
        )

    masters_cfg = config.get("masters") or {}
    db: LocalMastersDB | None = None
    if attach_frequent_lines and masters_cfg.get("enabled", True):
        index_path = Path(masters_cfg.get("index_path") or "")
        pgn_dir = Path(masters_cfg["pgn_dir"]) if masters_cfg.get("pgn_dir") else None
        if index_path.is_file():
            db = LocalMastersDB(index_path, pgn_dir)

    line_cache: dict[str, list[dict[str, Any]]] = {}
    entries: list[dict[str, Any]] = []
    for row in rows:
        if max_entries > 0 and len(entries) >= max_entries:
            break
        ecos = [e.upper() for e in (row.get("eco_hints") or []) if e][:4]
        frequent: list[dict[str, Any]] = []
        if db and ecos:
            for eco in ecos:
                if eco not in line_cache:
                    print(f"  sampling frequent lines for {eco}…", flush=True)
                    line_cache[eco] = frequent_lines_for_eco(db, eco)
                for item in line_cache[eco]:
                    if item not in frequent:
                        frequent.append(item)
                    if len(frequent) >= MAX_LINES_PER_ENTRY:
                        break
                if len(frequent) >= MAX_LINES_PER_ENTRY:
                    break
        motifs = list(
            dict.fromkeys(
                [
                    *( [row["key_id"]] if row.get("key_id") else [] ),
                    *(row.get("patterns") or []),
                    *(row.get("themes") or []),
                ]
            )
        )[:14]
        books = list(row.get("books") or [])
        book_label = row.get("label") or row.get("book") or "topic"
        notes = list(row.get("notes") or [])
        key_id = str(row.get("key_id") or "")
        if key_id:
            idea_notes = _load_key_idea_notes(config, key_id)
            if idea_notes:
                notes = idea_notes
        used_bw: set[str] = set()
        # GPT directives first (metric tips); bookwalk passages after (optional depth).
        gpt_notes = list(notes)
        if key_id and bookwalk_by_key.get(key_id):
            bw_notes = []
            for i, passage in enumerate(bookwalk_by_key[key_id][:MAX_BOOKWALK_NOTES_PER_KEY]):
                bw_notes.append(passage_to_note(passage, key_id, i))
                used_bw.add(passage_fingerprint(passage))
            notes = gpt_notes + bw_notes
        else:
            notes = gpt_notes
        # No bucket OCR / key-summary paste as notes
        if not notes:
            continue
        meta = key_meta(key_id)
        compact_def = adapt_compact(
            key_id,
            str(row.get("compactDefinition") or meta.get("compact") or ""),
        )
        model_game = str(row.get("modelGame") or meta.get("model_game") or "")
        if model_game and not model_game.startswith("Model game:"):
            model_game = f"Model game: {model_game}"
        games_out = [model_game] if model_game else []
        # Bookwalk keeps original book wording; GPT notes get metrics voice.
        bw_local = bookwalk_by_key.get(key_id) or []
        notes = enrich_gpt_notes_with_fens(
            list(notes),
            key_id=key_id,
            bookwalk_for_key=bw_local or all_passages,
            model_game=model_game,
            model_index=model_fen_index,
        )
        for note in notes:
            nid = str(note.get("id") or "")
            feats = note.get("features") or []
            if nid.startswith("bookwalk:") or "bookwalk-passage" in feats:
                continue
            principle = str(note.get("principle") or "")
            note["text"] = _clip(
                adapt_summary(
                    key_id, str(note.get("text") or ""), principle=principle
                ),
                MAX_NOTE_TEXT,
            )
            if note.get("compact"):
                note["compact"] = adapt_compact(
                    key_id, str(note.get("compact") or "")
                )
        # Card body = compact glossary (GPT), not stale OCR summary text
        card_text = compact_def or _clip(
            " ".join(str(n.get("text") or "") for n in notes[:2]), MAX_TEXT_KEY
        )
        entries.append(
            {
                "id": row["id"],
                "text": card_text,
                "book": book_label if used_source == "key" else row["book"],
                "chapter": row.get("chapter") or "",
                "themes": list(row.get("themes") or [])[:12],
                "motifs": motifs,
                "ecoHints": ecos,
                "frequentLines": frequent[:MAX_LINES_PER_ENTRY],
                "keyId": key_id,
                "keyType": row.get("key_type") or "",
                "label": row.get("label") or book_label,
                "games": games_out[:6],
                "books": books[:8],
                "sourceKind": row.get("source_kind") or "gpt-book-notes",
                "notes": notes[:MAX_NOTES_PER_KEY],
                "compactDefinition": compact_def,
                "modelGame": model_game,
            }
        )

    entries = [
        e for e in entries if CANON_KEY.match(str(e.get("keyId") or ""))
    ]

    # Second pass: land leftover bookwalk passages so retention stays high.
    if attach_bookwalk and all_passages and entries:
        by_id = {str(e.get("keyId") or ""): e for e in entries}
        already: set[str] = set()
        for e in entries:
            for n in e.get("notes") or []:
                if str(n.get("id") or "").startswith("bookwalk:"):
                    # fingerprint approx from first fen + text head
                    fens = n.get("fens") or []
                    already.add(f"{fens[0] if fens else ''}|{(n.get('text') or '')[:96]}")
        orphan_n = 0
        for passage in all_passages:
            fp = passage_fingerprint(passage)
            # normalize to same scheme as already set
            fp2 = f"{passage.fen}|{passage.text[:96]}"
            if fp2 in already or fp in already:
                continue
            # pick first key that exists in pack
            target = next((k for k in passage.key_ids if k in by_id), None)
            if not target:
                continue
            entry = by_id[target]
            notes = list(entry.get("notes") or [])
            if len(notes) >= MAX_NOTES_PER_KEY:
                continue
            idx = sum(1 for n in notes if str(n.get("id") or "").startswith("bookwalk:"))
            notes.insert(0, passage_to_note(passage, target, idx + 1000))
            entry["notes"] = notes[:MAX_NOTES_PER_KEY]
            already.add(fp2)
            orphan_n += 1
        if orphan_n:
            print(f"  bookwalk orphans attached={orphan_n}", flush=True)

    source_label = "gpt-book-notes"
    if bookwalk_by_key:
        source_label = "gpt-book-notes+bookwalk"
    return {
        "version": PACK_VERSION,
        "generatedBy": "chess-coach export-mobile-pack",
        "source": source_label,
        "entryCount": len(entries),
        "entries": entries,
    }


def write_mobile_pack_json(pack: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_mobile_pack_ts(pack: dict[str, Any], out_path: Path) -> None:
    """Types-only module. Pack JSON ships as Expo asset (not inlined TS)."""
    del pack  # pack payload lives in mobile_coach_pack.json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "/* Types for the bundled coach pack asset (assets/coach/mobile_coach_pack.json). */\n"
        "/* Pack data is NOT inlined here — ships with the app binary; parsed on first analyze. */\n\n"
        "export type DerivedFrequentLine = {\n"
        "  sanLine: string;\n"
        "  count: number;\n"
        "  eco: string;\n"
        "};\n\n"
        "export type DerivedCoachNote = {\n"
        "  id: string;\n"
        "  text: string;\n"
        "  book: string;\n"
        "  themes: string[];\n"
        "  ecoHints: string[];\n"
        "  patterns?: string[];\n"
        "  principle?: string;\n"
        "  phase?: string;\n"
        "  fens?: string[];\n"
        "  sanLines?: string[];\n"
        "  openings?: string[];\n"
        "  games?: string[];\n"
        "  specificity?: number;\n"
        "  features?: string[];\n"
        "  compact?: string;\n"
        "  /** Tip-structure slots: wire directly to lead/core/remember/plan. */\n"
        "  slots?: {\n"
        "    worked?: string;\n"
        "    attention?: string;\n"
        "    lesson?: string;\n"
        "    plan?: string;\n"
        "  };\n"
        "  /** Match notes to live metrics / situations / openings / polarity. */\n"
        "  conditions?: Array<{\n"
        "    softKey?: string;\n"
        "    metric?: string;\n"
        "    situation?: string;\n"
        "    theme?: string;\n"
        "    opening?: string;\n"
        "    polarity?: \"good\" | \"bad\" | \"any\";\n"
        "    feature?: string;\n"
        "  }>;\n"
        "};\n\n"
        "export type DerivedCoachEntry = {\n"
        "  id: string;\n"
        "  text: string;\n"
        "  book: string;\n"
        "  chapter: string;\n"
        "  themes: string[];\n"
        "  motifs: string[];\n"
        "  ecoHints: string[];\n"
        "  frequentLines: DerivedFrequentLine[];\n"
        "  notes?: DerivedCoachNote[];\n"
        "  keyId?: string;\n"
        "  keyType?: string;\n"
        "  label?: string;\n"
        "  games?: string[];\n"
        "  books?: string[];\n"
        "  sourceKind?: string;\n"
        "  compactDefinition?: string;\n"
        "  modelGame?: string;\n"
        "};\n\n"
        "export type DerivedCoachPack = {\n"
        "  version: number;\n"
        "  generatedBy: string;\n"
        "  source?: string;\n"
        "  entryCount: number;\n"
        "  entries: DerivedCoachEntry[];\n"
        "};\n"
    )
    out_path.write_text(body, encoding="utf-8")


def export_mobile_pack(
    config: dict[str, Any],
    *,
    json_out: Path | None = None,
    asset_out: Path | None = None,
    ts_out: Path | None = None,
    max_entries: int = MAX_ENTRIES,
    attach_frequent_lines: bool = True,
    attach_bookwalk: bool = True,
    bookwalk_dir: Path | None = None,
    source: str = "auto",
    moments_json: Path | None = None,
    notes_schema_out: Path | None = None,
    use_offline_llm: bool = True,
    game_specific_comments: bool = True,
) -> dict[str, Any]:
    print(
        "Building derived mobile coach pack (key ideas + bookwalk FEN passages)…",
        flush=True,
    )
    pack = build_mobile_pack(
        config,
        max_entries=max_entries,
        attach_frequent_lines=attach_frequent_lines,
        attach_bookwalk=attach_bookwalk,
        bookwalk_dir=bookwalk_dir,
        source=source,
    )
    root = Path(__file__).resolve().parents[3]
    json_path = json_out or (root / "data/derived/mobile_coach_pack.json")
    if not json_path.is_absolute():
        json_path = (root / json_path).resolve()
    write_mobile_pack_json(pack, json_path)
    print(
        f"Wrote {json_path} ({pack['entryCount']} entries, source={pack.get('source')})",
        flush=True,
    )

    if asset_out is not None:
        asset_path = asset_out if asset_out.is_absolute() else (root / asset_out).resolve()
        write_mobile_pack_json(pack, asset_path)
        print(f"Wrote app asset {asset_path}", flush=True)

    if ts_out is not None:
        ts_path = ts_out if ts_out.is_absolute() else (root / ts_out).resolve()
        write_mobile_pack_ts(pack, ts_path)
        print(f"Wrote types {ts_path}", flush=True)

    if moments_json is not None:
        metrics_path = (
            moments_json if moments_json.is_absolute() else (root / moments_json).resolve()
        )
        if metrics_path.exists():
            print(
                f"Generating offline LLM comments from {metrics_path} "
                f"(llm={'on' if use_offline_llm else 'stitch'})…",
                flush=True,
            )
            data = load_metrics_json(metrics_path)
            generated = generate_offline_comment_notes(
                data,
                config,
                use_llm=use_offline_llm,
                game_specific=game_specific_comments,
            )
            pack["commentNotes"] = generated
            pack["commentNoteCount"] = len(generated)
            write_mobile_pack_json(pack, json_path)
            if asset_out is not None:
                asset_path = (
                    asset_out if asset_out.is_absolute() else (root / asset_out).resolve()
                )
                write_mobile_pack_json(pack, asset_path)
            print(
                f"Attached {len(generated)} analyze-time comment drafts to pack (schema unchanged)",
                flush=True,
            )
            if notes_schema_out is not None:
                schema_path = (
                    notes_schema_out
                    if notes_schema_out.is_absolute()
                    else (root / notes_schema_out).resolve()
                )
                if schema_path.exists():
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                else:
                    schema = {"version": 1, "notes": []}
                merged = merge_notes_schema(schema, generated)
                write_notes_schema(merged, schema_path)
                print(
                    f"Wrote {len(generated)} offline comments → {schema_path.name}",
                    flush=True,
                )
        else:
            print(f"Moments JSON not found: {metrics_path}", flush=True)

    return pack
