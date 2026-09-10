"""
LLM: synthesize teaching NOTES from each soft-key document.

Notes are original coach prose (not book excerpts). Thin fragments merge into
coherent notes that together cover the key principle. Mobile attaches notes by
game metrics (structure / marks / swings), not FEN matching — write for that voice.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import chess
import httpx

from chess_coach.rag.key_bucket_summarize import (
    KeyBucket,
    load_key_buckets,
    _clip,
    _resolve_rag_dir,
    _safe_key_id,
)

# Canon soft-keys only (same filter as mobile pack)
CANON_KEY = re.compile(
    r"^(structure|opening|endgame|imbalance|positional|piece|motif|attack|methodology)\."
)
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)

IDEA_PROMPT = """You WRITE original chess coaching DIRECTIVES for one soft key.

Key: {label} ({key_id})
Family: {key_type}
Metric lookup id: {key_id}  (mobile matches this soft key to game metrics — do NOT narrate metrics)

You are given raw book excerpts under this key. Many are OCR-noisy, game-specific, or
move-order heavy. Do NOT paste excerpts. Do NOT retell master games or player stories.

How notes are used (coach call / buildCoachNoteRequest):
- Soft-key id is the ONLY topic key. themesByPhase / globalThemes store these metric ids.
- Mobile pools tips via softKeysForNoteRequest from: structuralKind, moment inputs,
  playedMetricDelta, playedLineMetricDelta, engineLineMetricDelta, engineVsPlayedMetricDelta.
- BoardMetricSnap / engine-vs-played Δ fields (emit soft-key summaries that fit these):
  material_balance, mobility, king_attackers_pct, opp_king_attackers_pct,
  space_advantage_pct, hanging_material_own, hanging_material_opponent,
  open_file_utilization (MG/EG; R+Q on open/semi-open),
  seventh_rank_infiltration (MG/EG; R+Q on 7th/2nd), wp, eval_cp.
- Hanging is material VALUE only — never hanging_own / hanging_opp piece counts.
- Tip text is a short LIST OF DIRECTIVES: impersonal, didactic, objective.
- Directives must be GENERIC for any similar position — overall lessons only.
- For opening.* keys: write GENERAL PLAN directives for that opening name (develop, castle, break).
- For metric keys (positional.*, piece.*, attack.*, …): fit directives to that concept only.
  Especially cover open-file occupation, seventh-rank invasion (incl. queens), and
  hanging-material vigilance when this key is piece.seventh_rank_invasion,
  piece.coordination, methodology.candidate_moves, or attack.initiative.
- Skip passages about a specific game, move sequence, formation anecdote, or player.
- Prefer opening principles style: "Develop minor pieces before launching pawn storms."
- No "when metrics flag…", no "in this position after e4…", no first-person, no names.
- themes array MUST use soft-key metric tags only, e.g. "positional.pawn_break", "attack.king_safety"
  (never free labels like "pawn_breaks" or "development").

Task:
1. Distill overall lessons for this key from the sources.
2. WRITE {max_ideas} or fewer notes. Each note is ONE directive (or two short bullets max).
3. Merge thin fragments. Drop game/move/player-specific material.
4. principle: short facet label (also usable as a directive stem)
5. phase: opening | middlegame | endgame | any
6. themes: soft-key metric ids for lookup only (same vocabulary as key_id family)
7. san_lines / fens / games: usually [] (illustration only if essential; not teaching body)

Return ONLY a JSON object (no markdown fence):
{{
  "notes": [
    {{
      "principle": "Develop minors before pawn storms",
      "phase": "opening|middlegame|endgame|any",
      "summary": "- Develop minor pieces before launching wing pawn storms.\\n- Castle before opening the center if the king is still exposed.",
      "san_lines": [],
      "fens": [],
      "openings": [],
      "games": [],
      "themes": ["piece.centralization", "attack.king_safety"]
    }}
  ]
}}

