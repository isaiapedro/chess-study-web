from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chess
import chess.pgn

from chess_coach.masters_db import LocalMastersDB
from chess_coach.rag.summarize_knowledge import (
    get_summaries_collection,
    summary_is_teachable,
)

MAX_TEXT = 360
MAX_ENTRIES = 120
MAX_LINES_PER_ENTRY = 4
LINE_PLIES = 10
GAMES_PER_ECO = 60


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
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


def _load_summaries_from_chroma(config: dict[str, Any]) -> list[dict[str, Any]]:
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
            text = _clip(doc or "")
            if not summary_is_teachable(text):
                continue
            rows.append(
                {
                    "id": str(i),
                    "text": text,
                    "book": str(meta.get("book") or "book"),
                    "chapter": str(meta.get("chapter") or ""),
                    "themes": [t for t in str(meta.get("themes") or "").split(",") if t],
                    "patterns": [p for p in str(meta.get("patterns") or "").split(",") if p],
                    "eco_hints": [e for e in str(meta.get("eco_hints") or "").split(",") if e],
                }
            )
        offset += len(ids)
    return rows


def _load_summaries_from_jsonl(directory: Path) -> list[dict[str, Any]]:
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _clip(str(obj.get("text") or ""))
            if not summary_is_teachable(text):
                continue
            rows.append(
                {
                    "id": str(obj.get("id") or path.stem),
                    "text": text,
                    "book": str(obj.get("book") or "book"),
                    "chapter": str(obj.get("chapter") or ""),
                    "themes": list(obj.get("themes") or []),
                    "patterns": list(obj.get("patterns") or []),
                    "eco_hints": list(obj.get("eco_hints") or []),
                }
            )
    return rows


def build_mobile_pack(
    config: dict[str, Any],
    *,
    max_entries: int = MAX_ENTRIES,
    attach_frequent_lines: bool = True,
) -> dict[str, Any]:
    rag = config.get("rag") or {}
    root = Path(__file__).resolve().parents[3]
    jsonl_dir = Path(rag.get("summaries_dir", "data/knowledge_summaries"))
    if not jsonl_dir.is_absolute():
        jsonl_dir = (root / jsonl_dir).resolve()

    rows = _load_summaries_from_chroma(config)
    if not rows:
        rows = _load_summaries_from_jsonl(jsonl_dir)

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
        if len(entries) >= max_entries:
            break
        ecos = [e.upper() for e in (row.get("eco_hints") or []) if e][:3]
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
            dict.fromkeys([*(row.get("patterns") or []), *(row.get("themes") or [])])
        )[:10]
        entries.append(
            {
                "id": row["id"],
                "text": row["text"],
                "book": row["book"],
                "chapter": row.get("chapter") or "",
                "themes": list(row.get("themes") or [])[:12],
                "motifs": motifs,
                "ecoHints": ecos,
                "frequentLines": frequent[:MAX_LINES_PER_ENTRY],
            }
        )

    return {
        "version": 1,
        "generatedBy": "chess-coach export-mobile-pack",
        "entryCount": len(entries),
        "entries": entries,
    }


def write_mobile_pack_json(pack: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_mobile_pack_ts(pack: dict[str, Any], out_path: Path) -> None:
    """Ship a typed TS module the Expo app can import — no PDF/DB runtime."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(pack, ensure_ascii=False, indent=2)
    body = (
        "/* Auto-generated by chess-coach export-mobile-pack. Do not edit by hand. */\n"
        "/* PDF ingest + masters DB stay offline in CLI; app loads this derived pack only. */\n\n"
        "export type DerivedFrequentLine = {\n"
        "  sanLine: string;\n"
        "  count: number;\n"
        "  eco: string;\n"
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
        "};\n\n"
        "export type DerivedCoachPack = {\n"
        "  version: number;\n"
        "  generatedBy: string;\n"
        "  entryCount: number;\n"
        "  entries: DerivedCoachEntry[];\n"
        "};\n\n"
        f"export const DERIVED_COACH_PACK: DerivedCoachPack = {payload} as const;\n"
    )
    out_path.write_text(body, encoding="utf-8")


def export_mobile_pack(
    config: dict[str, Any],
    *,
    json_out: Path | None = None,
    ts_out: Path | None = None,
    max_entries: int = MAX_ENTRIES,
    attach_frequent_lines: bool = True,
) -> dict[str, Any]:
    print("Building derived mobile coach pack (summaries + motifs + frequent lines)…", flush=True)
    pack = build_mobile_pack(
        config,
        max_entries=max_entries,
        attach_frequent_lines=attach_frequent_lines,
    )
    root = Path(__file__).resolve().parents[3]
    json_path = json_out or (root / "data/derived/mobile_coach_pack.json")
    if not json_path.is_absolute():
        json_path = (root / json_path).resolve()
    write_mobile_pack_json(pack, json_path)
    print(f"Wrote {json_path} ({pack['entryCount']} entries)", flush=True)

    if ts_out is not None:
        ts_path = ts_out if ts_out.is_absolute() else (root / ts_out).resolve()
        write_mobile_pack_ts(pack, ts_path)
        print(f"Wrote {ts_path}", flush=True)
    return pack