Source excerpts (reference only — extract lessons, do not quote dumps):
{body}
"""

DEFAULT_MAX_EXCERPTS = 8
DEFAULT_MAX_IDEAS = 4
MAX_EXCERPT_CHARS = 220
MAX_SUMMARY_CHARS = 360
MIN_NOTE_CHARS = 24
LLM_TIMEOUT_S = 120.0


@dataclass
class KeyIdea:
    idea_id: str
    key_id: str
    key_type: str
    label: str
    principle: str
    phase: str
    summary: str
    san_lines: list[str] = field(default_factory=list)
    fens: list[str] = field(default_factory=list)
    openings: list[str] = field(default_factory=list)
    games: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    source_books: list[str] = field(default_factory=list)
    specificity: int = 3
    features: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    conditions: list[dict[str, Any]] = field(default_factory=list)


def _phase_norm(raw: str) -> str:
    p = (raw or "any").strip().lower()
    if p in {"opening", "middlegame", "endgame", "any"}:
        return p
    if "open" in p:
        return "opening"
    if "end" in p:
        return "endgame"
    if "middle" in p or "middlegame" in p:
        return "middlegame"
    return "any"


def _sanitize_san_line(line: str, max_plies: int = 6) -> str:
    tokens = re.findall(
        r"(?:O-O-O|O-O|0-0-0|0-0|[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|[a-h]x[a-h][1-8](?:=[NBRQ])?[+#]?|[a-h][1-8](?:=[NBRQ])?[+#]?)",
        line or "",
    )
    return " ".join(tokens[:max_plies])


def _playable_san_line(line: str, max_plies: int = 6) -> str | None:
    """Keep only SAN lines that actually play ≥3 plies from start."""
    cleaned = _sanitize_san_line(line, max_plies=max_plies)
    if not cleaned:
        return None
    board = chess.Board()
    played: list[str] = []
    for tok in cleaned.split():
        try:
            board.push_san(tok)
            played.append(tok)
        except ValueError:
            break
        if len(played) >= max_plies:
            break
    if len(played) < 3:
        return None
    return " ".join(played)


def _fens_from_san_line(san_line: str, start_fen: str | None = None) -> list[str]:
    """Play SAN line; return FEN before each ply (up to 4 positions)."""
    board = chess.Board()
    if start_fen:
        try:
            board.set_fen(start_fen)
        except ValueError:
            board = chess.Board()
    fens: list[str] = [board.fen()]
    for tok in san_line.split():
        try:
            board.push_san(tok)
        except ValueError:
            break
        fens.append(board.fen())
        if len(fens) >= 4:
            break
    return fens


def _validate_fen(fen: str) -> str | None:
    fen = (fen or "").strip()
    if not fen or fen.count(" ") < 1:
        return None
    try:
        chess.Board(fen)
        return fen
    except ValueError:
        return None


def _entry_teach_score(text: str) -> int:
    if len(text) < 60:
        return -1
    teach = len(
        re.findall(
            r"\b(plan|idea|structure|motif|tactic|principle|should|must|"
            r"attack|blockade|pawn|king|develop|castle|weakness|outpost|"
            r"exchange|sacrifice|prophylaxis|initiative|endgame)\b",
            text,
            re.I,
        )
    )
    moves = len(
        re.findall(
            r"\b(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8])\b",
            text,
        )
    )
    if teach < 1:
        return -1
    return teach * 3 - max(0, moves - 8)


def _pick_excerpts_for_prompt(bucket: KeyBucket, max_excerpts: int) -> list[Any]:
    """Diverse teachable excerpts so LLM sees whole key, not first-book bias."""
    scored: list[tuple[int, Any]] = []
    for entry in bucket.entries:
        score = _entry_teach_score(entry.text or "")
        if score < 0:
            continue
        scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])

    by_book: dict[str, list[Any]] = {}
    for _, entry in scored:
        by_book.setdefault(entry.book or "unknown", []).append(entry)

    books = sorted(by_book.keys(), key=lambda b: (-len(by_book[b]), b))
    picked: list[Any] = []
    idx = 0
    while len(picked) < max_excerpts:
        progressed = False
        for book in books:
            rows = by_book[book]
            if idx >= len(rows):
                continue
            picked.append(rows[idx])
            progressed = True
            if len(picked) >= max_excerpts:
                break
        if not progressed:
            break
        idx += 1
    return picked


def _source_digest(bucket: KeyBucket, max_excerpts: int) -> str:
    """
    Compact reference for the LLM: merged teachable snippets + cited games.
    Keeps context small so rewrite stays original (not OCR paste).
    """
    parts: list[str] = [f"Key: {bucket.key.label} ({bucket.key.key_id})"]
    if bucket.games:
        parts.append("Cited games: " + "; ".join(bucket.games[:6]))
    bullets: list[str] = []
    for entry in _pick_excerpts_for_prompt(bucket, max_excerpts):
        t = re.sub(r"\s+", " ", (entry.text or "").strip())
        t = re.sub(r"\b(Chapter|Book)\b[^.]*\.?", "", t, flags=re.I)
        t = _clip(t, 140)
        if len(t) < 50:
            continue
        eco = ",".join(entry.eco_hints[:2])
        bullets.append(f"- [{entry.book or 'book'}|{eco}] {t}")
        if len(bullets) >= max_excerpts:
            break
    parts.append("Source bullets (rewrite into notes; do not paste):")
    parts.extend(bullets or ["- (sparse sources; write general principles for this key)"])
    return "\n".join(parts)


def _ollama_ideas(
    bucket: KeyBucket,
    config: dict[str, Any],
    *,
    max_excerpts: int,
    max_ideas: int,
) -> list[dict[str, Any]]:
    host = str(config.get("ollama_host") or "http://localhost:11434").rstrip("/")
    model = str(
        config.get("ideas_chat_model")
        or config.get("chat_model")
        or "llama3.2:latest"
    )
    digest = _source_digest(bucket, max_excerpts=min(max_excerpts, 6))
    # Keep prompt tiny — CPU Ollama stalls on long qwen/llama contexts.
    user = (
        f"Soft key: {bucket.key.label} ({bucket.key.key_id}), family={bucket.key.key_type}.\n"
        f"Write up to {max_ideas} ORIGINAL coaching notes that TOGETHER cover this key.\n"
        "Merge thin source bullets into fuller notes when a bullet alone lacks general knowledge.\n"
        "Each note: 2-4 teaching sentences (principles/plans/structures — not move dumps).\n"
        "No book/chapter names in summary.\n"
        "JSON only: {\"notes\":[{\"principle\":\"facet\",\"phase\":\"opening|middlegame|endgame|any\","
        "\"summary\":\"...\",\"san_lines\":[\"optional ≤6 plies\"],\"fens\":[],"
        "\"openings\":[],\"games\":[],\"themes\":[]}]}\n\n"
        f"{digest[:2200]}"
    )
    try:
        with httpx.Client(timeout=LLM_TIMEOUT_S) as client:
            response = client.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "think": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1200,
                        "num_ctx": 4096,
                    },
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Chess coach. Output JSON object with key notes only. "
                                "Write original teaching prose; merge fragments; never paste OCR."
                            ),
                        },
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
            message = response.json().get("message") or {}
            content = str(message.get("content") or "").strip()
            content = _THINK_RE.sub("", content).strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            data = json.loads(content)
            if isinstance(data, dict):
                if "notes" in data:
                    data = data["notes"]
                elif "ideas" in data:
                    data = data["ideas"]
                elif "summary" in data or "principle" in data:
                    data = [data]
            if not isinstance(data, list):
                print(
                    f"    llm: expected notes array for {bucket.key.key_id}",
                    flush=True,
                )
                return []
            rows = [x for x in data if isinstance(x, dict)]
            print(
                f"    llm ({model}): {len(rows)} raw notes for {bucket.key.key_id}",
                flush=True,
            )
            return rows
    except Exception as exc:
        print(f"    llm failed ({bucket.key.key_id} / {model}): {exc}", flush=True)
        return []


def _extract_san_lines_from_text(text: str, max_lines: int = 2) -> list[str]:
    tokens = re.findall(
        r"(?:O-O-O|O-O|0-0-0|0-0|[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|[a-h]x[a-h][1-8](?:=[NBRQ])?[+#]?|[a-h][1-8](?:=[NBRQ])?[+#]?)",
        text or "",
    )
    if len(tokens) < 3:
        return []
    lines: list[str] = []
    for start in range(0, min(len(tokens), 16), 3):
        chunk = tokens[start : start + 6]
        if len(chunk) < 3:
            continue
        playable = _playable_san_line(" ".join(chunk), max_plies=6)
        if playable and playable not in lines:
            lines.append(playable)
        if len(lines) >= max_lines:
            break
    return lines


def _compose_merged_summary(snippets: list[str], label: str) -> str:
    """Fallback: concatenate main idea snippets into one composed note body."""
    cleaned: list[str] = []
    for s in snippets:
        t = re.sub(r"\s+", " ", (s or "").strip())
        t = re.sub(r"\b(Chapter|Book|cf\.|Cf\.)\b[^.]*\.?", "", t, flags=re.I)
        t = t.strip(" ;-")
        if len(t) < 40:
            continue
        if t not in cleaned:
            cleaned.append(t)
    if not cleaned:
        return ""
    parts = [_clip(c, 160) for c in cleaned[:4]]
    body = " ".join(parts)
    if not body.lower().startswith(label.lower()[:12]):
        body = f"{label}: {body}"
    return _clip(body, MAX_SUMMARY_CHARS)


def _extractive_ideas(bucket: KeyBucket, max_ideas: int) -> list[dict[str, Any]]:
    """
    Fallback when LLM unavailable: merge thin excerpts into composed notes
    that together cover the key (not one note per raw clip).
    """
    phase_guess = "any"
    kid = bucket.key.key_id
    if kid.startswith("opening."):
        phase_guess = "opening"
    elif kid.startswith("endgame."):
        phase_guess = "endgame"
    elif kid.startswith(("motif.", "attack.")):
        phase_guess = "middlegame"

    scored: list[tuple[int, Any]] = []
    for entry in bucket.entries:
        score = _entry_teach_score(entry.text or "")
        if score < 0:
            continue
        scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return []

    pool = [e for _, e in scored[: max(max_ideas * 4, 8)]]
    groups: list[list[Any]] = [[] for _ in range(max_ideas)]
    for i, entry in enumerate(pool):
        groups[i % max_ideas].append(entry)
    groups = [g for g in groups if g]

    out: list[dict[str, Any]] = []
    for gi, group in enumerate(groups[:max_ideas]):
        snippets = [e.text for e in group[:4]]
        summary = _compose_merged_summary(snippets, bucket.key.label)
        if len(summary) < MIN_NOTE_CHARS:
            continue
        blob = " ".join(snippets)
        san_lines = _extract_san_lines_from_text(blob)
        fens: list[str] = []
        if san_lines:
            derived = _fens_from_san_line(san_lines[0])
            fens = [f for f in derived[1:4] if f] or derived[:1]
        openings: list[str] = []
        games: list[str] = []
        themes: list[str] = []
        for e in group:
            for o in e.eco_hints:
                if o and o not in openings:
                    openings.append(o)
            for g in e.games:
                if g and g not in games:
                    games.append(g)
            for t in e.themes:
                if t and t not in themes:
                    themes.append(t)
        for g in bucket.games:
            if g not in games:
                games.append(g)
        if kid.startswith("opening.") and bucket.key.label not in openings:
            openings = [bucket.key.label, *openings]
        facet = bucket.key.label if gi == 0 else f"{bucket.key.label} ({gi + 1})"
        out.append(
            {
                "principle": facet,
                "phase": phase_guess,
                "summary": summary,
                "san_lines": san_lines[:2],
                "fens": fens[:3],
                "openings": openings[:4],
                "games": games[:4],
                "themes": themes[:8],
            }
        )
    return out


def _looks_like_ocr_dump(summary: str) -> bool:
    t = summary or ""
    if re.search(r"Beginner Tactics|Guided Practice|Answer:\s*1\.", t, re.I):
        return True
    if t.count("…") >= 2 and len(re.findall(r"\d+\.\.\.", t)) >= 2:
        return True
    moves = len(re.findall(r"\b(?:O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8])\b", t))
    teach = len(
        re.findall(
            r"\b(plan|idea|should|when|because|structure|attack|defend|weakness|typical|"
            r"compare|calculate|blockade|accept|decline)\b",
            t,
            re.I,
        )
    )
    if moves >= 12 and teach < 1:
        return True
    return False


def _normalize_idea(
    raw: dict[str, Any],
    bucket: KeyBucket,
    index: int,
) -> KeyIdea | None:
    summary = _clip(str(raw.get("summary") or raw.get("note") or ""), MAX_SUMMARY_CHARS)
    if len(summary) < MIN_NOTE_CHARS:
        return None
    if _looks_like_ocr_dump(summary):
        return None
    if len(re.findall(r"\b\d+\s*\.\s*", summary)) >= 4 and not re.search(
        r"\b(plan|idea|should|structure|attack|defend|weakness)\b",
        summary,
        re.I,
    ):
        return None
    principle = str(raw.get("principle") or bucket.key.label).strip() or bucket.key.label
    phase = _phase_norm(str(raw.get("phase") or "any"))

    san_lines: list[str] = []
    for line in raw.get("san_lines") or []:
        cleaned = _playable_san_line(str(line)) or _sanitize_san_line(str(line))
        playable = _playable_san_line(cleaned) if cleaned else None
        if playable and playable not in san_lines:
            san_lines.append(playable)
        if len(san_lines) >= 3:
            break

    fens: list[str] = []
    for fen in raw.get("fens") or []:
        ok = _validate_fen(str(fen))
        if ok and ok not in fens:
            fens.append(ok)
    if not fens and san_lines:
        derived = _fens_from_san_line(san_lines[0])
        fens = [f for f in derived[1:4] if f]
        if not fens and derived:
            fens = derived[:1]

    openings = [str(x).strip() for x in (raw.get("openings") or []) if str(x).strip()][:4]
    for eco in bucket.entries[0].eco_hints[:2] if bucket.entries else []:
        if eco not in openings:
            openings.append(eco)

    games = [str(x).strip() for x in (raw.get("games") or []) if str(x).strip()][:4]
    for g in bucket.games[:2]:
        if g not in games:
            games.append(g)

    themes = [str(x).strip() for x in (raw.get("themes") or []) if str(x).strip()][:8]
    features = [str(x).strip() for x in (raw.get("features") or []) if str(x).strip()][:12]
    slots_raw = raw.get("slots") or {}
    slots: dict[str, str] = {}
    if isinstance(slots_raw, dict):
        for k in ("worked", "attention", "lesson", "plan"):
            v = str(slots_raw.get(k) or "").strip()
            if v:
                slots[k] = v[:160]
    conditions: list[dict[str, Any]] = []
    for c in raw.get("conditions") or []:
        if isinstance(c, dict):
            conditions.append(dict(c))
    try:
        specificity = int(raw.get("specificity") or 3)
    except (TypeError, ValueError):
        specificity = 3
    specificity = max(1, min(5, specificity))
    books: list[str] = []
    for e in bucket.entries[:8]:
        if e.book and e.book not in books:
            books.append(e.book)

    return KeyIdea(
        idea_id=f"{bucket.key.key_id}#{index}",
        key_id=bucket.key.key_id,
        key_type=bucket.key.key_type,
        label=bucket.key.label,
        principle=principle[:80],
        phase=phase,
        summary=summary,
        san_lines=san_lines,
        fens=fens,
        openings=openings[:4],
        games=games[:4],
        themes=themes,
        source_books=books[:6],
        specificity=specificity,
        features=features,
        slots=slots,
        conditions=conditions[:12],
    )


def summarize_key_ideas_for_bucket(
    bucket: KeyBucket,
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    max_excerpts: int = DEFAULT_MAX_EXCERPTS,
    max_ideas: int = DEFAULT_MAX_IDEAS,
) -> list[KeyIdea]:
    from chess_coach.features import narrative_seed_for_key
    from chess_coach.rag.canon_key_notes import notes_for_key

    del use_llm, max_excerpts
    _ = narrative_seed_for_key(bucket.key.key_id, label=bucket.key.label)
    curated = notes_for_key(bucket.key.key_id)
    if not curated:
        return []

    raw_ideas: list[dict[str, Any]] = []
    for row in curated[:max_ideas]:
        enriched = dict(row)
        if not enriched.get("games") and bucket.games:
            enriched["games"] = list(bucket.games)[:4]
        if not enriched.get("openings"):
            ecos: list[str] = []
            for e in bucket.entries[:12]:
                for eco in e.eco_hints:
                    if eco and eco not in ecos:
                        ecos.append(eco)
            if ecos:
                enriched["openings"] = ecos[:4]
        raw_ideas.append(enriched)

    out: list[KeyIdea] = []
    for i, raw in enumerate(raw_ideas[:max_ideas]):
        idea = _normalize_idea(raw, bucket, i)
        if idea:
            out.append(idea)
    return out


def load_key_ideas_jsonl(path: Path) -> list[KeyIdea]:
    if not path.is_file():
        return []
    out: list[KeyIdea] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            out.append(
                KeyIdea(
                    idea_id=str(row.get("idea_id") or ""),
                    key_id=str(row.get("key_id") or ""),
                    key_type=str(row.get("key_type") or ""),
                    label=str(row.get("label") or ""),
                    principle=str(row.get("principle") or ""),
                    phase=_phase_norm(str(row.get("phase") or "any")),
                    summary=str(row.get("summary") or ""),
                    san_lines=list(row.get("san_lines") or []),
                    fens=list(row.get("fens") or []),
                    openings=list(row.get("openings") or []),
                    games=list(row.get("games") or []),
                    themes=list(row.get("themes") or []),
                    source_books=list(row.get("source_books") or []),
                    specificity=max(1, min(5, int(row.get("specificity") or 3))),
                    features=list(row.get("features") or []),
                    slots={
                        k: str(v).strip()
                        for k, v in dict(row.get("slots") or {}).items()
                        if k in ("worked", "attention", "lesson", "plan")
                        and str(v).strip()
                    },
                    conditions=[
                        dict(c)
                        for c in (row.get("conditions") or [])
                        if isinstance(c, dict)
                    ][:12],
                )
            )
        except Exception:
            continue
    return out


def summarize_key_ideas_path(
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    force: bool = False,
    reset: bool = False,
    max_excerpts: int = DEFAULT_MAX_EXCERPTS,
    max_ideas: int = DEFAULT_MAX_IDEAS,
    only_key: str | None = None,
) -> dict[str, Any]:
    from chess_coach.rag.canon_key_notes import CANON_KEY_NOTES, notes_for_key
    from chess_coach.rag.key_bucket_summarize import SoftKey, KeyBucket

    del use_llm  # GPT book notes live in canon_key_notes
    bucket_dir = _resolve_rag_dir(config, "key_buckets_dir", "data/knowledge_key_buckets")
    ideas_dir = _resolve_rag_dir(config, "key_ideas_dir", "data/knowledge_key_ideas")
    ideas_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = ideas_dir / "by_key_ideas.jsonl"
    if reset:
        if out_jsonl.is_file():
            out_jsonl.unlink()
        for stale in ideas_dir.glob("*.json"):
            stale.unlink(missing_ok=True)

    buckets = load_key_buckets(bucket_dir)
    existing = {} if (force or reset) else {i.idea_id: i for i in load_key_ideas_jsonl(out_jsonl)}
    existing_by_key: dict[str, list[KeyIdea]] = {}
    for idea in existing.values():
        existing_by_key.setdefault(idea.key_id, []).append(idea)

    all_ideas: list[KeyIdea] = []
    built = 0
    skipped = 0

    if only_key and not reset:
        for kid, ideas in existing_by_key.items():
            if kid != only_key:
                all_ideas.extend(ideas)

    key_ids = sorted(CANON_KEY_NOTES.keys())
    for key_id in key_ids:
        if only_key and key_id != only_key:
            continue
        if not force and key_id in existing_by_key and existing_by_key[key_id]:
            if not only_key:
                all_ideas.extend(existing_by_key[key_id])
            skipped += 1
            continue
        if not notes_for_key(key_id):
            continue

        bucket = buckets.get(key_id)
        if bucket is None:
            key_type = key_id.split(".", 1)[0]
            label = key_id.split(".", 1)[-1].replace("_", " ").title()
            bucket = KeyBucket(key=SoftKey(key_id, key_type, label), games=[])

        print(f"  notes ← {key_id} (gpt book notes)…", flush=True)
        ideas = summarize_key_ideas_for_bucket(
            bucket,
            config,
            use_llm=False,
            max_excerpts=max_excerpts,
            max_ideas=max_ideas,
        )
        if not ideas:
            continue
        key_path = ideas_dir / f"{_safe_key_id(key_id)}.json"
        key_path.write_text(
            json.dumps(
                {
                    "key_id": key_id,
                    "key_type": bucket.key.key_type,
                    "label": bucket.key.label,
                    "idea_count": len(ideas),
                    "ideas": [asdict(i) for i in ideas],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        all_ideas.extend(ideas)
        built += 1

    # Drop stale idea files not in canon
    canon = set(CANON_KEY_NOTES.keys())
    for path in ideas_dir.glob("*.json"):
        if path.stem.replace("_", ".") not in canon and path.stem not in {
            _safe_key_id(k) for k in canon
        }:
            # stem may equal key_id with dots
            kid = path.stem
            if kid not in canon and kid.replace("_", ".") not in canon:
                # keep if matches any safe id
                if not any(_safe_key_id(k) == kid for k in canon):
                    path.unlink(missing_ok=True)

    all_ideas = [i for i in all_ideas if i.key_id in canon]
    all_ideas.sort(key=lambda i: (i.key_id, i.idea_id))
    out_jsonl.write_text(
        "".join(json.dumps(asdict(i), ensure_ascii=False) + "\n" for i in all_ideas),
        encoding="utf-8",
    )

    by_phase: dict[str, int] = {}
    for i in all_ideas:
        by_phase[i.phase] = by_phase.get(i.phase, 0) + 1

    return {
        "ideas": len(all_ideas),
        "keys_built": built,
        "keys_skipped": skipped,
        "by_phase": by_phase,
        "out": str(out_jsonl),
    }
